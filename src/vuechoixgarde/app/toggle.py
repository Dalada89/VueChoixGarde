"""Two-phase slot toggle planning and safe execution (FR-044 through FR-058)."""

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from vuechoixgarde.app.gate import OperationGate
from vuechoixgarde.app.results import FileClassification, UseCaseStatus
from vuechoixgarde.core.comparison import comparison_key
from vuechoixgarde.core.destination import destination_folder_key
from vuechoixgarde.core.sidecars import sidecars_for_image
from vuechoixgarde.core.temp_names import temp_file_name
from vuechoixgarde.core.toggle import (
    FileClass,
    ToggleAction,
    decide_toggle,
)
from vuechoixgarde.core.toggle import (
    TogglePlan as DomainTogglePlan,
)
from vuechoixgarde.ports.clock import Clock
from vuechoixgarde.ports.errors import FileSystemError, FileSystemErrorReason
from vuechoixgarde.ports.filesystem import FileSystemPort, SourceFolderScanner
from vuechoixgarde.ports.log import EventLogger, LogEvent, LogLevel
from vuechoixgarde.ports.models import (
    CopyRecord,
    DestinationStatus,
    OperationFileRecord,
    ProfileRecord,
)
from vuechoixgarde.ports.state import StateStore


@dataclass(frozen=True)
class ToggleTarget:
    """One source image or sidecar and its freshly classified destination state."""

    source_name: str
    classification: FileClassification


@dataclass(frozen=True)
class TogglePlan:
    """Captured user intent and fresh preflight state; execution reclassifies it."""

    profile_id: str
    source_root: Path
    image_name: str
    slot_index: int
    destination_name: str | None
    destination_folder: Path | None
    targets: tuple[ToggleTarget, ...]
    action: ToggleAction | None
    status: UseCaseStatus
    detail: str | None = None
    source_images: tuple[str, ...] = ()
    source_sidecars: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToggleResult:
    """Outcome of one slot activation, without UI-specific messages."""

    status: UseCaseStatus
    action: ToggleAction | None = None
    changed_files: tuple[str, ...] = ()
    conflict_names: tuple[str, ...] = ()
    error_reason: str | None = None


def plan_toggle(
    profile: ProfileRecord,
    source_root: Path,
    image_name: str,
    slot_index: int,
    scanner: SourceFolderScanner,
    filesystem: FileSystemPort,
    state: StateStore,
    *,
    register_available: bool = True,
) -> TogglePlan:
    """Capture the requested image and classify it plus fresh sidecars without writing files."""
    if not 0 <= slot_index < len(profile.slots):
        return _failed_plan(profile, source_root, image_name, slot_index, "slot index out of range")
    destination_name = profile.slots[slot_index].destination_name
    if destination_name is None:
        return TogglePlan(
            profile.id,
            source_root,
            image_name,
            slot_index,
            None,
            None,
            (),
            None,
            UseCaseStatus.NAME_REQUIRED,
        )
    if not register_available:
        return TogglePlan(
            profile.id,
            source_root,
            image_name,
            slot_index,
            destination_name,
            None,
            (),
            None,
            UseCaseStatus.CONFLICT,
            "copy register unavailable",
        )
    try:
        source_scan = scanner.scan_source_folder(source_root)
        if image_name not in source_scan.images:
            return _failed_plan(
                profile, source_root, image_name, slot_index, "image is not in source scan"
            )
        sidecars = sidecars_for_image(image_name, source_scan.sidecar_candidates)
        resolution = filesystem.resolve_destination_folder(source_root, destination_name)
        if resolution.status is DestinationStatus.FAULTY:
            return TogglePlan(
                profile.id,
                source_root,
                image_name,
                slot_index,
                destination_name,
                None,
                (),
                None,
                UseCaseStatus.FAULTY,
                str(resolution.reason or "faulty destination"),
            )
        destination_folder = (
            source_root / resolution.exact_name
            if resolution.status is DestinationStatus.FOUND and resolution.exact_name is not None
            else None
        )
        destination_names = (
            filesystem.list_destination_names(source_root, destination_folder)
            if destination_folder is not None
            else ()
        )
        records = (
            state.copy_records(profile.id, str(destination_folder))
            if destination_folder is not None
            else ()
        )
        targets = tuple(
            ToggleTarget(
                name,
                _classify_target(
                    name,
                    destination_names,
                    records,
                    source_root,
                    destination_folder,
                    filesystem,
                    state,
                    profile.id,
                    register_available,
                ),
            )
            for name in (image_name, *sidecars)
        )
        domain_plan: DomainTogglePlan = decide_toggle(
            targets[0].classification.file_class,
            tuple(target.classification.file_class for target in targets[1:]),
            register_available=register_available,
        )
        status = (
            UseCaseStatus.CONFLICT
            if domain_plan.action is ToggleAction.CONFLICT
            else UseCaseStatus.OK
        )
        conflicts = tuple(
            target.classification.actual_name or target.source_name
            for target in targets
            if target.classification.file_class in {FileClass.FOREIGN, FileClass.MODIFIED}
        )
        return TogglePlan(
            profile.id,
            source_root,
            image_name,
            slot_index,
            destination_name,
            destination_folder,
            targets,
            domain_plan.action,
            status,
            ",".join(conflicts) if conflicts else None,
            source_scan.images,
            source_scan.sidecar_candidates,
        )
    except Exception as error:
        return _failed_plan(profile, source_root, image_name, slot_index, _reason(error))


def execute_toggle(
    initial_plan: TogglePlan,
    profile: ProfileRecord,
    scanner: SourceFolderScanner,
    filesystem: FileSystemPort,
    state: StateStore,
    clock: Clock,
    gate: OperationGate,
    *,
    confirmed_modified: bool = False,
    auto_repeat: bool = False,
    register_available: bool = True,
    logger: EventLogger | None = None,
) -> ToggleResult:
    """Reclassify before acting, serialize non-blockingly, and journal safe toggle-on copies."""
    if initial_plan.status is UseCaseStatus.NAME_REQUIRED:
        return ToggleResult(UseCaseStatus.NAME_REQUIRED)
    if initial_plan.status is UseCaseStatus.FAULTY:
        return ToggleResult(UseCaseStatus.FAULTY, error_reason=initial_plan.detail)
    if initial_plan.status is UseCaseStatus.CONFLICT and initial_plan.action is None:
        return ToggleResult(UseCaseStatus.CONFLICT, conflict_names=(initial_plan.detail or "",))
    if not gate.try_acquire(auto_repeat=auto_repeat):
        return ToggleResult(UseCaseStatus.BUSY)
    try:
        fresh = plan_toggle(
            profile,
            initial_plan.source_root,
            initial_plan.image_name,
            initial_plan.slot_index,
            scanner,
            filesystem,
            state,
            register_available=register_available,
        )
        if fresh.status is not UseCaseStatus.OK or fresh.action is None:
            return ToggleResult(fresh.status, fresh.action, conflict_names=_conflict_names(fresh))
        if fresh.action is ToggleAction.CONFLICT:
            _safe_log(
                logger,
                LogLevel.WARNING,
                LogEvent.CONFLICT,
                "slot action conflicted",
                count=len(_conflict_names(fresh)),
            )
            return ToggleResult(
                UseCaseStatus.CONFLICT, fresh.action, conflict_names=_conflict_names(fresh)
            )
        if fresh.action is ToggleAction.TOGGLE_OFF_CONFIRM and not confirmed_modified:
            return ToggleResult(
                UseCaseStatus.MODIFIED_CONFIRMATION_REQUIRED,
                fresh.action,
                conflict_names=_conflict_names(fresh),
            )
        if fresh.action in {ToggleAction.TOGGLE_OFF, ToggleAction.TOGGLE_OFF_CONFIRM}:
            return _toggle_off(fresh, filesystem, state, confirmed_modified, logger)
        return _toggle_on(fresh, filesystem, state, clock, logger)
    finally:
        gate.release()


def _classify_target(
    source_name: str,
    destination_names: tuple[str, ...],
    records: tuple[CopyRecord, ...],
    source_root: Path,
    destination_folder: Path | None,
    filesystem: FileSystemPort,
    state: StateStore,
    profile_id: str,
    register_available: bool,
) -> FileClassification:
    if destination_folder is None:
        return FileClassification(FileClass.ABSENT)
    exact_record = next(
        (record for record in records if record.destination_name == source_name), None
    )
    exact_present = source_name in destination_names
    collision_name = next(
        (name for name in destination_names if comparison_key(name) == comparison_key(source_name)),
        None,
    )
    if not exact_present:
        if exact_record is not None:
            state.remove_copy_record(
                profile_id, exact_record.destination_folder, exact_record.destination_name
            )
        return (
            FileClassification(FileClass.FOREIGN, actual_name=collision_name)
            if collision_name is not None
            else FileClassification(FileClass.ABSENT)
        )
    if not register_available or exact_record is None:
        return FileClassification(FileClass.FOREIGN, actual_name=source_name)
    record = exact_record
    fingerprint = filesystem.fingerprint_file(source_root, destination_folder / source_name)
    is_verified = fingerprint.size == record.size and fingerprint.sha256 == record.sha256
    return FileClassification(
        FileClass.VERIFIED if is_verified else FileClass.MODIFIED,
        record,
        source_name,
    )


def _toggle_off(
    plan: TogglePlan,
    filesystem: FileSystemPort,
    state: StateStore,
    confirmed_modified: bool,
    logger: EventLogger | None,
) -> ToggleResult:
    destination = plan.destination_folder
    if destination is None:
        return ToggleResult(UseCaseStatus.ERROR, error_reason="destination disappeared")
    records = state.copy_records(plan.profile_id, str(destination))
    deleted: list[str] = []
    try:
        for index, target in enumerate(plan.targets):
            classification = target.classification
            record = classification.record
            if (
                classification.file_class not in {FileClass.VERIFIED, FileClass.MODIFIED}
                or record is None
            ):
                continue
            if index > 0 and _shared_by_another_selected_image(
                record,
                records,
                plan.image_name,
                plan.source_images,
                plan.source_sidecars,
                plan.source_root,
                filesystem,
            ):
                continue
            actual_name = classification.actual_name or record.destination_name
            if classification.file_class is FileClass.MODIFIED:
                if not confirmed_modified:
                    return ToggleResult(
                        UseCaseStatus.MODIFIED_CONFIRMATION_REQUIRED,
                        ToggleAction.TOGGLE_OFF_CONFIRM,
                        conflict_names=(actual_name,),
                    )
                filesystem.delete_modified_copy(plan.source_root, destination, actual_name)
            else:
                filesystem.delete_verified_file(
                    plan.source_root,
                    destination,
                    actual_name,
                    record.size,
                    record.sha256,
                )
            state.remove_copy_record(
                plan.profile_id, record.destination_folder, record.destination_name
            )
            deleted.append(actual_name)
        _safe_log(
            logger, LogLevel.INFO, LogEvent.DELETE, "managed copies removed", count=len(deleted)
        )
        return ToggleResult(UseCaseStatus.OK, ToggleAction.TOGGLE_OFF, tuple(deleted))
    except Exception as error:
        _safe_log(
            logger, LogLevel.ERROR, LogEvent.ERROR, "toggle off failed", reason=_reason(error)
        )
        return ToggleResult(
            UseCaseStatus.ERROR,
            ToggleAction.TOGGLE_OFF,
            tuple(deleted),
            error_reason=_reason(error),
        )


def _shared_by_another_selected_image(
    record: CopyRecord,
    records: tuple[CopyRecord, ...],
    current_image: str,
    source_images: tuple[str, ...],
    source_sidecars: tuple[str, ...],
    source_root: Path,
    filesystem: FileSystemPort,
) -> bool:
    for other_image in source_images:
        if other_image == current_image or record.destination_name not in sidecars_for_image(
            other_image, source_sidecars
        ):
            continue
        image_record = next(
            (
                candidate
                for candidate in records
                if candidate.source_name == other_image
                and candidate.destination_name == other_image
            ),
            None,
        )
        if image_record is None:
            continue
        try:
            metadata = filesystem.file_metadata(
                source_root,
                Path(image_record.destination_folder) / image_record.destination_name,
            )
        except Exception:
            return True
        if metadata is not None:
            return True
    return False


def _toggle_on(
    plan: TogglePlan,
    filesystem: FileSystemPort,
    state: StateStore,
    clock: Clock,
    logger: EventLogger | None,
) -> ToggleResult:
    destination = plan.destination_folder
    try:
        if destination is None:
            destination = filesystem.create_destination_folder(
                plan.source_root, plan.destination_name or ""
            )
        copy_targets = [plan.targets[0]] + [
            target
            for target in plan.targets[1:]
            if target.classification.file_class is FileClass.ABSENT
        ]
        source_fingerprints = {
            target.source_name: filesystem.fingerprint_file(
                plan.source_root, plan.source_root / target.source_name
            )
            for target in copy_targets
        }
        operation_id = uuid4().hex
        operation_files = tuple(
            OperationFileRecord(
                index,
                temp_file_name(operation_id, index),
                target.source_name,
                source_fingerprints[target.source_name].size,
                source_fingerprints[target.source_name].sha256,
            )
            for index, target in enumerate(copy_targets)
        )
        state.start_operation(
            operation_id, plan.profile_id, plan.destination_name or "", operation_files
        )
        finalized: list[OperationFileRecord] = []
        try:
            copies: list[CopyRecord] = []
            finalized_at = _timestamp(clock)
            for item, target in zip(operation_files, copy_targets, strict=True):
                copied = filesystem.copy_to_temp(
                    plan.source_root, destination, target.source_name, item.temp_name
                )
                expected = source_fingerprints[target.source_name]
                if copied.size != expected.size or copied.sha256 != expected.sha256:
                    raise FileSystemError(
                        FileSystemErrorReason.FILE_CHANGED,
                        path=plan.source_root / target.source_name,
                        detail="source changed during copy",
                    )
                current_names = filesystem.list_destination_names(plan.source_root, destination)
                if any(
                    comparison_key(name) == comparison_key(item.final_name)
                    for name in current_names
                ):
                    raise FileSystemError(
                        FileSystemErrorReason.NAME_CONFLICT,
                        path=destination / item.final_name,
                    )
                filesystem.finalize_temp_file(
                    plan.source_root, destination, item.temp_name, item.final_name
                )
                finalized.append(item)
                copies.append(
                    CopyRecord(
                        plan.profile_id,
                        str(plan.source_root),
                        target.source_name,
                        destination_folder_key(plan.source_root, destination.name),
                        item.final_name,
                        expected.size,
                        expected.sha256,
                        expected.mtime_ns,
                        finalized_at,
                    )
                )
            state.complete_operation(operation_id, copies)
            _safe_log(
                logger, LogLevel.INFO, LogEvent.COPY, "managed copies added", count=len(copies)
            )
            return ToggleResult(
                UseCaseStatus.OK,
                ToggleAction.TOGGLE_ON,
                tuple(item.final_name for item in operation_files),
            )
        except Exception as error:
            cleanup_ok = True
            try:
                present = set(filesystem.list_destination_names(plan.source_root, destination))
            except Exception:
                present = set()
                cleanup_ok = False
            for item in operation_files:
                if item.temp_name in present:
                    try:
                        filesystem.delete_own_temp_file(
                            plan.source_root, destination, item.temp_name
                        )
                    except Exception:
                        cleanup_ok = False
            for item in reversed(finalized):
                try:
                    filesystem.delete_verified_file(
                        plan.source_root,
                        destination,
                        item.final_name,
                        item.expected_size,
                        item.expected_sha256,
                    )
                except Exception:
                    cleanup_ok = False
            if cleanup_ok:
                try:
                    state.mark_rolled_back(operation_id)
                except Exception:
                    cleanup_ok = False
            _safe_log(
                logger,
                LogLevel.ERROR,
                LogEvent.ROLLBACK,
                "toggle on failed",
                reason=_reason(error),
                cleanup_complete=cleanup_ok,
            )
            return ToggleResult(
                UseCaseStatus.ERROR,
                ToggleAction.TOGGLE_ON,
                error_reason=_reason(error),
            )
    except Exception as error:
        _safe_log(
            logger, LogLevel.ERROR, LogEvent.ERROR, "toggle on setup failed", reason=_reason(error)
        )
        return ToggleResult(
            UseCaseStatus.ERROR, ToggleAction.TOGGLE_ON, error_reason=_reason(error)
        )


def _timestamp(clock: Clock) -> str:
    value = clock.now_utc()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware timestamp")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _failed_plan(
    profile: ProfileRecord, source_root: Path, image_name: str, slot_index: int, detail: str
) -> TogglePlan:
    return TogglePlan(
        profile.id,
        source_root,
        image_name,
        slot_index,
        profile.slots[slot_index].destination_name
        if 0 <= slot_index < len(profile.slots)
        else None,
        None,
        (),
        None,
        UseCaseStatus.ERROR,
        detail,
    )


def _conflict_names(plan: TogglePlan) -> tuple[str, ...]:
    names = tuple(
        target.classification.actual_name or target.source_name
        for target in plan.targets
        if target.classification.file_class in {FileClass.FOREIGN, FileClass.MODIFIED}
    )
    return names or ((plan.detail,) if plan.detail else ())


def _reason(error: Exception) -> str:
    return str(error.reason) if isinstance(error, FileSystemError) else type(error).__name__


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
