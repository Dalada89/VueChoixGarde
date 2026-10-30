"""Virtualized image-name list with slot markers for the main window."""

from collections.abc import Sequence
from typing import override

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFontMetrics, QPainter, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QListView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

SlotInfo = tuple[str, str]


class ImageListModel(QAbstractListModel):
    """List image names and optional slot color/name markers without row widgets."""

    SlotColorsRole = int(Qt.ItemDataRole.UserRole) + 1
    HasMoreSlotsRole = int(Qt.ItemDataRole.UserRole) + 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._names: tuple[str, ...] = ()
        self._slot_info: tuple[tuple[SlotInfo, ...], ...] = ()
        self._current_index: int | None = None

    @override
    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._names)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._names):
            return None
        row = index.row()
        if role == Qt.ItemDataRole.DisplayRole:
            return self._names[row]
        if role == Qt.ItemDataRole.ToolTipRole:
            return ", ".join(name for _color, name in self._slot_info[row]) or None
        if role == self.SlotColorsRole:
            return tuple(color for color, _name in self._slot_info[row][:3])
        if role == self.HasMoreSlotsRole:
            return len(self._slot_info[row]) > 3
        if role == Qt.ItemDataRole.BackgroundRole and row == self._current_index:
            return QBrush(QApplication.palette().color(QPalette.ColorRole.Highlight))
        if role == Qt.ItemDataRole.FontRole and row == self._current_index:
            font = QApplication.font()
            font.setBold(True)
            return font
        return None

    def set_images(
        self,
        image_names: Sequence[str],
        slot_info: Sequence[Sequence[SlotInfo]] | None = None,
    ) -> None:
        names = tuple(image_names)
        if slot_info is None:
            slots = ((),) * len(names)
        else:
            if len(slot_info) != len(names):
                raise ValueError("slot info must contain one entry per image")
            slots = tuple(tuple(entries) for entries in slot_info)
        self.beginResetModel()
        self._names = names
        self._slot_info = slots
        self._current_index = None
        self.endResetModel()

    def set_slot_info(self, slot_info: Sequence[Sequence[SlotInfo]]) -> None:
        if len(slot_info) != len(self._names):
            raise ValueError("slot info must contain one entry per image")
        slots = tuple(tuple(entries) for entries in slot_info)
        if slots == self._slot_info:
            return
        self._slot_info = slots
        if self._names:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._names) - 1, 0),
                [
                    Qt.ItemDataRole.ToolTipRole,
                    self.SlotColorsRole,
                    self.HasMoreSlotsRole,
                ],
            )

    def set_current_index(self, index: int | None) -> None:
        if index is not None and not 0 <= index < len(self._names):
            raise IndexError(index)
        previous, self._current_index = self._current_index, index
        for row in {previous, index} - {None}:
            model_index = self.index(row, 0)
            self.dataChanged.emit(
                model_index,
                model_index,
                [Qt.ItemDataRole.BackgroundRole, Qt.ItemDataRole.FontRole],
            )


class ImageListDelegate(QStyledItemDelegate):
    """Draw image names and up to three colored stars in each virtualized row."""

    _STAR_WIDTH = 18
    _OVERFLOW_WIDTH = 20
    _HORIZONTAL_PADDING = 8

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        row_rect = option.rect
        current = index.data(Qt.ItemDataRole.BackgroundRole)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            background = option.palette.color(QPalette.ColorRole.Highlight)
            text_color = option.palette.color(QPalette.ColorRole.HighlightedText)
        elif isinstance(current, QBrush):
            background = current.color()
            text_color = option.palette.color(QPalette.ColorRole.HighlightedText)
        else:
            background = option.palette.color(QPalette.ColorRole.Base)
            text_color = option.palette.color(QPalette.ColorRole.Text)
        painter.fillRect(row_rect, background)

        colors = index.data(ImageListModel.SlotColorsRole) or ()
        has_more = bool(index.data(ImageListModel.HasMoreSlotsRole))
        marker_width = len(colors) * self._STAR_WIDTH
        if has_more:
            marker_width += self._OVERFLOW_WIDTH
        text_rect = QRect(
            row_rect.left() + self._HORIZONTAL_PADDING,
            row_rect.top(),
            max(0, row_rect.width() - marker_width - 2 * self._HORIZONTAL_PADDING),
            row_rect.height(),
        )
        painter.setPen(text_color)
        font = index.data(Qt.ItemDataRole.FontRole)
        if font is not None:
            painter.setFont(font)
        metrics = QFontMetrics(painter.font())
        label = metrics.elidedText(
            str(index.data(Qt.ItemDataRole.DisplayRole) or ""),
            Qt.TextElideMode.ElideRight,
            text_rect.width(),
        )
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            label,
        )

        x = row_rect.right() - self._HORIZONTAL_PADDING - marker_width
        for color in colors:
            painter.setPen(QColor(color))
            painter.drawText(
                QRect(x, row_rect.top(), self._STAR_WIDTH, row_rect.height()),
                Qt.AlignmentFlag.AlignCenter,
                "★",
            )
            x += self._STAR_WIDTH
        if has_more:
            painter.setPen(text_color)
            painter.drawText(
                QRect(x, row_rect.top(), self._OVERFLOW_WIDTH, row_rect.height()),
                Qt.AlignmentFlag.AlignCenter,
                "…",
            )
        painter.restore()

    @override
    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        size = super().sizeHint(option, index)
        return QSize(size.width(), max(24, size.height()))


class ImageListPanel(QWidget):
    """A virtualized image list that emits zero-based navigation requests."""

    image_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = QListView(self)
        self.image_model = ImageListModel(self)
        self.view.setModel(self.image_model)
        self.view.setItemDelegate(ImageListDelegate(self.view))
        self.view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.view.setUniformItemSizes(True)
        self.view.clicked.connect(self._request_image)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    def set_images(
        self,
        image_names: Sequence[str],
        slot_info: Sequence[Sequence[SlotInfo]] | None = None,
    ) -> None:
        self.image_model.set_images(image_names, slot_info)

    def set_slot_info(self, slot_info: Sequence[Sequence[SlotInfo]]) -> None:
        self.image_model.set_slot_info(slot_info)

    def set_current_index(self, index: int | None) -> None:
        self.image_model.set_current_index(index)
        if index is None:
            self.view.setCurrentIndex(QModelIndex())
            return
        model_index = self.image_model.index(index, 0)
        self.view.setCurrentIndex(model_index)
        self.view.scrollTo(model_index, QListView.ScrollHint.EnsureVisible)

    def _request_image(self, index: QModelIndex) -> None:
        if index.isValid():
            self.image_requested.emit(index.row())
