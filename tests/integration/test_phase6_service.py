import json
from pathlib import Path

import pytest
from PIL import Image

from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.slots import Slot


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
