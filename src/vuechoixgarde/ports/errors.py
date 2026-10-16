"""Typed, translatable boundary errors shared by application ports (FR-090)."""

from enum import StrEnum
from pathlib import Path


class FileSystemErrorReason(StrEnum):
    """Stable reasons for source, destination, copy and delete failures."""

    SOURCE_MISSING = "source_missing"
    SOURCE_NOT_DIRECTORY = "source_not_directory"
    SOURCE_NOT_READABLE = "source_not_readable"
    PATH_OUTSIDE_ROOT = "path_outside_root"
    DESTINATION_FILE = "destination_file"
    DESTINATION_LINK = "destination_link"
    DESTINATION_OUTSIDE = "destination_outside"
    AMBIGUOUS = "ambiguous"
    INVALID_NAME = "invalid_name"
    NAME_CONFLICT = "name_conflict"
    INVALID_TEMP_NAME = "invalid_temp_name"
    COPY_FAILED = "copy_failed"
    FILE_CHANGED = "file_changed"
    DELETE_REFUSED = "delete_refused"
    FINALIZE_UNSUPPORTED = "finalize_unsupported"
    IO_ERROR = "io_error"


class FolderLockErrorReason(StrEnum):
    """Stable lock acquisition failure reasons."""

    FOLDER_LOCKED = "folder_locked"
    LOCK_IO_ERROR = "lock_io_error"


class SettingsErrorReason(StrEnum):
    """Stable settings validation and persistence reasons."""

    INVALID_JSON = "invalid_json"
    INVALID_SETTINGS = "invalid_settings"
    IO_ERROR = "io_error"


class StateStoreErrorReason(StrEnum):
    """Stable state database and repository failure reasons."""

    INVALID_DATABASE = "invalid_database"
    INTEGRITY_FAILURE = "integrity_failure"
    UNSUPPORTED_VERSION = "unsupported_version"
    MIGRATION_FAILURE = "migration_failure"
    PROFILE_NOT_FOUND = "profile_not_found"
    OPERATION_NOT_FOUND = "operation_not_found"
    INVALID_DATA = "invalid_data"
    IO_ERROR = "io_error"


class PortError(Exception):
    """Base class for port-level failures with a stable reason for translation."""

    def __init__(self, reason: StrEnum, *, path: Path | None = None, detail: str | None = None):
        self.reason = reason
        self.path = path
        self.detail = detail
        message = str(reason)
        if path is not None:
            message = f"{message}: {path}"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)


class FileSystemError(PortError):
    """A typed file-system operation failure."""


class FolderLockError(PortError):
    """A typed per-source-folder lock failure."""


class SettingsStoreError(PortError):
    """A typed settings file validation or persistence failure."""


class StateStoreError(PortError):
    """A typed SQLite state repository failure."""
