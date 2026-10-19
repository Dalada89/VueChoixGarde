from collections.abc import Sequence
from pathlib import Path
from typing import cast

from vuechoixgarde.app.gate import OperationGate
from vuechoixgarde.app.keys import learn_key_label
from vuechoixgarde.app.reconcile import reconcile
from vuechoixgarde.app.startup import accept_damaged_data, decline_damaged_data, load_startup
from vuechoixgarde.core.slots import DEFAULT_SLOTS
from vuechoixgarde.core.toggle import FileClass
from vuechoixgarde.ports.errors import FileSystemError, FileSystemErrorReason
from vuechoixgarde.ports.filesystem import FileSystemPort
from vuechoixgarde.ports.models import (
    CopyRecord,
    FileFingerprint,
    FileMetadata,
    LoadStatus,
    Settings,
    SettingsLoadResult,
    StateLoadResult,
)
from vuechoixgarde.ports.settings import SettingsStore
from vuechoixgarde.ports.state import StateStore


def _settings() -> Settings:
    return Settings(1, "en", True, "asc", False, None, DEFAULT_SLOTS, ())


def _record(name: str, *, size: int = 4, digest: str = "abcd", mtime: int = 10) -> CopyRecord:
    return CopyRecord(
        "profile",
        "/source",
        f"{name}.jpg",
        "/source/Sorted",
        f"{name}.jpg",
        size,
        digest,
        mtime,
        "created",
    )


class FakeState:
    def __init__(self, records: Sequence[CopyRecord]) -> None:
        self.records = tuple(records)
        self.removed: list[tuple[str, str, str]] = []

    def copy_records(
        self, profile_id: str, destination_folder: str | None = None, source_name: str | None = None
    ) -> tuple[CopyRecord, ...]:
        return tuple(
            record
            for record in self.records
            if destination_folder is None or record.destination_folder == destination_folder
        )

    def remove_copy_record(
        self, profile_id: str, destination_folder: str, destination_name: str
    ) -> None:
        self.removed.append((profile_id, destination_folder, destination_name))
        self.records = tuple(
            record
            for record in self.records
            if not (
                record.profile_id == profile_id
                and record.destination_folder == destination_folder
                and record.destination_name == destination_name
            )
        )


class FakeFileSystem:
    def __init__(self, values: dict[str, FileMetadata | None]) -> None:
        self.values = values
        self.hashes: list[str] = []

    def file_metadata(self, source_root: Path, path: Path) -> FileMetadata | None:
        return self.values[path.name]

    def fingerprint_file(self, source_root: Path, path: Path) -> FileFingerprint:
        self.hashes.append(path.name)
        metadata = self.values[path.name]
        if metadata is None:
            raise FileNotFoundError(path)
        return FileFingerprint(metadata.size, "abcd", metadata.mtime_ns)


def test_operation_gate_rejects_busy_and_auto_repeat() -> None:
    gate = OperationGate()
    assert gate.try_acquire()
    assert gate.busy
    assert not gate.try_acquire()
    gate.release()
    assert not gate.try_acquire(auto_repeat=True)
    assert gate.try_acquire()
    gate.release()


def test_automatic_reconcile_skips_hash_when_metadata_matches() -> None:
    record = _record("one")
    state = FakeState((record,))
    filesystem = FakeFileSystem({"one.jpg": FileMetadata(4, 10)})

    report = reconcile(
        cast(StateStore, state),
        cast(FileSystemPort, filesystem),
        "profile",
        Path("/source"),
        automatic=True,
    )

    assert report.verified == 1
    assert filesystem.hashes == []
    assert report.items[0].file_class is FileClass.VERIFIED


def test_manual_reconcile_always_hashes_and_removes_missing_rows() -> None:
    records = (_record("one"), _record("gone"))
    state = FakeState(records)
    filesystem = FakeFileSystem({"one.jpg": FileMetadata(4, 10), "gone.jpg": None})

    report = reconcile(
        cast(StateStore, state),
        cast(FileSystemPort, filesystem),
        "profile",
        Path("/source"),
        automatic=False,
    )

    assert filesystem.hashes == ["one.jpg"]
    assert report.verified == 1
    assert report.removed == 1
    assert len(state.removed) == 1


def test_reconcile_size_mismatch_needs_no_hash_and_errors_do_not_abort() -> None:
    records = (_record("changed"), _record("broken"), _record("good"))
    state = FakeState(records)

    class FaultyFileSystem(FakeFileSystem):
        def file_metadata(self, source_root: Path, path: Path) -> FileMetadata | None:
            if path.name == "broken.jpg":
                raise FileSystemError(FileSystemErrorReason.IO_ERROR)
            return super().file_metadata(source_root, path)

    filesystem = FaultyFileSystem(
        {
            "changed.jpg": FileMetadata(8, 10),
            "broken.jpg": FileMetadata(4, 10),
            "good.jpg": FileMetadata(4, 11),
        }
    )

    report = reconcile(
        cast(StateStore, state),
        cast(FileSystemPort, filesystem),
        "profile",
        Path("/source"),
        automatic=True,
    )

    assert report.modified == 1
    assert report.errors == 1
    assert report.verified == 1
    assert filesystem.hashes == ["good.jpg"]


class FakeSettingsStore:
    def __init__(self, result: SettingsLoadResult) -> None:
        self.result = result
        self.saved: list[Settings] = []
        self.resets = 0

    def load(self, locale_name: str | None = None) -> SettingsLoadResult:
        return self.result

    def save(self, settings: Settings) -> None:
        self.saved.append(settings)

    def reset_damaged(self) -> Path | None:
        self.resets += 1
        self.result = SettingsLoadResult(LoadStatus.CREATED_DEFAULTS, _settings())
        return Path("quarantine")


class FakeStateStore:
    def __init__(self, result: StateLoadResult) -> None:
        self.result = result
        self.resets = 0

    def load(self) -> StateLoadResult:
        return self.result

    def reset_damaged(self) -> Path | None:
        self.resets += 1
        self.result = StateLoadResult(LoadStatus.CREATED_DEFAULTS, True)
        return Path("quarantine")


def test_startup_damaged_data_requires_explicit_acceptance() -> None:
    damaged_settings = SettingsLoadResult(LoadStatus.DAMAGED)
    damaged_state = StateLoadResult(LoadStatus.DAMAGED, False)
    settings_store = FakeSettingsStore(damaged_settings)
    state_store = FakeStateStore(damaged_state)

    report = load_startup(cast(SettingsStore, settings_store), cast(StateStore, state_store))
    declined = decline_damaged_data(report)

    assert settings_store.resets == 0
    assert state_store.resets == 0
    assert declined.settings_damaged
    assert not declined.register_available

    accepted = accept_damaged_data(
        report, cast(SettingsStore, settings_store), cast(StateStore, state_store)
    )

    assert settings_store.resets == 1
    assert state_store.resets == 1
    assert accepted.settings == _settings()
    assert accepted.register_available
    assert accepted.accepted_defaults


class FakeSettingsWriter:
    def __init__(self) -> None:
        self.saved: list[Settings] = []

    def save(self, settings: Settings) -> None:
        self.saved.append(settings)


def test_learned_key_label_persists_only_when_value_changes() -> None:
    store = FakeSettingsWriter()
    original = _settings()

    unchanged = learn_key_label(
        original, cast(SettingsStore, store), "KeyW", "", modifier_active=False
    )
    learned = learn_key_label(
        original, cast(SettingsStore, store), "KeyW", "z", modifier_active=False
    )
    same = learn_key_label(learned, cast(SettingsStore, store), "KeyW", "z", modifier_active=False)

    assert unchanged is original
    assert learned.learned_key_labels == (("KeyW", "Z"),)
    assert same is learned
    assert store.saved == [learned]
