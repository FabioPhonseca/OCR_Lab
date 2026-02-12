from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QObject
from PySide6.QtGui import QBrush, QPen
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsSimpleTextItem


class RectSignals(QObject):
    changed = Signal(object)  # emite o próprio item


class AnnotRectItem(QGraphicsRectItem):
    """
    Retângulo anotável: selecionável, movível e com clamp nos limites da imagem.
    Desenha label no canto superior esquerdo.
    """
    def __init__(self, rect: QRectF, label: str, image_bounds: QRectF):
        super().__init__(rect)
        self.signals = RectSignals()

        self._label = label
        self._image_bounds = image_bounds

        self.setFlags(
            QGraphicsRectItem.ItemIsSelectable
            | QGraphicsRectItem.ItemIsMovable
            | QGraphicsRectItem.ItemSendsGeometryChanges
        )

        self.setPen(QPen(Qt.red, 2))
        self.setBrush(QBrush(Qt.transparent))

        self._text = QGraphicsSimpleTextItem(self._label, self)
        self._text.setBrush(QBrush(Qt.red))
        self._text.setPos(self.rect().topLeft() + QPointF(2, 2))

    def set_label(self, label: str):
        self._label = label
        self._text.setText(label)
        self.signals.changed.emit(self)

    def label(self) -> str:
        return self._label

    def set_image_bounds(self, bounds: QRectF):
        self._image_bounds = bounds

    def _clamp_rect_to_bounds(self, rect: QRectF) -> QRectF:
        r = QRectF(rect).normalized()

        if r.width() < 1:
            r.setWidth(1)
        if r.height() < 1:
            r.setHeight(1)

        if r.left() < self._image_bounds.left():
            r.moveLeft(self._image_bounds.left())
        if r.top() < self._image_bounds.top():
            r.moveTop(self._image_bounds.top())
        if r.right() > self._image_bounds.right():
            r.moveRight(self._image_bounds.right())
        if r.bottom() > self._image_bounds.bottom():
            r.moveBottom(self._image_bounds.bottom())

        return r

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.ItemPositionChange:
            new_pos: QPointF = value
            current_scene_rect = self.sceneBoundingRect()
            delta = new_pos - self.pos()
            moved_rect = current_scene_rect.translated(delta)

            clamped = QRectF(moved_rect)
            if clamped.left() < self._image_bounds.left():
                clamped.moveLeft(self._image_bounds.left())
            if clamped.top() < self._image_bounds.top():
                clamped.moveTop(self._image_bounds.top())
            if clamped.right() > self._image_bounds.right():
                clamped.moveRight(self._image_bounds.right())
            if clamped.bottom() > self._image_bounds.bottom():
                clamped.moveBottom(self._image_bounds.bottom())

            correction = clamped.topLeft() - moved_rect.topLeft()
            return new_pos + correction

        if change in (QGraphicsRectItem.ItemPositionHasChanged, QGraphicsRectItem.ItemTransformHasChanged):
            self.signals.changed.emit(self)

        return super().itemChange(change, value)

    def setRect(self, rect: QRectF):
        rect = self._clamp_rect_to_bounds(rect)
        super().setRect(rect)
        self._text.setPos(self.rect().topLeft() + QPointF(2, 2))
        self.signals.changed.emit(self)
