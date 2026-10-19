"""Non-destructive copy-register reconciliation (FR-070)."""

from pathlib import Path

from vuechoixgarde.app.results import ReconcileItem, ReconcileReport
from vuechoixgarde.core.toggle import FileClass
from vuechoixgarde.ports.errors import FileSystemError
from vuechoixgarde.ports.filesystem import FileSystemPort
from vuechoixgarde.ports.log import EventLogger, LogEvent, LogLevel
from vuechoixgarde.ports.state import StateStore


def reconcile(
    state: StateStore,
    filesystem: FileSystemPort,
    profile_id: str,
    source_root: Path,
    *,
    automatic: bool,
    logger: EventLogger | None = None,
) -> ReconcileReport:
    """Check registered copies, removing stale rows but never modifying files."""
    items: list[ReconcileItem] = []
    removed = verified = modified = errors = 0
    try:
        records = state.copy_records(profile_id)
    except Exception:
        _safe_log(logger, LogLevel.ERROR, "register unavailable", error_count=1)
        return ReconcileReport((), 0, 0, 0, 1, automatic)

    for record in records:
        try:
            metadata = filesystem.file_metadata(
                source_root, Path(record.destination_folder) / record.destination_name
            )
            if metadata is None:
                state.remove_copy_record(
                    profile_id, record.destination_folder, record.destination_name
                )
                removed += 1
                items.append(ReconcileItem(record, FileClass.ABSENT))
                continue
            if metadata.size != record.size:
                modified += 1
                items.append(ReconcileItem(record, FileClass.MODIFIED))
                continue
            if automatic and metadata.mtime_ns == record.mtime_ns:
                verified += 1
                items.append(ReconcileItem(record, FileClass.VERIFIED))
                continue
            fingerprint = filesystem.fingerprint_file(
                source_root, Path(record.destination_folder) / record.destination_name
            )
            file_class = (
                FileClass.VERIFIED
                if fingerprint.size == record.size and fingerprint.sha256 == record.sha256
                else FileClass.MODIFIED
            )
            if file_class is FileClass.VERIFIED:
                verified += 1
            else:
                modified += 1
            items.append(ReconcileItem(record, file_class))
        except Exception as error:
            errors += 1
            items.append(ReconcileItem(record, None, _error_reason(error)))

    report = ReconcileReport(tuple(items), removed, verified, modified, errors, automatic)
    _safe_log(
        logger,
        LogLevel.INFO if errors == 0 else LogLevel.WARNING,
        "reconciliation completed",
        automatic=automatic,
        removed=removed,
        verified=verified,
        modified=modified,
        error_count=errors,
    )
    return report


def _error_reason(error: Exception) -> str:
    if isinstance(error, FileSystemError):
        return str(error.reason)
    return type(error).__name__


def _safe_log(
    logger: EventLogger | None,
    level: LogLevel,
    message: str,
    **fields: object,
) -> None:
    if logger is None:
        return
    try:
        logger.log(level, LogEvent.RECONCILE, message, **fields)
    except Exception:
        return
