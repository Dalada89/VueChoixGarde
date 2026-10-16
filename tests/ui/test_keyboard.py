import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog, QLineEdit, QWidget
from pytestqt.qtbot import QtBot

from vuechoixgarde.core.native_keys import NativeKeyPlatform
from vuechoixgarde.ui.keyboard import (
    keyboard_event_data,
    keyboard_event_from_raw,
    main_window_key_filter_enabled,
)


def make_key_event(
    *,
    native_scan_code: int = 25,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    auto_repeat: bool = False,
) -> QKeyEvent:
    return QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_W,
        modifiers,
        native_scan_code,
        0,
        0,
        "z",
        auto_repeat,
        1,
    )


def test_linux_qt_event_maps_native_scan_code_to_physical_position(qtbot: QtBot) -> None:
    qtbot.addWidget(QWidget())
    event = make_key_event()
    assert event.nativeScanCode() == 25
    data = keyboard_event_data(event, platform=NativeKeyPlatform.LINUX)
    assert data.position == "KeyW"
    assert data.text == "z"
    assert data.triggers_slot


@pytest.mark.parametrize(
    "modifier",
    [
        Qt.KeyboardModifier.ShiftModifier,
        Qt.KeyboardModifier.ControlModifier,
        Qt.KeyboardModifier.AltModifier,
        Qt.KeyboardModifier.GroupSwitchModifier,
    ],
)
def test_modifier_keys_prevent_slot_activation(qtbot: QtBot, modifier: Qt.KeyboardModifier) -> None:
    qtbot.addWidget(QWidget())
    data = keyboard_event_data(make_key_event(modifiers=modifier), platform=NativeKeyPlatform.LINUX)
    assert data.position == "KeyW"
    assert data.modifier_active
    assert not data.triggers_slot


def test_keypad_modifier_does_not_count_as_a_modifier(qtbot: QtBot) -> None:
    qtbot.addWidget(QWidget())
    data = keyboard_event_data(
        make_key_event(modifiers=Qt.KeyboardModifier.KeypadModifier),
        platform=NativeKeyPlatform.LINUX,
    )
    assert not data.modifier_active
    assert data.triggers_slot


def test_auto_repeat_slot_event_is_ignored(qtbot: QtBot) -> None:
    qtbot.addWidget(QWidget())
    data = keyboard_event_data(make_key_event(auto_repeat=True), platform=NativeKeyPlatform.LINUX)
    assert data.position == "KeyW"
    assert data.auto_repeat
    assert not data.triggers_slot


def test_macos_uses_native_virtual_key_in_raw_event_logic() -> None:
    data = keyboard_event_from_raw(
        native_scan_code=999,
        native_virtual_key=0x0D,
        modifiers=Qt.KeyboardModifier.NoModifier,
        auto_repeat=False,
        text="w",
        platform=NativeKeyPlatform.MACOS,
    )
    assert data.position == "KeyW"


def test_windows_uses_scan_code_and_ignores_native_virtual_key() -> None:
    data = keyboard_event_from_raw(
        native_scan_code=0x11,
        native_virtual_key=0x41,
        modifiers=Qt.KeyboardModifier.NoModifier,
        auto_repeat=False,
        text="w",
        platform=NativeKeyPlatform.WINDOWS,
    )
    assert data.position == "KeyW"


def test_unknown_scan_code_has_no_slot_position() -> None:
    data = keyboard_event_from_raw(
        native_scan_code=999,
        native_virtual_key=0,
        modifiers=Qt.KeyboardModifier.NoModifier,
        auto_repeat=False,
        text="",
        platform=NativeKeyPlatform.LINUX,
    )
    assert data.position is None
    assert not data.triggers_slot


def test_main_window_shortcut_filter_is_enabled_for_ordinary_focus(qtbot: QtBot) -> None:
    window = QWidget()
    qtbot.addWidget(window)
    window.show()
    window.setFocus()
    qtbot.waitUntil(window.hasFocus)
    assert main_window_key_filter_enabled()


def test_main_window_shortcut_filter_is_disabled_for_text_input(qtbot: QtBot) -> None:
    line_edit = QLineEdit()
    qtbot.addWidget(line_edit)
    line_edit.show()
    line_edit.setFocus()
    qtbot.waitUntil(line_edit.hasFocus)
    assert not main_window_key_filter_enabled()


def test_main_window_shortcut_filter_is_disabled_while_dialog_is_open(qtbot: QtBot) -> None:
    dialog = QDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(dialog.isVisible)
    assert not main_window_key_filter_enabled()
