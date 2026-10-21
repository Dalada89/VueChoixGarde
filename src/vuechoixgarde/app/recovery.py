"""Recover only files named by unfinished operations for the current profile."""

from pathlib import Path

from vuechoixgarde.app.results import RecoveryReport
from vuechoixgarde.core.destination import destination_folder_key
from vuechoixgarde.core.folder_names import validate_folder_name
from vuechoixgarde.ports.filesystem import FileSystemPort
from vuechoixgarde.ports.log import EventLogger, LogEvent, LogLevel
from vuechoixgarde.ports.models import (
    DestinationStatus,
    FolderRenameRecord,
)
from vuechoixgarde.ports.state import StateStore


def recover_folder_renames(
    state: StateStore,
    filesystem: FileSystemPort,
    profile_id: str,
    source_root: Path,
    *,
    logger: EventLogger | None = None,
) -> RecoveryReport:
    """Recover started destination-folder renames before copy recovery or reconciliation."""
    recovered: list[str] = []
    pending: list[str] = []
    errors: list[str] = []
    try:
        records = tuple(
            record
            for record in state.unfinished_folder_renames()
            if record.profile_id == profile_id
        )
    except Exception as error:
        _safe_log(
            logger, LogLevel.ERROR, "rename journal read failed", code="rename_recovery_failed"
        )
        return RecoveryReport((), (), (type(error).__name__,))

    batches: list[list[FolderRenameRecord]] = []
    for record in records:
        batch = next(
            (items for items in batches if items[0].target_slots == record.target_slots), None
        )
        if batch is None:
            batches.append([record])
        else:
            batch.append(record)

    for batch in batches:
        try:
            classified: list[tuple[FolderRenameRecord, str, str, str | None, str]] = []
            names = filesystem.list_destination_names(source_root, source_root)
            for record in batch:
                old_name = Path(record.old_folder).name
                new_name = Path(record.new_folder).name
                intermediate_name = (
                    Path(record.intermediate_folder).name
                    if record.intermediate_folder is not None
                    else None
                )
                _validate_journal_key(source_root, record.old_folder, old_name)
                _validate_journal_key(source_root, record.new_folder, new_name)
                if record.intermediate_folder is not None:
                    _validate_journal_key(
                        source_root, record.intermediate_folder, intermediate_name
                    )
                old_exists = old_name in names
                new_exists = new_name in names
                intermediate_exists = intermediate_name is not None and intermediate_name in names
                for name, exists in (
                    (old_name, old_exists),
                    (new_name, new_exists),
                    (intermediate_name, intermediate_exists),
                ):
                    if exists and name is not None:
                        resolution = filesystem.resolve_destination_folder(source_root, name)
                        if (
                            resolution.status is not DestinationStatus.FOUND
                            or resolution.exact_name != name
                        ):
                            raise ValueError("journal entry is not a verified direct folder")
                if old_exists and not intermediate_exists and not new_exists:
                    state_name = "untouched"
                elif not old_exists and not intermediate_exists and new_exists:
                    state_name = "completed"
                elif not old_exists and intermediate_exists and not new_exists:
                    state_name = "intermediate"
                elif not old_exists and not intermediate_exists and not new_exists:
                    state_name = "missing"
                else:
                    raise ValueError("inconsistent folder state")
                classified.append((record, old_name, new_name, intermediate_name, state_name))

            states = {entry[4] for entry in classified}
            rename_ids = tuple(entry[0].id for entry in classified)
            if states <= {"untouched"}:
                state.mark_folder_renames_rolled_back(rename_ids)
                recovered.extend(rename_ids)
            elif states <= {"completed", "missing"}:
                updates = tuple(
                    (entry[0].old_folder, entry[0].new_folder)
                    for entry in classified
                    if entry[4] == "completed"
                )
                removed = tuple(
                    entry[0].old_folder for entry in classified if entry[4] == "missing"
                )
                state.complete_folder_renames(
                    profile_id, (), updates, removed, batch[0].target_slots
                )
                for record in batch:
                    state.mark_folder_rename_recovered(record.id)
                    recovered.append(record.id)
                for entry in classified:
                    if entry[4] == "missing":
                        _safe_log(
                            logger,
                            LogLevel.WARNING,
                            "renamed folder disappeared during recovery",
                            code="rename_folder_missing",
                            old_name=entry[1],
                            new_name=entry[2],
                        )
            else:
                for _record, old_name, new_name, intermediate_name, state_name in reversed(
                    classified
                ):
                    if state_name == "completed":
                        filesystem.rename_destination_folder(source_root, new_name, old_name)
                    elif state_name == "intermediate":
                        assert intermediate_name is not None
                        filesystem.rename_destination_folder(
                            source_root, intermediate_name, old_name
                        )
                state.mark_folder_renames_rolled_back(rename_ids)
                recovered.extend(rename_ids)
        except Exception as error:
            pending.extend(record.id for record in batch)
            errors.extend(f"{record.id}:{type(error).__name__}" for record in batch)
            first = batch[0]
            _safe_log(
                logger,
                LogLevel.ERROR,
                "rename recovery failed",
                code="rename_recovery_failed",
                old_name=Path(first.old_folder).name,
                new_name=Path(first.new_folder).name,
            )

    _safe_log(
        logger,
        LogLevel.INFO if not errors and not pending else LogLevel.WARNING,
        "folder rename recovery completed",
        code="rename_recovery_completed",
        recovered_count=len(recovered),
        pending_count=len(pending),
        error_count=len(errors),
    )
    return RecoveryReport(tuple(recovered), tuple(pending), tuple(errors))


def _validate_journal_key(source_root: Path, value: str, name: str | None) -> None:
    if (
        name is None
        or validate_folder_name(name) is not None
        or Path(value).parent != source_root
        or value != destination_folder_key(source_root, name)
    ):
        raise ValueError("invalid rename journal path")


def recover_operations(
    state: StateStore,
    filesystem: FileSystemPort,
    profile_id: str,
    source_root: Path,
    *,
    logger: EventLogger | None = None,
) -> RecoveryReport:
    """Clean unfinished journal files without touching unlisted destination files."""
    recovered: list[str] = []
    pending: list[str] = []
    errors: list[str] = []
    try:
        operations = tuple(
            operation
            for operation in state.unfinished_operations()
            if operation.profile_id == profile_id
        )
    except Exception as error:
        _safe_log(logger, LogLevel.ERROR, "recovery could not read journal", errors=1)
        return RecoveryReport((), (), (type(error).__name__,))

    for operation in operations:
        try:
            resolution = filesystem.resolve_destination_folder(
                source_root, operation.destination_name
            )
            if resolution.status is DestinationStatus.NOT_FOUND:
                state.mark_recovered(operation.id)
                recovered.append(operation.id)
                continue
            if resolution.status is DestinationStatus.FAULTY or resolution.exact_name is None:
                pending.append(operation.id)
                continue

            destination = source_root / resolution.exact_name
            names = filesystem.list_destination_names(source_root, destination)
            present = set(names)
            safe_to_close = True
            for item in operation.files:
                temp_exists = item.temp_name in present
                final_exists = item.final_name in present
                if temp_exists:
                    filesystem.delete_own_temp_file(source_root, destination, item.temp_name)
                if not final_exists:
                    continue
                if temp_exists:
                    safe_to_close = False
                    continue
                fingerprint = filesystem.fingerprint_file(
                    source_root, destination / item.final_name
                )
                if (
                    fingerprint.size == item.expected_size
                    and fingerprint.sha256 == item.expected_sha256
                ):
                    filesystem.delete_verified_file(
                        source_root,
                        destination,
                        item.final_name,
                        item.expected_size,
                        item.expected_sha256,
                    )
                else:
                    safe_to_close = False
            if safe_to_close:
                state.mark_recovered(operation.id)
                recovered.append(operation.id)
            else:
                pending.append(operation.id)
        except Exception as error:
            errors.append(f"{operation.id}:{type(error).__name__}")
            pending.append(operation.id)

    level = LogLevel.INFO if not errors and not pending else LogLevel.WARNING
    _safe_log(
        logger,
        level,
        "recovery completed",
        recovered_count=len(recovered),
        pending_count=len(pending),
        error_count=len(errors),
    )
    return RecoveryReport(tuple(recovered), tuple(pending), tuple(errors))


def _safe_log(
    logger: EventLogger | None,
    level: LogLevel,
    message: str,
    **fields: object,
) -> None:
    if logger is None:
        return
    try:
        logger.log(level, LogEvent.RECOVERY, message, **fields)
    except Exception:
        return
