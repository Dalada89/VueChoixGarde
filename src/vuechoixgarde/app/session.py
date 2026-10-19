"""Synchronous source-folder session orchestration and UI-neutral read models."""

from __future__ import annotations

from pathlib import Path

from vuechoixgarde.app.gate import OperationGate
from vuechoixgarde.app.reconcile import reconcile
from vuechoixgarde.app.recovery import recover_operations
from vuechoixgarde.app.results import ReconcileItem, SessionSnapshot, SlotState
from vuechoixgarde.core.comparison import comparison_key
from vuechoixgarde.core.folder_names import validate_folder_name
from vuechoixgarde.core.navigation import (
    ImageNavigation,
    NavigationDirection,
    change_sort_direction,
    create_navigation,
    navigate,
    refresh_navigation,
)
from vuechoixgarde.core.sidecars import sidecars_for_image
from vuechoixgarde.core.toggle import FileClass
from vuechoixgarde.ports.filesystem import FileSystemPort, SourceFolderScanner
from vuechoixgarde.ports.lock import FolderLock, FolderLockFactory
from vuechoixgarde.ports.log import EventLogger, LogEvent, LogLevel
from vuechoixgarde.ports.models import (
    DestinationStatus,
    ProfileRecord,
    Settings,
    SourceScan,
)
from vuechoixgarde.ports.settings import SettingsStore
from vuechoixgarde.ports.state import StateStore


class FolderSession:
    """Own one locked source-folder session and its navigation/read-model state."""

    def __init__(
        self,
        source_path: Path,
        folder_identity: str,
        scan: SourceScan,
        profile: ProfileRecord,
        navigation: ImageNavigation,
        lock: FolderLock,
        filesystem: FileSystemPort,
        scanner: SourceFolderScanner,
        state: StateStore,
        settings_store: SettingsStore,
        settings: Settings,
        *,
        gate: OperationGate,
        register_available: bool,
        logger: EventLogger | None,
    ) -> None:
        self.source_path = source_path
        self.folder_identity = folder_identity
        self.scan = scan
        self.profile = profile
        self.navigation = navigation
        self.lock = lock
        self.filesystem = filesystem
        self.scanner = scanner
        self.state = state
        self.settings_store = settings_store
        self.settings = settings
        self.gate = gate
        self.register_available = register_available
        self.logger = logger
        self.reconciled: tuple[ReconcileItem, ...] = ()
        self.checking = False
        self.boundary_reached = False
        self.closed = False

    @classmethod
    def open(
        cls,
        source_path: Path,
        scanner: SourceFolderScanner,
        filesystem: FileSystemPort,
        state: StateStore,
        settings_store: SettingsStore,
        settings: Settings,
        lock_factory: FolderLockFactory,
        *,
        gate: OperationGate | None = None,
        register_available: bool = True,
        logger: EventLogger | None = None,
    ) -> FolderSession:
        """Validate/lock/scan a folder, establish its profile, recover, then reconcile."""
        lock: FolderLock | None = None
        try:
            scanner.check_source_folder(source_path)
            identity = scanner.folder_identity(source_path)
            lock = lock_factory.create(identity)
            lock.acquire()
            scan = scanner.scan_source_folder(source_path)
            profile = state.get_profile_by_identity(identity)
            if profile is None:
                profile = state.create_profile_from_template(
                    identity, str(source_path.resolve()), settings.global_slot_template
                )
            navigation = create_navigation(
                scan.images,
                descending=settings.sort_direction == "desc",
            )
            session = cls(
                source_path.resolve(),
                identity,
                scan,
                profile,
                navigation,
                lock,
                filesystem,
                scanner,
                state,
                settings_store,
                settings,
                gate=gate or OperationGate(),
                register_available=register_available,
                logger=logger,
            )
            if register_available:
                recovery = recover_operations(
                    state, filesystem, profile.id, session.source_path, logger=logger
                )
                if recovery.errors or recovery.pending:
                    session.checking = True
                session.reconcile(automatic=True, acquire_gate=False)
            _safe_log(
                logger,
                LogLevel.INFO,
                LogEvent.FOLDER_OPEN,
                "source folder opened",
                image_count=len(scan.images),
                register_available=register_available,
            )
            return session
        except Exception as error:
            if lock is not None:
                lock.release()
            _safe_log(
                logger,
                LogLevel.ERROR,
                LogEvent.FOLDER_OPEN_FAILED,
                "source folder could not be opened",
                reason=type(error).__name__,
            )
            raise

    def navigate(self, direction: NavigationDirection) -> SessionSnapshot:
        """Move without wrapping and report whether the current list boundary was hit."""
        before = self.navigation.current
        updated = navigate(self.navigation, direction)
        self.boundary_reached = before == updated.current and before is not None
        self.navigation = updated
        return self.snapshot()

    def set_sort_direction(self, *, descending: bool) -> SessionSnapshot:
        """Persist sort preference and reorder while preserving the current image."""
        self.navigation = change_sort_direction(self.navigation, descending=descending)
        self.boundary_reached = False
        updated_settings = Settings(
            self.settings.schema_version,
            self.settings.language,
            self.settings.sound_enabled,
            "desc" if descending else "asc",
            self.settings.reopen_last_folder,
            self.settings.last_folder,
            self.settings.global_slot_template,
            self.settings.learned_key_labels,
        )
        self.settings_store.save(updated_settings)
        self.settings = updated_settings
        return self.snapshot()

    def refresh(self) -> SessionSnapshot:
        """Rescan visible source files and preserve the current or nearest following image."""
        self.scan = self.scanner.scan_source_folder(self.source_path)
        self.navigation = refresh_navigation(self.navigation, self.scan.images)
        self.boundary_reached = False
        return self.snapshot()

    def set_destination_name(self, slot_index: int, destination_name: str) -> ProfileRecord:
        """Validate and persist a confirmed destination name for one slot."""
        if validate_folder_name(destination_name) is not None:
            raise ValueError(f"invalid destination name: {validate_folder_name(destination_name)}")
        if not 0 <= slot_index < len(self.profile.slots):
            raise IndexError(slot_index)
        slots = list(self.profile.slots)
        slots[slot_index] = type(slots[slot_index])(
            slots[slot_index].key_position, destination_name, slots[slot_index].color
        )
        updated = self.state.replace_profile_slots(self.profile.id, slots)
        self.profile = updated
        return updated

    def reconcile(self, *, automatic: bool, acquire_gate: bool = True) -> bool:
        """Run reconciliation under the shared non-blocking operation gate."""
        if not self.register_available:
            return False
        acquired = self.gate.try_acquire() if acquire_gate else True
        if not acquired:
            return False
        self.checking = True
        try:
            report = reconcile(
                self.state,
                self.filesystem,
                self.profile.id,
                self.source_path,
                automatic=automatic,
                logger=self.logger,
            )
            self.reconciled = report.items
            return True
        finally:
            self.checking = False
            if acquire_gate:
                self.gate.release()

    def slot_states(self, image_name: str | None = None) -> tuple[SlotState, ...]:
        """Derive per-slot status for the current image from the register and filesystem."""
        current = image_name if image_name is not None else self.navigation.current
        if current is None:
            return tuple(
                SlotState.NO_DESTINATION if slot.destination_name is None else SlotState.READY
                for slot in self.profile.slots
            )
        sidecars = sidecars_for_image(current, self.scan.sidecar_candidates)
        outcomes: list[SlotState] = []
        for slot in self.profile.slots:
            if slot.destination_name is None:
                outcomes.append(SlotState.NO_DESTINATION)
                continue
            try:
                resolution = self.filesystem.resolve_destination_folder(
                    self.source_path, slot.destination_name
                )
                if resolution.status is DestinationStatus.FAULTY:
                    outcomes.append(SlotState.FAULTY)
                    continue
                if (
                    resolution.status is DestinationStatus.NOT_FOUND
                    or resolution.exact_name is None
                ):
                    outcomes.append(SlotState.READY)
                    continue
                destination = self.source_path / resolution.exact_name
                names = self.filesystem.list_destination_names(self.source_path, destination)
                records = (
                    self.state.copy_records(self.profile.id, str(destination))
                    if self.register_available
                    else ()
                )
                source_names = (current, *sidecars)
                matching_records = [
                    record
                    for record in records
                    if any(
                        comparison_key(record.source_name) == comparison_key(name)
                        for name in source_names
                    )
                ]
                if matching_records:
                    classes = {
                        item.record.destination_name: item.file_class
                        for item in self.reconciled
                        if item.file_class is not None
                    }
                    if any(
                        classes.get(record.destination_name) is FileClass.MODIFIED
                        for record in matching_records
                    ):
                        outcomes.append(SlotState.MODIFIED)
                    else:
                        outcomes.append(SlotState.SELECTED)
                    continue
                target_names = {comparison_key(name) for name in source_names}
                if any(comparison_key(name) in target_names for name in names):
                    outcomes.append(SlotState.CONFLICT)
                else:
                    outcomes.append(SlotState.READY)
            except Exception:
                outcomes.append(SlotState.FAULTY)
        return tuple(outcomes)

    def snapshot(self) -> SessionSnapshot:
        """Return a complete immutable read model for the current session."""
        images = self.navigation.images
        index = (
            images.index(self.navigation.current) + 1 if self.navigation.current in images else 0
        )
        return SessionSnapshot(
            source_path=str(self.source_path),
            folder_identity=self.folder_identity,
            profile=self.profile,
            scan=self.scan,
            current_name=self.navigation.current,
            image_index=index,
            image_count=len(images),
            descending=self.navigation.descending,
            boundary_reached=self.boundary_reached,
            checking=self.checking,
            register_available=self.register_available,
            reconciled=self.reconciled,
        )

    def close(self) -> None:
        """Release the folder lock once and emit a privacy-safe close event."""
        if self.closed:
            return
        self.closed = True
        self.lock.release()
        _safe_log(
            self.logger,
            LogLevel.INFO,
            LogEvent.FOLDER_CLOSE,
            "source folder closed",
            image_count=len(self.scan.images),
        )


def _safe_log(
    logger: EventLogger | None,
    level: LogLevel,
    event: LogEvent,
    message: str,
    **fields: object,
) -> None:
    if logger is None:
        return
    try:
        logger.log(level, event, message, **fields)
    except Exception:
        return
