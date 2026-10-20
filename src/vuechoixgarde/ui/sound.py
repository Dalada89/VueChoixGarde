"""Best-effort quiet feedback for successful toggle-on operations."""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import QWidget


class SoundPlayer:
    """Play a bundled sound without allowing audio failures to affect file operations."""

    def __init__(self, parent: QWidget) -> None:
        self.effect = QSoundEffect(parent)
        self.effect.setSource(
            QUrl.fromLocalFile(
                str(Path(__file__).parents[1] / "resources" / "sounds" / "added.wav")
            )
        )
        self.effect.setVolume(0.4)

    def play_added(self) -> None:
        """Play the subtle added cue when the audio backend is available."""
        try:
            self.effect.play()
        except Exception:
            return
