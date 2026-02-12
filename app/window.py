from __future__ import annotations
from ocr.dock import OCRDock
import numpy as np
import cv2
from PySide6.QtGui import QImage
import os
import fitz  # PyMuPDF
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPixmap, QAction, QKeySequence, QShortcut, QTransform
from PySide6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QInputDialog,
    QSlider,
    QSizePolicy,
)

from .view import AnnotView
from .items import AnnotRectItem
from .model import StoredRectNorm
from .pdf_render import render_pdf_page
from .project_io import save_project_json, load_project_json
from .export_csv import export_csv_file


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Marcador de Áreas — PySide6 (Imagem + PDF)")

        self.scene = QGraphicsScene(self)
        self.view = AnnotView(self.scene)
        self.setCentralWidget(self.view)

        # Fonte atual
        self._file_path: str | None = None
        self._is_pdf: bool = False

        # PDF
        self._pdf_doc: fitz.Document | None = None
        self._pdf_page_index: int = 0
        self._pdf_page_count: int = 0
        self._pdf_render_zoom: float = 2.5

        # Render atual
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._image_bounds = QRectF(0, 0, 0, 0)

        # Itens (apenas página atual)
        self._items: list[AnnotRectItem] = []
        self._item_to_row: dict[AnnotRectItem, int] = {}
        self._suppress_table_events = False

        # Armazenamento por página (normalizado 0–1)
        self._stored_norm: dict[int, list[StoredRectNorm]] = {}

        # Zoom persistente entre páginas
        self._keep_view_transform_on_page_change = True

        # Slider
        self._suppress_slider = False

        # OCR
        self._ocr_profiles: dict[str, dict] = {}
        self._active_profile_name: str = ""


        self._build_toolbar()
        self._build_dock()
        self._build_shortcuts()

        self.view.rect_created.connect(self._on_rect_created)
        self.scene.selectionChanged.connect(self._on_scene_selection_changed)

        self._set_has_doc(False)

        self.ocr_dock = OCRDock(
            self,
            get_current_crop_bgr=self._get_selected_crop_bgr,
            get_profiles=lambda: self._ocr_profiles,
            set_profiles=self._set_ocr_profiles,
            get_active_profile=lambda: self._active_profile_name,
            set_active_profile=self._set_active_profile_name,
        )
        self.addDockWidget(Qt.RightDockWidgetArea, self.ocr_dock)
        self.tabifyDockWidget(self.rect_dock, self.ocr_dock)
        self.ocr_dock.raise_()  # opcional: abre na aba OCR

    def _set_ocr_profiles(self, profiles: dict):
        self._ocr_profiles = profiles or {}

    def _set_active_profile_name(self, name: str):
        self._active_profile_name = (name or "").strip()


    def _get_selected_crop_bgr(self):
        if not self._pixmap_item:
            return None
        selected = [it for it in self.scene.selectedItems() if isinstance(it, AnnotRectItem)]
        if not selected:
            return None

        item = selected[0]
        r = item.sceneBoundingRect().toRect()

        pix = self._pixmap_item.pixmap()
        if pix.isNull():
            return None

        r = r.intersected(pix.rect())
        if r.width() <= 1 or r.height() <= 1:
            return None

        crop = pix.copy(r)
        qimg = crop.toImage().convertToFormat(QImage.Format_RGB888)

        w, h = qimg.width(), qimg.height()
        bpl = qimg.bytesPerLine()

        ptr = qimg.constBits()  # memoryview com buffer protocol
        buf = np.frombuffer(ptr, dtype=np.uint8).reshape((h, bpl))

        rgb = buf[:, : w * 3].reshape((h, w, 3))
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        return bgr
    # ---------------- UI ----------------

    def _build_toolbar(self):
        tb = self.addToolBar("Ações")

        act_open_img = QAction("Abrir imagem", self)
        act_open_img.triggered.connect(self.open_image)
        tb.addAction(act_open_img)

        act_open_pdf = QAction("Abrir PDF", self)
        act_open_pdf.triggered.connect(self.open_pdf)
        tb.addAction(act_open_pdf)

        act_open_proj = QAction("Abrir projeto", self)
        act_open_proj.triggered.connect(self.open_project)
        tb.addAction(act_open_proj)

        act_save_proj = QAction("Salvar projeto", self)
        act_save_proj.triggered.connect(self.save_project)
        tb.addAction(act_save_proj)

        tb.addSeparator()

        self.act_prev = QAction("◀", self)
        self.act_prev.triggered.connect(self.prev_page)
        tb.addAction(self.act_prev)

        self.act_next = QAction("▶", self)
        self.act_next.triggered.connect(self.next_page)
        tb.addAction(self.act_next)

        self.lbl_page = QLabel(" ")
        self.lbl_page.setMinimumWidth(110)
        tb.addWidget(self.lbl_page)

        self.page_slider = QSlider(Qt.Horizontal, self)
        self.page_slider.setMinimumWidth(260)
        self.page_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.page_slider.valueChanged.connect(self._on_slider_changed)
        tb.addWidget(self.page_slider)

        tb.addSeparator()

        self.act_draw = QAction("Desenhar retângulos", self)
        self.act_draw.setCheckable(True)
        self.act_draw.setChecked(True)
        self.act_draw.triggered.connect(lambda checked: self.view.set_drawing_enabled(checked))
        tb.addAction(self.act_draw)

        tb.addSeparator()

        act_export = QAction("Exportar CSV", self)
        act_export.triggered.connect(self.export_csv)
        tb.addAction(act_export)

        act_delete = QAction("Excluir", self)
        act_delete.setShortcut(QKeySequence.Delete)
        act_delete.triggered.connect(self.delete_selected)
        self.addAction(act_delete)
        tb.addAction(act_delete)

        tb.addSeparator()

        act_fit_width = QAction("Ajustar largura", self)
        act_fit_width.triggered.connect(self.zoom_fit_width)
        tb.addAction(act_fit_width)

        act_fit_page = QAction("Ajustar página", self)
        act_fit_page.triggered.connect(self.zoom_fit_page)
        tb.addAction(act_fit_page)

        act_100 = QAction("100%", self)
        act_100.triggered.connect(self.zoom_100)
        tb.addAction(act_100)

        act_zoom_in = QAction("Zoom +", self)
        act_zoom_in.triggered.connect(lambda: self.view.zoom_in())
        tb.addAction(act_zoom_in)

        act_zoom_out = QAction("Zoom -", self)
        act_zoom_out.triggered.connect(lambda: self.view.zoom_out())
        tb.addAction(act_zoom_out)

    def _build_dock(self):
        self.rect_dock = QDockWidget("Retângulos", self)
        self.rect_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        root = QWidget()
        layout = QVBoxLayout(root)

        btn_row = QHBoxLayout()
        self.btn_delete = QPushButton("Excluir selecionado (Del)")
        self.btn_delete.clicked.connect(self.delete_selected)
        btn_row.addWidget(self.btn_delete)

        self.btn_rename = QPushButton("Renomear")
        self.btn_rename.clicked.connect(self.rename_selected)
        btn_row.addWidget(self.btn_rename)

        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Label", "x0", "y0", "x1", "y1", "w×h(px)"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)

        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.itemChanged.connect(self._on_table_item_changed)
        layout.addWidget(self.table)

        self.rect_dock.setWidget(root)
        self.addDockWidget(Qt.RightDockWidgetArea, self.rect_dock)

    def _build_shortcuts(self):
        # Navegação PDF
        QShortcut(QKeySequence(Qt.Key_Left), self, activated=self.prev_page)
        QShortcut(QKeySequence(Qt.Key_Right), self, activated=self.next_page)

        # Zoom
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self.zoom_fit_width)
        QShortcut(QKeySequence("Ctrl+9"), self, activated=self.zoom_fit_page)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=self.zoom_100)
        QShortcut(QKeySequence("Ctrl++"), self, activated=lambda: self.view.zoom_in())
        QShortcut(QKeySequence("Ctrl+="), self, activated=lambda: self.view.zoom_in())
        QShortcut(QKeySequence("Ctrl+-"), self, activated=lambda: self.view.zoom_out())

    def _set_has_doc(self, has: bool):
        self.act_draw.setEnabled(has)
        self.btn_delete.setEnabled(has)
        self.btn_rename.setEnabled(has)
        self.act_prev.setEnabled(has and self._is_pdf)
        self.act_next.setEnabled(has and self._is_pdf)
        self.page_slider.setEnabled(has and self._is_pdf)

    def _update_page_widgets(self):
        if not self._is_pdf:
            self.lbl_page.setText("Imagem")
            self._suppress_slider = True
            try:
                self.page_slider.setRange(0, 0)
                self.page_slider.setValue(0)
            finally:
                self._suppress_slider = False
            return

        self.lbl_page.setText(f"{self._pdf_page_index + 1}/{self._pdf_page_count}")
        self._suppress_slider = True
        try:
            self.page_slider.setRange(1, self._pdf_page_count)
            self.page_slider.setValue(self._pdf_page_index + 1)
        finally:
            self._suppress_slider = False

    # ---------------- Load / Render ----------------

    def _clear_scene_all(self):
        self.scene.clear()
        self._items.clear()
        self._item_to_row.clear()
        self.table.setRowCount(0)
        self._pixmap_item = None

    def _set_pixmap(self, pix: QPixmap):
        self._pixmap_item = QGraphicsPixmapItem(pix)
        self._pixmap_item.setPos(0, 0)
        self.scene.addItem(self._pixmap_item)

        w, h = pix.width(), pix.height()
        self._image_bounds = QRectF(0, 0, w, h)
        self.scene.setSceneRect(self._image_bounds)
        self.view.set_image_bounds(self._image_bounds)

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir imagem", "",
            "Imagens (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp);;Todos (*.*)"
        )
        if not path:
            return

        pix = QPixmap(path)
        if pix.isNull():
            QMessageBox.critical(self, "Erro", "Não foi possível carregar a imagem.")
            return

        self._file_path = path
        self._is_pdf = False
        self._pdf_doc = None
        self._pdf_page_index = 0
        self._pdf_page_count = 0

        self._stored_norm = {0: []}

        self._clear_scene_all()
        self._set_pixmap(pix)
        self._load_stored_rects_for_page(0)

        self._set_has_doc(True)
        self._update_page_widgets()
        self.zoom_fit_width()

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir PDF", "", "PDF (*.pdf)")
        if not path:
            return
        self._open_pdf_path(path, reset_storage=True)

    def _open_pdf_path(self, path: str, reset_storage: bool):
        try:
            doc = fitz.open(path)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao abrir PDF:\n{e}")
            return

        if doc.page_count <= 0:
            QMessageBox.warning(self, "Aviso", "PDF sem páginas.")
            doc.close()
            return

        self._file_path = path
        self._is_pdf = True
        self._pdf_doc = doc
        self._pdf_page_index = min(self._pdf_page_index, doc.page_count - 1)
        self._pdf_page_count = doc.page_count

        if reset_storage:
            self._stored_norm = {}

        self._clear_scene_all()
        self._render_pdf_page(self._pdf_page_index)

        self._set_has_doc(True)
        self._update_page_widgets()
        self.zoom_fit_width()

    def _render_pdf_page(self, page_index: int, restore_transform: QTransform | None = None):
        assert self._pdf_doc is not None

        pix = render_pdf_page(self._pdf_doc, page_index, self._pdf_render_zoom)

        self._clear_scene_all()
        self._set_pixmap(pix)
        self._load_stored_rects_for_page(page_index)

        if restore_transform is not None:
            self.view.setTransform(restore_transform)

    # ---------------- Slider / Page nav ----------------

    def _on_slider_changed(self, value: int):
        if self._suppress_slider:
            return
        if not self._is_pdf or not self._pdf_doc:
            return
        target_index = max(0, min(self._pdf_page_count - 1, value - 1))
        if target_index == self._pdf_page_index:
            return
        self._go_to_page(target_index)

    def prev_page(self):
        if not self._is_pdf or not self._pdf_doc:
            return
        if self._pdf_page_index <= 0:
            return
        self._go_to_page(self._pdf_page_index - 1)

    def next_page(self):
        if not self._is_pdf or not self._pdf_doc:
            return
        if self._pdf_page_index >= self._pdf_page_count - 1:
            return
        self._go_to_page(self._pdf_page_index + 1)

    def _go_to_page(self, page_index: int):
        prev_transform = self.view.transform() if self._keep_view_transform_on_page_change else None
        self._save_current_page_rects_norm()

        self._pdf_page_index = page_index
        self._update_page_widgets()

        self._render_pdf_page(self._pdf_page_index, restore_transform=prev_transform)

    # ---------------- Storage (normalized) ----------------

    def _current_page_key(self) -> int:
        return self._pdf_page_index if self._is_pdf else 0

    def _save_current_page_rects_norm(self):
        page = self._current_page_key()
        img_w = max(1.0, self._image_bounds.width())
        img_h = max(1.0, self._image_bounds.height())

        out: list[StoredRectNorm] = []
        for item in self._items:
            r = item.sceneBoundingRect()
            out.append(
                StoredRectNorm(
                    label=item.label(),
                    x0n=float(r.left() / img_w),
                    y0n=float(r.top() / img_h),
                    x1n=float(r.right() / img_w),
                    y1n=float(r.bottom() / img_h),
                )
            )
        self._stored_norm[page] = out

    def _load_stored_rects_for_page(self, page_index: int):
        rects = self._stored_norm.get(page_index, [])
        img_w = max(1.0, self._image_bounds.width())
        img_h = max(1.0, self._image_bounds.height())

        for sr in rects:
            x0 = sr.x0n * img_w
            y0 = sr.y0n * img_h
            x1 = sr.x1n * img_w
            y1 = sr.y1n * img_h
            rect = QRectF(QPointF(x0, y0), QPointF(x1, y1)).normalized()

            item = AnnotRectItem(rect, sr.label, self._image_bounds)
            item.signals.changed.connect(self._on_item_changed)
            self.scene.addItem(item)
            self._items.append(item)
            self._add_table_row(item)

    # ---------------- Zoom ----------------

    def zoom_fit_width(self):
        if not self._pixmap_item:
            return
        self.view.fit_to_width(self._image_bounds)

    def zoom_fit_page(self):
        if not self._pixmap_item:
            return
        self.view.fit_to_page(self._image_bounds)

    def zoom_100(self):
        if not self._pixmap_item:
            return
        self.view.reset_zoom()

    # ---------------- Annotations ----------------

    def _on_rect_created(self, item: AnnotRectItem):
        item.set_image_bounds(self._image_bounds)
        item.signals.changed.connect(self._on_item_changed)
        self._items.append(item)
        self._add_table_row(item)
        item.setSelected(True)
        self._save_current_page_rects_norm()

    def _add_table_row(self, item: AnnotRectItem):
        self._suppress_table_events = True
        try:
            row = self.table.rowCount()
            self.table.insertRow(row)

            label_item = QTableWidgetItem(item.label())
            self.table.setItem(row, 0, label_item)

            self._fill_row_coords(row, item)
            self._item_to_row[item] = row
        finally:
            self._suppress_table_events = False

    def _fill_row_coords(self, row: int, item: AnnotRectItem):
        r = item.sceneBoundingRect()
        x0, y0, x1, y1 = r.left(), r.top(), r.right(), r.bottom()
        w, h = r.width(), r.height()

        for col, val in enumerate([x0, y0, x1, y1], start=1):
            it = self.table.item(row, col)
            if it is None:
                it = QTableWidgetItem()
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, col, it)
            it.setText(f"{val:.2f}")

        wh_item = self.table.item(row, 5)
        if wh_item is None:
            wh_item = QTableWidgetItem()
            wh_item.setFlags(wh_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 5, wh_item)
        wh_item.setText(f"{w:.0f}×{h:.0f}")

    def _on_item_changed(self, item: AnnotRectItem):
        row = self._item_to_row.get(item)
        if row is not None:
            self._suppress_table_events = True
            try:
                self.table.item(row, 0).setText(item.label())
                self._fill_row_coords(row, item)
            finally:
                self._suppress_table_events = False
        self._save_current_page_rects_norm()

    def _on_scene_selection_changed(self):
        if self._suppress_table_events:
            return
        selected = [it for it in self.scene.selectedItems() if isinstance(it, AnnotRectItem)]
        if not selected:
            return
        item = selected[0]
        row = self._item_to_row.get(item)
        if row is None:
            return
        self._suppress_table_events = True

        if hasattr(self, "ocr_dock"):
            self.ocr_dock.update_previews()
        try:
            self.table.selectRow(row)
        finally:
            self._suppress_table_events = False

    def _on_table_selection_changed(self):
        if self._suppress_table_events:
            return
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        for item, r in self._item_to_row.items():
            if r == row:
                self.scene.clearSelection()
                item.setSelected(True)
                self.view.centerOn(item)
                break

    def _on_table_item_changed(self, changed_item: QTableWidgetItem):
        if self._suppress_table_events:
            return
        if changed_item.column() != 0:
            return
        row = changed_item.row()
        new_label = (changed_item.text() or "").strip()
        if not new_label:
            QMessageBox.warning(self, "Aviso", "Label não pode ser vazio.")
            self._suppress_table_events = True
            try:
                rect_item = self._get_item_by_row(row)
                if rect_item:
                    changed_item.setText(rect_item.label())
            finally:
                self._suppress_table_events = False
            return

        rect_item = self._get_item_by_row(row)
        if rect_item:
            rect_item.set_label(new_label)
            self._save_current_page_rects_norm()

    def _get_item_by_row(self, row: int) -> AnnotRectItem | None:
        for item, r in self._item_to_row.items():
            if r == row:
                return item
        return None

    def delete_selected(self):
        selected = [it for it in self.scene.selectedItems() if isinstance(it, AnnotRectItem)]
        if not selected:
            return
        for item in selected:
            row = self._item_to_row.get(item)
            if row is not None:
                self._remove_row_and_reindex(row)
            self.scene.removeItem(item)
            if item in self._items:
                self._items.remove(item)
            if item in self._item_to_row:
                del self._item_to_row[item]
        self._save_current_page_rects_norm()

    def _remove_row_and_reindex(self, row: int):
        self._suppress_table_events = True
        try:
            self.table.removeRow(row)
            new_map: dict[AnnotRectItem, int] = {}
            for item, r in self._item_to_row.items():
                if r < row:
                    new_map[item] = r
                elif r > row:
                    new_map[item] = r - 1
            self._item_to_row = new_map
        finally:
            self._suppress_table_events = False

    def rename_selected(self):
        selected = [it for it in self.scene.selectedItems() if isinstance(it, AnnotRectItem)]
        if not selected:
            return
        item = selected[0]
        text, ok = QInputDialog.getText(self, "Renomear", "Novo label:", text=item.label())
        if ok and text.strip():
            item.set_label(text.strip())
            self._save_current_page_rects_norm()

    # ---------------- Export / Project ----------------

    def export_csv(self):
        if not self._file_path or not self._pixmap_item:
            QMessageBox.warning(self, "Aviso", "Abra uma imagem ou PDF primeiro.")
            return

        self._save_current_page_rects_norm()

        suggested = os.path.splitext(self._file_path)[0] + "_areas.csv"
        out_path, _ = QFileDialog.getSaveFileName(self, "Salvar CSV", suggested, "CSV (*.csv)")
        if not out_path:
            return

        try:
            export_csv_file(
                out_path,
                source_path=self._file_path,
                is_pdf=self._is_pdf,
                pdf_doc=self._pdf_doc,
                pdf_page_count=self._pdf_page_count,
                pdf_render_zoom=self._pdf_render_zoom,
                stored_norm=self._stored_norm,
                image_w_px=int(self._image_bounds.width()),
                image_h_px=int(self._image_bounds.height()),
                profile_name=self._active_profile_name,
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao salvar CSV:\n{e}")
            return

        QMessageBox.information(self, "OK", f"CSV salvo em:\n{out_path}")

    def save_project(self):
        if not self._file_path:
            QMessageBox.warning(self, "Aviso", "Abra uma imagem ou PDF primeiro.")
            return

        self._save_current_page_rects_norm()

        suggested = os.path.splitext(self._file_path)[0] + "_projeto.json"
        out_path, _ = QFileDialog.getSaveFileName(self, "Salvar projeto", suggested, "Projeto (*.json)")
        if not out_path:
            return

        try:
            save_project_json(
                out_path,
                source_path=self._file_path,
                is_pdf=self._is_pdf,
                pdf_page_index=self._pdf_page_index,
                pdf_render_zoom=self._pdf_render_zoom,
                view_transform=self.view.transform(),
                stored_norm=self._stored_norm,
                ocr_profiles=self._ocr_profiles,
                active_profile_name=self._active_profile_name,
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao salvar projeto:\n{e}")
            return

        QMessageBox.information(self, "OK", f"Projeto salvo em:\n{out_path}")

    def open_project(self):
        proj_path, _ = QFileDialog.getOpenFileName(self, "Abrir projeto", "", "Projeto (*.json)")
        if not proj_path:
            return

        try:
            data = load_project_json(proj_path)
            self._ocr_profiles = data.get("ocr_profiles", {}) or {}
            self._active_profile_name = data.get("active_profile_name", "") or ""
            if hasattr(self, "ocr_dock"):
                self.ocr_dock.refresh_profiles()

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao ler projeto:\n{e}")
            return

        source_path = data.get("source_path")
        is_pdf = bool(data.get("is_pdf", False))
        page_index = int(data.get("pdf_page_index", 0))
        render_zoom = float(data.get("pdf_render_zoom", 2.5))
        restore_transform: QTransform | None = data.get("view_transform_parsed")
        stored_norm = data.get("annotations_parsed", {})

        if not source_path or not os.path.exists(source_path):
            QMessageBox.warning(
                self,
                "Arquivo não encontrado",
                "O arquivo fonte do projeto não foi encontrado.\nSelecione manualmente o PDF/imagem.",
            )
            source_path, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar arquivo fonte",
                "",
                "PDF (*.pdf);;Imagens (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp);;Todos (*.*)"
            )
            if not source_path:
                return

        self._stored_norm = stored_norm
        self._pdf_render_zoom = render_zoom

        # Abre fonte
        if is_pdf or str(source_path).lower().endswith(".pdf"):
            self._pdf_page_index = max(0, page_index)
            self._open_pdf_path(source_path, reset_storage=False)

            if self._pdf_doc:
                self._pdf_page_index = min(self._pdf_page_index, self._pdf_page_count - 1)
                self._update_page_widgets()
                self._render_pdf_page(self._pdf_page_index, restore_transform=restore_transform)
        else:
            pix = QPixmap(source_path)
            if pix.isNull():
                QMessageBox.critical(self, "Erro", "Não foi possível carregar a imagem do projeto.")
                return

            self._file_path = source_path
            self._is_pdf = False
            self._pdf_doc = None
            self._pdf_page_index = 0
            self._pdf_page_count = 0

            self._clear_scene_all()
            self._set_pixmap(pix)
            self._load_stored_rects_for_page(0)

            self._set_has_doc(True)
            self._update_page_widgets()

            if restore_transform is not None:
                self.view.setTransform(restore_transform)
            else:
                self.zoom_fit_width()

        QMessageBox.information(self, "OK", "Projeto carregado com sucesso.")
