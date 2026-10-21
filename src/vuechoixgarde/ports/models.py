"""Immutable data values exchanged through Phase 3 ports."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from vuechoixgarde.core.slots import Slot
from vuechoixgarde.ports.errors import SettingsErrorReason, StateStoreErrorReason


@dataclass(frozen=True)
class FileFingerprint:
    """Content and modification-time evidence for a file."""

    size: int
    sha256: str
    mtime_ns: int


@dataclass(frozen=True)
class FileMetadata:
    """Size and modification-time metadata for a regular file."""

    size: int
    mtime_ns: int


@dataclass(frozen=True)
class SourceScan:
    """One top-level source scan, preserving exact names from the directory listing."""

    images: tuple[str, ...]
    sidecar_candidates: tuple[str, ...]
    directories: tuple[str, ...]


class DestinationStatus(StrEnum):
    """Outcome of resolving a configured destination folder."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    FAULTY = "faulty"


class DestinationFault(StrEnum):
    """Reasons a configured destination folder cannot be safely used."""

    FILE = "file"
    LINK = "link"
    OUTSIDE = "outside"
    AMBIGUOUS = "ambiguous"


class EntryKind(StrEnum):
    """No-follow classification of an entry in a destination folder."""

    FILE = "file"
    DIRECTORY = "directory"
    LINK = "link"
    OTHER = "other"


@dataclass(frozen=True)
class DestinationEntry:
    """One exact direct-child entry in a destination folder."""

    name: str
    kind: EntryKind


@dataclass(frozen=True)
class DestinationResolution:
    """Resolution result; `exact_name` is populated only for FOUND."""

    status: DestinationStatus
    exact_name: str | None = None
    reason: DestinationFault | None = None


@dataclass(frozen=True)
class Settings:
    """Validated persisted global preferences and the global slot template."""

    schema_version: int
    language: str
    sound_enabled: bool
    sort_direction: str
    reopen_last_folder: bool
    last_folder: str | None
    global_slot_template: tuple[Slot, ...]
    learned_key_labels: tuple[tuple[str, str], ...]


class LoadStatus(StrEnum):
    """Common result status for app-data loading."""

    LOADED = "loaded"
    CREATED_DEFAULTS = "created_defaults"
    DAMAGED = "damaged"


@dataclass(frozen=True)
class SettingsLoadResult:
    """Settings load outcome; damaged input is never replaced during loading."""

    status: LoadStatus
    settings: Settings | None = None
    reason: SettingsErrorReason | None = None
    detail: str | None = None


@dataclass(frozen=True)
class StateLoadResult:
    """State database load outcome and whether the copy register is usable."""

    status: LoadStatus
    register_available: bool
    reason: StateStoreErrorReason | None = None
    detail: str | None = None


@dataclass(frozen=True)
class ProfileRecord:
    """A source-folder profile and its immutable ordered slots."""

    id: str
    folder_identity: str
    display_path: str
    created_at: str
    updated_at: str
    slots: tuple[Slot, ...]


@dataclass(frozen=True)
class CopyRecord:
    """A persisted managed copy with enough evidence to verify deletion."""

    profile_id: str
    source_folder: str
    source_name: str
    destination_folder: str
    destination_name: str
    size: int
    sha256: str
    mtime_ns: int
    created_at: str


@dataclass(frozen=True)
class OperationFileRecord:
    """One journaled temp/final file and its expected content fingerprint."""

    index: int
    temp_name: str
    final_name: str
    expected_size: int
    expected_sha256: str


class OperationState(StrEnum):
    """Final or in-progress state of a journaled operation."""

    STARTED = "started"
    DONE = "done"
    ROLLED_BACK = "rolled_back"
    RECOVERED = "recovered"


@dataclass(frozen=True)
class OperationRecord:
    """A journal row and its ordered child file rows."""

    id: str
    profile_id: str
    destination_name: str
    state: OperationState
    started_at: str
    updated_at: str
    files: tuple[OperationFileRecord, ...]


class FolderRenameState(StrEnum):
    """State of a journaled destination-folder rename."""

    STARTED = "started"
    DONE = "done"
    ROLLED_BACK = "rolled_back"
    RECOVERED = "recovered"


@dataclass(frozen=True)
class FolderRenameRecord:
    """A folder-rename journal row, including the slots to restore after a crash."""

    id: str
    profile_id: str
    old_folder: str
    new_folder: str
    intermediate_folder: str | None
    state: FolderRenameState
    started_at: str
    updated_at: str
    target_slots: tuple[Slot, ...] = ()


@dataclass(frozen=True)
class ProfileIdentity:
    """New resolved identity and display path for explicit profile reassignment."""

    folder_identity: str
    display_path: Path


@dataclass(frozen=True)
class Timestamp:
    """UTC timestamp value when a strongly typed wrapper is useful at port edges."""

    value: datetime
