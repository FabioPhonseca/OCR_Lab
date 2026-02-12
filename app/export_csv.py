from __future__ import annotations

import csv
import os
from typing import Dict, List, Union

import fitz  # PyMuPDF

from .model import StoredRectNorm
from .pdf_render import get_rendered_size


def export_csv_file(
    out_path: str,
    *,
    source_path: str,
    is_pdf: bool,
    pdf_doc: fitz.Document | None,
    pdf_page_count: int,
    pdf_render_zoom: float,
    stored_norm: Dict[int, List[StoredRectNorm]],
    image_w_px: int,
    image_h_px: int,
    profile_name: str = "",
) -> None:
    rows: List[Dict[str, Union[str, int]]] = []
    base = os.path.basename(source_path)

    if not is_pdf:
        img_w, img_h = int(image_w_px), int(image_h_px)
        rects = stored_norm.get(0, [])
        for sr in rects:
            rows.append(_row_for_rect(base, page_index + 1, sr, img_w, img_h, profile_name))
    else:
        if pdf_doc is None:
            raise RuntimeError("PDF doc não carregado.")
        for page_index in range(pdf_page_count):
            img_w, img_h = get_rendered_size(pdf_doc, page_index, pdf_render_zoom)
            rects = stored_norm.get(page_index, [])
            for sr in rects:
                # page no CSV: 1-based
                rows.append(_row_for_rect(base, page_index + 1, sr, img_w, img_h, profile_name))

    fieldnames = [
        "file", "page", "label", "ocr_profile",
        "x0_norm", "y0_norm", "x1_norm", "y1_norm",
        "x0_px", "y0_px", "w_px", "h_px",
        "image_w_px", "image_h_px",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _row_for_rect(
        base_file: str,
        page_value: int,
        sr: StoredRectNorm,
        img_w: int,
        img_h: int,
        profile_name: str = "",  
    ) -> Dict[str, Union[str, int]]:

    x0 = sr.x0n * img_w
    y0 = sr.y0n * img_h
    x1 = sr.x1n * img_w
    y1 = sr.y1n * img_h
    w = abs(x1 - x0)
    h = abs(y1 - y0)

    return {
        "file": base_file,
        "page": page_value,
        "label": sr.label,
        "ocr_profile": profile_name or "",
        "x0_norm": f"{sr.x0n:.6f}",
        "y0_norm": f"{sr.y0n:.6f}",
        "x1_norm": f"{sr.x1n:.6f}",
        "y1_norm": f"{sr.y1n:.6f}",
        "x0_px": f"{x0:.2f}",
        "y0_px": f"{y0:.2f}",
        "w_px": f"{w:.2f}",
        "h_px": f"{h:.2f}",
        "image_w_px": img_w,
        "image_h_px": img_h,
    }

