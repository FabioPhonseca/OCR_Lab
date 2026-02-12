from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class StoredRectNorm:
    label: str
    x0n: float
    y0n: float
    x1n: float
    y1n: float


def annotations_to_json(stored: Dict[int, List[StoredRectNorm]]) -> Dict[str, Any]:
    return {
        str(k): [
            {"label": r.label, "x0_norm": r.x0n, "y0_norm": r.y0n, "x1_norm": r.x1n, "y1_norm": r.y1n}
            for r in v
        ]
        for k, v in stored.items()
    }


def annotations_from_json(data: Dict[str, Any]) -> Dict[int, List[StoredRectNorm]]:
    out: Dict[int, List[StoredRectNorm]] = {}
    for k, items in (data or {}).items():
        try:
            page_k = int(k)
        except Exception:
            continue

        rects: List[StoredRectNorm] = []
        for it in items or []:
            rects.append(
                StoredRectNorm(
                    label=str(it.get("label", "Campo")),
                    x0n=float(it.get("x0_norm", 0.0)),
                    y0n=float(it.get("y0_norm", 0.0)),
                    x1n=float(it.get("x1_norm", 0.0)),
                    y1n=float(it.get("y1_norm", 0.0)),
                )
            )
        out[page_k] = rects
    return out
