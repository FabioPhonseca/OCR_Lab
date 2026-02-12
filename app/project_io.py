from __future__ import annotations

import json
from typing import Any, Dict, Optional

from PySide6.QtGui import QTransform

from .model import annotations_to_json, annotations_from_json, StoredRectNorm


def save_project_json(
    out_path: str,
    *,
    source_path: str,
    is_pdf: bool,
    pdf_page_index: int,
    pdf_render_zoom: float,
    view_transform: QTransform,
    stored_norm: dict[int, list[StoredRectNorm]],
    ocr_profiles: dict,
    active_profile_name: str
) -> None:
    tr = view_transform
    data: Dict[str, Any] = {
        "version": 1,
        "source_path": source_path,
        "is_pdf": is_pdf,
        "pdf_page_index": pdf_page_index,
        "pdf_render_zoom": pdf_render_zoom,
        "view_transform": [
            tr.m11(), tr.m12(), tr.m13(),
            tr.m21(), tr.m22(), tr.m23(),
            tr.m31(), tr.m32(), tr.m33(),
        ],
        "annotations": annotations_to_json(stored_norm),
        "ocr_profiles": ocr_profiles or {},
        "active_profile_name": active_profile_name or "",
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_project_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Normaliza campos básicos e converte annotations
    data["annotations_parsed"] = annotations_from_json(data.get("annotations", {}))

    tr_list = data.get("view_transform")
    data["view_transform_parsed"] = parse_transform(tr_list)

    data["ocr_profiles"] = data.get("ocr_profiles", {})
    data["active_profile_name"] = data.get("active_profile_name", "")

    return data


def parse_transform(tr_list: Any) -> Optional[QTransform]:
    if isinstance(tr_list, list) and len(tr_list) == 9:
        try:
            vals = [float(x) for x in tr_list]
            return QTransform(*vals)
        except Exception:
            return None
    return None
