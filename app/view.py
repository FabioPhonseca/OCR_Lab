from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPen
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QInputDialog

from .items import AnnotRectItem


class AnnotView(QGraphicsView):
    rect_created = Signal(object)  # AnnotRectItem

    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        self.setMouseTracking(True)
        self._drawing_enabled = False
        self._image_bounds = QRectF(0, 0, 0, 0)

        self._start_scene: QPointF | None = None
        self._rubber: QGraphicsRectItem | None = None

        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

    def set_drawing_enabled(self, enabled: bool):
        self._drawing_enabled = enabled
        self.setDragMode(QGraphicsView.NoDrag if enabled else QGraphicsView.RubberBandDrag)

    def set_image_bounds(self, bounds: QRectF):
        self._image_bounds = bounds

    def zoom_in(self, factor: float = 1.15):
        self.scale(factor, factor)

    def zoom_out(self, factor: float = 1.15):
        self.scale(1 / factor, 1 / factor)

    def reset_zoom(self):
        self.resetTransform()

    def fit_to_page(self, bounds: QRectF):
        self.resetTransform()
        self.fitInView(bounds, Qt.KeepAspectRatio)

    def fit_to_width(self, bounds: QRectF):
        self.resetTransform()
        view_w = max(1, self.viewport().width())
        img_w = max(1.0, bounds.width())
        scale = view_w / img_w
        self.scale(scale, scale)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        if self._drawing_enabled and event.button() == Qt.LeftButton:
            self._start_scene = self.mapToScene(event.position().toPoint())
            self._start_scene = QPointF(
                max(self._image_bounds.left(), min(self._start_scene.x(), self._image_bounds.right())),
                max(self._image_bounds.top(), min(self._start_scene.y(), self._image_bounds.bottom())),
            )

            self._rubber = QGraphicsRectItem(QRectF(self._start_scene, self._start_scene))
            self._rubber.setPen(QPen(Qt.green, 2, Qt.DashLine))
            self.scene().addItem(self._rubber)

            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drawing_enabled and self._start_scene is not None and self._rubber is not None:
            cur = self.mapToScene(event.position().toPoint())
            cur = QPointF(
                max(self._image_bounds.left(), min(cur.x(), self._image_bounds.right())),
                max(self._image_bounds.top(), min(cur.y(), self._image_bounds.bottom())),
            )
            rect = QRectF(self._start_scene, cur).normalized()
            self._rubber.setRect(rect)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drawing_enabled and event.button() == Qt.LeftButton and self._rubber is not None:
            rect = self._rubber.rect().normalized()

            self.scene().removeItem(self._rubber)
            self._rubber = None
            self._start_scene = None

            if rect.width() < 5 or rect.height() < 5:
                event.accept()
                return

            label, ok = QInputDialog.getText(self, "Novo campo", "Nome do retângulo:", text="Campo1")
            if not ok or not label.strip():
                event.accept()
                return

            item = AnnotRectItem(rect, label.strip(), self._image_bounds)
            self.scene().addItem(item)
            self.rect_created.emit(item)
            event.accept()
            return

        super().mouseReleaseEvent(event)
