"""Best-effort quiet feedback for successful toggle-on operations."""

import logging
from collections.abc import Callable
from importlib.resources import as_file, files
from typing import Protocol, cast

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import QWidget


class SoundSignal(Protocol):
    """Minimal signal interface for status notifications."""

    def connect(self, callback: Callable[[], None]) -> None: ...


class SoundEffect(Protocol):
    """Minimal Qt sound-effect surface used by the player and its tests."""

    def setSource(self, source: QUrl) -> None: ...  # noqa: N802

    def setVolume(self, volume: float) -> None: ...  # noqa: N802

    def play(self) -> None: ...

    def status(self) -> QSoundEffect.Status: ...

    statusChanged: SoundSignal  # noqa: N815


class SoundPlayer:
    """Play a bundled sound without allowing audio failures to affect file operations."""

    def __init__(
        self,
        parent: QWidget,
        effect_factory: Callable[[QWidget], object] = QSoundEffect,
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self._logged_error = False
        self._resource = as_file(
            files("vuechoixgarde").joinpath("resources", "sounds", "added.wav")
        )
        resource_path = self._resource.__enter__()
        self.effect = cast(SoundEffect, effect_factory(parent))
        self.effect.setSource(QUrl.fromLocalFile(str(resource_path)))
        self.effect.setVolume(0.4)
        self.effect.statusChanged.connect(self._status_changed)  # type: ignore[attr-defined]

    def play_added(self) -> None:
        """Play the subtle added cue when the audio backend is available."""
        try:
            self.effect.play()
            self._check_status()
        except Exception as error:
            self._log_error(error)

    def _status_changed(self) -> None:
        self._check_status()

    def _check_status(self) -> None:
        try:
            if self.effect.status() == QSoundEffect.Status.Error:
                self._log_error()
        except Exception as error:
            self._log_error(error)

    def _log_error(self, error: BaseException | None = None) -> None:
        if self._logged_error:
            return
        self._logged_error = True
        self._logger.warning(
            "audio feedback unavailable%s",
            f" ({type(error).__name__})" if error is not None else "",
        )
