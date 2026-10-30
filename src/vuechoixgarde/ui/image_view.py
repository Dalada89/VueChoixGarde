from typing import override

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPainter, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QFrame

from vuechoixgarde.ui.zoom import ZoomState


class ImageView(QFrame):
    zoom_changed = Signal(float)

    def __init__(self, message: str = "", parent=None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self._fit_image_size: tuple[int, int] | None = None
        self._message = message
        self._zoom_state = ZoomState()
        self._drag_position: QPoint | None = None
        self._drag_offset: tuple[float, float] = (0.0, 0.0)
        self.setObjectName("panel")
        self.setMinimumSize(320, 240)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setAccessibleDescription(message)

    @property
    def image(self) -> QImage | None:
        return self._image

    @property
    def message(self) -> str:
        return self._message

    @property
    def zoom_state(self) -> ZoomState:
        return self._zoom_state

    def set_image(self, image: QImage | None) -> None:
        self._image = image if image is not None and not image.isNull() else None
        self._fit_image_size = (
            (self._image.width(), self._image.height()) if self._image is not None else None
        )
        self._message = ""
        self.setAccessibleDescription("")
        self.reset_zoom()

    def set_full_resolution_image(self, image: QImage) -> None:
        if image.isNull():
            return
        self._image = image
        if self._fit_image_size is None:
            self._fit_image_size = (image.width(), image.height())
        self._message = ""
        self.setAccessibleDescription("")
        self._clamp_offset()
        self.update()

    def set_message(self, message: str) -> None:
        self._image = None
        self._fit_image_size = None
        self._message = message
        self.setAccessibleDescription(message)
        self.reset_zoom()

    def reset_zoom(self) -> None:
        self._zoom_state.reset()
        self._drag_position = None
        self.update()

    def zoom_by(self, factor: float) -> None:
        if self._image is None:
            return
        self._zoom_state.zoom_at((0.0, 0.0), factor)
        self._clamp_offset()
        self.update()
        self.zoom_changed.emit(self._zoom_state.scale)

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._clamp_offset()

    def _fit_scale(self) -> float:
        if self._fit_image_size is None:
            return 1.0
        return min(
            1.0,
            self.width() / max(1, self._fit_image_size[0]),
            self.height() / max(1, self._fit_image_size[1]),
        )

    def _clamp_offset(self) -> None:
        if self._image is None:
            self._zoom_state.offset = (0.0, 0.0)
            return
        scale = self._fit_scale() * self._zoom_state.scale
        overflow_x = abs(self._image.width() * scale - self.width()) / 2
        overflow_y = abs(self._image.height() * scale - self.height()) / 2
        self._zoom_state.offset = (
            max(-overflow_x, min(overflow_x, self._zoom_state.offset[0])),
            max(-overflow_y, min(overflow_y, self._zoom_state.offset[1])),
        )

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._image is None:
            if self._message:
                painter.setPen(self.palette().color(self.foregroundRole()))
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._message)
            return
        scale = self._fit_scale() * self._zoom_state.scale
        width = self._image.width() * scale
        height = self._image.height() * scale
        center_x = self.width() / 2 + self._zoom_state.offset[0]
        center_y = self.height() / 2 + self._zoom_state.offset[1]
        target = QRectF(center_x - width / 2, center_y - height / 2, width, height)
        painter.drawImage(target, self._image)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self._image is None or event.angleDelta().y() == 0:
            event.ignore()
            return
        anchor = event.position()
        anchor_from_center = (
            anchor.x() - self.width() / 2,
            anchor.y() - self.height() / 2,
        )
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self._zoom_state.zoom_at(anchor_from_center, factor)
        self._clamp_offset()
        self.update()
        self.zoom_changed.emit(self._zoom_state.scale)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._image is not None and event.button() is Qt.MouseButton.LeftButton:
            self._drag_position = event.position().toPoint()
            self._drag_offset = self._zoom_state.offset
            event.accept()
            return
        event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_position is None or self._image is None:
            event.ignore()
            return
        delta = event.position().toPoint() - self._drag_position
        self._zoom_state.offset = (
            self._drag_offset[0] + delta.x(),
            self._drag_offset[1] + delta.y(),
        )
        self._clamp_offset()
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() is Qt.MouseButton.LeftButton:
            self._drag_position = None
            event.accept()
            return
        event.ignore()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._image is not None and event.button() is Qt.MouseButton.LeftButton:
            self.reset_zoom()
            event.accept()
            return
        event.ignore()
