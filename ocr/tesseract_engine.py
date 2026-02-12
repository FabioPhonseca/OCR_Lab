from __future__ import annotations

from typing import Dict, Any, Tuple, Optional

import pytesseract
from pytesseract import Output
import numpy as np

from .preprocess import OCRParams


def configure_tesseract(params: OCRParams) -> None:
    if params.tesseract_cmd and params.tesseract_cmd.strip():
        pytesseract.pytesseract.tesseract_cmd = params.tesseract_cmd.strip()


def build_config(params: OCRParams) -> str:
    cfg = []
    if params.whitelist.strip():
        cfg.append(f'-c tessedit_char_whitelist={params.whitelist.strip()}')
    if params.blacklist.strip():
        cfg.append(f'-c tessedit_char_blacklist={params.blacklist.strip()}')
    return " ".join(cfg)


def run_ocr(image_gray: np.ndarray, params: OCRParams) -> Tuple[str, Optional[float], Dict[str, Any]]:
    """
    Retorna: (texto, conf_media, raw_data)
    conf_media = média das confs válidas (>=0), quando disponível
    """
    configure_tesseract(params)
    config = build_config(params)

    data = pytesseract.image_to_data(
        image_gray,
        lang=params.lang.strip() or "por",
        config=config,
        output_type=Output.DICT,
    )

    text = (pytesseract.image_to_string(
        image_gray,
        lang=params.lang.strip() or "por",
        config=config,
    ) or "").strip()

    confs = []
    for c in data.get("conf", []):
        try:
            v = float(c)
            if v >= 0:
                confs.append(v)
        except Exception:
            pass

    conf_mean = (sum(confs) / len(confs)) if confs else None
    return text, conf_mean, data
