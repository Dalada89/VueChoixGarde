"""Immutable, UI-neutral values returned by Phase 4 application use cases."""

from dataclasses import dataclass
from enum import StrEnum

from vuechoixgarde.core.toggle import FileClass
from vuechoixgarde.ports.models import CopyRecord, ProfileRecord, Settings, SourceScan


class FolderManagementReason(StrEnum):
    """Stable folder-rename outcomes for translation at the UI boundary."""

    NAME_OCCUPIED = "name_occupied"
    INVALID_NAME = "invalid_name"
    OLD_FOLDER_FAULTY = "old_folder_faulty"
    RENAME_FAILED = "rename_failed"
    ROLLBACK_FAILED = "rollback_failed"
    RECOVERY_FAILED = "recovery_failed"
    UNAVAILABLE = "unavailable"


class FolderManagementError(Exception):
    """UI-neutral folder-management failure with stable reason and safe name values."""

    def __init__(
        self,
        reason: FolderManagementReason,
        *,
        old_name: str | None = None,
        new_name: str | None = None,
        names: tuple[str, ...] = (),
    ) -> None:
        self.reason = reason
        self.old_name = old_name
        self.new_name = new_name
        self.names = names
        super().__init__(reason.value)


@dataclass(frozen=True)
class FolderRename:
    """A user-requested rename from a saved slot name to its new exact name."""

    old_name: str
    new_name: str


class FolderDeletionCase(StrEnum):
    """Safe classification presented before removing or detaching a destination."""

    DELETABLE = "deletable"
    FOREIGN_ENTRIES = "foreign_entries"
    MISSING = "missing"
    FAULTY = "faulty"


class FolderDeletionStatus(StrEnum):
    """Outcome of a destination-folder delete/detach request."""

    DELETED = "deleted"
    DETACHED = "detached"
    REMOVED_INFO = "removed_info"
    PARTIAL = "partial"
    CHECK_CHANGED = "check_changed"


@dataclass(frozen=True)
class FolderDeletionCheck:
    """Fingerprint-bound, immutable confirmation data for one destination slot."""

    case: FolderDeletionCase
    slot_index: int
    folder_name: str
    managed_names: tuple[str, ...]
    foreign_names: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True)
class FolderDeletionResult:
    """Outcome plus the latest check, if a confirmation must be repeated."""

    status: FolderDeletionStatus
    check: FolderDeletionCheck
    deleted_count: int = 0
    error_reason: str | None = None


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
    recovery_pending: bool = False
