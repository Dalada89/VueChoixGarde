from pathlib import Path
from threading import Event
from time import sleep

from PIL import Image
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLineEdit, QMessageBox
from pytestqt.qtbot import QtBot

from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.ui.main_window import MainWindow


def _slot_key(*, auto_repeat: bool = False) -> QKeyEvent:
    return QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_W,
        Qt.KeyboardModifier.NoModifier,
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
    qtbot.waitUntil(
        lambda: (
            window.image_label.pixmap() is not None and not window.image_label.pixmap().isNull()
        ),
        timeout=5000,
    )
    assert window.filename_label.toolTip() == "IMG_1.png"
    assert window.progress_text.text() == "1 of 2"

    qtbot.keyClick(window, Qt.Key.Key_Right)
    qtbot.waitUntil(
        lambda: window.view is not None and window.view.snapshot.current_name == "IMG_2.png",
        timeout=5000,
    )
    qtbot.keyClick(window, Qt.Key.Key_Right)
    qtbot.waitUntil(lambda: "end of the image list" in window.statusBar().currentMessage())

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
        lambda: window.image_label.text() == "This image is damaged or cannot be decoded.",
        timeout=5000,
    )
    assert window.filename_label.toolTip() == "broken.jpg"
    assert window.progress_text.text() == "1 of 1"
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
