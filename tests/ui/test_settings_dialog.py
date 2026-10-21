from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import QApplication, QColorDialog, QLabel
from pytestqt.qtbot import QtBot

from vuechoixgarde.app.results import FolderRename
from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.slots import Slot
from vuechoixgarde.ui.settings_dialog import SettingsDialog, SettingsSubmission


def _dialog(tmp_path: Path, *, read_only: bool = False):
    runtime = create_runtime(tmp_path / "application-data")
    source = tmp_path / "source"
    source.mkdir()
    view = runtime.service.open_folder(source)
    dialog = SettingsDialog(
        runtime.service.settings,
        view.snapshot.profile,
        runtime.service.profile_catalog(),
        runtime.log_directory,
        read_only=read_only,
        on_save=lambda *_args: None,
        on_profile_action=lambda *_args: None,
    )
    return runtime, dialog


def test_slot_editor_live_validation_blocks_duplicate_names_and_keys(
    qtbot: QtBot, tmp_path: Path
) -> None:
    runtime, dialog = _dialog(tmp_path)
    qtbot.addWidget(dialog)

    assert dialog.save_button is not None and dialog.save_button.isEnabled()
    first = dialog.slot_editor.rows[0]
    second = dialog.slot_editor.rows[1]
    first[1].setText("Favorites")
    second[1].setText("favorites")

    assert dialog.save_button is not None and not dialog.save_button.isEnabled()
    assert "destination name" in first[3].text().lower()
    assert "destination name" in second[3].text().lower()
    dialog.reject()
    runtime.shutdown()


def test_key_capture_uses_physical_position_and_persists_learned_label(
    qtbot: QtBot, tmp_path: Path
) -> None:
    runtime, dialog = _dialog(tmp_path)
    qtbot.addWidget(dialog)
    button = dialog.slot_editor.rows[0][0]
    button.start_capture()
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Q,
        Qt.KeyboardModifier.NoModifier,
        24,
        0,
        0,
        "q",
        False,
        1,
    )

    QApplication.sendEvent(button, event)

    assert button.position == "KeyQ"
    assert button.text() == "Q"
    saved: list[SettingsSubmission] = []

    def capture_save(submission: SettingsSubmission) -> None:
        saved.append(submission)

    dialog.on_save = capture_save
    dialog._save()
    assert saved
    assert saved[0].global_slot_template[0].key_position == "KeyQ"
    assert ("KeyQ", "Q") in saved[0].learned_key_labels
    assert saved[0].language == runtime.service.settings.language
    assert saved[0].sound_enabled == runtime.service.settings.sound_enabled
    dialog.reject()
    runtime.shutdown()


def test_slot_color_swatch_renders_configured_color(qtbot: QtBot, tmp_path: Path) -> None:
    runtime, dialog = _dialog(tmp_path)
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()

    sample = dialog.findChild(QLabel, "colorSample")
    assert sample is not None
    rendered = sample.grab().toImage().pixelColor(sample.width() // 2, sample.height() // 2).name()
    assert rendered == dialog.slot_editor.rows[0][2].property("slotColor").lower()
    dialog.reject()
    runtime.shutdown()


def test_damaged_data_read_only_mode_disables_editing(qtbot: QtBot, tmp_path: Path) -> None:
    runtime, dialog = _dialog(tmp_path, read_only=True)
    qtbot.addWidget(dialog)

    assert dialog.save_button is not None and not dialog.save_button.isEnabled()
    assert not dialog.slot_editor.add_button.isEnabled()
    assert not dialog.slot_editor.remove_button.isEnabled()
    assert dialog.slot_editor.rows[0][1].isReadOnly()
    assert all(not button.isEnabled() for button in dialog.action_buttons.values())
    dialog.reject()
    runtime.shutdown()


def test_key_capture_conflict_updates_validation_immediately_and_escape_cancels(
    qtbot: QtBot, tmp_path: Path
) -> None:
    runtime, dialog = _dialog(tmp_path)
    qtbot.addWidget(dialog)
    dialog.show()
    first = dialog.slot_editor.rows[0][0]
    second = dialog.slot_editor.rows[1][0]
    first.position = "KeyW"
    second.start_capture()
    conflict = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_W,
        Qt.KeyboardModifier.NoModifier,
        25,
        0,
        0,
        "w",
        False,
        1,
    )
    QApplication.sendEvent(second, conflict)
    assert dialog.save_button is not None and not dialog.save_button.isEnabled()

    second.start_capture()
    escape = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Escape,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(second, escape)
    assert not second.capturing
    assert dialog.isVisible()
    dialog.reject()
    runtime.shutdown()


def test_color_swatch_updates_after_picker_selection(
    qtbot: QtBot, tmp_path: Path, monkeypatch
) -> None:
    runtime, dialog = _dialog(tmp_path)
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    button = dialog.slot_editor.rows[0][2]
    sample = dialog.findChild(QLabel, "colorSample")
    assert sample is not None
    monkeypatch.setattr(QColorDialog, "getColor", lambda **_kwargs: QColor("#AA33CC"))
    dialog.slot_editor._choose_color(button, sample)
    QApplication.processEvents()
    rendered = sample.grab().toImage().pixelColor(sample.width() // 2, sample.height() // 2).name()
    assert rendered == "#aa33cc"
    dialog.reject()
    runtime.shutdown()


def test_submission_captures_profile_rename_and_delete_button_state(
    qtbot: QtBot, tmp_path: Path
) -> None:
    runtime = create_runtime(tmp_path / "application-data")
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=(Slot("KeyW", "Saved", "#4488CC"),),
    )
    source = tmp_path / "source"
    source.mkdir()
    view = runtime.service.open_folder(source)
    captured: list[SettingsSubmission] = []
    dialog = SettingsDialog(
        runtime.service.settings,
        view.snapshot.profile,
        runtime.service.profile_catalog(),
        runtime.log_directory,
        read_only=False,
        on_save=captured.append,
        on_profile_action=lambda *_args: None,
        on_delete_request=lambda _index: None,
    )
    qtbot.addWidget(dialog)
    editor = dialog.slot_editors["profile"]
    name = editor.rows[0][1]
    delete_button = editor.delete_controls[0][1]
    assert delete_button.isEnabled()

    name.setText("Renamed")
    assert not delete_button.isEnabled()
    dialog._save()

    assert captured[0].renames == (FolderRename("Saved", "Renamed"),)
    assert captured[0].profile_slots == (Slot("KeyW", "Renamed", "#4488CC"),)
    dialog.set_busy(False)
    name.setText("Saved")
    assert delete_button.isEnabled()
    dialog.reject()
    runtime.shutdown()


def test_active_profile_delete_is_disabled(qtbot: QtBot, tmp_path: Path) -> None:
    runtime, dialog = _dialog(tmp_path)
    qtbot.addWidget(dialog)
    dialog.profile_table.selectRow(0)

    assert not dialog.action_buttons["delete_profile"].isEnabled()
    dialog._profile_action("delete_profile")

    assert dialog.profile_table.rowCount() == 1
    dialog.reject()
    runtime.shutdown()
