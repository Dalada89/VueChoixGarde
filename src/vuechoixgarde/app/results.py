"""Immutable, UI-neutral values returned by Phase 4 application use cases."""

from dataclasses import dataclass
from enum import StrEnum

from vuechoixgarde.core.toggle import FileClass
from vuechoixgarde.ports.models import CopyRecord, ProfileRecord, Settings, SourceScan


class SlotState(StrEnum):
    """Current slot state that a presentation layer can translate."""

    NO_DESTINATION = "no_destination"
    READY = "ready"
    CHECKING = "checking"
    SELECTED = "selected"
    MODIFIED = "modified"
    CONFLICT = "conflict"
    FAULTY = "faulty"


class UseCaseStatus(StrEnum):
    """Stable outcome categories independent of UI wording."""

    OK = "ok"
    BUSY = "busy"
    CANCELLED = "cancelled"
    NAME_REQUIRED = "name_required"
    CONFLICT = "conflict"
    FAULTY = "faulty"
    MODIFIED_CONFIRMATION_REQUIRED = "modified_confirmation_required"
    ERROR = "error"


@dataclass(frozen=True)
class FileClassification:
    """Classification of one destination filename against the copy register."""

    file_class: FileClass
    record: CopyRecord | None = None
    actual_name: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class ReconcileItem:
    """Immutable reconciliation result for one managed copy."""

    record: CopyRecord
    file_class: FileClass | None
    error: str | None = None


@dataclass(frozen=True)
class ReconcileReport:
    """One complete automatic or manual reconciliation pass."""

    items: tuple[ReconcileItem, ...]
    removed: int
    verified: int
    modified: int
    errors: int
    automatic: bool


@dataclass(frozen=True)
class RecoveryReport:
    """Summary of journal entries cleaned after an interrupted operation."""

    recovered: tuple[str, ...]
    pending: tuple[str, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class StartupReport:
    """Startup data status with damaged-store decisions left to the caller."""

    settings_status: str
    state_status: str
    settings: Settings | None
    settings_damaged: bool
    state_damaged: bool
    register_available: bool
    accepted_defaults: bool = False


@dataclass(frozen=True)
class SessionSnapshot:
    """Read model exposed by a folder session; files and slot state are immutable."""

    source_path: str
    folder_identity: str
    profile: ProfileRecord
    scan: SourceScan
    current_name: str | None
    image_index: int
    image_count: int
    descending: bool
    boundary_reached: bool
    checking: bool
    register_available: bool
    reconciled: tuple[ReconcileItem, ...]
