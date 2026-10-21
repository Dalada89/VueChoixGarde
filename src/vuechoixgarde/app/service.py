"""Qt-free session orchestration and settings/profile use cases."""

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import uuid4

from vuechoixgarde.app.keys import learn_key_label
from vuechoixgarde.app.recovery import recover_folder_renames, recover_operations
from vuechoixgarde.app.results import (
    FolderDeletionCase,
    FolderDeletionCheck,
    FolderDeletionResult,
    FolderDeletionStatus,
    FolderManagementError,
    FolderManagementReason,
    FolderRename,
    SessionSnapshot,
    SlotState,
    UseCaseStatus,
)
from vuechoixgarde.app.session import FolderSession
from vuechoixgarde.app.toggle import TogglePlan, ToggleResult, execute_toggle, plan_toggle
from vuechoixgarde.core.comparison import comparison_key
from vuechoixgarde.core.destination import destination_folder_key
from vuechoixgarde.core.folder_names import validate_folder_name
from vuechoixgarde.core.navigation import NavigationDirection, change_sort_direction
from vuechoixgarde.core.slots import DEFAULT_SLOTS, Slot, validate_slot_profile
from vuechoixgarde.ports.clock import Clock
from vuechoixgarde.ports.errors import FileSystemError, FileSystemErrorReason
from vuechoixgarde.ports.filesystem import FileSystemPort, SourceFolderScanner
from vuechoixgarde.ports.lock import FolderLockFactory
from vuechoixgarde.ports.log import EventLogger, LogEvent, LogLevel
from vuechoixgarde.ports.models import (
    DestinationStatus,
    EntryKind,
    FolderRenameRecord,
    FolderRenameState,
    ProfileRecord,
    Settings,
)
from vuechoixgarde.ports.settings import SettingsStore
from vuechoixgarde.ports.state import StateStore


class PartialSettingsSaveError(RuntimeError):
    """Preferences failed after profile slots had already been committed."""


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
    renamed: tuple[tuple[str, str], ...] = ()


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
                    warning = "destination_unassigned"
            except Exception:
                warning = "selection_count_failed"
                self._log_warning("selected-image count could not be loaded")
        return SlotStatusResult(image_name, generation, states, selected, warning)

    def save_settings_and_profile_slots(
        self,
        *,
        reopen_last_folder: bool,
        sort_direction: str,
        language: str,
        sound_enabled: bool,
        global_slot_template: tuple[Slot, ...],
        profile_slots: tuple[Slot, ...] | None,
        learned_key_labels: tuple[tuple[str, str], ...],
        renames: tuple[FolderRename, ...] = (),
    ) -> SessionView | None:
        """Validate and save profile folder renames before global preferences."""
        if validate_slot_profile(global_slot_template):
            raise ValueError("global slot template is invalid")
        if profile_slots is not None and validate_slot_profile(profile_slots):
            raise ValueError("profile slots are invalid")
        if profile_slots is not None:
            self._require_session()
            self._ensure_idle()

        if renames:
            if profile_slots is None:
                raise ValueError("folder renames require saved profile slots")
            view, renamed = self._save_profile_slots_with_renames(profile_slots, renames)
            try:
                self.save_preferences(
                    reopen_last_folder=reopen_last_folder,
                    sort_direction=sort_direction,
                    language=language,
                    sound_enabled=sound_enabled,
                    global_slot_template=global_slot_template,
                    learned_key_labels=learned_key_labels,
                )
            except Exception as error:
                raise PartialSettingsSaveError(
                    "Profile slots and folder renames were saved, but global settings were not."
                ) from error
            return replace(view, settings=self.settings, renamed=renamed)

        self.save_preferences(
            reopen_last_folder=reopen_last_folder,
            sort_direction=sort_direction,
            language=language,
            sound_enabled=sound_enabled,
            global_slot_template=global_slot_template,
            learned_key_labels=learned_key_labels,
        )
        if profile_slots is None:
            return self.current_view()
        try:
            return self.save_profile_slots(profile_slots)
        except Exception as error:
            raise PartialSettingsSaveError(
                "Global settings were saved, but profile slots were not saved. "
                "The settings dialog remains open."
            ) from error

    def _save_profile_slots_with_renames(
        self, slots: tuple[Slot, ...], renames: tuple[FolderRename, ...]
    ) -> tuple[SessionView, tuple[tuple[str, str], ...]]:
        session = self._require_session()
        self._ensure_idle()
        if (
            not self.register_available
            or not session.register_available
            or session.recovery_pending
        ):
            raise FolderManagementError(FolderManagementReason.UNAVAILABLE)
        try:
            if any(
                operation.profile_id == session.profile.id
                for operation in self.state_store.unfinished_operations()
            ):
                raise FolderManagementError(FolderManagementReason.UNAVAILABLE)
        except FolderManagementError:
            raise
        except Exception as error:
            raise FolderManagementError(FolderManagementReason.UNAVAILABLE) from error

        requested = tuple(rename for rename in renames if rename.old_name != rename.new_name)
        if not requested:
            session.profile = self.state_store.replace_profile_slots(session.profile.id, slots)
            return self._view(), ()
        targets = [comparison_key(rename.new_name) for rename in requested]
        if len(set(targets)) != len(targets):
            raise FolderManagementError(FolderManagementReason.NAME_OCCUPIED)
        if len({comparison_key(rename.old_name) for rename in requested}) != len(requested):
            raise FolderManagementError(FolderManagementReason.NAME_OCCUPIED)
        for rename in requested:
            if validate_folder_name(rename.old_name) is not None:
                raise FolderManagementError(
                    FolderManagementReason.INVALID_NAME,
                    old_name=rename.old_name,
                    new_name=rename.new_name,
                )
            if validate_folder_name(rename.new_name) is not None:
                raise FolderManagementError(
                    FolderManagementReason.INVALID_NAME,
                    old_name=rename.old_name,
                    new_name=rename.new_name,
                )

        source_root = session.source_path
        old_exact_names: list[str | None] = []
        for rename in requested:
            try:
                resolution = self.filesystem.resolve_destination_folder(
                    source_root, rename.old_name
                )
            except Exception as error:
                raise FolderManagementError(
                    FolderManagementReason.OLD_FOLDER_FAULTY,
                    old_name=rename.old_name,
                    new_name=rename.new_name,
                ) from error
            if resolution.status is DestinationStatus.FAULTY:
                raise FolderManagementError(
                    FolderManagementReason.OLD_FOLDER_FAULTY,
                    old_name=rename.old_name,
                    new_name=rename.new_name,
                )
            old_exact_names.append(
                resolution.exact_name if resolution.status is DestinationStatus.FOUND else None
            )

        try:
            existing_names = self.filesystem.list_destination_names(source_root, source_root)
        except Exception as error:
            raise FolderManagementError(FolderManagementReason.RENAME_FAILED) from error
        for rename, exact_old in zip(requested, old_exact_names, strict=True):
            if any(
                comparison_key(entry) == comparison_key(rename.new_name) and entry != exact_old
                for entry in existing_names
            ):
                raise FolderManagementError(
                    FolderManagementReason.NAME_OCCUPIED,
                    old_name=rename.old_name,
                    new_name=rename.new_name,
                    names=(rename.new_name,),
                )

        journal: list[FolderRenameRecord] = []
        intermediate_names: list[str | None] = []
        reserved = {comparison_key(name) for name in existing_names}
        for rename, exact_old in zip(requested, old_exact_names, strict=True):
            intermediate = None
            if exact_old is not None and comparison_key(exact_old) == comparison_key(
                rename.new_name
            ):
                while True:
                    candidate = f".vcg-rename-{uuid4().hex}"
                    if comparison_key(candidate) not in reserved:
                        intermediate = candidate
                        reserved.add(comparison_key(candidate))
                        break
            old_key_name = exact_old if exact_old is not None else rename.old_name
            journal.append(
                FolderRenameRecord(
                    uuid4().hex,
                    session.profile.id,
                    destination_folder_key(source_root, old_key_name),
                    destination_folder_key(source_root, rename.new_name),
                    destination_folder_key(source_root, intermediate)
                    if intermediate is not None
                    else None,
                    FolderRenameState.STARTED,
                    "",
                    "",
                    slots,
                )
            )
            intermediate_names.append(intermediate)

        rename_ids = tuple(record.id for record in journal)
        try:
            self.state_store.start_folder_renames(session.profile.id, tuple(journal))
        except Exception as error:
            self._log_folder_rename(
                LogLevel.ERROR,
                LogEvent.FOLDER_RENAME_FAILED,
                "folder rename journal could not be started",
                code="rename_failed",
            )
            raise FolderManagementError(FolderManagementReason.RENAME_FAILED) from error

        completed: list[tuple[str, str, str | None]] = []
        active: tuple[str, str, str | None] | None = None
        try:
            for rename, exact_old, intermediate in zip(
                requested, old_exact_names, intermediate_names, strict=True
            ):
                if exact_old is None:
                    continue
                active = (exact_old, rename.new_name, intermediate)
                self.filesystem.rename_destination_folder(
                    source_root, exact_old, rename.new_name, intermediate
                )
                completed.append(active)
                active = None
        except Exception as error:
            rollback_ok = self._rollback_folder_renames(source_root, completed, active)
            if rollback_ok:
                try:
                    self.state_store.mark_folder_renames_rolled_back(rename_ids)
                except Exception:
                    rollback_ok = False
            if not rollback_ok:
                session.recovery_pending = True
                self._log_folder_rename(
                    LogLevel.ERROR,
                    LogEvent.FOLDER_RENAME_FAILED,
                    "folder rename rollback failed",
                    code="rename_rollback_failed",
                    old_name=active[0] if active else None,
                    new_name=active[1] if active else None,
                )
                raise FolderManagementError(
                    FolderManagementReason.ROLLBACK_FAILED,
                    old_name=active[0] if active else None,
                    new_name=active[1] if active else None,
                ) from error
            self._log_folder_rename(
                LogLevel.ERROR,
                LogEvent.FOLDER_RENAME_FAILED,
                "folder rename failed and was rolled back",
                code="rename_failed",
                old_name=active[0] if active else None,
                new_name=active[1] if active else None,
            )
            raise _folder_management_error(
                error, (active[0], active[1]) if active is not None else None
            ) from error

        folder_updates = tuple(
            (
                destination_folder_key(source_root, old_name),
                destination_folder_key(source_root, new_name),
            )
            for old_name, new_name, _ in completed
        )
        removed_folders = tuple(
            destination_folder_key(source_root, rename.old_name)
            for rename, exact_old in zip(requested, old_exact_names, strict=True)
            if exact_old is None
        )
        try:
            self.state_store.complete_folder_renames(
                session.profile.id, rename_ids, folder_updates, removed_folders, slots
            )
        except Exception as error:
            if self._rollback_folder_renames(source_root, completed, None):
                try:
                    self.state_store.mark_folder_renames_rolled_back(rename_ids)
                except Exception:
                    session.recovery_pending = True
                    raise FolderManagementError(FolderManagementReason.ROLLBACK_FAILED) from error
            else:
                session.recovery_pending = True
                raise FolderManagementError(FolderManagementReason.ROLLBACK_FAILED) from error
            self._log_folder_rename(
                LogLevel.ERROR,
                LogEvent.FOLDER_RENAME_FAILED,
                "folder rename register update failed and was rolled back",
                code="rename_failed",
            )
            raise FolderManagementError(FolderManagementReason.RENAME_FAILED) from error

        session.profile = replace(session.profile, slots=slots)
        session.reconciled = ()
        self.warning = None
        renamed = tuple((item.old_name, item.new_name) for item in requested)
        for old_name, new_name in renamed:
            self._log_folder_rename(
                LogLevel.INFO,
                LogEvent.FOLDER_RENAMED,
                "destination folder renamed",
                code="folder_renamed",
                old_name=old_name,
                new_name=new_name,
            )
        return self._view(), renamed

    def inspect_destination_folder(self, slot_index: int) -> FolderDeletionCheck:
        """Classify one configured destination and produce a confirmation fingerprint."""
        session = self._require_session()
        self._ensure_idle()
        self._ensure_folder_management_available(session)
        return self._inspect_destination_folder(session, slot_index)

    def delete_destination_folder(
        self, slot_index: int, confirmed: FolderDeletionCheck
    ) -> FolderDeletionResult:
        """Recheck a user-confirmed folder state, then delete only verified copies or detach."""
        session = self._require_session()
        self._ensure_idle()
        self._ensure_folder_management_available(session)
        current = self._inspect_destination_folder(session, slot_index)
        if (
            confirmed.slot_index != slot_index
            or confirmed.case is not current.case
            or confirmed.fingerprint != current.fingerprint
        ):
            return FolderDeletionResult(FolderDeletionStatus.CHECK_CHANGED, current)

        folder_key = destination_folder_key(session.source_path, current.folder_name)
        if current.case is FolderDeletionCase.DELETABLE:
            records = {
                record.destination_name: record
                for record in self.state_store.copy_records(session.profile.id, folder_key)
            }
            deleted: list[str] = []
            try:
                for name in current.managed_names:
                    record = records.get(name)
                    if record is None:
                        return FolderDeletionResult(
                            FolderDeletionStatus.CHECK_CHANGED,
                            self._inspect_destination_folder(session, slot_index),
                        )
                    self.filesystem.delete_verified_file(
                        session.source_path,
                        session.source_path / current.folder_name,
                        name,
                        record.size,
                        record.sha256,
                    )
                    deleted.append(name)
                self.filesystem.remove_empty_destination_folder(
                    session.source_path, current.folder_name
                )
            except Exception as error:
                if deleted:
                    self.state_store.remove_copy_records(
                        session.profile.id, folder_key, tuple(deleted)
                    )
                self._log_folder_delete(
                    LogLevel.WARNING,
                    LogEvent.FOLDER_DELETE_FAILED,
                    current.folder_name,
                    deleted_count=len(deleted),
                    error_reason=_folder_delete_error_reason(error),
                )
                return FolderDeletionResult(
                    FolderDeletionStatus.PARTIAL,
                    current,
                    len(deleted),
                    _folder_delete_error_reason(error),
                )
            updated_slots = _clear_destination_slot(session.profile.slots, slot_index)
            self.state_store.remove_destination_folder_records(
                session.profile.id, folder_key, updated_slots
            )
            self._update_session_profile(session)
            self._log_folder_delete(
                LogLevel.INFO,
                LogEvent.FOLDER_DELETED,
                current.folder_name,
                deleted_count=len(deleted),
            )
            return FolderDeletionResult(FolderDeletionStatus.DELETED, current, len(deleted))

        updated_slots = _clear_destination_slot(session.profile.slots, slot_index)
        self.state_store.remove_destination_folder_records(
            session.profile.id, folder_key, updated_slots
        )
        self._update_session_profile(session)
        if current.case is FolderDeletionCase.MISSING:
            return FolderDeletionResult(FolderDeletionStatus.REMOVED_INFO, current)
        self._log_folder_delete(
            LogLevel.WARNING,
            LogEvent.FOLDER_DETACHED,
            current.folder_name,
            foreign_count=len(current.foreign_names),
        )
        return FolderDeletionResult(FolderDeletionStatus.DETACHED, current)

    def _inspect_destination_folder(
        self, session: FolderSession, slot_index: int
    ) -> FolderDeletionCheck:
        if not 0 <= slot_index < len(session.profile.slots):
            raise IndexError(slot_index)
        folder_name = session.profile.slots[slot_index].destination_name
        if folder_name is None:
            raise ValueError("slot has no saved destination name")
        resolution = self.filesystem.resolve_destination_folder(session.source_path, folder_name)
        if resolution.status is DestinationStatus.NOT_FOUND:
            case = FolderDeletionCase.MISSING
            evidence: list[dict[str, object]] = []
            managed: tuple[str, ...] = ()
            foreign: tuple[str, ...] = ()
        elif resolution.status is DestinationStatus.FAULTY or resolution.exact_name is None:
            case = FolderDeletionCase.FAULTY
            evidence = [{"reason": resolution.reason.value if resolution.reason else "faulty"}]
            managed = ()
            foreign = ()
        else:
            exact_name = resolution.exact_name
            destination = session.source_path / exact_name
            records = {
                record.destination_name: record
                for record in self.state_store.copy_records(
                    session.profile.id,
                    destination_folder_key(session.source_path, exact_name),
                )
            }
            verified: list[str] = []
            unknown: list[str] = []
            evidence = []
            entries = self.filesystem.list_destination_entries(session.source_path, destination)
            for entry in sorted(entries, key=lambda item: item.name):
                item: dict[str, object] = {"name": entry.name, "kind": entry.kind.value}
                record = records.get(entry.name)
                if entry.kind is EntryKind.FILE:
                    try:
                        fingerprint = self.filesystem.fingerprint_file(
                            session.source_path, destination / entry.name
                        )
                        item["size"] = fingerprint.size
                        item["sha256"] = fingerprint.sha256
                        if (
                            record is not None
                            and fingerprint.size == record.size
                            and fingerprint.sha256 == record.sha256
                        ):
                            verified.append(entry.name)
                        else:
                            unknown.append(entry.name)
                    except Exception as error:
                        item["fingerprint_error"] = type(error).__name__
                        unknown.append(entry.name)
                else:
                    item["size"] = None
                    item["sha256"] = None
                    unknown.append(entry.name)
                evidence.append(item)
            managed = tuple(sorted(verified))
            foreign = tuple(sorted(unknown))
            case = FolderDeletionCase.FOREIGN_ENTRIES if foreign else FolderDeletionCase.DELETABLE
            folder_name = exact_name

        fingerprint = hashlib.sha256(
            json.dumps(
                [case.value, folder_name, evidence],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return FolderDeletionCheck(case, slot_index, folder_name, managed, foreign, fingerprint)

    def _ensure_folder_management_available(self, session: FolderSession) -> None:
        if (
            not self.register_available
            or not session.register_available
            or session.recovery_pending
        ):
            raise FolderManagementError(FolderManagementReason.UNAVAILABLE)
        try:
            pending_operations = any(
                operation.profile_id == session.profile.id
                for operation in self.state_store.unfinished_operations()
            )
            pending_renames = any(
                record.profile_id == session.profile.id
                for record in self.state_store.unfinished_folder_renames()
            )
        except Exception as error:
            raise FolderManagementError(FolderManagementReason.UNAVAILABLE) from error
        if pending_operations or pending_renames:
            raise FolderManagementError(FolderManagementReason.UNAVAILABLE)

    def _update_session_profile(self, session: FolderSession) -> None:
        profile = self.state_store.get_profile_by_identity(session.folder_identity)
        if profile is not None:
            session.profile = profile
        session.reconciled = ()
        self.warning = None

    def _log_folder_delete(
        self,
        level: LogLevel,
        event: LogEvent,
        folder_name: str,
        **fields: object,
    ) -> None:
        try:
            self.logger.log(
                level, event, "destination folder delete flow", folder_name=folder_name, **fields
            )
        except Exception:
            return

    def _rollback_folder_renames(
        self,
        source_root: Path,
        completed: list[tuple[str, str, str | None]],
        active: tuple[str, str, str | None] | None,
    ) -> bool:
        rollback_ok = True
        for old_name, new_name, _ in reversed(completed):
            try:
                self.filesystem.rename_destination_folder(source_root, new_name, old_name)
            except Exception:
                rollback_ok = False
        if active is not None:
            try:
                names = self.filesystem.list_destination_names(source_root, source_root)
                if active[0] in names:
                    if active[1] in names or (active[2] is not None and active[2] in names):
                        rollback_ok = False
                else:
                    current_name = (
                        active[1]
                        if active[1] in names
                        else active[2]
                        if active[2] is not None and active[2] in names
                        else None
                    )
                    if current_name is None:
                        rollback_ok = False
                    else:
                        self.filesystem.rename_destination_folder(
                            source_root, current_name, active[0]
                        )
            except Exception:
                rollback_ok = False
        return rollback_ok

    def _log_folder_rename(
        self,
        level: LogLevel,
        event: LogEvent,
        message: str,
        **fields: object,
    ) -> None:
        try:
            self.logger.log(level, event, message, **fields)
        except Exception:
            return

    def save_preferences(
        self,
        *,
        reopen_last_folder: bool,
        sort_direction: str,
        global_slot_template: tuple[Slot, ...] | None = None,
        learned_key_labels: tuple[tuple[str, str], ...] | None = None,
        language: str | None = None,
        sound_enabled: bool | None = None,
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
            language=language,
            sound_enabled=sound_enabled,
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
        rename_recovery = recover_folder_renames(
            self.state_store,
            self.filesystem,
            profile.id,
            session.source_path,
            logger=self.logger,
        )
        operation_recovery = recover_operations(
            self.state_store,
            self.filesystem,
            profile.id,
            session.source_path,
            logger=self.logger,
        )
        session.recovery_pending = bool(
            rename_recovery.errors
            or rename_recovery.pending
            or operation_recovery.errors
            or operation_recovery.pending
        )
        recovered_profile = self.state_store.get_profile_by_identity(session.folder_identity)
        if recovered_profile is not None:
            session.profile = recovered_profile
        if not session.recovery_pending:
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


def _clear_destination_slot(slots: tuple[Slot, ...], slot_index: int) -> tuple[Slot, ...]:
    return tuple(
        replace(slot, destination_name=None) if index == slot_index else slot
        for index, slot in enumerate(slots)
    )


def _folder_delete_error_reason(error: Exception) -> str:
    if isinstance(error, FileSystemError):
        return error.reason.value
    return "io_error"


def _folder_management_error(
    error: Exception,
    names: tuple[str, str] | None,
) -> FolderManagementError:
    old_name, new_name = names if names is not None else (None, None)
    reason = FolderManagementReason.RENAME_FAILED
    if isinstance(error, FileSystemError):
        if error.reason is FileSystemErrorReason.NAME_CONFLICT:
            reason = FolderManagementReason.NAME_OCCUPIED
        elif error.reason is FileSystemErrorReason.INVALID_NAME:
            reason = FolderManagementReason.INVALID_NAME
        elif error.reason in {
            FileSystemErrorReason.DESTINATION_FILE,
            FileSystemErrorReason.DESTINATION_LINK,
            FileSystemErrorReason.DESTINATION_OUTSIDE,
            FileSystemErrorReason.PATH_OUTSIDE_ROOT,
        }:
            reason = FolderManagementReason.OLD_FOLDER_FAULTY
    return FolderManagementError(reason, old_name=old_name, new_name=new_name)


def _settings_with(
    settings: Settings,
    *,
    reopen_last_folder: bool | None = None,
    sort_direction: str | None = None,
    last_folder: str | None = None,
    global_slot_template: tuple[Slot, ...] | None = None,
    learned_key_labels: tuple[tuple[str, str], ...] | None = None,
    language: str | None = None,
    sound_enabled: bool | None = None,
) -> Settings:
    if language is not None and language not in {"de", "en", "fr"}:
        raise ValueError("language must be de, en, or fr")
    return Settings(
        settings.schema_version,
        language if language is not None else settings.language,
        sound_enabled if sound_enabled is not None else settings.sound_enabled,
        sort_direction if sort_direction is not None else settings.sort_direction,
        reopen_last_folder if reopen_last_folder is not None else settings.reopen_last_folder,
        last_folder if last_folder is not None else settings.last_folder,
        global_slot_template if global_slot_template is not None else settings.global_slot_template,
        learned_key_labels if learned_key_labels is not None else settings.learned_key_labels,
    )
