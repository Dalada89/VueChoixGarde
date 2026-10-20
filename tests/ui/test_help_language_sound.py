import logging
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QWidget
from pytestqt.qtbot import QtBot

from vuechoixgarde.app.results import UseCaseStatus
from vuechoixgarde.app.service import SessionView
from vuechoixgarde.app.toggle import TogglePlan, ToggleResult
from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.slots import DEFAULT_SLOTS
from vuechoixgarde.ui.help_dialog import HelpDialog
from vuechoixgarde.ui.keyboard import main_window_key_filter_enabled
from vuechoixgarde.ui.main_window import MainWindow
from vuechoixgarde.ui.sound import SoundPlayer
from vuechoixgarde.ui.texts import set_language, text


class FakeEffect(QObject):
    statusChanged = Signal()  # noqa: N815

    def __init__(self, _parent: QWidget) -> None:
        super().__init__()
        self.current_status = QSoundEffect.Status.Ready
        self.play_count = 0

    def setSource(self, source: QUrl) -> None:  # noqa: N802
        _ = source

    def setVolume(self, volume: float) -> None:  # noqa: N802
        _ = volume

    def play(self) -> None:
        self.play_count += 1

    def status(self) -> QSoundEffect.Status:
        return self.current_status


def test_help_dialog_has_close_button_and_real_shortcut_lines(qtbot: QtBot) -> None:
    set_language("en")
    dialog = HelpDialog(None)
    qtbot.addWidget(dialog)

    assert "\\n" not in text("help_shortcuts")
    assert "\n" in text("help_shortcuts")
    close_button = dialog.findChild(QPushButton)
    assert close_button is not None
    assert close_button.text() == "Close"


def test_non_us_keyboard_help_is_translated_in_all_languages(qtbot: QtBot) -> None:
    expected = {
        "en": "non-US layouts",
        "de": "Nicht-US-Tastaturlayouts",
        "fr": "disposition non américaine",
    }
    for language, hint in expected.items():
        set_language(language)
        dialog = HelpDialog(None)
        qtbot.addWidget(dialog)
        assert any(hint in label.text() for label in dialog.findChildren(QLabel))
        dialog.close()
    set_language("en")


def test_f1_opens_help_and_shortcut_guard_disables_under_modal(
    qtbot: QtBot, tmp_path: Path
) -> None:
    set_language("en")
    window = MainWindow(create_runtime(tmp_path / "app-data"))
    qtbot.addWidget(window)
    window.show()

    observed: list[bool] = []

    def close_help() -> None:
        dialog = QApplication.activeModalWidget()
        observed.append(isinstance(dialog, HelpDialog) and not main_window_key_filter_enabled())
        if isinstance(dialog, QDialog):
            dialog.reject()

    QTimer.singleShot(100, close_help)
    qtbot.keyClick(window, Qt.Key.Key_F1)
    assert observed == [True]
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is None)
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_language_retranslation_works_without_open_folder(qtbot: QtBot, tmp_path: Path) -> None:
    runtime = create_runtime(tmp_path / "app-data")
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    set_language("de")
    window._retranslate()
    assert window.open_button.text() == "Ordner öffnen…"
    assert window.image_label.text() == text("empty")
    assert window.profile_label.text() == text("empty")

    set_language("fr")
    window._retranslate()
    assert window.open_button.text() == "Ouvrir un dossier…"
    assert window.filename_label.text() == text("filename")

    set_language("en")
    window._retranslate()
    assert window.open_button.text() == "Open folder…"
    assert window.progress_text.text() == "0 of 0"
    window.close()


def test_sound_player_plays_and_logs_backend_error_once(qtbot: QtBot, caplog) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)
    player = SoundPlayer(parent, FakeEffect)
    effect = cast(FakeEffect, player.effect)

    player.play_added()
    assert effect.play_count == 1

    with caplog.at_level(logging.WARNING, logger="vuechoixgarde.ui.sound"):
        effect.current_status = QSoundEffect.Status.Error
        effect.statusChanged.emit()
        player.play_added()
        effect.statusChanged.emit()

    warnings = [
        record for record in caplog.records if "audio feedback unavailable" in record.message
    ]
    assert len(warnings) == 1


@pytest.mark.parametrize(
    ("sound_enabled", "action", "expected_calls"),
    ((True, "toggle_on", 1), (False, "toggle_on", 0), (True, "toggle_off", 0)),
)
def test_sound_only_plays_after_successful_added_toggle(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sound_enabled: bool,
    action: str,
    expected_calls: int,
) -> None:
    set_language("en")
    window = MainWindow(create_runtime(tmp_path / "app-data"))
    qtbot.addWidget(window)

    class RecordingSound:
        calls = 0

        def play_added(self) -> None:
            self.calls += 1

    sound = RecordingSound()
    monkeypatch.setattr(window, "_apply_view", lambda _view: None)
    monkeypatch.setattr(window, "sound_player", sound)
    view = SimpleNamespace(
        snapshot=SimpleNamespace(profile=SimpleNamespace(slots=(DEFAULT_SLOTS[0],))),
        settings=SimpleNamespace(learned_key_labels=(), sound_enabled=sound_enabled),
    )
    result = SimpleNamespace(
        status=UseCaseStatus.OK,
        action=SimpleNamespace(value=action),
        conflict_names=(),
        error_reason=None,
    )

    window._handle_toggle_result(
        (cast(ToggleResult, result), cast(SessionView, view)),
        cast(TogglePlan, SimpleNamespace(slot_index=0)),
    )

    assert sound.calls == expected_calls
    window.close()
