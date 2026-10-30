import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image

from vuechoixgarde.app.results import FolderManagementError, FolderManagementReason
from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.slots import Slot, SlotMode
from vuechoixgarde.core.temp_names import temp_file_name
from vuechoixgarde.ports.models import CopyRecord, OperationFileRecord


def test_failed_last_folder_save_is_logged_and_shown_without_path_leakage(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "private-source-name"
    source.mkdir()
    runtime = create_runtime(tmp_path / "application-data")

    def fail_save(_settings) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(runtime.service.settings_store, "save", fail_save)
    try:
        view = runtime.service.open_folder(source)
        assert view.warning == "settings_save_failed"
        previous = runtime.service.settings
        with pytest.raises(OSError):
            runtime.service.save_preferences(
                reopen_last_folder=True,
                sort_direction="desc",
            )
        assert runtime.service.settings == previous
        log_path = runtime.log_directory / "vuechoixgarde.jsonl"
        events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        warning = next(
            event for event in events if event["msg"] == "last-folder setting could not be saved"
        )
        assert "private-source-name" not in json.dumps(warning)
    finally:
        runtime.shutdown()


def test_unassigned_destination_is_reported_without_moving_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    image = source / "photo.png"
    Image.new("RGB", (8, 8), "blue").save(image)
    runtime = create_runtime(tmp_path / "application-data")
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=(Slot("KeyW", "Before", "#4488CC"),),
    )
    try:
        runtime.service.open_folder(source)
        plan = runtime.service.plan_slot(image.name, 0)
        _, copied_view = runtime.service.execute_plan(plan, confirmed_modified=False)
        assert (source / "Before" / image.name).is_file()
        runtime.service.refresh()
        changed_view = runtime.service.save_profile_slots((Slot("KeyW", "After", "#4488CC"),))
        status = runtime.service.slot_status(
            changed_view.snapshot.current_name,
            changed_view.generation,
        )

        assert status.warning == "destination_unassigned"
        assert (source / "Before" / image.name).is_file()
        assert not (source / "After").exists()
        assert copied_view.snapshot.profile.id == changed_view.snapshot.profile.id
    finally:
        runtime.shutdown()


def test_move_mode_in_global_template_survives_runtime_restart(tmp_path: Path) -> None:
    data_dir = tmp_path / "application-data"
    move_slots = (Slot("KeyR", "trash", "#FF7B7B", SlotMode.MOVE),)
    runtime = create_runtime(data_dir)
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=move_slots,
    )
    runtime.shutdown()

    restarted = create_runtime(data_dir)
    try:
        assert restarted.settings.global_slot_template == move_slots
    finally:
        restarted.shutdown()


@pytest.mark.parametrize(
    ("current_mode", "requested_mode"),
    [(SlotMode.COPY, SlotMode.MOVE), (SlotMode.MOVE, SlotMode.COPY)],
)
def test_mode_change_with_registered_copies_is_rejected_before_saving_preferences(
    tmp_path: Path, current_mode: SlotMode, requested_mode: SlotMode
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    image = source / "photo.png"
    Image.new("RGB", (8, 8), "blue").save(image)
    runtime = create_runtime(tmp_path / "application-data")
    slot = Slot("KeyW", "Archive", "#4488CC", current_mode)
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=(slot,),
    )
    try:
        runtime.service.open_folder(source)
        if current_mode is SlotMode.COPY:
            plan = runtime.service.plan_slot(image.name, 0)
            runtime.service.execute_plan(plan, confirmed_modified=False)
        else:
            session = runtime.service.session
            assert session is not None
            destination = source / "Archive"
            destination.mkdir()
            data = image.read_bytes()
            (destination / image.name).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            operation_id = uuid4().hex
            runtime.service.state_store.start_operation(
                operation_id,
                session.profile.id,
                "Archive",
                (
                    OperationFileRecord(
                        0,
                        temp_file_name(operation_id, 0),
                        image.name,
                        len(data),
                        digest,
                    ),
                ),
            )
            runtime.service.state_store.complete_operation(
                operation_id,
                (
                    CopyRecord(
                        session.profile.id,
                        str(source),
                        image.name,
                        str(destination),
                        image.name,
                        len(data),
                        digest,
                        image.stat().st_mtime_ns,
                        "2025-01-02T03:04:05.123456Z",
                    ),
                ),
            )
        settings_before = runtime.service.settings
        replacement_template = (Slot("KeyQ", "TemplateOnly", "#4488CC"),)

        with pytest.raises(FolderManagementError) as caught:
            runtime.service.save_settings_and_profile_slots(
                reopen_last_folder=False,
                sort_direction="asc",
                language=settings_before.language,
                sound_enabled=settings_before.sound_enabled,
                global_slot_template=replacement_template,
                profile_slots=(Slot("KeyW", "Archive", "#4488CC", requested_mode),),
                learned_key_labels=settings_before.learned_key_labels,
            )

        assert caught.value.reason is FolderManagementReason.MODE_CHANGE_BLOCKED
        assert caught.value.destination_name == "Archive"
        assert runtime.service.settings == settings_before
        assert runtime.service.session is not None
        assert runtime.service.session.profile.slots == (slot,)
        assert (
            len(runtime.service.state_store.copy_records(runtime.service.session.profile.id)) == 1
        )
    finally:
        runtime.shutdown()
