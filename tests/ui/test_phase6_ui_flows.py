from pathlib import Path

from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox
from pytestqt.qtbot import QtBot

from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.slots import Slot, SlotMode
from vuechoixgarde.ui.main_window import MainWindow
from vuechoixgarde.ui.settings_dialog import SettingsDialog


def test_busy_slot_press_is_ignored_with_feedback(qtbot: QtBot, tmp_path: Path) -> None:
    runtime = create_runtime(tmp_path / "application-data")
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()
    window._slot_operation_pending = True

    window._slot_pressed(0, "image.png")

    assert window.statusBar().currentMessage() == "Busy — slot action ignored"
    window._slot_operation_pending = False
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_conflict_result_names_foreign_destination_file(qtbot: QtBot, tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = source / "Sorted"
    destination.mkdir(parents=True)
    image_path = source / "one.png"
    Image.new("RGB", (8, 8), "red").save(image_path)
    (destination / image_path.name).write_bytes(b"foreign file")
    runtime = create_runtime(tmp_path / "application-data")
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=(Slot("KeyW", "Sorted", "#4488CC"),),
    )
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()
    window._open_folder(source)
    qtbot.waitUntil(lambda: window.view is not None, timeout=5000)
    observed: list[str] = []

    def close_conflict() -> None:
        dialog = QApplication.activeModalWidget()
        if not isinstance(dialog, QMessageBox) or dialog.windowTitle() != "File conflict":
            return
        observed.append(dialog.informativeText())
        dialog.accept()

    timer = QTimer(window)
    timer.setInterval(10)
    timer.timeout.connect(close_conflict)
    timer.start()
    window._run_file(
        lambda: runtime.service.plan_slot(image_path.name, 0),
        lambda plan, _error: window._handle_plan(plan, image_path.name, 0),
    )
    qtbot.waitUntil(lambda: bool(observed), timeout=5000)
    timer.stop()

    assert image_path.name in observed[0]
    assert (destination / image_path.name).read_bytes() == b"foreign file"
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_blocked_mode_change_keeps_settings_dialog_open_and_names_folder(
    qtbot: QtBot, tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    image = source / "photo.png"
    Image.new("RGB", (8, 8), "blue").save(image)
    runtime = create_runtime(tmp_path / "application-data")
    slot = Slot("KeyW", "Archive", "#4488CC")
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=(slot,),
    )
    try:
        runtime.service.open_folder(source)
        plan = runtime.service.plan_slot(image.name, 0)
        _, view = runtime.service.execute_plan(plan, confirmed_modified=False)
        window = MainWindow(runtime)
        qtbot.addWidget(window)
        window._apply_view(view)
        observed: dict[str, str | bool] = {}

        def run_file(function, callback=None) -> None:
            try:
                result = function()
                error = None
            except Exception as caught:
                result = None
                error = caught
            if callback is not None:
                callback(result, error)

        def enter_settings(dialog: SettingsDialog) -> int:
            qtbot.addWidget(dialog)
            dialog.show()
            mode = dialog.slot_editors["profile"].mode_controls[0]
            mode.setCurrentIndex(mode.findData(SlotMode.MOVE.value))
            dialog._save()
            observed["visible"] = dialog.isVisible()
            observed["message"] = dialog.message.text()
            dialog.reject()
            return 0

        monkeypatch.setattr(window, "_run_file", run_file)
        monkeypatch.setattr(SettingsDialog, "exec", enter_settings)

        window._show_settings(runtime.service.profile_catalog(), None)

        assert observed["visible"] is True
        assert "Archive" in str(observed["message"])
        window.close()
    finally:
        runtime.shutdown()
