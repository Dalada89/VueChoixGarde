from pathlib import Path

from vuechoixgarde.app.results import (
    FolderDeletionCase,
    FolderDeletionStatus,
)
from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.slots import Slot
from vuechoixgarde.ports.errors import FileSystemError, FileSystemErrorReason


def _open_runtime(tmp_path: Path, source_guard):
    source = source_guard.root
    (source / "photo.jpg").write_bytes(b"original source bytes")
    (source / "Target").mkdir()
    runtime = create_runtime(tmp_path / "application-data")
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=(Slot("KeyW", "Target", "#4488CC"),),
    )
    source_guard.seal(allowed_destinations={"Target"})
    runtime.service.open_folder(source)
    return runtime, source


def _current_profile(runtime):
    session = runtime.service.session
    assert session is not None
    return session.profile


def _copy_one(runtime, source: Path, name: str = "photo.jpg") -> None:
    runtime.service.refresh()
    plan = runtime.service.plan_slot(name, 0)
    result, _ = runtime.service.execute_plan(plan, confirmed_modified=False)
    assert result.status.value == "ok"
    assert (source / name).read_bytes() == b"original source bytes"


def test_deletable_destination_removes_only_managed_copy_and_slot(
    tmp_path: Path, source_guard
) -> None:
    runtime, source = _open_runtime(tmp_path, source_guard)
    try:
        _copy_one(runtime, source)
        check = runtime.service.inspect_destination_folder(0)
        assert check.case is FolderDeletionCase.DELETABLE
        assert check.managed_names == ("photo.jpg",)

        result = runtime.service.delete_destination_folder(0, check)

        assert result.status is FolderDeletionStatus.DELETED
        assert not (source / "Target").exists()
        assert (source / "photo.jpg").read_bytes() == b"original source bytes"
        assert _current_profile(runtime).slots[0].destination_name is None
        assert runtime.service.state_store.copy_records(_current_profile(runtime).id) == ()
    finally:
        runtime.shutdown()


def test_empty_destination_can_be_deleted(tmp_path: Path, source_guard) -> None:
    runtime, source = _open_runtime(tmp_path, source_guard)
    try:
        check = runtime.service.inspect_destination_folder(0)
        assert check.case is FolderDeletionCase.DELETABLE
        assert check.managed_names == ()

        result = runtime.service.delete_destination_folder(0, check)

        assert result.status is FolderDeletionStatus.DELETED
        assert not (source / "Target").exists()
        assert _current_profile(runtime).slots[0].destination_name is None
    finally:
        runtime.shutdown()


def test_foreign_entries_are_preserved_when_destination_is_detached(
    tmp_path: Path, source_guard
) -> None:
    runtime, source = _open_runtime(tmp_path, source_guard)
    try:
        _copy_one(runtime, source)
        foreign = source / "Target" / "foreign.jpg"
        hidden = source / "Target" / ".DS_Store"
        foreign.write_bytes(b"foreign bytes")
        hidden.write_bytes(b"hidden bytes")
        nested = source / "Target" / "nested"
        nested.mkdir()
        nested_file = nested / "keep.txt"
        nested_file.write_bytes(b"nested bytes")
        foreign_before = foreign.read_bytes()
        hidden_before = hidden.read_bytes()
        nested_before = nested_file.read_bytes()
        managed = source / "Target" / "photo.jpg"

        check = runtime.service.inspect_destination_folder(0)
        assert check.case is FolderDeletionCase.FOREIGN_ENTRIES
        assert check.foreign_names == (".DS_Store", "foreign.jpg", "nested")
        result = runtime.service.delete_destination_folder(0, check)

        assert result.status is FolderDeletionStatus.DETACHED
        assert managed.read_bytes() == b"original source bytes"
        assert foreign.read_bytes() == foreign_before
        assert hidden.read_bytes() == hidden_before
        assert nested_file.read_bytes() == nested_before
        assert _current_profile(runtime).slots[0].destination_name is None
        assert runtime.service.state_store.copy_records(_current_profile(runtime).id) == ()
    finally:
        runtime.shutdown()


def test_modified_managed_copy_is_treated_as_foreign_and_preserved(
    tmp_path: Path, source_guard
) -> None:
    runtime, source = _open_runtime(tmp_path, source_guard)
    try:
        _copy_one(runtime, source)
        modified = source / "Target" / "photo.jpg"
        modified.write_bytes(b"user-modified copy")
        check = runtime.service.inspect_destination_folder(0)

        assert check.case is FolderDeletionCase.FOREIGN_ENTRIES
        assert check.foreign_names == ("photo.jpg",)
        result = runtime.service.delete_destination_folder(0, check)

        assert result.status is FolderDeletionStatus.DETACHED
        assert modified.read_bytes() == b"user-modified copy"
        assert _current_profile(runtime).slots[0].destination_name is None
    finally:
        runtime.shutdown()


def test_faulty_symlink_destination_is_detached_without_following_it(
    tmp_path: Path, source_guard
) -> None:
    runtime, source = _open_runtime(tmp_path, source_guard)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_bytes(b"outside bytes")
    try:
        target = source / "Target"
        target.rmdir()
        target.symlink_to(outside, target_is_directory=True)
        check = runtime.service.inspect_destination_folder(0)

        assert check.case is FolderDeletionCase.FAULTY
        result = runtime.service.delete_destination_folder(0, check)

        assert result.status is FolderDeletionStatus.DETACHED
        assert target.is_symlink()
        assert sentinel.read_bytes() == b"outside bytes"
        assert _current_profile(runtime).slots[0].destination_name is None
    finally:
        runtime.shutdown()


def test_missing_destination_removes_saved_assignment_only(tmp_path: Path, source_guard) -> None:
    runtime, source = _open_runtime(tmp_path, source_guard)
    try:
        (source / "Target").rmdir()
        check = runtime.service.inspect_destination_folder(0)
        assert check.case is FolderDeletionCase.MISSING

        result = runtime.service.delete_destination_folder(0, check)

        assert result.status is FolderDeletionStatus.REMOVED_INFO
        assert _current_profile(runtime).slots[0].destination_name is None
        assert runtime.service.state_store.copy_records(_current_profile(runtime).id) == ()
    finally:
        runtime.shutdown()


def test_changed_folder_check_prevents_deletion(tmp_path: Path, source_guard) -> None:
    runtime, source = _open_runtime(tmp_path, source_guard)
    try:
        _copy_one(runtime, source)
        check = runtime.service.inspect_destination_folder(0)
        (source / "Target" / "new-foreign.jpg").write_bytes(b"new data")

        result = runtime.service.delete_destination_folder(0, check)

        assert result.status is FolderDeletionStatus.CHECK_CHANGED
        assert (source / "Target" / "photo.jpg").read_bytes() == b"original source bytes"
        assert (source / "Target" / "new-foreign.jpg").read_bytes() == b"new data"
        assert _current_profile(runtime).slots[0].destination_name == "Target"
    finally:
        runtime.shutdown()


def test_rmdir_failure_keeps_slot_and_cleans_register_for_deleted_copy(
    tmp_path: Path, source_guard, monkeypatch
) -> None:
    runtime, source = _open_runtime(tmp_path, source_guard)
    try:
        _copy_one(runtime, source)
        filesystem = runtime.service.filesystem

        def fail_rmdir(_source_root: Path, _exact_name: str) -> None:
            raise FileSystemError(FileSystemErrorReason.FOLDER_NOT_EMPTY, path=source / "Target")

        monkeypatch.setattr(filesystem, "remove_empty_destination_folder", fail_rmdir)
        check = runtime.service.inspect_destination_folder(0)
        result = runtime.service.delete_destination_folder(0, check)

        assert result.status is FolderDeletionStatus.PARTIAL
        assert result.deleted_count == 1
        assert (source / "Target").is_dir()
        assert not (source / "Target" / "photo.jpg").exists()
        assert _current_profile(runtime).slots[0].destination_name == "Target"
        assert runtime.service.state_store.copy_records(_current_profile(runtime).id) == ()
    finally:
        runtime.shutdown()
