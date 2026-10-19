"""Composition root for local adapters, startup recovery and the Qt main window."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from vuechoixgarde.app.keys import learn_key_label
from vuechoixgarde.app.results import SessionSnapshot, SlotState, UseCaseStatus
from vuechoixgarde.app.session import FolderSession
from vuechoixgarde.app.startup import (
    accept_damaged_data,
    decline_damaged_data,
    load_startup,
    stop_application,
)
from vuechoixgarde.app.toggle import TogglePlan, ToggleResult, execute_toggle, plan_toggle
from vuechoixgarde.core.navigation import NavigationDirection
from vuechoixgarde.fsops.clock import SystemClock
from vuechoixgarde.fsops.filesystem import LocalFileSystem
from vuechoixgarde.fsops.lock import LocalFolderLockFactory
from vuechoixgarde.ports.imaging import ImageDecoder
from vuechoixgarde.ports.log import EventLogger, LogEvent, LogLevel
from vuechoixgarde.ports.models import Settings
from vuechoixgarde.store.paths import application_data_dir, prepare_application_data
from vuechoixgarde.store.settings import JsonSettingsStore
from vuechoixgarde.store.state import SQLiteStateStore
from vuechoixgarde.ui.texts import text


@dataclass(frozen=True)
class SessionView:
    """Immutable presentation data returned after serialized session operations."""

    snapshot: SessionSnapshot
    slot_states: tuple[SlotState, ...]
    selected_image_count: int
    settings: Settings


class SessionService:
    """Own a FolderSession; call every method only on the single file-operation worker."""

    def __init__(
        self,
        scanner: LocalFileSystem,
        filesystem: LocalFileSystem,
        state_store: SQLiteStateStore,
        settings_store: JsonSettingsStore,
        lock_factory: LocalFolderLockFactory,
        settings: Settings,
        register_available: bool,
        settings_writable: bool,
        clock: SystemClock,
        logger: EventLogger,
    ) -> None:
        self.scanner = scanner
        self.filesystem = filesystem
        self.state_store = state_store
        self.settings_store = settings_store
        self.lock_factory = lock_factory
        self.settings = settings
        self.register_available = register_available
        self.settings_writable = settings_writable
        self.clock = clock
        self.logger = logger
        self.session: FolderSession | None = None

    def open_folder(self, path: Path) -> SessionView:
        """Open and lock a folder, replacing the prior session only after success."""
        if self.session is not None and self.session.source_path == path.resolve():
            return self._view()
        replacement = FolderSession.open(
            path,
            self.scanner,
            self.filesystem,
            self.state_store,
            self.settings_store,
            self.settings,
            self.lock_factory,
            register_available=self.register_available,
            logger=self.logger,
        )
        previous = self.session
        self.session = replacement
        if previous is not None:
            previous.close()
        if self.settings_writable:
            updated = Settings(
                self.settings.schema_version,
                self.settings.language,
                self.settings.sound_enabled,
                self.settings.sort_direction,
                self.settings.reopen_last_folder,
                str(replacement.source_path),
                self.settings.global_slot_template,
                self.settings.learned_key_labels,
            )
            try:
                self.settings_store.save(updated)
            except Exception:
                pass
            else:
                self.settings = updated
                self.session.settings = updated
        return self._view()

    def navigate(self, direction: NavigationDirection) -> SessionView:
        self._require_session().navigate(direction)
        return self._view()

    def refresh(self) -> SessionView:
        self._require_session().refresh()
        return self._view()

    def set_sort_direction(self, descending: bool) -> SessionView:
        self._require_session().set_sort_direction(descending=descending)
        self.settings = self._require_session().settings
        return self._view()

    def reconcile(self) -> SessionView:
        session = self._require_session()
        if not session.reconcile(automatic=False):
            raise RuntimeError("another file operation is in progress")
        return self._view()

    def plan_slot(self, image_name: str, slot_index: int) -> TogglePlan:
        session = self._require_session()
        return plan_toggle(
            session.profile,
            session.source_path,
            image_name,
            slot_index,
            self.scanner,
            self.filesystem,
            self.state_store,
            register_available=self.register_available,
        )

    def name_slot_and_plan(self, image_name: str, slot_index: int, name: str) -> TogglePlan:
        session = self._require_session()
        session.set_destination_name(slot_index, name)
        return self.plan_slot(image_name, slot_index)

    def execute_plan(
        self, plan: TogglePlan, *, confirmed_modified: bool
    ) -> tuple[ToggleResult, SessionView]:
        session = self._require_session()
        result = execute_toggle(
            plan,
            session.profile,
            self.scanner,
            self.filesystem,
            self.state_store,
            self.clock,
            session.gate,
            confirmed_modified=confirmed_modified,
            register_available=self.register_available,
            logger=self.logger,
        )
        if result.status is UseCaseStatus.MODIFIED_CONFIRMATION_REQUIRED:
            session.reconcile(automatic=False)
        return result, self._view()

    def learn_key(self, position: str, value: str, *, modifier_active: bool) -> None:
        if not self.settings_writable:
            return
        self.settings = learn_key_label(
            self.settings,
            self.settings_store,
            position,
            value,
            modifier_active=modifier_active,
        )
        if self.session is not None:
            self.session.settings = self.settings

    def close(self) -> None:
        session, self.session = self.session, None
        if session is not None:
            session.close()

    def _require_session(self) -> FolderSession:
        if self.session is None:
            raise RuntimeError("no source folder is open")
        return self.session

    def _view(self) -> SessionView:
        session = self._require_session()
        snapshot = session.snapshot()
        states = session.slot_states()
        selected = 0
        if self.register_available:
            try:
                selected_names = {
                    record.source_name
                    for record in self.state_store.copy_records(session.profile.id)
                    if record.source_name in session.scan.images
                }
                selected = len(selected_names)
            except Exception:
                selected = 0
        return SessionView(snapshot, states, selected, self.settings)


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
) -> Runtime:
    """Build the concrete local application graph and explicitly resolve damaged data."""
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
            accepted = _ask_damaged_data()
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
    )


def _create_logger(root: Path, clock: SystemClock) -> EventLogger:
    from vuechoixgarde.applog.jsonl import JsonlEventLogger

    return JsonlEventLogger(root / "logs", clock=clock)


def _ask_damaged_data() -> bool:
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
