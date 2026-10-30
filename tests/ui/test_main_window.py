from pathlib import Path
from threading import Event
from time import sleep

import pytest
from PIL import Image
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QKeyEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QLineEdit,
    QMessageBox,
)
from pytestqt.qtbot import QtBot

from vuechoixgarde.app.results import FolderDeletionCase, FolderDeletionCheck
from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.slots import Slot, SlotMode
from vuechoixgarde.ui.main_window import MainWindow
from vuechoixgarde.ui.texts import set_language, text


def _slot_key(
    *,
    auto_repeat: bool = False,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> QKeyEvent:
    return QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_W,
        modifiers,
        25,
        0,
        0,
        "w",
        auto_repeat,
        1,
    )


def _fill_name_dialog() -> bool:
    dialog = QApplication.activeModalWidget()
    if not isinstance(dialog, QDialog) or dialog.windowTitle() != "Choose destination folder name":
        return False
    editor = dialog.findChild(QLineEdit)
    if editor is None:
        return False
    editor.setText("Sorted")
    buttons = dialog.findChild(QDialogButtonBox)
    if buttons is None:
        return False
    button = buttons.button(QDialogButtonBox.StandardButton.Ok)
    if button is None:
        return False
    button.click()
    return True


def _open_two_image_window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (640, 480), "red").save(source / "IMG_1.png")
    Image.new("RGB", (640, 480), "blue").save(source / "IMG_2.png")
    window = MainWindow(create_runtime(tmp_path / "app-data"))
    qtbot.addWidget(window)
    window.show()
    window._open_folder(source)
    qtbot.waitUntil(
        lambda: window.view is not None and window.image_view.image is not None,
        timeout=5000,
    )
    return window


def _send_wheel(view, position: QPoint, delta: int = 120) -> None:
    global_position = QPointF(view.mapToGlobal(position))
    event = QWheelEvent(
        QPointF(position),
        global_position,
        QPoint(),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(view, event)


def _zoom_in(view, position: QPoint, steps: int = 4) -> None:
    for _ in range(steps):
        _send_wheel(view, position)


def _image_point_at(view, position: QPoint) -> tuple[float, float]:
    zoom = view.zoom_state
    image = view.image
    assert image is not None
    fit_scale = min(1.0, view.width() / image.width(), view.height() / image.height())
    return (
        (position.x() - view.width() / 2 - zoom.offset[0]) / (fit_scale * zoom.scale),
        (position.y() - view.height() / 2 - zoom.offset[1]) / (fit_scale * zoom.scale),
    )


def test_folder_delete_confirmation_defaults_to_cancel_and_shows_foreign_names(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window = MainWindow(create_runtime(tmp_path / "app-data"))
    qtbot.addWidget(window)
    check = FolderDeletionCheck(
        FolderDeletionCase.FOREIGN_ENTRIES,
        0,
        "Target",
        (),
        ("<unexpected>.jpg",),
        "fingerprint",
    )
    observed: dict[str, object] = {}

    def cancel_confirmation() -> None:
        box = QApplication.activeModalWidget()
        assert isinstance(box, QMessageBox)
        cancel_button = box.button(QMessageBox.StandardButton.Cancel)
        observed["default"] = box.defaultButton() == cancel_button
        observed["escape"] = box.escapeButton() == cancel_button
        observed["format"] = box.textFormat()
        observed["informative"] = box.informativeText()
        QTest.keyClick(box, Qt.Key.Key_Escape)

    QTimer.singleShot(0, cancel_confirmation)
    assert not window._ask_folder_delete_confirmation(window, check)
    assert observed["default"] is True
    assert observed["escape"] is True
    assert observed["format"] is Qt.TextFormat.PlainText
    assert "<unexpected>.jpg" in str(observed["informative"])


def test_main_window_opens_displays_navigates_and_shuts_down(qtbot: QtBot, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (12, 8), "red").save(source / "IMG_1.png")
    Image.new("RGB", (12, 8), "blue").save(source / "IMG_2.png")
    runtime = create_runtime(tmp_path / "app-data")
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()
    window._open_folder(source)

    qtbot.waitUntil(lambda: window.view is not None, timeout=5000)
    qtbot.waitUntil(lambda: window.image_view.image is not None, timeout=5000)
    assert window.filename_label.toolTip() == "IMG_1.png"
    assert window.progress_text.text() == "1 of 2"
    window.open_button.setFocus()
    qtbot.waitUntil(window.open_button.hasFocus)

    qtbot.keyClick(window.open_button, Qt.Key.Key_Right)
    qtbot.waitUntil(
        lambda: window.view is not None and window.view.snapshot.current_name == "IMG_2.png",
        timeout=5000,
    )
    assert QApplication.focusWidget() is window.open_button
    qtbot.keyClick(window.open_button, Qt.Key.Key_Right)
    qtbot.waitUntil(lambda: "end of the image list" in window.statusBar().currentMessage())
    qtbot.keyClick(window.open_button, Qt.Key.Key_Left)
    qtbot.waitUntil(
        lambda: window.view is not None and window.view.snapshot.current_name == "IMG_1.png",
        timeout=5000,
    )
    qtbot.keyClick(window.open_button, Qt.Key.Key_Left)
    qtbot.waitUntil(lambda: "beginning of the image list" in window.statusBar().currentMessage())

    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_arrow_key_in_dialog_editor_does_not_navigate_main_window(
    qtbot: QtBot, tmp_path: Path
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (12, 8), "red").save(source / "IMG_1.png")
    Image.new("RGB", (12, 8), "blue").save(source / "IMG_2.png")
    runtime = create_runtime(tmp_path / "app-data")
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()
    window._open_folder(source)
    qtbot.waitUntil(lambda: window.view is not None, timeout=5000)

    dialog = QDialog(window)
    editor = QLineEdit(dialog)
    editor.resize(240, 32)
    dialog.resize(280, 80)
    qtbot.addWidget(dialog)
    dialog.show()
    editor.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() is editor)
    qtbot.keyClick(editor, Qt.Key.Key_Right)
    qtbot.wait(100)

    assert window.view is not None
    assert window.view.snapshot.current_name == "IMG_1.png"
    dialog.close()
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_slot_key_prompts_validates_toggles_and_modified_confirmation_defaults_to_cancel(
    qtbot: QtBot, tmp_path: Path
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    image_path = source / "IMG_1.png"
    Image.new("RGB", (8, 8), "green").save(image_path)
    runtime = create_runtime(tmp_path / "app-data")
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()
    window._open_folder(source)
    qtbot.waitUntil(lambda: window.view is not None, timeout=5000)
    QApplication.sendEvent(
        window,
        _slot_key(modifiers=Qt.KeyboardModifier.ControlModifier),
    )
    QApplication.sendEvent(window, _slot_key(auto_repeat=True))
    qtbot.wait(50)
    assert not (source / "Sorted").exists()

    fill_name = QTimer(window)
    fill_name.setInterval(10)
    fill_name.timeout.connect(_fill_name_dialog)
    fill_name.start()
    QApplication.sendEvent(window, _slot_key())
    copied = source / "Sorted" / image_path.name
    qtbot.waitUntil(lambda: copied.exists(), timeout=7000)
    qtbot.waitUntil(lambda: not window._slot_operation_pending, timeout=5000)
    fill_name.stop()
    assert copied.read_bytes() == image_path.read_bytes()

    copied.write_bytes(b"user changed the managed copy")
    confirmation_observed: list[bool] = []

    def cancel_confirmation() -> None:
        dialog = QApplication.activeModalWidget()
        if not isinstance(dialog, QMessageBox):
            return
        if dialog.windowTitle() != "Confirm removal of modified copies":
            return
        default = dialog.defaultButton()
        confirmation_observed.append(default is not None and default.text() == "Cancel")
        dialog.button(QMessageBox.StandardButton.Cancel).click()

    cancel_timer = QTimer(window)
    cancel_timer.setInterval(10)
    cancel_timer.timeout.connect(cancel_confirmation)
    cancel_timer.start()
    QApplication.sendEvent(window, _slot_key())
    qtbot.waitUntil(lambda: bool(confirmation_observed), timeout=7000)
    qtbot.waitUntil(lambda: not window._slot_operation_pending, timeout=5000)
    cancel_timer.stop()

    assert confirmation_observed == [True]
    assert copied.read_bytes() == b"user changed the managed copy"
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_broken_image_remains_navigable_and_shows_decode_error(
    qtbot: QtBot, tmp_path: Path
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "broken.jpg").write_bytes(b"not an image")
    runtime = create_runtime(tmp_path / "app-data")
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()
    window._open_folder(source)

    qtbot.waitUntil(lambda: window.view is not None, timeout=5000)
    qtbot.waitUntil(
        lambda: window.image_view.message == "This image is damaged or cannot be decoded.",
        timeout=5000,
    )
    assert window.filename_label.toolTip() == "broken.jpg"
    assert window.progress_text.text() == "1 of 1"
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_image_view_starts_at_the_previous_fit_size(qtbot: QtBot, tmp_path: Path) -> None:
    window = _open_two_image_window(qtbot, tmp_path)
    view = window.image_view
    image = view.image
    assert image is not None
    fit_scale = min(1.0, view.width() / image.width(), view.height() / image.height())
    expected_width = image.width() * fit_scale
    expected_height = image.height() * fit_scale
    rendered = view.grab().toImage()
    center_x = view.width() // 2
    center_y = view.height() // 2
    horizontal = [
        x
        for x in range(view.width())
        if rendered.pixelColor(x, center_y).red() > 220
        and rendered.pixelColor(x, center_y).green() < 40
    ]
    vertical = [
        y
        for y in range(view.height())
        if rendered.pixelColor(center_x, y).red() > 220
        and rendered.pixelColor(center_x, y).green() < 40
    ]

    assert max(horizontal) - min(horizontal) + 1 == pytest.approx(expected_width, abs=2)
    assert max(vertical) - min(vertical) + 1 == pytest.approx(expected_height, abs=2)
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_image_view_wheel_zoom_keeps_the_anchor_point_fixed(qtbot: QtBot, tmp_path: Path) -> None:
    window = _open_two_image_window(qtbot, tmp_path)
    view = window.image_view
    anchor = QPoint(view.width() // 2 + 8, view.height() // 2 + 8)
    image_point_before = _image_point_at(view, anchor)

    _send_wheel(view, anchor)

    assert view.zoom_state.scale > 1.0
    assert _image_point_at(view, anchor) == pytest.approx(image_point_before)
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_image_view_drag_moves_the_zoomed_image(qtbot: QtBot, tmp_path: Path) -> None:
    window = _open_two_image_window(qtbot, tmp_path)
    view = window.image_view
    center = QPoint(view.width() // 2, view.height() // 2)
    _zoom_in(view, center)
    qtbot.waitUntil(lambda: view.zoom_state.scale > 1.0, timeout=1000)
    initial_offset = view.zoom_state.offset
    target = QPoint(center.x() - 24, center.y() - 18)

    QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=center)
    QTest.mouseMove(view, target, delay=10)
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=target)

    assert view.zoom_state.offset != initial_offset
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_image_change_resets_zoom_and_offset(qtbot: QtBot, tmp_path: Path) -> None:
    window = _open_two_image_window(qtbot, tmp_path)
    view = window.image_view
    center = QPoint(view.width() // 2, view.height() // 2)
    _zoom_in(view, center)
    target = QPoint(center.x() - 24, center.y() - 18)
    QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=center)
    QTest.mouseMove(view, target, delay=10)
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=target)
    assert view.zoom_state.offset != (0.0, 0.0)

    QTest.keyClick(window.open_button, Qt.Key.Key_Right)
    qtbot.waitUntil(
        lambda: window.view is not None and window.view.snapshot.current_name == "IMG_2.png",
        timeout=5000,
    )

    assert view.zoom_state.scale == 1.0
    assert view.zoom_state.offset == (0.0, 0.0)
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_image_view_double_click_resets_zoom_and_offset(qtbot: QtBot, tmp_path: Path) -> None:
    window = _open_two_image_window(qtbot, tmp_path)
    view = window.image_view
    center = QPoint(view.width() // 2, view.height() // 2)
    _zoom_in(view, center)
    target = QPoint(center.x() - 24, center.y() - 18)
    QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=center)
    QTest.mouseMove(view, target, delay=10)
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=target)
    assert view.zoom_state.offset != (0.0, 0.0)

    QTest.mouseDClick(view, Qt.MouseButton.LeftButton, pos=center)

    assert view.zoom_state.scale == 1.0
    assert view.zoom_state.offset == (0.0, 0.0)
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_empty_image_view_ignores_zoom_input(qtbot: QtBot, tmp_path: Path) -> None:
    window = MainWindow(create_runtime(tmp_path / "app-data"))
    qtbot.addWidget(window)
    window.show()
    view = window.image_view

    _send_wheel(view, QPoint(view.width() // 2, view.height() // 2))
    QTest.mouseDClick(
        view,
        Qt.MouseButton.LeftButton,
        pos=QPoint(view.width() // 2, view.height() // 2),
    )

    assert view.image is None
    assert view.zoom_state.scale == 1.0
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_busy_indicator_appears_after_one_second(qtbot: QtBot, tmp_path: Path) -> None:
    runtime = create_runtime(tmp_path / "app-data")
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()
    window._run_file(lambda: sleep(1.1))

    qtbot.waitUntil(window.busy_label.isVisible, timeout=1500)
    qtbot.waitUntil(lambda: window._pending_operations == 0, timeout=3000)
    assert not window.busy_label.isVisible()
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_close_waits_for_in_flight_file_operation(qtbot: QtBot, tmp_path: Path) -> None:
    runtime = create_runtime(tmp_path / "app-data")
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()
    completed = Event()

    def operation() -> None:
        sleep(0.15)
        completed.set()

    window._run_file(operation)
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)

    assert completed.is_set()
    assert runtime.service.session is None


def test_image_list_dock_starts_collapsed_toggles_and_keeps_arrow_navigation(
    qtbot: QtBot, tmp_path: Path
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for index in range(3):
        Image.new("RGB", (8, 8), "red").save(source / f"image-{index:03}.png")
    window = MainWindow(create_runtime(tmp_path / "app-data"))
    qtbot.addWidget(window)
    window.show()
    window._open_folder(source)

    qtbot.waitUntil(lambda: window.view is not None, timeout=5000)
    qtbot.waitUntil(lambda: window.image_list.image_model.rowCount() == 3, timeout=5000)
    assert window.image_list_dock.isHidden()
    assert window.image_list_dock.features() == QDockWidget.DockWidgetFeature.NoDockWidgetFeatures

    window.image_list_button.click()
    qtbot.waitUntil(window.image_list_dock.isVisible)
    QTest.keyClick(window, Qt.Key.Key_F2)
    qtbot.waitUntil(window.image_list_dock.isHidden)
    QTest.keyClick(window, Qt.Key.Key_F2)
    qtbot.waitUntil(window.image_list_dock.isVisible)

    target = window.image_list.image_model.index(1, 0)
    QTest.mouseClick(
        window.image_list.view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=window.image_list.view.visualRect(target).center(),
    )
    qtbot.waitUntil(
        lambda: window.view is not None and window.view.snapshot.current_name == "image-001.png",
        timeout=5000,
    )
    qtbot.keyClick(window.open_button, Qt.Key.Key_Right)
    qtbot.waitUntil(
        lambda: window.view is not None and window.view.snapshot.current_name == "image-002.png",
        timeout=5000,
    )

    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_ctrl_z_restores_move_and_updates_ui_without_playing_sound(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_language("en")
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (12, 8), "red").save(source / "IMG_1.png")
    Image.new("RGB", (12, 8), "blue").save(source / "IMG_2.png")
    runtime = create_runtime(tmp_path / "app-data")
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        sound_enabled=True,
        global_slot_template=(Slot("KeyZ", "trash", "#FF7B7B", SlotMode.MOVE),),
    )
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    played: list[bool] = []
    monkeypatch.setattr(window.sound_player, "play_added", lambda: played.append(True))
    window.show()
    window._open_folder(source)
    qtbot.waitUntil(
        lambda: window.view is not None and window.view.snapshot.current_name == "IMG_1.png",
        timeout=5000,
    )

    window._slot_pressed(0, "IMG_1.png")
    qtbot.waitUntil(
        lambda: (
            window.view is not None
            and window.view.snapshot.current_name == "IMG_2.png"
            and not window._slot_operation_pending
        ),
        timeout=8000,
    )
    assert played == [True]
    window.image_view.zoom_by(1.25)

    QTest.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)

    qtbot.waitUntil(
        lambda: (
            window.view is not None
            and window.view.snapshot.current_name == "IMG_1.png"
            and not window._slot_operation_pending
        ),
        timeout=8000,
    )
    assert window.view.snapshot.image_index == 1
    assert window.view.snapshot.image_count == 2
    assert window.progress_text.text() == "1 of 2"
    assert window.filename_label.toolTip() == "IMG_1.png"
    assert window.image_list.image_model.rowCount() == 2
    assert (source / "IMG_1.png").exists()
    assert not (source / "trash" / "IMG_1.png").exists()
    assert window.image_view.zoom_state.scale == 1.0
    assert window.image_view.zoom_state.offset == (0.0, 0.0)
    assert window.statusBar().currentMessage() == text("undo_success", name="IMG_1.png")
    assert played == [True]
    assert QApplication.activeModalWidget() is None
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_ctrl_z_conflict_shows_error_and_preserves_both_files(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    image = source / "IMG_1.png"
    Image.new("RGB", (12, 8), "green").save(image)
    original_data = image.read_bytes()
    runtime = create_runtime(tmp_path / "app-data")
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=(Slot("KeyZ", "trash", "#FF7B7B", SlotMode.MOVE),),
    )
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    played: list[bool] = []
    monkeypatch.setattr(window.sound_player, "play_added", lambda: played.append(True))
    window.show()
    window._open_folder(source)
    qtbot.waitUntil(lambda: window.view is not None, timeout=5000)
    window._slot_pressed(0, image.name)
    qtbot.waitUntil(
        lambda: (
            window.view is not None
            and window.view.snapshot.current_name is None
            and not window._slot_operation_pending
        ),
        timeout=8000,
    )
    destination = source / "trash" / image.name
    image.write_bytes(b"conflicting-original")
    errors: list[str] = []

    def dismiss_error() -> None:
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            errors.append(dialog.informativeText())
            dialog.accept()

    timer = QTimer(window)
    timer.setInterval(10)
    timer.timeout.connect(dismiss_error)
    timer.start()
    QTest.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(lambda: bool(errors), timeout=5000)
    timer.stop()

    assert errors[0]
    assert image.read_bytes() == b"conflicting-original"
    assert destination.read_bytes() == original_data
    assert played == [True]
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


@pytest.mark.parametrize(
    ("image_names", "moved_name", "expected_names", "expected_current", "expected_progress"),
    (
        (
            ("IMG_1.png", "IMG_2.png", "IMG_3.png"),
            "IMG_2.png",
            ("IMG_1.png", "IMG_3.png"),
            "IMG_3.png",
            "2 of 2",
        ),
        (("IMG_1.png", "IMG_2.png"), "IMG_2.png", ("IMG_1.png",), "IMG_1.png", "1 of 1"),
        (("IMG_1.png",), "IMG_1.png", (), None, "0 of 0"),
    ),
)
def test_move_slot_removes_image_and_refreshes_session_ui(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch,
    image_names: tuple[str, ...],
    moved_name: str,
    expected_names: tuple[str, ...],
    expected_current: str | None,
    expected_progress: str,
) -> None:
    set_language("en")
    source = tmp_path / "source"
    source.mkdir()
    for index, name in enumerate(image_names):
        Image.new("RGB", (12, 8), (index * 40, 80, 120)).save(source / name)
    runtime = create_runtime(tmp_path / "app-data")
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        sound_enabled=True,
        global_slot_template=(Slot("KeyW", "trash", "#FF7B7B", SlotMode.MOVE),),
    )
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    played: list[bool] = []
    monkeypatch.setattr(window.sound_player, "play_added", lambda: played.append(True))
    window.show()
    window._open_folder(source)
    qtbot.waitUntil(lambda: window.view is not None, timeout=5000)
    qtbot.waitUntil(
        lambda: window.image_list.image_model.rowCount() == len(image_names), timeout=5000
    )

    window._navigate_to_image(image_names.index(moved_name))
    qtbot.waitUntil(
        lambda: window.view is not None and window.view.snapshot.current_name == moved_name,
        timeout=5000,
    )
    QApplication.sendEvent(window, _slot_key())

    qtbot.waitUntil(
        lambda: (
            window.view is not None
            and window.view.snapshot.image_count == len(expected_names)
            and not window._slot_operation_pending
        ),
        timeout=8000,
    )

    assert window.view is not None
    assert set(window.view.snapshot.scan.images) == set(expected_names)
    assert window.view.snapshot.current_name == expected_current
    listed_names = tuple(
        window.image_list.image_model.data(window.image_list.image_model.index(index, 0))
        for index in range(window.image_list.image_model.rowCount())
    )
    assert listed_names == expected_names
    assert window.image_list.image_model.rowCount() == len(expected_names)
    assert window.progress_text.text() == expected_progress
    assert window.filename_label.toolTip() == (expected_current or "")
    assert (source / moved_name).exists() is False
    assert (source / "trash" / moved_name).exists()
    assert QApplication.activeModalWidget() is None
    assert played == [True]
    assert window.statusBar().currentMessage() == text("move_success", key="W", name="trash")
    assert "#FF7B7B" in window.statusBar().styleSheet()
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)
