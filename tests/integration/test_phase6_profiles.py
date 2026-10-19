import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.slots import DEFAULT_SLOTS, Slot
from vuechoixgarde.core.temp_names import temp_file_name
from vuechoixgarde.ports.models import CopyRecord, OperationFileRecord
from vuechoixgarde.store.state import SQLiteStateStore


def _record_copy(store: SQLiteStateStore, profile_id: str, root: str) -> None:
    operation_id = uuid4().hex
    digest = hashlib.sha256(b"image-bytes").hexdigest()
    store.start_operation(
        operation_id,
        profile_id,
        "Chosen",
        (OperationFileRecord(0, temp_file_name(operation_id, 0), "photo.jpg", 12, digest),),
    )
    store.complete_operation(
        operation_id,
        (
            CopyRecord(
                profile_id,
                root,
                "photo.jpg",
                str(Path(root) / "Chosen"),
                "photo.jpg",
                12,
                digest,
                1,
                "unused",
            ),
        ),
    )


def test_profile_slots_and_global_template_remain_independent(tmp_path: Path) -> None:
    runtime = create_runtime(tmp_path / "application-data")
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    try:
        first_view = runtime.service.open_folder(first)
        original_profile_id = first_view.snapshot.profile.id
        customized = (Slot("KeyW", "Chosen", "#4488CC"),)
        runtime.service.save_profile_slots(customized)
        runtime.service.save_profile_as_template()
        assert runtime.service.settings.global_slot_template == customized
        assert runtime.service.session is not None
        assert runtime.service.session.profile.slots == customized

        runtime.service.close()
        second_view = runtime.service.open_folder(second)
        assert second_view.snapshot.profile.slots == customized
        assert second_view.snapshot.profile.id != original_profile_id
    finally:
        runtime.shutdown()


def test_orphan_reassignment_replaces_only_empty_target_and_rewrites_register(
    tmp_path: Path, fixed_clock
) -> None:
    store = SQLiteStateStore(tmp_path / "app", fixed_clock)
    store.load()
    orphan = store.create_profile_from_template("/missing/source", "/missing/source", DEFAULT_SLOTS)
    _record_copy(store, orphan.id, "/missing/source")
    empty_target = store.create_profile_from_template("/new/source", "/new/source", DEFAULT_SLOTS)

    moved = store.reassign_profile(
        orphan.id,
        "/new/source",
        "/new/source",
        replace_profile_id=empty_target.id,
    )

    assert moved.id == orphan.id
    assert moved.folder_identity == "/new/source"
    assert store.get_profile_by_identity("/new/source") == moved
    assert store.list_profiles() == (moved,)
    (record,) = store.copy_records(orphan.id)
    assert record.source_folder == "/new/source"
    assert record.destination_folder == "/new/source/Chosen"
    assert store.unfinished_operations() == ()


def test_orphan_reassignment_rolls_back_profile_register_and_target_on_failure(
    tmp_path: Path, fixed_clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteStateStore(tmp_path / "app", fixed_clock)
    store.load()
    orphan = store.create_profile_from_template("/missing/source", "/missing/source", DEFAULT_SLOTS)
    _record_copy(store, orphan.id, "/missing/source")
    target = store.create_profile_from_template("/new/source", "/new/source", DEFAULT_SLOTS)

    def fail_after_updates(*_args: object) -> None:
        raise RuntimeError("injected readback failure")

    monkeypatch.setattr(store, "_read_profile", fail_after_updates)
    with pytest.raises(RuntimeError, match="injected"):
        store.reassign_profile(
            orphan.id,
            "/new/source",
            "/new/source",
            replace_profile_id=target.id,
        )
    monkeypatch.undo()

    assert store.get_profile_by_identity("/missing/source") == orphan
    assert store.get_profile_by_identity("/new/source") == target
    (record,) = store.copy_records(orphan.id)
    assert record.source_folder == "/missing/source"
    assert record.destination_folder == "/missing/source/Chosen"


def test_deleting_profile_does_not_delete_destination_image_files(
    tmp_path: Path, fixed_clock
) -> None:
    destination = tmp_path / "source" / "Chosen"
    destination.mkdir(parents=True)
    image = destination / "photo.jpg"
    image.write_bytes(b"image-bytes")
    store = SQLiteStateStore(tmp_path / "app", fixed_clock)
    store.load()
    profile = store.create_profile_from_template("/source", "/source", DEFAULT_SLOTS)
    _record_copy(store, profile.id, "/source")

    store.delete_profile(profile.id)

    assert store.list_profiles() == ()
    assert store.copy_records(profile.id) == ()
    assert image.read_bytes() == b"image-bytes"
