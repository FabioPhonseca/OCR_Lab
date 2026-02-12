from __future__ import annotations

import fitz  # PyMuPDF
from PySide6.QtGui import QImage, QPixmap


def render_pdf_page(doc: fitz.Document, page_index: int, zoom: float) -> QPixmap:
    page = doc.load_page(page_index)
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)  # RGB

    qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


def get_rendered_size(doc: fitz.Document, page_index: int, zoom: float) -> tuple[int, int]:
    page = doc.load_page(page_index)
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return pix.width, pix.height
