"""Protocol-conforming application fakes and filesystem fault injection."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from vuechoixgarde.core.slots import Slot
from vuechoixgarde.fsops.filesystem import LocalFileSystem
from vuechoixgarde.ports.clock import Clock
from vuechoixgarde.ports.errors import (
    FileSystemError,
    FileSystemErrorReason,
    FolderLockError,
    FolderLockErrorReason,
)
from vuechoixgarde.ports.lock import FolderLock, FolderLockFactory
from vuechoixgarde.ports.log import EventLogger, LogEvent, LogLevel
from vuechoixgarde.ports.models import (
    CopyRecord,
    FileFingerprint,
    LoadStatus,
    OperationFileRecord,
    OperationRecord,
    OperationState,
    ProfileRecord,
    Settings,
    SettingsLoadResult,
    StateLoadResult,
)
from vuechoixgarde.ports.settings import SettingsStore
from vuechoixgarde.ports.state import StateStore


@dataclass
class FakeClock(Clock):
    """Return a stable timezone-aware timestamp for deterministic tests."""

    instant: datetime = field(default_factory=lambda: datetime(2025, 1, 2, tzinfo=UTC))

    def now_utc(self) -> datetime:
        return self.instant


@dataclass
class FakeEventLogger(EventLogger):
    """Collect structured log calls without writing to disk."""

    entries: list[tuple[LogLevel, LogEvent, str, dict[str, object]]] = field(default_factory=list)

    def log(self, level: LogLevel, event: LogEvent, message: str, **fields: object) -> None:
        self.entries.append((level, event, message, fields))


class FakeFolderLock(FolderLock):
    def __init__(self, identity: str, held: set[str]) -> None:
        self.identity = identity
        self.held = held
        self.acquired = False

    def acquire(self) -> None:
        if self.identity in self.held:
            raise FolderLockError(FolderLockErrorReason.FOLDER_LOCKED)
        self.held.add(self.identity)
        self.acquired = True

    def release(self) -> None:
        if self.acquired:
            self.held.discard(self.identity)
            self.acquired = False

    def __enter__(self) -> FakeFolderLock:
        self.acquire()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: Any
    ) -> None:
        self.release()


class FakeFolderLockFactory(FolderLockFactory):
    def __init__(self) -> None:
        self.held: set[str] = set()

    def create(self, identity: str) -> FakeFolderLock:
        return FakeFolderLock(identity, self.held)


class InMemorySettingsStore(SettingsStore):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.damaged = False
        self.quarantined = False

    def load(self, locale_name: str | None = None) -> SettingsLoadResult:
        if self.damaged:
            return SettingsLoadResult(LoadStatus.DAMAGED)
        return SettingsLoadResult(LoadStatus.LOADED, self.settings)

    def save(self, settings: Settings) -> None:
        self.settings = settings

    def reset_damaged(self) -> Path | None:
        self.quarantined = self.damaged
        self.damaged = False
        return Path("quarantine.json") if self.quarantined else None


class InMemoryStateStore(StateStore):
    """Store protocol values in memory for deterministic application unit tests."""

    def __init__(self, clock: Clock | None = None) -> None:
        self.clock = clock or FakeClock()
        self.profiles: dict[str, ProfileRecord] = {}
        self.records: list[CopyRecord] = []
        self.operations: dict[str, OperationRecord] = {}

    def load(self) -> StateLoadResult:
        return StateLoadResult(LoadStatus.LOADED, True)

    def reset_damaged(self) -> Path | None:
        self.profiles.clear()
        self.records.clear()
        self.operations.clear()
        return Path("quarantine.db")

    def get_profile_by_identity(self, folder_identity: str) -> ProfileRecord | None:
        return next(
            (
                profile
                for profile in self.profiles.values()
                if profile.folder_identity == folder_identity
            ),
            None,
        )

    def list_profiles(self) -> tuple[ProfileRecord, ...]:
        return tuple(self.profiles.values())

    def delete_profile(self, profile_id: str) -> None:
        self._profile(profile_id)
        self.profiles.pop(profile_id)
        self.records = [record for record in self.records if record.profile_id != profile_id]
        self.operations = {
            operation_id: operation
            for operation_id, operation in self.operations.items()
            if operation.profile_id != profile_id
        }

    def create_profile_from_template(
        self, folder_identity: str, display_path: str, slots: Sequence[Slot]
    ) -> ProfileRecord:
        if self.get_profile_by_identity(folder_identity) is not None:
            raise ValueError("profile identity already exists")
        now = self._timestamp()
        profile = ProfileRecord(uuid4().hex, folder_identity, display_path, now, now, tuple(slots))
        self.profiles[profile.id] = profile
        return profile

    def replace_profile_slots(self, profile_id: str, slots: Sequence[Slot]) -> ProfileRecord:
        profile = self._profile(profile_id)
        updated = replace(profile, slots=tuple(slots), updated_at=self._timestamp())
        self.profiles[profile_id] = updated
        return updated

    def orphaned_profiles(self, folder_exists: Callable[[str], bool]) -> tuple[ProfileRecord, ...]:
        return tuple(
            profile for profile in self.profiles.values() if not folder_exists(profile.display_path)
        )

    def reassign_profile(
        self,
        profile_id: str,
        folder_identity: str,
        display_path: str,
        *,
        replace_profile_id: str | None = None,
    ) -> ProfileRecord:
        collision = self.get_profile_by_identity(folder_identity)
        if collision is not None and collision.id != profile_id:
            if collision.id != replace_profile_id:
                raise ValueError("profile identity already exists")
            if any(record.profile_id == collision.id for record in self.records):
                raise ValueError("target profile has copy records")
            self.delete_profile(collision.id)
        profile = self._profile(profile_id)
        updated = replace(
            profile,
            folder_identity=folder_identity,
            display_path=display_path,
            updated_at=self._timestamp(),
        )
        self.profiles[profile_id] = updated
        self.records = [
            replace(record, source_folder=display_path)
            if record.profile_id == profile_id
            else record
            for record in self.records
        ]
        return updated

    def copy_records(
        self,
        profile_id: str,
        destination_folder: str | None = None,
        source_name: str | None = None,
    ) -> tuple[CopyRecord, ...]:
        return tuple(
            record
            for record in self.records
            if record.profile_id == profile_id
            and (destination_folder is None or record.destination_folder == destination_folder)
            and (source_name is None or record.source_name == source_name)
        )

    def remove_copy_record(
        self, profile_id: str, destination_folder: str, destination_name: str
    ) -> None:
        self.records = [
            record
            for record in self.records
            if not (
                record.profile_id == profile_id
                and record.destination_folder == destination_folder
                and record.destination_name == destination_name
            )
        ]

    def start_operation(
        self,
        operation_id: str,
        profile_id: str,
        destination_name: str,
        files: Sequence[OperationFileRecord],
    ) -> OperationRecord:
        now = self._timestamp()
        operation = OperationRecord(
            operation_id,
            profile_id,
            destination_name,
            OperationState.STARTED,
            now,
            now,
            tuple(files),
        )
        self.operations[operation_id] = operation
        return operation

    def complete_operation(self, operation_id: str, copies: Sequence[CopyRecord]) -> None:
        operation = self._operation(operation_id)
        self.records.extend(copies)
        self.operations[operation_id] = replace(
            operation, state=OperationState.DONE, updated_at=self._timestamp()
        )

    def mark_rolled_back(self, operation_id: str) -> None:
        self._mark(operation_id, OperationState.ROLLED_BACK)

    def mark_recovered(self, operation_id: str) -> None:
        self._mark(operation_id, OperationState.RECOVERED)

    def unfinished_operations(self) -> tuple[OperationRecord, ...]:
        return tuple(
            operation
            for operation in self.operations.values()
            if operation.state is OperationState.STARTED
        )

    def _profile(self, profile_id: str) -> ProfileRecord:
        try:
            return self.profiles[profile_id]
        except KeyError as error:
            raise KeyError(f"unknown profile: {profile_id}") from error

    def _operation(self, operation_id: str) -> OperationRecord:
        try:
            return self.operations[operation_id]
        except KeyError as error:
            raise KeyError(f"unknown operation: {operation_id}") from error

    def _mark(self, operation_id: str, state: OperationState) -> None:
        operation = self._operation(operation_id)
        self.operations[operation_id] = replace(
            operation, state=state, updated_at=self._timestamp()
        )

    def _timestamp(self) -> str:
        value = self.clock.now_utc()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return an aware timestamp")
        return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


class SimulatedCrash(BaseException):
    """Represent process termination, which application rollback must not catch."""


class FaultInjectingFileSystem(LocalFileSystem):
    """Use real filesystem safety checks and inject copy/finalize failures deterministically."""

    def __init__(self) -> None:
        self.fail_copy = False
        self.fail_finalize = False
        self.fail_finalize_at: int | None = None
        self.finalize_attempts = 0
        self.crash_after_finalize = False
        self.conflict_before_crash = False
        self.finalized: list[str] = []

    def copy_to_temp(
        self, source_root: Path, destination_folder: Path, source_name: str, temp_name: str
    ) -> FileFingerprint:
        if self.fail_copy:
            raise FileSystemError(FileSystemErrorReason.COPY_FAILED, path=source_root / source_name)
        return super().copy_to_temp(source_root, destination_folder, source_name, temp_name)

    def finalize_temp_file(
        self, source_root: Path, destination_folder: Path, temp_name: str, final_name: str
    ) -> Path:
        self.finalize_attempts += 1
        if self.conflict_before_crash:
            temp_path = destination_folder / temp_name
            (destination_folder / final_name).write_bytes(temp_path.read_bytes())
            self.conflict_before_crash = False
            raise SimulatedCrash
        if self.fail_finalize or self.finalize_attempts == self.fail_finalize_at:
            raise FileSystemError(
                FileSystemErrorReason.FINALIZE_UNSUPPORTED, path=destination_folder / final_name
            )
        result = super().finalize_temp_file(source_root, destination_folder, temp_name, final_name)
        self.finalized.append(final_name)
        if self.crash_after_finalize:
            raise SimulatedCrash
        return result
