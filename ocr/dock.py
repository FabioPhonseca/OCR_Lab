from __future__ import annotations
from PySide6.QtWidgets import QSizePolicy
from typing import Optional, Callable, Dict, Any

import numpy as np
import cv2

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QTextEdit,
    QGroupBox, QFormLayout
)

from .preprocess import OCRParams, apply_preprocess
from .tesseract_engine import run_ocr


def bgr_to_qpix(bgr: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


class OCRDock(QDockWidget):
    """
    Dock de OCR:
    - mostra preview do recorte e do preprocessado
    - ajusta params
    - roda OCR
    - salva/carrega perfil via callbacks externos
    """
    def __init__(
        self,
        parent=None,
        *,
        get_current_crop_bgr: Callable[[], Optional[np.ndarray]],
        get_profiles: Callable[[], Dict[str, Any]],
        set_profiles: Callable[[Dict[str, Any]], None],
        get_active_profile: Callable[[], str],
        set_active_profile: Callable[[str], None],
    ):
        super().__init__("OCR", parent)
        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)

        self._get_current_crop_bgr = get_current_crop_bgr
        self._get_profiles = get_profiles
        self._set_profiles = set_profiles
        self._get_active_profile = get_active_profile
        self._set_active_profile = set_active_profile

        self.params = OCRParams()

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(350)
        self._debounce.timeout.connect(self._run_pipeline_if_autorun)

        root = QWidget()
        self.setWidget(root)
        main = QVBoxLayout(root)

        # previews
        prev_row = QHBoxLayout()
        self.lbl_orig = QLabel("Recorte (original)")
        self.lbl_proc = QLabel("Recorte (processado)")
        for lbl in (self.lbl_orig, self.lbl_proc):
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setMinimumSize(240, 180)                 # mínimo razoável (fixo)
            lbl.setMaximumHeight(260)                    # não deixa “puxar” vertical
            lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)  # <- CRÍTICO
            lbl.setScaledContents(False)                 # vamos escalar manualmente
            lbl.setStyleSheet("border: 1px solid #777;")
        prev_row.addWidget(self.lbl_orig, 1)
        prev_row.addWidget(self.lbl_proc, 1)
        main.addLayout(prev_row)

        # params
        gb = QGroupBox("Parâmetros OCR / Pré-processamento")
        form = QFormLayout(gb)

        self.sp_scale = QDoubleSpinBox()
        self.sp_scale.setRange(1.0, 6.0)
        self.sp_scale.setSingleStep(0.5)
        self.sp_scale.setValue(self.params.scale)
        form.addRow("Scale", self.sp_scale)

        self.ck_gray = QCheckBox()
        self.ck_gray.setChecked(self.params.grayscale)
        form.addRow("Grayscale", self.ck_gray)

        self.ck_invert = QCheckBox()
        self.ck_invert.setChecked(self.params.invert)
        form.addRow("Invert", self.ck_invert)

        self.cb_thresh = QComboBox()
        self.cb_thresh.addItems(["none", "otsu", "adaptive"])
        self.cb_thresh.setCurrentText(self.params.threshold_mode)
        form.addRow("Threshold", self.cb_thresh)

        self.sp_adapt_bs = QSpinBox()
        self.sp_adapt_bs.setRange(3, 99)
        self.sp_adapt_bs.setSingleStep(2)
        self.sp_adapt_bs.setValue(self.params.adaptive_block_size)
        form.addRow("Adaptive block", self.sp_adapt_bs)

        self.sp_adapt_c = QSpinBox()
        self.sp_adapt_c.setRange(-50, 50)
        self.sp_adapt_c.setValue(self.params.adaptive_c)
        form.addRow("Adaptive C", self.sp_adapt_c)

        self.sp_blur = QSpinBox()
        self.sp_blur.setRange(0, 31)
        self.sp_blur.setSingleStep(2)
        self.sp_blur.setValue(self.params.blur_ksize)
        form.addRow("Blur ksize", self.sp_blur)

        self.ck_sharp = QCheckBox()
        self.ck_sharp.setChecked(self.params.sharpen)
        form.addRow("Sharpen", self.ck_sharp)

        self.cb_morph = QComboBox()
        self.cb_morph.addItems(["none", "open", "close"])
        self.cb_morph.setCurrentText(self.params.morph_mode)
        form.addRow("Morph", self.cb_morph)

        self.sp_morph_k = QSpinBox()
        self.sp_morph_k.setRange(1, 31)
        self.sp_morph_k.setSingleStep(2)
        self.sp_morph_k.setValue(self.params.morph_ksize)
        form.addRow("Morph ksize", self.sp_morph_k)

        self.ed_lang = QLineEdit(self.params.lang)
        form.addRow("Idioma (lang)", self.ed_lang)

        self.ed_whitelist = QLineEdit(self.params.whitelist)
        form.addRow("Whitelist", self.ed_whitelist)

        self.ed_blacklist = QLineEdit(self.params.blacklist)
        form.addRow("Blacklist", self.ed_blacklist)

        self.ed_tcmd = QLineEdit(self.params.tesseract_cmd)
        self.ed_tcmd.setPlaceholderText(r"Ex: C:\Program Files\Tesseract-OCR\tesseract.exe")
        form.addRow("tesseract_cmd", self.ed_tcmd)

        main.addWidget(gb)

        # actions row
        act_row = QHBoxLayout()
        self.ck_autorun = QCheckBox("Auto-run")
        self.ck_autorun.setChecked(False)
        act_row.addWidget(self.ck_autorun)

        self.btn_run = QPushButton("Rodar OCR")
        self.btn_run.clicked.connect(self.run_now)
        act_row.addWidget(self.btn_run)

        self.lbl_conf = QLabel("Conf: —")
        act_row.addWidget(self.lbl_conf)
        act_row.addStretch(1)
        main.addLayout(act_row)

        # profile row
        prof = QHBoxLayout()
        self.ed_profile = QLineEdit()
        self.ed_profile.setPlaceholderText("Nome do perfil (ex: padrao_laudo)")
        prof.addWidget(self.ed_profile, 2)

        self.btn_save_prof = QPushButton("Salvar perfil")
        self.btn_save_prof.clicked.connect(self.save_profile)
        prof.addWidget(self.btn_save_prof)

        self.cb_profiles = QComboBox()
        self.cb_profiles.currentTextChanged.connect(self.load_profile_by_name)
        prof.addWidget(self.cb_profiles, 2)

        self.btn_refresh_prof = QPushButton("Atualizar lista")
        self.btn_refresh_prof.clicked.connect(self.refresh_profiles)
        prof.addWidget(self.btn_refresh_prof)

        main.addLayout(prof)

        # output
        self.txt_out = QTextEdit()
        self.txt_out.setPlaceholderText("Texto reconhecido aparecerá aqui…")
        main.addWidget(self.txt_out, 1)

        # connect changes to debounce
        for w in (
            self.sp_scale, self.ck_gray, self.ck_invert, self.cb_thresh,
            self.sp_adapt_bs, self.sp_adapt_c, self.sp_blur, self.ck_sharp,
            self.cb_morph, self.sp_morph_k, self.ed_lang, self.ed_whitelist,
            self.ed_blacklist, self.ed_tcmd
        ):
            self._connect_change(w)

        self.refresh_profiles()

    def _connect_change(self, widget):
        # liga o melhor sinal de cada tipo
        if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
            widget.valueChanged.connect(self._schedule_preview)
        elif isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(self._schedule_preview)
        elif isinstance(widget, QCheckBox):
            widget.toggled.connect(self._schedule_preview)
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(self._schedule_preview)

    def _schedule_preview(self):
        self._debounce.start()

    def _run_pipeline_if_autorun(self):
        self.update_previews()
        if self.ck_autorun.isChecked():
            self.run_now()

    def pull_params_from_ui(self) -> OCRParams:
        p = OCRParams(
            scale=float(self.sp_scale.value()),
            grayscale=bool(self.ck_gray.isChecked()),
            invert=bool(self.ck_invert.isChecked()),
            threshold_mode=str(self.cb_thresh.currentText()),
            adaptive_block_size=int(self.sp_adapt_bs.value()),
            adaptive_c=int(self.sp_adapt_c.value()),
            blur_ksize=int(self.sp_blur.value()),
            sharpen=bool(self.ck_sharp.isChecked()),
            morph_mode=str(self.cb_morph.currentText()),
            morph_ksize=int(self.sp_morph_k.value()),
            lang=self.ed_lang.text().strip() or "por",
            whitelist=self.ed_whitelist.text(),
            blacklist=self.ed_blacklist.text(),
            tesseract_cmd=self.ed_tcmd.text(),
        )
        self.params = OCRParams.from_dict(p.to_dict())
        return self.params

    def update_previews(self):
        crop = self._get_current_crop_bgr()
        if crop is None:
            self.lbl_orig.setText("Selecione um retângulo")
            self.lbl_proc.setText("—")
            return

        params = self.pull_params_from_ui()

        # original preview (com scale aplicada para ficar comparável)
        orig = crop
        if params.scale and params.scale != 1.0:
            orig = cv2.resize(orig, None, fx=params.scale, fy=params.scale, interpolation=cv2.INTER_CUBIC)

        img_ocr, proc_bgr = apply_preprocess(crop, params)

        pm_orig = bgr_to_qpix(orig)
        pm_proc = bgr_to_qpix(proc_bgr)

        self.lbl_orig.setPixmap(pm_orig.scaled(
            self.lbl_orig.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        ))
        self.lbl_proc.setPixmap(pm_proc.scaled(
            self.lbl_proc.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        ))

        self.lbl_orig.setMinimumSize(240, 180)
        self.lbl_proc.setMinimumSize(240, 180)


    def resizeEvent(self, event):
        super().resizeEvent(event)
        # re-render previews to new size
        self.update_previews()

    def run_now(self):
        crop = self._get_current_crop_bgr()
        if crop is None:
            self.txt_out.setPlainText("Selecione um retângulo para rodar OCR.")
            self.lbl_conf.setText("Conf: —")
            return

        params = self.pull_params_from_ui()
        img_ocr, _ = apply_preprocess(crop, params)

        text, conf, _ = run_ocr(img_ocr, params)
        self.txt_out.setPlainText(text)

        if conf is None:
            self.lbl_conf.setText("Conf: —")
        else:
            self.lbl_conf.setText(f"Conf: {conf:.1f}")

    # -------- profiles --------

    def refresh_profiles(self):
        profiles = self._get_profiles() or {}
        names = sorted(list(profiles.keys()))
        self.cb_profiles.blockSignals(True)
        try:
            self.cb_profiles.clear()
            self.cb_profiles.addItem("")
            for n in names:
                self.cb_profiles.addItem(n)
            active = self._get_active_profile() or ""
            if active in names:
                self.cb_profiles.setCurrentText(active)
        finally:
            self.cb_profiles.blockSignals(False)

    def save_profile(self):
        name = (self.ed_profile.text() or "").strip()
        if not name:
            return

        params = self.pull_params_from_ui()
        profiles = dict(self._get_profiles() or {})
        profiles[name] = params.to_dict()
        self._set_profiles(profiles)
        self._set_active_profile(name)
        self.refresh_profiles()

    def load_profile_by_name(self, name: str):
        name = (name or "").strip()
        if not name:
            return
        profiles = self._get_profiles() or {}
        if name not in profiles:
            return

        self._set_active_profile(name)
        p = OCRParams.from_dict(profiles[name])

        # push to UI
        self.sp_scale.setValue(float(p.scale))
        self.ck_gray.setChecked(bool(p.grayscale))
        self.ck_invert.setChecked(bool(p.invert))
        self.cb_thresh.setCurrentText(str(p.threshold_mode))
        self.sp_adapt_bs.setValue(int(p.adaptive_block_size))
        self.sp_adapt_c.setValue(int(p.adaptive_c))
        self.sp_blur.setValue(int(p.blur_ksize))
        self.ck_sharp.setChecked(bool(p.sharpen))
        self.cb_morph.setCurrentText(str(p.morph_mode))
        self.sp_morph_k.setValue(int(p.morph_ksize))
        self.ed_lang.setText(str(p.lang))
        self.ed_whitelist.setText(str(p.whitelist))
        self.ed_blacklist.setText(str(p.blacklist))
        self.ed_tcmd.setText(str(p.tesseract_cmd))

        self.update_previews()
