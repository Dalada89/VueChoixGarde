from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QImage, QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QMenu, QWidget
from pytestqt.qtbot import QtBot

from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.native_keys import NativeKeyPlatform
from vuechoixgarde.ui.image_view import ImageView
from vuechoixgarde.ui.keyboard import (
    is_zoom_reset_event,
    keyboard_event_data,
    keyboard_event_from_raw,
    main_window_key_filter_enabled,
    zoom_factor_from_event,
)
from vuechoixgarde.ui.main_window import MainWindow


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


def test_main_window_shortcut_filter_is_disabled_while_popup_is_open(qtbot: QtBot) -> None:
    menu = QMenu()
    qtbot.addWidget(menu)
    menu.addAction("item")
    menu.popup(menu.pos())
    qtbot.waitUntil(lambda: QApplication.activePopupWidget() is menu)
    assert not main_window_key_filter_enabled()
    menu.close()


def test_f2_shortcut_is_disabled_for_text_input_and_dialog(qtbot: QtBot, tmp_path: Path) -> None:
    window = MainWindow(create_runtime(tmp_path / "app-data"))
    qtbot.addWidget(window)
    editor = QLineEdit(window)
    editor.setGeometry(0, 0, 120, 24)
    window.show()
    editor.setFocus()
    qtbot.waitUntil(editor.hasFocus)

    QTest.keyClick(window, Qt.Key.Key_F2)
    assert window.image_list_dock.isHidden()

    dialog = QDialog(window)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(dialog.isVisible)
    QTest.keyClick(window, Qt.Key.Key_F2)
    assert window.image_list_dock.isHidden()

    dialog.close()
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


@pytest.mark.parametrize(
    ("key", "text", "modifiers", "expected"),
    [
        (Qt.Key.Key_Plus, "+", Qt.KeyboardModifier.NoModifier, 1.25),
        (Qt.Key.Key_Plus, "+", Qt.KeyboardModifier.ShiftModifier, 1.25),
        (Qt.Key.Key_Plus, "+", Qt.KeyboardModifier.KeypadModifier, 1.25),
        (Qt.Key.Key_Minus, "-", Qt.KeyboardModifier.NoModifier, 0.8),
        (Qt.Key.Key_Minus, "-", Qt.KeyboardModifier.ShiftModifier, 0.8),
        (Qt.Key.Key_Plus, "+", Qt.KeyboardModifier.ControlModifier, None),
        (Qt.Key.Key_Minus, "-", Qt.KeyboardModifier.AltModifier, None),
        (Qt.Key.Key_X, "x", Qt.KeyboardModifier.NoModifier, None),
    ],
)
def test_zoom_factor_uses_generated_sign_and_allows_only_shift_or_keypad(
    key: Qt.Key, text: str, modifiers: Qt.KeyboardModifier, expected: float | None
) -> None:
    event = QKeyEvent(QEvent.Type.KeyPress, key, modifiers, 0, 0, 0, text, False, 1)

    assert zoom_factor_from_event(event) == expected


def test_zoom_reset_requires_unmodified_control_zero() -> None:
    reset = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_0,
        Qt.KeyboardModifier.ControlModifier,
        0,
        0,
        0,
        "0",
        False,
        1,
    )
    shifted_reset = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_0,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        0,
        0,
        0,
        "0",
        False,
        1,
    )

    assert is_zoom_reset_event(reset)
    assert not is_zoom_reset_event(shifted_reset)


def test_high_resolution_image_replacement_preserves_zoom_fit_and_offset() -> None:
    view = ImageView()
    view.resize(320, 240)
    view.set_image(QImage(640, 480, QImage.Format.Format_RGB32))
    view.zoom_by(1.25)
    view.zoom_state.offset = (12.0, -8.0)
    fit_scale = view._fit_scale()

    view.set_full_resolution_image(QImage(2560, 1920, QImage.Format.Format_RGB32))

    assert view.image is not None
    assert (view.image.width(), view.image.height()) == (2560, 1920)
    assert view.zoom_state.scale == 1.25
    assert view.zoom_state.offset == (12.0, -8.0)
    assert view._fit_scale() == fit_scale


def _send_zoom_key(
    window: MainWindow,
    key: Qt.Key,
    text: str,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    native_scan_code: int = 0,
) -> None:
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        key,
        modifiers,
        native_scan_code,
        0,
        0,
        text,
        False,
        1,
    )
    QApplication.sendEvent(window, event)


def test_main_window_zoom_keys_and_control_zero(qtbot: QtBot, tmp_path: Path) -> None:
    window = MainWindow(create_runtime(tmp_path / "app-data"))
    qtbot.addWidget(window)
    window.image_view.set_image(QImage(640, 480, QImage.Format.Format_RGB32))
    window.show()

    _send_zoom_key(window, Qt.Key.Key_Plus, "+", Qt.KeyboardModifier.ShiftModifier)
    assert window.image_view.zoom_state.scale == 1.25
    _send_zoom_key(window, Qt.Key.Key_Minus, "-")
    assert window.image_view.zoom_state.scale == 1.0
    _send_zoom_key(window, Qt.Key.Key_Plus, "+")
    _send_zoom_key(window, Qt.Key.Key_0, "0", Qt.KeyboardModifier.ControlModifier)
    assert window.image_view.zoom_state.scale == 1.0

    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


@pytest.mark.parametrize(
    ("zoom_key", "zoom_text"),
    [(Qt.Key.Key_Plus, "+"), (Qt.Key.Key_Minus, "-")],
)
def test_slot_binding_on_zoom_sign_takes_precedence(
    qtbot: QtBot, tmp_path: Path, zoom_key: Qt.Key, zoom_text: str
) -> None:
    runtime = replace(create_runtime(tmp_path / "app-data"), settings_writable=False)
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.image_view.set_image(QImage(640, 480, QImage.Format.Format_RGB32))
    window.view = SimpleNamespace(
        snapshot=SimpleNamespace(
            current_name="image.png",
            profile=SimpleNamespace(slots=(SimpleNamespace(key_position="KeyW"),)),
        )
    )
    pressed: list[tuple[int, str]] = []
    window._slot_pressed = lambda index, name: pressed.append((index, name))
    window.show()

    _send_zoom_key(
        window,
        zoom_key,
        zoom_text,
        Qt.KeyboardModifier.ShiftModifier,
        native_scan_code=25,
    )

    assert pressed == [(0, "image.png")]
    assert window.image_view.zoom_state.scale == 1.0
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_full_resolution_decode_happens_once_after_zoom_threshold(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (2048, 1536), "green").save(source / "image.png")
    original_runtime = create_runtime(tmp_path / "app-data")

    class RecordingDecoder:
        def __init__(self) -> None:
            self.calls: list[tuple[int, int]] = []

        def decode(self, path: Path, max_width: int, max_height: int):
            self.calls.append((max_width, max_height))
            return original_runtime.decoder.decode(path, max_width, max_height)

    decoder = RecordingDecoder()
    runtime = replace(original_runtime, decoder=decoder)
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_decode_bounds", lambda: (640, 480))
    window.show()
    window._open_folder(source)
    qtbot.waitUntil(
        lambda: window.image_view.image is not None and len(decoder.calls) == 1,
        timeout=5000,
    )

    _send_zoom_key(window, Qt.Key.Key_Plus, "+", Qt.KeyboardModifier.ShiftModifier)
    window.image_view.zoom_state.offset = (12.0, -8.0)
    _send_zoom_key(window, Qt.Key.Key_Plus, "+", Qt.KeyboardModifier.ShiftModifier)
    qtbot.waitUntil(
        lambda: (
            len(decoder.calls) == 2
            and window.image_view.image is not None
            and window.image_view.image.width() == 2048
        ),
        timeout=5000,
    )
    assert decoder.calls[1] == (2**31 - 1, 2**31 - 1)
    assert window.image_view.zoom_state.scale == pytest.approx(1.5625)
    assert window.image_view.zoom_state.offset == pytest.approx((15.0, -10.0))

    _send_zoom_key(window, Qt.Key.Key_Plus, "+", Qt.KeyboardModifier.ShiftModifier)
    qtbot.wait(100)
    assert len(decoder.calls) == 2
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)
