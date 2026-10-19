from pathlib import Path
from typing import Any

from fakes import FaultInjectingFileSystem

from vuechoixgarde.app.gate import OperationGate
from vuechoixgarde.app.results import UseCaseStatus
from vuechoixgarde.app.toggle import execute_toggle, plan_toggle
from vuechoixgarde.core.slots import Slot
from vuechoixgarde.fsops.filesystem import LocalFileSystem
from vuechoixgarde.ports.models import LoadStatus
from vuechoixgarde.store.state import SQLiteStateStore


def _profile(state: SQLiteStateStore, filesystem: LocalFileSystem, root: Path):
    return state.create_profile_from_template(
        filesystem.folder_identity(root),
        str(root),
        (Slot("KeyW", "Sorted", "#abcdef"),),
    )


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
