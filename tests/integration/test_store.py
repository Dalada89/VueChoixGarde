import hashlib
import json
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

import vuechoixgarde.store.settings as settings_module
from vuechoixgarde.core.slots import DEFAULT_SLOTS, Slot
from vuechoixgarde.core.temp_names import temp_file_name
from vuechoixgarde.ports.errors import (
    SettingsStoreError,
    StateStoreError,
    StateStoreErrorReason,
)
from vuechoixgarde.ports.models import (
    CopyRecord,
    LoadStatus,
    OperationFileRecord,
    OperationState,
    Settings,
)
from vuechoixgarde.store.damage import quarantine_damaged
from vuechoixgarde.store.paths import application_data_dir
from vuechoixgarde.store.settings import JsonSettingsStore
from vuechoixgarde.store.state import SQLiteStateStore


def test_application_data_path_can_be_injected_and_prepared(tmp_path: Path, fixed_clock) -> None:
    root = tmp_path / "custom-data"
    assert application_data_dir(root) == root
    settings = JsonSettingsStore(root, fixed_clock)
    assert settings.path == root / "settings.json"
    assert (root / "locks").is_dir()
    assert (root / "logs").is_dir()


def test_settings_create_defaults_and_roundtrip(tmp_path: Path, fixed_clock) -> None:
    store = JsonSettingsStore(tmp_path / "app", fixed_clock)
    created = store.load("de_DE.UTF-8")
    assert created.status is LoadStatus.CREATED_DEFAULTS
    assert created.settings is not None
    assert created.settings.language == "de"
    assert created.settings.global_slot_template == DEFAULT_SLOTS
    loaded = store.load("fr_FR")
    assert loaded.status is LoadStatus.LOADED
    assert loaded.settings == created.settings

    changed = Settings(
        schema_version=1,
        language="fr",
        sound_enabled=False,
        sort_direction="desc",
        reopen_last_folder=True,
        last_folder="/tmp/example",
        global_slot_template=(Slot("KeyW", "Best", "#abcdef"),),
        learned_key_labels=(("KeyW", "Z"),),
    )
    store.save(changed)
    assert store.load().settings == changed


def test_settings_atomic_write_failure_preserves_old_file(
    tmp_path: Path, fixed_clock, monkeypatch
) -> None:
    store = JsonSettingsStore(tmp_path / "app", fixed_clock)
    first = store.defaults("en")
    store.save(first)
    original = store.path.read_bytes()
    monkeypatch.setattr(
        settings_module.os,
        "replace",
        lambda *_args: (_ for _ in ()).throw(OSError("replace failed")),
    )
    changed = Settings(
        schema_version=1,
        language="fr",
        sound_enabled=False,
        sort_direction="asc",
        reopen_last_folder=False,
        last_folder=None,
        global_slot_template=DEFAULT_SLOTS,
        learned_key_labels=(),
    )
    with pytest.raises(SettingsStoreError):
        store.save(changed)
    assert store.path.read_bytes() == original
    assert not list(store.root.glob(".settings-*.tmp"))


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("language", "es"),
        ("sound_enabled", 1),
        ("sort_direction", "forward"),
        ("reopen_last_folder", "false"),
        ("schema_version", True),
        ("learned_key_labels", {"ArrowLeft": "A"}),
        ("learned_key_labels", {"KeyW": "long"}),
        (
            "global_slot_template",
            [{"key_position": "KeyW", "destination_name": "CON", "color": "#112233"}],
        ),
        (
            "global_slot_template",
            [{"key_position": "ArrowLeft", "destination_name": None, "color": "#112233"}],
        ),
        (
            "global_slot_template",
            [{"key_position": "KeyW", "destination_name": None, "color": "red"}],
        ),
    ],
)
def test_invalid_settings_return_damaged_without_modifying_json(
    tmp_path: Path, fixed_clock, field: str, invalid: object
) -> None:
    store = JsonSettingsStore(tmp_path / "app", fixed_clock)
    store.save(store.defaults("en"))
    value = json.loads(store.path.read_text(encoding="utf-8"))
    value[field] = invalid
    damaged_bytes = json.dumps(value).encode("utf-8")
    store.path.write_bytes(damaged_bytes)

    result = store.load()
    assert result.status is LoadStatus.DAMAGED
    assert store.path.read_bytes() == damaged_bytes


def test_corrupt_json_is_damaged_and_kept(tmp_path: Path, fixed_clock) -> None:
    store = JsonSettingsStore(tmp_path / "app", fixed_clock)
    store.path.write_bytes(b"{broken")
    original = store.path.read_bytes()
    result = store.load()
    assert result.status is LoadStatus.DAMAGED
    assert store.path.read_bytes() == original


def test_quarantine_uses_a_unique_name_without_replacing_existing_file(
    tmp_path: Path, fixed_clock
) -> None:
    damaged = tmp_path / "settings.json"
    damaged.write_bytes(b"corrupt")
    collision = tmp_path / "settings.json.damaged-20250102T030405123456Z"
    collision.write_bytes(b"existing")

    result = quarantine_damaged(damaged, fixed_clock)
    assert result == tmp_path / "settings.json.damaged-20250102T030405123456Z-1"
    assert result.read_bytes() == b"corrupt"
    assert collision.read_bytes() == b"existing"
    assert not damaged.exists()


def test_state_store_creates_schema_and_roundtrips_profiles_and_register(
    tmp_path: Path, fixed_clock
) -> None:
    root = tmp_path / "app"
    store = SQLiteStateStore(root, fixed_clock)
    assert store.load().status is LoadStatus.CREATED_DEFAULTS
    assert store.load().status is LoadStatus.LOADED
    with store._connect() as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].casefold() == "wal"
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        copy_columns = {row["name"] for row in connection.execute("PRAGMA table_info(copies)")}
        assert "modified" not in copy_columns
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'operation_files'"
            ).fetchone()
            is not None
        )
    profile = store.create_profile_from_template("/old/source", "/old/source", DEFAULT_SLOTS)
    assert profile.slots == DEFAULT_SLOTS
    assert store.get_profile_by_identity("/old/source") == profile
    changed_slots = (Slot("KeyQ", "Best", "#112233"),)
    updated = store.replace_profile_slots(profile.id, changed_slots)
    assert updated.slots == changed_slots
    assert store.orphaned_profiles(lambda identity: identity == "/exists") == (updated,)

    copy = CopyRecord(
        profile_id=profile.id,
        source_folder="/old/source",
        source_name="photo.jpg",
        destination_folder="/old/source/Best",
        destination_name="photo.jpg",
        size=4,
        sha256=hashlib.sha256(b"copy").hexdigest(),
        mtime_ns=1_735_789_445_987_654_321,
        created_at="2025-01-02T03:04:05.123456Z",
    )
    operation_id = uuid4().hex
    file_row = OperationFileRecord(
        index=0,
        temp_name=temp_file_name(operation_id, 0),
        final_name="photo.jpg",
        expected_size=4,
        expected_sha256=copy.sha256,
    )
    operation = store.start_operation(operation_id, profile.id, "Best", (file_row,))
    assert operation.state is OperationState.STARTED
    assert store.unfinished_operations() == (operation,)
    store.complete_operation(operation_id, (copy,))
    assert store.unfinished_operations() == ()
    assert store.copy_records(profile.id, "/old/source/Best", "photo.jpg") == (copy,)
    store.remove_copy_record(profile.id, "/old/source/Best", "photo.jpg")
    assert store.copy_records(profile.id) == ()


def test_complete_operation_rolls_back_register_and_done_state_together(
    tmp_path: Path, fixed_clock
) -> None:
    store = SQLiteStateStore(tmp_path / "app", fixed_clock)
    store.load()
    profile = store.create_profile_from_template("/source", "/source", DEFAULT_SLOTS)
    operation_id = uuid4().hex
    operation_file = OperationFileRecord(
        0, temp_file_name(operation_id, 0), "one.jpg", 4, hashlib.sha256(b"data").hexdigest()
    )
    store.start_operation(operation_id, profile.id, "Best", (operation_file,))
    first = CopyRecord(
        profile.id,
        "/source",
        "one.jpg",
        "/source/Best",
        "one.jpg",
        4,
        hashlib.sha256(b"data").hexdigest(),
        1,
        "2025-01-02T03:04:05.123456Z",
    )
    duplicate = CopyRecord(
        profile.id,
        "/source",
        "two.jpg",
        "/source/Best",
        "one.jpg",
        4,
        hashlib.sha256(b"data").hexdigest(),
        1,
        "2025-01-02T03:04:05.123456Z",
    )

    with pytest.raises(StateStoreError):
        store.complete_operation(operation_id, (first, duplicate))
    assert store.copy_records(profile.id) == ()
    (unfinished,) = store.unfinished_operations()
    assert unfinished.id == operation_id
    assert unfinished.state is OperationState.STARTED

    store.complete_operation(operation_id, (first,))
    assert store.copy_records(profile.id) == (first,)
    assert store.unfinished_operations() == ()


def test_profile_reassignment_rewrites_register_paths(tmp_path: Path, fixed_clock) -> None:
    store = SQLiteStateStore(tmp_path / "app", fixed_clock)
    store.load()
    profile = store.create_profile_from_template("/old/root", "/old/root", DEFAULT_SLOTS)
    operation_id = uuid4().hex
    file_row = OperationFileRecord(
        0,
        temp_file_name(operation_id, 0),
        "one.jpg",
        3,
        hashlib.sha256(b"one").hexdigest(),
    )
    store.start_operation(operation_id, profile.id, "Best", (file_row,))
    copy = CopyRecord(
        profile.id,
        "/old/root",
        "one.jpg",
        "/old/root/Best",
        "one.jpg",
        3,
        hashlib.sha256(b"one").hexdigest(),
        1,
        "unused",
    )
    store.complete_operation(operation_id, (copy,))

    reassigned = store.reassign_profile(profile.id, "/new/root", "/new/root")
    assert reassigned.folder_identity == "/new/root"
    entries = store.copy_records(profile.id)
    assert entries[0].source_folder == "/new/root"
    assert entries[0].destination_folder == "/new/root/Best"


def test_corrupt_sqlite_is_damaged_and_unchanged(tmp_path: Path, fixed_clock) -> None:
    root = tmp_path / "app"
    root.mkdir()
    path = root / "state.sqlite3"
    original = b"not a sqlite database"
    path.write_bytes(original)
    store = SQLiteStateStore(root, fixed_clock)

    result = store.load()
    assert result.status is LoadStatus.DAMAGED
    assert not result.register_available
    assert path.read_bytes() == original


def test_existing_version_zero_database_migrates_to_version_one(
    tmp_path: Path, fixed_clock
) -> None:
    root = tmp_path / "app"
    root.mkdir()
    path = root / "state.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 0")

    result = SQLiteStateStore(root, fixed_clock).load()
    assert result.status is LoadStatus.LOADED
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert {"profiles", "slots", "copies", "operations", "operation_files"}.issubset(tables)


def test_unknown_sqlite_version_is_damaged_without_modifying_database(
    tmp_path: Path, fixed_clock
) -> None:
    root = tmp_path / "app"
    root.mkdir()
    path = root / "state.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 99")
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    result = SQLiteStateStore(root, fixed_clock).load()
    assert result.status is LoadStatus.DAMAGED
    assert result.reason is StateStoreErrorReason.UNSUPPORTED_VERSION
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original_hash


def test_state_journal_mark_rolled_back_and_recovered(tmp_path: Path, fixed_clock) -> None:
    store = SQLiteStateStore(tmp_path / "app", fixed_clock)
    store.load()
    profile = store.create_profile_from_template("/source", "/source", DEFAULT_SLOTS)
    for action, expected in (
        (store.mark_rolled_back, OperationState.ROLLED_BACK),
        (store.mark_recovered, OperationState.RECOVERED),
    ):
        operation_id = uuid4().hex
        store.start_operation(operation_id, profile.id, "Best", ())
        action(operation_id)
        assert all(record.state is not expected for record in store.unfinished_operations())
