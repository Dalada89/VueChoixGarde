"""Recover only files named by unfinished operations for the current profile."""

from pathlib import Path

from vuechoixgarde.app.results import RecoveryReport
from vuechoixgarde.ports.filesystem import FileSystemPort
from vuechoixgarde.ports.log import EventLogger, LogEvent, LogLevel
from vuechoixgarde.ports.models import DestinationStatus
from vuechoixgarde.ports.state import StateStore


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
