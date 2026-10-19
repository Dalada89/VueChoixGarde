"""Qt-free session orchestration and settings/profile use cases."""

from dataclasses import dataclass
from pathlib import Path

from vuechoixgarde.app.keys import learn_key_label
from vuechoixgarde.app.recovery import recover_operations
from vuechoixgarde.app.results import SessionSnapshot, SlotState, UseCaseStatus
from vuechoixgarde.app.session import FolderSession
from vuechoixgarde.app.toggle import TogglePlan, ToggleResult, execute_toggle, plan_toggle
from vuechoixgarde.core.comparison import comparison_key
from vuechoixgarde.core.navigation import NavigationDirection, change_sort_direction
from vuechoixgarde.core.slots import DEFAULT_SLOTS, Slot
from vuechoixgarde.ports.clock import Clock
from vuechoixgarde.ports.filesystem import FileSystemPort, SourceFolderScanner
from vuechoixgarde.ports.lock import FolderLockFactory
from vuechoixgarde.ports.log import EventLogger, LogEvent, LogLevel
from vuechoixgarde.ports.models import ProfileRecord, Settings
from vuechoixgarde.ports.settings import SettingsStore
from vuechoixgarde.ports.state import StateStore


@dataclass(frozen=True)
class ProfileSummary:
    """Profile information with a worker-computed source-folder existence flag."""

    profile: ProfileRecord
    folder_exists: bool


@dataclass(frozen=True)
class SessionView:
    """Immutable lightweight presentation data returned after session operations."""

    snapshot: SessionSnapshot
    slot_states: tuple[SlotState, ...]
    selected_image_count: int
    settings: Settings
    generation: int = 0
    warning: str | None = None


@dataclass(frozen=True)
class SlotStatusResult:
    """Asynchronous slot-status response tagged to the image and view generation."""

    image_name: str | None
    generation: int
    slot_states: tuple[SlotState, ...]
    selected_image_count: int
    warning: str | None = None


class SessionService:
    """Own a FolderSession; call every method only on the single file-operation worker."""

    def __init__(
        self,
        scanner: SourceFolderScanner,
        filesystem: FileSystemPort,
        state_store: StateStore,
        settings_store: SettingsStore,
        lock_factory: FolderLockFactory,
        settings: Settings,
        register_available: bool,
        settings_writable: bool,
        clock: Clock,
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
        self._view_generation = 0
        self.warning: str | None = None

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
        self.warning = None
        if self.settings_writable:
            updated = _settings_with(
                self.settings,
                last_folder=str(replacement.source_path),
            )
            try:
                self.settings_store.save(updated)
            except Exception:
                self.warning = "settings_save_failed"
                self._log_warning("last-folder setting could not be saved")
            else:
                self.settings = updated
                self.session.settings = updated
        return self._view()

    def navigate(self, direction: NavigationDirection) -> SessionView:
        self._require_session().navigate(direction)
        return self._view()

    def navigate_batch(self, directions: tuple[NavigationDirection, ...]) -> SessionView:
        """Apply a coalesced set of pending navigation keys before building one view."""
        session = self._require_session()
        for direction in directions:
            session.navigate(direction)
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

    def learn_key(self, position: str, value: str, *, modifier_active: bool) -> SessionView | None:
        """Persist a newly learned key label and say whether visible slot labels changed."""
        if not self.settings_writable:
            return None
        previous = self.settings.learned_key_labels
        updated = learn_key_label(
            self.settings,
            self.settings_store,
            position,
            value,
            modifier_active=modifier_active,
        )
        changed = updated.learned_key_labels != previous
        self.settings = updated
        if self.session is not None:
            self.session.settings = self.settings
        return self._view() if changed and self.session is not None else None

    def current_view(self) -> SessionView | None:
        """Return a cheap view of the current folder, if one is open."""
        return self._view() if self.session is not None else None

    def slot_status(self, image_name: str | None, generation: int) -> SlotStatusResult:
        """Compute potentially expensive slot status and selection count on the file worker."""
        session = self._require_session()
        if generation != self._view_generation or session.navigation.current != image_name:
            return SlotStatusResult(image_name, generation, (), 0)
        warning: str | None = None
        try:
            states = session.slot_states(image_name)
            if session.slot_status_warning:
                warning = "slot_status_failed"
        except Exception:
            states = tuple(SlotState.FAULTY for _ in session.profile.slots)
            warning = "slot_status_failed"
            self._log_warning("slot state lookup failed")
        selected = 0
        if self.register_available:
            try:
                records = self.state_store.copy_records(session.profile.id)
                selected_names = {
                    record.source_name
                    for record in records
                    if record.source_name in session.scan.images
                }
                selected = len(selected_names)
                configured = {
                    comparison_key(slot.destination_name)
                    for slot in session.profile.slots
                    if slot.destination_name is not None
                }
                renamed = any(
                    Path(record.destination_folder).parent == session.source_path
                    and Path(record.destination_folder).name in session.scan.directories
                    and comparison_key(Path(record.destination_folder).name) not in configured
                    for record in records
                )
                if renamed and warning is None:
                    warning = "destination_renamed"
            except Exception:
                warning = "selection_count_failed"
                self._log_warning("selected-image count could not be loaded")
        return SlotStatusResult(image_name, generation, states, selected, warning)

    def save_preferences(
        self,
        *,
        reopen_last_folder: bool,
        sort_direction: str,
        global_slot_template: tuple[Slot, ...] | None = None,
        learned_key_labels: tuple[tuple[str, str], ...] | None = None,
    ) -> Settings:
        """Persist preferences before updating the active in-memory settings/session."""
        if not self.settings_writable:
            raise RuntimeError("settings are read-only because damaged data was declined")
        if sort_direction not in {"asc", "desc"}:
            raise ValueError("sort direction must be asc or desc")
        updated = _settings_with(
            self.settings,
            reopen_last_folder=reopen_last_folder,
            sort_direction=sort_direction,
            global_slot_template=(
                global_slot_template
                if global_slot_template is not None
                else self.settings.global_slot_template
            ),
            learned_key_labels=learned_key_labels,
        )
        self.settings_store.save(updated)
        self.settings = updated
        if self.session is not None:
            session = self.session
            if session.navigation.descending != (sort_direction == "desc"):
                session.navigation = change_sort_direction(
                    session.navigation, descending=sort_direction == "desc"
                )
                session.boundary_reached = False
            session.settings = updated
        return updated

    def save_profile_slots(self, slots: tuple[Slot, ...]) -> SessionView:
        """Save profile slots atomically, then replace the live profile."""
        session = self._require_session()
        self._ensure_idle()
        session.profile = self.state_store.replace_profile_slots(session.profile.id, slots)
        self.warning = None
        return self._view()

    def reset_profile_to_template(self) -> SessionView:
        """Copy the current global template into the active profile."""
        return self.save_profile_slots(self.settings.global_slot_template)

    def save_profile_as_template(self) -> Settings:
        """Save a copy of the active profile slots as the independent global template."""
        session = self._require_session()
        return self.save_preferences(
            reopen_last_folder=self.settings.reopen_last_folder,
            sort_direction=self.settings.sort_direction,
            global_slot_template=session.profile.slots,
        )

    def reset_global_template(self) -> Settings:
        """Restore the independent global slot template to its defaults."""
        return self.save_preferences(
            reopen_last_folder=self.settings.reopen_last_folder,
            sort_direction=self.settings.sort_direction,
            global_slot_template=DEFAULT_SLOTS,
        )

    def profile_catalog(self) -> tuple[ProfileSummary, ...]:
        """Load every profile and its source-folder existence on the file worker."""
        return tuple(
            ProfileSummary(profile, Path(profile.folder_identity).is_dir())
            for profile in self.state_store.list_profiles()
        )

    def reassign_orphan(self, profile_id: str) -> SessionView:
        """Explicitly move an orphan profile identity/register to the current source folder."""
        session = self._require_session()
        self._ensure_idle()
        existing = self.state_store.get_profile_by_identity(session.folder_identity)
        replace_profile_id = None
        if existing is not None:
            if session.profile.id != existing.id:
                raise ValueError("the current folder already has a destination profile")
            replace_profile_id = existing.id
        profile = self.state_store.reassign_profile(
            profile_id,
            session.folder_identity,
            str(session.source_path),
            replace_profile_id=replace_profile_id,
        )
        session.profile = profile
        recovery = recover_operations(
            self.state_store,
            self.filesystem,
            profile.id,
            session.source_path,
            logger=self.logger,
        )
        session.recovery_pending = bool(recovery.errors or recovery.pending)
        session.reconcile(automatic=True)
        self.warning = None
        return self._view()

    def delete_profile(self, profile_id: str) -> tuple[ProfileSummary, ...]:
        """Delete profile metadata, register and journal only; never touch image files."""
        self._ensure_idle()
        if self.session is not None and self.session.profile.id == profile_id:
            raise ValueError("close the active folder before deleting its profile")
        self.state_store.delete_profile(profile_id)
        return self.profile_catalog()

    def close(self) -> None:
        session, self.session = self.session, None
        if session is not None:
            session.close()

    def _ensure_idle(self) -> None:
        if self.session is not None and self.session.gate.busy:
            raise RuntimeError("settings cannot be saved during a file operation")

    def _require_session(self) -> FolderSession:
        if self.session is None:
            raise RuntimeError("no source folder is open")
        return self.session

    def _view(self) -> SessionView:
        session = self._require_session()
        self._view_generation += 1
        snapshot = session.snapshot()
        count = len(session.profile.slots)
        states = tuple(SlotState.CHECKING for _ in range(count))
        warning, self.warning = self.warning, None
        return SessionView(snapshot, states, 0, self.settings, self._view_generation, warning)

    def _log_warning(self, message: str) -> None:
        try:
            self.logger.log(LogLevel.WARNING, LogEvent.ERROR, message)
        except Exception:
            return


def _settings_with(
    settings: Settings,
    *,
    reopen_last_folder: bool | None = None,
    sort_direction: str | None = None,
    last_folder: str | None = None,
    global_slot_template: tuple[Slot, ...] | None = None,
    learned_key_labels: tuple[tuple[str, str], ...] | None = None,
) -> Settings:
    return Settings(
        settings.schema_version,
        settings.language,
        settings.sound_enabled,
        sort_direction if sort_direction is not None else settings.sort_direction,
        reopen_last_folder if reopen_last_folder is not None else settings.reopen_last_folder,
        last_folder if last_folder is not None else settings.last_folder,
        global_slot_template if global_slot_template is not None else settings.global_slot_template,
        learned_key_labels if learned_key_labels is not None else settings.learned_key_labels,
    )
