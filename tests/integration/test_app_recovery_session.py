import hashlib
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fakes import FaultInjectingFileSystem, SimulatedCrash

from vuechoixgarde.app.gate import OperationGate
from vuechoixgarde.app.recovery import recover_operations
from vuechoixgarde.app.session import FolderSession
from vuechoixgarde.app.toggle import execute_toggle, plan_toggle
from vuechoixgarde.core.navigation import NavigationDirection
from vuechoixgarde.core.slots import Slot
from vuechoixgarde.core.temp_names import temp_file_name
from vuechoixgarde.fsops.filesystem import LocalFileSystem
from vuechoixgarde.fsops.lock import LocalFolderLockFactory
from vuechoixgarde.ports.errors import FolderLockError
from vuechoixgarde.ports.models import LoadStatus, OperationFileRecord
from vuechoixgarde.store.settings import JsonSettingsStore
from vuechoixgarde.store.state import SQLiteStateStore


def test_recovery_removes_only_journaled_temp_and_verified_final(
    tmp_path: Path, fixed_clock: Any, source_guard: Any
) -> None:
    root = source_guard.root
    destination = root / "Sorted"
    destination.mkdir()
    data = b"owned-copy"
    digest = hashlib.sha256(data).hexdigest()
    (destination / "IMG_1.jpg").write_bytes(data)
    (destination / "unlisted.txt").write_bytes(b"foreign")
    operation_id = uuid4().hex
    temp_name = temp_file_name(operation_id, 0)
    missing_temp_name = temp_file_name(operation_id, 1)
    (destination / temp_name).write_bytes(b"partial")
    state = SQLiteStateStore(tmp_path / "app-data", fixed_clock)
    assert state.load().status is LoadStatus.CREATED_DEFAULTS
    filesystem = LocalFileSystem()
    profile = state.create_profile_from_template(
        filesystem.folder_identity(root),
        str(root),
        JsonSettingsStore(tmp_path / "app-data", fixed_clock).defaults().global_slot_template,
    )
    state.start_operation(
        operation_id,
        profile.id,
        "Sorted",
        (
            OperationFileRecord(0, temp_name, "IMG_0.jpg", len(data), digest),
            OperationFileRecord(1, missing_temp_name, "IMG_1.jpg", len(data), digest),
        ),
    )
    source_guard.seal(allowed_destinations={"Sorted"})

    report = recover_operations(state, filesystem, profile.id, root)

    assert report.recovered == (operation_id,)
    assert not (destination / temp_name).exists()
    assert not (destination / "IMG_1.jpg").exists()
    assert (destination / "unlisted.txt").read_bytes() == b"foreign"
    assert state.unfinished_operations() == ()


def test_crash_after_finalization_is_recovered_from_journal(
    tmp_path: Path, fixed_clock: Any, source_guard: Any
) -> None:
    root = source_guard.root
    source = root / "IMG_1.jpg"
    source.write_bytes(b"crash-recovery-data")
    app_data = tmp_path / "app-data"
    state = SQLiteStateStore(app_data, fixed_clock)
    assert state.load().status is LoadStatus.CREATED_DEFAULTS
    filesystem = FaultInjectingFileSystem()
    profile = state.create_profile_from_template(
        filesystem.folder_identity(root),
        str(root),
        (Slot("KeyW", "Sorted", "#abcdef"),),
    )
    source_guard.seal(allowed_destinations={"Sorted"})
    plan = plan_toggle(profile, root, source.name, 0, filesystem, filesystem, state)
    filesystem.crash_after_finalize = True

    with pytest.raises(SimulatedCrash):
        execute_toggle(plan, profile, filesystem, filesystem, state, fixed_clock, OperationGate())

    destination = root / "Sorted" / source.name
    assert destination.exists()
    assert len(state.unfinished_operations()) == 1
    filesystem.crash_after_finalize = False
    report = recover_operations(state, filesystem, profile.id, root)

    assert report.recovered
    assert not destination.exists()
    assert state.unfinished_operations() == ()
    assert source.read_bytes() == b"crash-recovery-data"


def test_recovery_never_deletes_same_content_conflict_when_temp_also_exists(
    tmp_path: Path, fixed_clock: Any, source_guard: Any
) -> None:
    root = source_guard.root
    source = root / "IMG_1.jpg"
    source.write_bytes(b"identical-conflict-content")
    app_data = tmp_path / "app-data"
    state = SQLiteStateStore(app_data, fixed_clock)
    state.load()
    filesystem = FaultInjectingFileSystem()
    profile = state.create_profile_from_template(
        filesystem.folder_identity(root),
        str(root),
        (Slot("KeyW", "Sorted", "#abcdef"),),
    )
    source_guard.seal(allowed_destinations={"Sorted"})
    plan = plan_toggle(profile, root, source.name, 0, filesystem, filesystem, state)
    filesystem.conflict_before_crash = True

    with pytest.raises(SimulatedCrash):
        execute_toggle(plan, profile, filesystem, filesystem, state, fixed_clock, OperationGate())

    destination = root / "Sorted"
    conflict = destination / source.name
    temp_files = tuple(destination.glob(".vuechoixgarde-*.tmp"))
    assert conflict.read_bytes() == source.read_bytes()
    assert len(temp_files) == 1
    operation_id = state.unfinished_operations()[0].id

    report = recover_operations(state, filesystem, profile.id, root)

    assert report.pending == (operation_id,)
    assert not temp_files[0].exists()
    assert conflict.read_bytes() == source.read_bytes()
    assert state.unfinished_operations()[0].id == operation_id


def test_session_open_locks_navigates_refreshes_and_closes(
    tmp_path: Path, fixed_clock: Any, source_guard: Any
) -> None:
    root = source_guard.root
    (root / "IMG_1.jpg").write_bytes(b"one")
    (root / "IMG_2.jpg").write_bytes(b"two")
    app_data = tmp_path / "app-data"
    filesystem = LocalFileSystem()
    state = SQLiteStateStore(app_data, fixed_clock)
    assert state.load().status is LoadStatus.CREATED_DEFAULTS
    settings_store = JsonSettingsStore(app_data, fixed_clock)
    settings = settings_store.defaults()
    session = FolderSession.open(
        root,
        filesystem,
        filesystem,
        state,
        settings_store,
        settings,
        LocalFolderLockFactory(app_data),
    )
    first = session.snapshot()
    before = session.navigate(NavigationDirection.PREVIOUS)
    after = session.navigate(NavigationDirection.NEXT)
    (root / "IMG_1.jpg").unlink()
    source_guard.seal()
    refreshed = session.refresh()

    assert first.current_name == "IMG_1.jpg"
    assert before.boundary_reached
    assert after.current_name == "IMG_2.jpg"
    assert refreshed.current_name == "IMG_2.jpg"
    with pytest.raises(FolderLockError):
        FolderSession.open(
            root,
            filesystem,
            filesystem,
            state,
            settings_store,
            settings,
            LocalFolderLockFactory(app_data),
        )
    session.close()
    session.close()


def test_empty_session_refresh_keeps_empty_navigation(
    tmp_path: Path, fixed_clock: Any, source_guard: Any
) -> None:
    root = source_guard.root
    app_data = tmp_path / "app-data"
    filesystem = LocalFileSystem()
    state = SQLiteStateStore(app_data, fixed_clock)
    state.load()
    settings_store = JsonSettingsStore(app_data, fixed_clock)
    session = FolderSession.open(
        root,
        filesystem,
        filesystem,
        state,
        settings_store,
        settings_store.defaults(),
        LocalFolderLockFactory(app_data),
    )
    source_guard.seal()

    snapshot = session.refresh()

    assert snapshot.current_name is None
    assert snapshot.image_count == 0
    session.close()
