"""Translate Qt key events to immutable physical-position data (FR-051, FR-082, FR-084)."""

import sys
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)

from vuechoixgarde.core.native_keys import NativeKeyPlatform, position_for_native_code


@dataclass(frozen=True)
class KeyboardEventData:
    """Qt-independent facts needed by the later application layer (FR-051/FR-082)."""

    position: str | None
    modifier_active: bool
    auto_repeat: bool
    text: str

    @property
    def triggers_slot(self) -> bool:
        """Return whether this event is an unmodified, non-repeat slot press (FR-051/FR-082)."""
        return self.position is not None and not self.modifier_active and not self.auto_repeat


def running_platform() -> NativeKeyPlatform:
    """Return the native keyboard-code family for this process (FR-081)."""
    if sys.platform == "win32":
        return NativeKeyPlatform.WINDOWS
    if sys.platform == "darwin":
        return NativeKeyPlatform.MACOS
    return NativeKeyPlatform.LINUX


def keyboard_event_from_raw(
    *,
    native_scan_code: int,
    native_virtual_key: int,
    modifiers: Qt.KeyboardModifier,
    auto_repeat: bool,
    text: str,
    platform: NativeKeyPlatform,
) -> KeyboardEventData:
    """Create Qt-independent key facts from raw event fields (FR-051/FR-082)."""
    native_code = native_virtual_key if platform is NativeKeyPlatform.MACOS else native_scan_code
    position = position_for_native_code(platform, native_code)
    active_modifiers = (
        Qt.KeyboardModifier.ShiftModifier
        | Qt.KeyboardModifier.ControlModifier
        | Qt.KeyboardModifier.AltModifier
        | Qt.KeyboardModifier.MetaModifier
        | Qt.KeyboardModifier.GroupSwitchModifier
    )
    return KeyboardEventData(
        position=position,
        modifier_active=bool(modifiers & active_modifiers),
        auto_repeat=auto_repeat,
        text=text,
    )


def main_window_key_filter_enabled() -> bool:
    """Disable main-window shortcuts while a dialog or text editor owns interaction (FR-084)."""
    if QApplication.instance() is None:
        return False
    if (
        QApplication.activeModalWidget() is not None
        or QApplication.activePopupWidget() is not None
        or any(
            isinstance(widget, QDialog) and widget.isVisible()
            for widget in QApplication.topLevelWidgets()
        )
    ):
        return False

    focus_widget: QWidget | None = QApplication.focusWidget()
    while focus_widget is not None:
        if isinstance(focus_widget, (QAbstractSpinBox, QLineEdit, QPlainTextEdit, QTextEdit)):
            return False
        if isinstance(focus_widget, QComboBox) and focus_widget.isEditable():
            return False
        focus_widget = focus_widget.parentWidget()
    return True


def keyboard_event_data(
    event: QKeyEvent, *, platform: NativeKeyPlatform | None = None
) -> KeyboardEventData:
    """Translate a Qt key event using the correct platform-native field (FR-081/FR-082)."""
    return keyboard_event_from_raw(
        native_scan_code=event.nativeScanCode(),
        native_virtual_key=event.nativeVirtualKey(),
        modifiers=event.modifiers(),
        auto_repeat=event.isAutoRepeat(),
        text=event.text(),
        platform=platform or running_platform(),
    )
