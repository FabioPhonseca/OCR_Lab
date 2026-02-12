from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Tuple

import numpy as np
import cv2


@dataclass
class OCRParams:
    # tesseract
    lang: str = "por"
    whitelist: str = ""
    blacklist: str = ""
    tesseract_cmd: str = ""  # opcional (Windows)

    # preprocess
    scale: float = 2.0
    grayscale: bool = True
    invert: bool = False

    threshold_mode: str = "otsu"  # "none" | "otsu" | "adaptive"
    adaptive_block_size: int = 31
    adaptive_c: int = 7

    blur_ksize: int = 0  # 0 desliga; valores ímpares: 3,5,7...
    sharpen: bool = False

    morph_mode: str = "none"  # "none" | "open" | "close"
    morph_ksize: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "OCRParams":
        p = OCRParams()
        for k, v in (d or {}).items():
            if hasattr(p, k):
                setattr(p, k, v)
        # sanitização mínima
        p.adaptive_block_size = max(3, int(p.adaptive_block_size) | 1)  # ímpar >=3
        p.blur_ksize = int(p.blur_ksize)
        if p.blur_ksize != 0:
            p.blur_ksize = max(3, p.blur_ksize | 1)
        p.morph_ksize = max(1, int(p.morph_ksize) | 1)
        p.scale = max(1.0, float(p.scale))
        return p


def apply_preprocess(bgr: np.ndarray, params: OCRParams) -> Tuple[np.ndarray, np.ndarray]:
    """
    Entrada: imagem BGR (OpenCV).
    Saída:
      - img_for_ocr: normalmente 1 canal (uint8) ou 3 canais, pronto para OCR
      - img_preview_bgr: BGR para preview no Qt
    """
    img = bgr

    # Scale
    if params.scale and params.scale != 1.0:
        img = cv2.resize(img, None, fx=params.scale, fy=params.scale, interpolation=cv2.INTER_CUBIC)

    # Grayscale
    if params.grayscale:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = None

    # Invert
    if params.invert:
        if gray is not None:
            gray = cv2.bitwise_not(gray)
        else:
            img = cv2.bitwise_not(img)

    # Blur
    if params.blur_ksize and params.blur_ksize >= 3:
        if gray is not None:
            gray = cv2.GaussianBlur(gray, (params.blur_ksize, params.blur_ksize), 0)
        else:
            img = cv2.GaussianBlur(img, (params.blur_ksize, params.blur_ksize), 0)

    # Sharpen (unsharp mask simples)
    if params.sharpen:
        if gray is not None:
            blur = cv2.GaussianBlur(gray, (0, 0), 1.2)
            gray = cv2.addWeighted(gray, 1.6, blur, -0.6, 0)
        else:
            blur = cv2.GaussianBlur(img, (0, 0), 1.2)
            img = cv2.addWeighted(img, 1.6, blur, -0.6, 0)

    # Threshold
    img_ocr = gray if gray is not None else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if params.threshold_mode == "otsu":
        _, img_ocr = cv2.threshold(img_ocr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif params.threshold_mode == "adaptive":
        bs = max(3, int(params.adaptive_block_size) | 1)
        c = int(params.adaptive_c)
        img_ocr = cv2.adaptiveThreshold(img_ocr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY, bs, c)
    # else "none": mantém

    # Morphology
    if params.morph_mode in ("open", "close"):
        k = max(1, int(params.morph_ksize) | 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
        op = cv2.MORPH_OPEN if params.morph_mode == "open" else cv2.MORPH_CLOSE
        img_ocr = cv2.morphologyEx(img_ocr, op, kernel)

    # Preview BGR
    preview_bgr = cv2.cvtColor(img_ocr, cv2.COLOR_GRAY2BGR)

    return img_ocr, preview_bgr
