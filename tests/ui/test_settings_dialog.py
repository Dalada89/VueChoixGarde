from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox
from pytestqt.qtbot import QtBot

from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.slots import Slot
from vuechoixgarde.ui.settings_dialog import SettingsDialog


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
    saved: list[tuple[bool, str, str, tuple[Slot, ...], tuple[tuple[str, str], ...]]] = []

    def capture_save(
        reopen: bool,
        direction: str,
        target: str,
        slots: tuple[Slot, ...],
        labels: tuple[tuple[str, str], ...],
    ) -> None:
        saved.append((reopen, direction, target, slots, labels))

    dialog.on_save = capture_save
    dialog._save()
    assert saved
    assert saved[0][3][0].key_position == "KeyQ"
    assert ("KeyQ", "Q") in saved[0][4]
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


def test_profile_delete_confirmation_defaults_to_cancel(
    qtbot: QtBot, tmp_path: Path, monkeypatch
) -> None:
    runtime, dialog = _dialog(tmp_path)
    qtbot.addWidget(dialog)
    dialog.profile_table.selectRow(0)
    observed: list[bool] = []

    def cancel_by_default(box: QMessageBox) -> QMessageBox.StandardButton:
        observed.append(box.defaultButton() is box.button(QMessageBox.StandardButton.Cancel))
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "exec", cancel_by_default)
    dialog._profile_action("delete_profile")

    assert observed == [True]
    assert dialog.profile_table.rowCount() == 1
    dialog.reject()
    runtime.shutdown()
