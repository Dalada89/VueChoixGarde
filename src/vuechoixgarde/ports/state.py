"""SQLite-backed profile, copy-register, and operation-journal port contract."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from vuechoixgarde.core.slots import Slot
from vuechoixgarde.ports.models import (
    CopyRecord,
    FolderRenameRecord,
    OperationFileRecord,
    OperationRecord,
    ProfileRecord,
    StateLoadResult,
)


class StateStore(Protocol):
    """Persistent profile, register, and journal operations needed by Phase 4."""

    def load(self) -> StateLoadResult:
        """Open/migrate the schema or report damaged data without modifying it."""
        ...

    def reset_damaged(self) -> Path | None:
        """Quarantine damaged SQLite state and establish a new empty schema."""
        ...

    def get_profile_by_identity(self, folder_identity: str) -> ProfileRecord | None:
        """Find a profile by canonical source-folder identity."""
        ...

    def list_profiles(self) -> tuple[ProfileRecord, ...]:
        """Return all persisted profiles in deterministic creation order."""
        ...

    def delete_profile(self, profile_id: str) -> None:
        """Delete profile metadata, register, and closed journal rows, never image files."""
        ...

    def create_profile_from_template(
        self, folder_identity: str, display_path: str, slots: Sequence[Slot]
    ) -> ProfileRecord:
        """Create an independent profile copy from the supplied template slots (FR-041)."""
        ...

    def replace_profile_slots(self, profile_id: str, slots: Sequence[Slot]) -> ProfileRecord:
        """Replace all profile slots atomically and return the updated profile."""
        ...

    def start_folder_renames(
        self, profile_id: str, records: tuple[FolderRenameRecord, ...]
    ) -> None:
        """Persist all started rename journal rows for one profile atomically."""
        ...

    def complete_folder_renames(
        self,
        profile_id: str,
        rename_ids: tuple[str, ...],
        folder_updates: tuple[tuple[str, str], ...],
        removed_folders: tuple[str, ...],
        slots: tuple[Slot, ...],
    ) -> None:
        """Update register, slots, and rename journal rows atomically."""
        ...

    def mark_folder_renames_rolled_back(self, rename_ids: tuple[str, ...]) -> None:
        """Mark started rename journal rows as rolled back."""
        ...

    def mark_folder_rename_recovered(self, rename_id: str) -> None:
        """Mark a started rename journal row as recovered."""
        ...

    def unfinished_folder_renames(self) -> tuple[FolderRenameRecord, ...]:
        """Return rename journal rows still in the started state."""
        ...

    def remove_destination_folder_records(
        self, profile_id: str, destination_folder: str, slots: tuple[Slot, ...]
    ) -> int:
        """Remove all records for a folder and replace profile slots atomically."""
        ...

    def remove_copy_records(
        self, profile_id: str, destination_folder: str, names: tuple[str, ...]
    ) -> None:
        """Remove the selected copy register records for one destination folder."""
        ...

    def orphaned_profiles(self, folder_exists: Callable[[str], bool]) -> tuple[ProfileRecord, ...]:
        """Return profiles whose folder is absent according to the caller's predicate."""
        ...

    def reassign_profile(
        self,
        profile_id: str,
        folder_identity: str,
        display_path: str,
        *,
        replace_profile_id: str | None = None,
    ) -> ProfileRecord:
        """Reassign a profile and register paths transactionally (FR-042)."""
        ...

    def copy_records(
        self,
        profile_id: str,
        destination_folder: str | None = None,
        source_name: str | None = None,
    ) -> tuple[CopyRecord, ...]:
        """Read copy-register entries by profile and optional folder/source name."""
        ...

    def remove_copy_record(
        self, profile_id: str, destination_folder: str, destination_name: str
    ) -> None:
        """Remove one stale or successfully-deleted register entry."""
        ...

    def start_operation(
        self,
        operation_id: str,
        profile_id: str,
        destination_name: str,
        files: Sequence[OperationFileRecord],
    ) -> OperationRecord:
        """Commit the journal header and all file rows before file creation (FR-046)."""
        ...

    def complete_operation(self, operation_id: str, copies: Sequence[CopyRecord]) -> None:
        """Insert register rows and set `done` within one transaction."""
        ...

    def mark_rolled_back(self, operation_id: str) -> None:
        """Mark an operation rolled back."""
        ...

    def mark_recovered(self, operation_id: str) -> None:
        """Mark a recovered operation as closed."""
        ...

    def unfinished_operations(self) -> tuple[OperationRecord, ...]:
        """Return journal entries still in the `started` state."""
        ...
