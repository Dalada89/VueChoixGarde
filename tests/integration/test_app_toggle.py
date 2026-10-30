from pathlib import Path
from typing import Any

import pytest
from fakes import FaultInjectingFileSystem

from vuechoixgarde.app.gate import OperationGate
from vuechoixgarde.app.results import UseCaseStatus
from vuechoixgarde.app.toggle import execute_toggle, plan_toggle
from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.slots import Slot, SlotMode
from vuechoixgarde.fsops.filesystem import LocalFileSystem
from vuechoixgarde.ports.errors import FileSystemError
from vuechoixgarde.ports.models import LoadStatus
from vuechoixgarde.store.state import SQLiteStateStore


def _profile(state: SQLiteStateStore, filesystem: LocalFileSystem, root: Path):
    return state.create_profile_from_template(
        filesystem.folder_identity(root),
        str(root),
        (Slot("KeyW", "Sorted", "#abcdef"),),
    )


def _open_move_runtime(tmp_path: Path, source: Path):
    runtime = create_runtime(tmp_path / "app-data")
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=(Slot("KeyR", "trash", "#FF7B7B", SlotMode.MOVE),),
    )
    runtime.service.open_folder(source)
    return runtime


def _move_image(runtime: Any, image_name: str) -> None:
    plan = runtime.service.plan_slot(image_name, 0)
    result, _view = runtime.service.execute_plan(plan, confirmed_modified=False)
    assert result.status is UseCaseStatus.OK


def test_toggle_on_and_off_with_real_adapters_and_source_guard(
    tmp_path: Path, fixed_clock: Any, source_guard: Any
) -> None:
    root = source_guard.root
    source = root / "IMG_1.jpg"
    source_bytes = b"test-image-bytes\x00\xff"
    source.write_bytes(source_bytes)
    app_data = tmp_path / "app-data"
    state = SQLiteStateStore(app_data, fixed_clock)
    assert state.load().status is LoadStatus.CREATED_DEFAULTS
    filesystem = LocalFileSystem()
    profile = _profile(state, filesystem, root)
    source_guard.seal(allowed_destinations={"Sorted"})
    gate = OperationGate()

    planned_on = plan_toggle(profile, root, source.name, 0, filesystem, filesystem, state)
    added = execute_toggle(
        planned_on,
        profile,
        filesystem,
        filesystem,
        state,
        fixed_clock,
        gate,
    )

    destination = root / "Sorted" / source.name
    assert added.status is UseCaseStatus.OK
    assert destination.read_bytes() == source_bytes
    assert len(state.copy_records(profile.id, str(root / "Sorted"))) == 1

    planned_off = plan_toggle(profile, root, source.name, 0, filesystem, filesystem, state)
    removed = execute_toggle(
        planned_off,
        profile,
        filesystem,
        filesystem,
        state,
        fixed_clock,
        gate,
    )

    assert removed.status is UseCaseStatus.OK
    assert not destination.exists()
    assert state.copy_records(profile.id, str(root / "Sorted")) == ()
    assert source.read_bytes() == source_bytes


def test_modified_managed_copy_requires_confirmation(
    tmp_path: Path, fixed_clock: Any, source_guard: Any
) -> None:
    root = source_guard.root
    source = root / "IMG_1.jpg"
    source.write_bytes(b"source-original")
    state = SQLiteStateStore(tmp_path / "app-data", fixed_clock)
    state.load()
    filesystem = LocalFileSystem()
    profile = _profile(state, filesystem, root)
    source_guard.seal(allowed_destinations={"Sorted"})
    gate = OperationGate()
    initial = plan_toggle(profile, root, source.name, 0, filesystem, filesystem, state)
    assert (
        execute_toggle(initial, profile, filesystem, filesystem, state, fixed_clock, gate).status
        is UseCaseStatus.OK
    )
    destination = root / "Sorted" / source.name
    destination.write_bytes(b"user-modified")

    modified = plan_toggle(profile, root, source.name, 0, filesystem, filesystem, state)
    refused = execute_toggle(modified, profile, filesystem, filesystem, state, fixed_clock, gate)

    assert refused.status is UseCaseStatus.MODIFIED_CONFIRMATION_REQUIRED
    assert destination.read_bytes() == b"user-modified"
    confirmed = execute_toggle(
        modified,
        profile,
        filesystem,
        filesystem,
        state,
        fixed_clock,
        gate,
        confirmed_modified=True,
    )

    assert confirmed.status is UseCaseStatus.OK
    assert not destination.exists()
    assert source.read_bytes() == b"source-original"


def test_casefolded_foreign_conflict_is_never_overwritten(
    tmp_path: Path, fixed_clock: Any, source_guard: Any
) -> None:
    root = source_guard.root
    source = root / "IMG_1.jpg"
    source.write_bytes(b"source")
    destination = root / "Sorted"
    destination.mkdir()
    conflict = destination / "img_1.JPG"
    conflict.write_bytes(b"foreign")
    state = SQLiteStateStore(tmp_path / "app-data", fixed_clock)
    state.load()
    filesystem = LocalFileSystem()
    profile = _profile(state, filesystem, root)
    source_guard.seal(allowed_destinations={"Sorted"})
    plan = plan_toggle(profile, root, source.name, 0, filesystem, filesystem, state)

    result = execute_toggle(
        plan, profile, filesystem, filesystem, state, fixed_clock, OperationGate()
    )

    assert result.status is UseCaseStatus.CONFLICT
    assert conflict.read_bytes() == b"foreign"
    assert not (destination / source.name).exists()
    assert source.read_bytes() == b"source"


def test_shared_sidecar_is_kept_until_last_selected_image_is_removed(
    tmp_path: Path, fixed_clock: Any, source_guard: Any
) -> None:
    root = source_guard.root
    first = root / "IMG_1.jpg"
    second = root / "IMG_1.png"
    sidecar = root / "IMG_1.xmp"
    first.write_bytes(b"jpeg")
    second.write_bytes(b"png")
    sidecar.write_bytes(b"xmp")
    state = SQLiteStateStore(tmp_path / "app-data", fixed_clock)
    state.load()
    filesystem = LocalFileSystem()
    profile = _profile(state, filesystem, root)
    source_guard.seal(allowed_destinations={"Sorted"})
    gate = OperationGate()

    for image in (first, second):
        plan = plan_toggle(profile, root, image.name, 0, filesystem, filesystem, state)
        result = execute_toggle(plan, profile, filesystem, filesystem, state, fixed_clock, gate)
        assert result.status is UseCaseStatus.OK

    copied_sidecar = root / "Sorted" / sidecar.name
    assert copied_sidecar.exists()
    off_first = plan_toggle(profile, root, first.name, 0, filesystem, filesystem, state)
    assert (
        execute_toggle(off_first, profile, filesystem, filesystem, state, fixed_clock, gate).status
        is UseCaseStatus.OK
    )
    assert copied_sidecar.exists()
    assert (root / "Sorted" / second.name).exists()

    off_second = plan_toggle(profile, root, second.name, 0, filesystem, filesystem, state)
    assert (
        execute_toggle(off_second, profile, filesystem, filesystem, state, fixed_clock, gate).status
        is UseCaseStatus.OK
    )
    assert not copied_sidecar.exists()
    assert source_guard.root.joinpath(first.name).read_bytes() == b"jpeg"
    assert second.read_bytes() == b"png"


def test_failed_second_finalize_rolls_back_only_operation_files(
    tmp_path: Path, fixed_clock: Any, source_guard: Any
) -> None:
    root = source_guard.root
    first = root / "IMG_1.jpg"
    sidecar = root / "IMG_1.xmp"
    first.write_bytes(b"jpeg")
    sidecar.write_bytes(b"xmp")
    state = SQLiteStateStore(tmp_path / "app-data", fixed_clock)
    state.load()
    filesystem = FaultInjectingFileSystem()
    profile = _profile(state, filesystem, root)
    source_guard.seal(allowed_destinations={"Sorted"})
    filesystem.fail_finalize_at = 2
    plan = plan_toggle(profile, root, first.name, 0, filesystem, filesystem, state)

    result = execute_toggle(
        plan, profile, filesystem, filesystem, state, fixed_clock, OperationGate()
    )

    destination = root / "Sorted"
    assert result.status is UseCaseStatus.ERROR
    assert list(destination.iterdir()) == []
    assert state.unfinished_operations() == ()
    assert filesystem.finalized == [first.name]
    assert first.read_bytes() == b"jpeg"
    assert sidecar.read_bytes() == b"xmp"


def test_move_toggle_moves_source_and_does_not_register_copy(
    tmp_path: Path, fixed_clock: Any
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    source = root / "IMG_1.jpg"
    sidecar = root / "IMG_1.xmp"
    source.write_bytes(b"move-image")
    sidecar.write_bytes(b"move-sidecar")
    state = SQLiteStateStore(tmp_path / "app-data", fixed_clock)
    state.load()
    filesystem = LocalFileSystem()
    profile = state.create_profile_from_template(
        filesystem.folder_identity(root),
        str(root),
        (Slot("KeyR", "trash", "#FF7B7B", SlotMode.MOVE),),
    )
    plan = plan_toggle(profile, root, source.name, 0, filesystem, filesystem, state)

    result = execute_toggle(
        plan, profile, filesystem, filesystem, state, fixed_clock, OperationGate()
    )

    destination = root / "trash"
    assert result.status is UseCaseStatus.OK
    assert not source.exists()
    assert not sidecar.exists()
    assert (destination / source.name).read_bytes() == b"move-image"
    assert (destination / sidecar.name).read_bytes() == b"move-sidecar"
    assert state.copy_records(profile.id, str(destination)) == ()
    assert state.unfinished_operations() == ()


def test_undo_last_move_restores_group_at_sorted_position_and_selects_it(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    files = {
        "IMG_1.jpg": b"first-image",
        "IMG_2.jpg": b"moved-image",
        "IMG_2.xmp": b"moved-sidecar",
        "IMG_3.jpg": b"last-image",
    }
    for name, data in files.items():
        (source / name).write_bytes(data)
    runtime = _open_move_runtime(tmp_path, source)

    try:
        runtime.service.navigate_to(1)
        plan = runtime.service.plan_slot("IMG_2.jpg", 0)
        result, moved_view = runtime.service.execute_plan(plan, confirmed_modified=False)
        assert result.status is UseCaseStatus.OK
        assert moved_view.snapshot.current_name == "IMG_3.jpg"

        restored_view = runtime.service.undo_last_move()

        assert restored_view.snapshot.image_index == 2
        assert restored_view.snapshot.current_name == "IMG_2.jpg"
        assert set(restored_view.snapshot.scan.images) == {
            "IMG_1.jpg",
            "IMG_2.jpg",
            "IMG_3.jpg",
        }
        assert all((source / name).read_bytes() == data for name, data in files.items())
        assert not (source / "trash" / "IMG_2.jpg").exists()
        assert not (source / "trash" / "IMG_2.xmp").exists()
    finally:
        runtime.shutdown()


def test_undo_move_removes_shared_sidecar_copy_but_keeps_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    moved_image = source / "IMG_1.jpg"
    other_image = source / "IMG_1.png"
    sidecar = source / "IMG_1.xmp"
    moved_image.write_bytes(b"jpeg-image")
    other_image.write_bytes(b"png-image")
    sidecar.write_bytes(b"shared-sidecar")
    runtime = _open_move_runtime(tmp_path, source)
    destination = source / "trash"

    try:
        _move_image(runtime, moved_image.name)
        assert not moved_image.exists()
        assert other_image.read_bytes() == b"png-image"
        assert sidecar.read_bytes() == b"shared-sidecar"
        assert (destination / sidecar.name).read_bytes() == b"shared-sidecar"

        restored_view = runtime.service.undo_last_move()

        assert restored_view.snapshot.current_name == moved_image.name
        assert moved_image.read_bytes() == b"jpeg-image"
        assert other_image.read_bytes() == b"png-image"
        assert sidecar.read_bytes() == b"shared-sidecar"
        assert not (destination / moved_image.name).exists()
        assert not (destination / sidecar.name).exists()
    finally:
        runtime.shutdown()


def test_undo_move_history_is_lifo_and_empty_stack_is_a_noop(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "IMG_1.jpg").write_bytes(b"first")
    (source / "IMG_2.jpg").write_bytes(b"second")
    runtime = _open_move_runtime(tmp_path, source)

    try:
        _move_image(runtime, "IMG_1.jpg")
        _move_image(runtime, "IMG_2.jpg")

        second_view = runtime.service.undo_last_move()
        assert second_view.snapshot.current_name == "IMG_2.jpg"
        assert (source / "IMG_1.jpg").exists() is False
        assert (source / "IMG_2.jpg").read_bytes() == b"second"

        first_view = runtime.service.undo_last_move()
        assert first_view.snapshot.current_name == "IMG_1.jpg"
        assert (source / "IMG_1.jpg").read_bytes() == b"first"
        assert (source / "IMG_2.jpg").read_bytes() == b"second"

        empty_view = runtime.service.undo_last_move()
        assert empty_view.snapshot.current_name == first_view.snapshot.current_name
        assert empty_view.snapshot.scan.images == first_view.snapshot.scan.images
    finally:
        runtime.shutdown()


@pytest.mark.parametrize("blocker", ("original_name", "missing_destination"))
def test_failed_undo_preserves_move_and_stack_for_retry(tmp_path: Path, blocker: str) -> None:
    source = tmp_path / "source"
    source.mkdir()
    image = source / "IMG_1.jpg"
    original_data = b"original-image"
    image.write_bytes(original_data)
    runtime = _open_move_runtime(tmp_path, source)
    destination_file = source / "trash" / image.name

    try:
        _move_image(runtime, image.name)
        if blocker == "original_name":
            image.write_bytes(b"foreign-original")
        else:
            destination_file.unlink()

        with pytest.raises(FileSystemError):
            runtime.service.undo_last_move()

        if blocker == "original_name":
            assert image.read_bytes() == b"foreign-original"
            assert destination_file.read_bytes() == original_data
            image.unlink()
        else:
            assert not image.exists()
            assert not destination_file.exists()
            destination_file.write_bytes(original_data)

        restored_view = runtime.service.undo_last_move()

        assert restored_view.snapshot.current_name == image.name
        assert image.read_bytes() == original_data
        assert not destination_file.exists()
    finally:
        runtime.shutdown()


def test_undo_restores_modified_destination_file_contents(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    image = source / "IMG_1.jpg"
    image.write_bytes(b"original-image")
    runtime = _open_move_runtime(tmp_path, source)
    destination_file = source / "trash" / image.name

    try:
        _move_image(runtime, image.name)
        destination_file.write_bytes(b"modified-while-moved")

        restored_view = runtime.service.undo_last_move()

        assert restored_view.snapshot.current_name == image.name
        assert image.read_bytes() == b"modified-while-moved"
        assert not destination_file.exists()
    finally:
        runtime.shutdown()


def test_opening_another_folder_clears_move_undo_history(tmp_path: Path) -> None:
    first_source = tmp_path / "first-source"
    second_source = tmp_path / "second-source"
    first_source.mkdir()
    second_source.mkdir()
    (first_source / "first.jpg").write_bytes(b"first")
    (second_source / "second.jpg").write_bytes(b"second")
    runtime = _open_move_runtime(tmp_path, first_source)

    try:
        _move_image(runtime, "first.jpg")
        second_view = runtime.service.open_folder(second_source)

        unchanged_view = runtime.service.undo_last_move()

        assert unchanged_view.snapshot.current_name == second_view.snapshot.current_name
        assert unchanged_view.snapshot.source_path == second_view.snapshot.source_path
        assert not (first_source / "first.jpg").exists()
        assert (first_source / "trash" / "first.jpg").read_bytes() == b"first"
        assert (second_source / "second.jpg").read_bytes() == b"second"
    finally:
        runtime.shutdown()


def test_runtime_restart_does_not_restore_move_undo_history(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    image = source / "IMG_1.jpg"
    image.write_bytes(b"original-image")
    runtime = _open_move_runtime(tmp_path, source)
    _move_image(runtime, image.name)
    runtime.shutdown()

    restarted_runtime = _open_move_runtime(tmp_path, source)
    try:
        view = restarted_runtime.service.undo_last_move()

        assert view.snapshot.current_name is None
        assert not image.exists()
        assert (source / "trash" / image.name).read_bytes() == b"original-image"
    finally:
        restarted_runtime.shutdown()


def test_move_toggle_copies_shared_sidecar_and_keeps_source_for_other_image(
    tmp_path: Path, fixed_clock: Any
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    source = root / "IMG_1.jpg"
    other_image = root / "IMG_1.png"
    sidecar = root / "IMG_1.xmp"
    source.write_bytes(b"move-image")
    other_image.write_bytes(b"other-image")
    sidecar.write_bytes(b"shared-sidecar")
    state = SQLiteStateStore(tmp_path / "app-data", fixed_clock)
    state.load()
    filesystem = LocalFileSystem()
    profile = state.create_profile_from_template(
        filesystem.folder_identity(root),
        str(root),
        (Slot("KeyR", "trash", "#FF7B7B", SlotMode.MOVE),),
    )
    plan = plan_toggle(profile, root, source.name, 0, filesystem, filesystem, state)

    result = execute_toggle(
        plan, profile, filesystem, filesystem, state, fixed_clock, OperationGate()
    )

    destination = root / "trash"
    assert result.status is UseCaseStatus.OK
    assert not source.exists()
    assert other_image.read_bytes() == b"other-image"
    assert sidecar.read_bytes() == b"shared-sidecar"
    assert (destination / source.name).read_bytes() == b"move-image"
    assert (destination / sidecar.name).read_bytes() == b"shared-sidecar"
    assert state.copy_records(profile.id, str(destination)) == ()
    assert state.unfinished_operations() == ()
