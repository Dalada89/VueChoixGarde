"""Composition root for local adapters, startup recovery and the Qt main window."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from vuechoixgarde.app.service import SessionService
from vuechoixgarde.app.startup import (
    accept_damaged_data,
    decline_damaged_data,
    load_startup,
    stop_application,
)
from vuechoixgarde.fsops.clock import SystemClock
from vuechoixgarde.fsops.filesystem import LocalFileSystem
from vuechoixgarde.fsops.lock import LocalFolderLockFactory
from vuechoixgarde.ports.imaging import ImageDecoder
from vuechoixgarde.ports.log import EventLogger, LogEvent, LogLevel
from vuechoixgarde.ports.models import Settings
from vuechoixgarde.store.paths import application_data_dir, prepare_application_data
from vuechoixgarde.store.settings import JsonSettingsStore
from vuechoixgarde.store.state import SQLiteStateStore


@dataclass(frozen=True)
class Runtime:
    """All composed runtime services required by the user interface."""

    service: SessionService
    scanner: LocalFileSystem
    filesystem: LocalFileSystem
    decoder: ImageDecoder
    logger: EventLogger
    settings: Settings
    register_available: bool
    settings_writable: bool
    log_directory: Path

    def shutdown(self) -> None:
        """Release session lock and write the final application event."""
        self.service.close()
        stop_application(self.logger)
        close = getattr(self.logger, "close", None)
        if callable(close):
            close()


def create_runtime(
    data_dir: Path | None = None,
    *,
    locale_name: str | None = None,
    damaged_choice: bool | None = None,
    damaged_prompt: Callable[[], bool] | None = None,
) -> Runtime:
    """Build the local application graph and resolve damaged data through a callback."""
    from vuechoixgarde.imaging.decoder import PillowImageDecoder

    root = application_data_dir(data_dir)
    prepare_application_data(root)
    clock = SystemClock()
    logger = _create_logger(root, clock)
    settings_store = JsonSettingsStore(root, clock)
    state_store = SQLiteStateStore(root, clock)
    report = load_startup(settings_store, state_store, locale_name=locale_name, logger=logger)
    damaged = report.settings_damaged or report.state_damaged
    if damaged:
        accepted = damaged_choice
        if accepted is None:
            accepted = damaged_prompt() if damaged_prompt is not None else _ask_damaged_data()
        if accepted:
            report = accept_damaged_data(
                report,
                settings_store,
                state_store,
                locale_name=locale_name,
                logger=logger,
            )
        else:
            report = decline_damaged_data(report)
        logger.log(
            LogLevel.INFO,
            LogEvent.APP_START,
            "application started after damaged-data decision",
            settings_damaged=report.settings_damaged,
            state_damaged=report.state_damaged,
            register_available=report.register_available,
        )
    settings = report.settings or settings_store.defaults(locale_name)
    settings_writable = not report.settings_damaged
    scanner = LocalFileSystem()
    filesystem = scanner
    lock_factory = LocalFolderLockFactory(root)
    service = SessionService(
        scanner,
        filesystem,
        state_store,
        settings_store,
        lock_factory,
        settings,
        report.register_available,
        settings_writable,
        clock,
        logger,
    )
    return Runtime(
        service,
        scanner,
        filesystem,
        PillowImageDecoder(),
        logger,
        settings,
        report.register_available,
        settings_writable,
        root / "logs",
    )


def _create_logger(root: Path, clock: SystemClock) -> EventLogger:
    from vuechoixgarde.applog.jsonl import JsonlEventLogger

    return JsonlEventLogger(root / "logs", clock=clock)


def _ask_damaged_data() -> bool:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from vuechoixgarde.ui.texts import text

    if QApplication.instance() is None:
        return False
    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(text("damaged_title"))
    box.setText(text("damaged_prompt"))
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    defaults = box.button(QMessageBox.StandardButton.Yes)
    view_only = box.button(QMessageBox.StandardButton.No)
    if defaults is None or view_only is None:
        return False
    defaults.setText(text("defaults"))
    view_only.setText(text("view_only"))
    box.setDefaultButton(QMessageBox.StandardButton.No)
    box.exec()
    return box.clickedButton() is defaults
