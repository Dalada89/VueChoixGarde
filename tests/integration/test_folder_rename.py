from pathlib import Path

import pytest
from fakes import SimulatedCrash

from vuechoixgarde.app.results import FolderManagementError, FolderRename, SlotState
from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.slots import Slot


def _active_profile(runtime):
    session = runtime.service.session
    assert session is not None
    return session.profile


def _save_rename(runtime, old_name: str, new_name: str):
    settings = runtime.service.settings
    return runtime.service.save_settings_and_profile_slots(
        reopen_last_folder=settings.reopen_last_folder,
        sort_direction=settings.sort_direction,
        language=settings.language,
        sound_enabled=settings.sound_enabled,
        global_slot_template=settings.global_slot_template,
        profile_slots=(Slot("KeyW", new_name, "#4488CC"),),
        learned_key_labels=settings.learned_key_labels,
        renames=(FolderRename(old_name, new_name),),
    )


def test_saved_slot_rename_moves_folder_and_copy_register(tmp_path: Path, source_guard) -> None:
    source = source_guard.root
    image = source / "photo.jpg"
    image.write_bytes(b"registered image bytes")
    runtime = create_runtime(tmp_path / "application-data")
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=(Slot("KeyW", "Before", "#4488CC"),),
    )
    source_guard.seal(allowed_destinations={"Before", "After"})
    try:
        runtime.service.open_folder(source)
        plan = runtime.service.plan_slot(image.name, 0)
        result, _ = runtime.service.execute_plan(plan, confirmed_modified=False)
        assert result.status.value == "ok"
        old_copy = source / "Before" / image.name
        digest = old_copy.read_bytes()

        view = _save_rename(runtime, "Before", "After")
        assert view is not None

        assert not (source / "Before").exists()
        assert (source / "After" / image.name).read_bytes() == digest
        assert runtime.service.state_store.copy_records(
            view.snapshot.profile.id, str(source / "After")
        )
        status = runtime.service.slot_status(view.snapshot.current_name, view.generation)
        assert status.slot_states == (SlotState.SELECTED,)
        assert view.renamed == (("Before", "After"),)

        plan = runtime.service.plan_slot(image.name, 0)
        result, _ = runtime.service.execute_plan(plan, confirmed_modified=False)
        assert result.status.value == "ok"
        assert not (source / "After" / image.name).exists()
    finally:
        runtime.shutdown()


def test_occupied_target_rejected_without_changing_slots_or_folders(
    tmp_path: Path, source_guard
) -> None:
    source = source_guard.root
    (source / "Before").mkdir()
    (source / "After").mkdir()
    runtime = create_runtime(tmp_path / "application-data")
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=(Slot("KeyW", "Before", "#4488CC"),),
    )
    source_guard.seal(allowed_destinations={"Before", "After"})
    try:
        runtime.service.open_folder(source)
        before = _active_profile(runtime).slots
        with pytest.raises(FolderManagementError) as error:
            _save_rename(runtime, "Before", "After")
        assert error.value.reason.value == "name_occupied"
        assert _active_profile(runtime).slots == before
        assert (source / "Before").is_dir()
        assert (source / "After").is_dir()
        assert runtime.service.state_store.unfinished_folder_renames() == ()
    finally:
        runtime.shutdown()


def test_multi_rename_rolls_back_after_second_physical_rename_raises(
    tmp_path: Path, source_guard, monkeypatch
) -> None:
    source = source_guard.root
    (source / "One").mkdir()
    (source / "Two").mkdir()
    runtime = create_runtime(tmp_path / "application-data")
    original_slots = (
        Slot("KeyW", "One", "#4488CC"),
        Slot("KeyQ", "Two", "#44AA88"),
    )
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=original_slots,
    )
    source_guard.seal(allowed_destinations={"One", "Two", "First", "Second"})
    try:
        runtime.service.open_folder(source)
        filesystem = runtime.service.filesystem
        original_rename = filesystem.rename_destination_folder
        attempts = 0

        def fail_after_second_move(root, old_name, new_name, intermediate_name=None):
            nonlocal attempts
            attempts += 1
            if attempts == 2:
                original_rename(root, old_name, new_name, intermediate_name)
                raise OSError("injected failure after rename")
            return original_rename(root, old_name, new_name, intermediate_name)

        monkeypatch.setattr(filesystem, "rename_destination_folder", fail_after_second_move)
        settings = runtime.service.settings
        with pytest.raises(FolderManagementError):
            runtime.service.save_settings_and_profile_slots(
                reopen_last_folder=settings.reopen_last_folder,
                sort_direction=settings.sort_direction,
                language=settings.language,
                sound_enabled=settings.sound_enabled,
                global_slot_template=settings.global_slot_template,
                profile_slots=(
                    Slot("KeyW", "First", "#4488CC"),
                    Slot("KeyQ", "Second", "#44AA88"),
                ),
                learned_key_labels=settings.learned_key_labels,
                renames=(FolderRename("One", "First"), FolderRename("Two", "Second")),
            )

        assert (source / "One").is_dir()
        assert (source / "Two").is_dir()
        assert not (source / "First").exists()
        assert not (source / "Second").exists()
        assert _active_profile(runtime).slots == original_slots
        assert runtime.service.state_store.unfinished_folder_renames() == ()
    finally:
        runtime.shutdown()


def test_case_only_rename_and_missing_old_folder(tmp_path: Path, source_guard) -> None:
    source = source_guard.root
    (source / "Before").mkdir()
    runtime = create_runtime(tmp_path / "application-data")
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=(Slot("KeyW", "Before", "#4488CC"),),
    )
    source_guard.seal(allowed_destinations={"Before", "bEFORE", "After"})
    try:
        runtime.service.open_folder(source)
        _save_rename(runtime, "Before", "bEFORE")
        assert (source / "bEFORE").is_dir()
        assert not (source / "Before").exists()
        (source / "bEFORE").rmdir()
        _save_rename(runtime, "bEFORE", "After")
        assert not (source / "After").exists()
        assert _active_profile(runtime).slots[0].destination_name == "After"
    finally:
        runtime.shutdown()


def test_journaled_rename_without_physical_move_is_rolled_back_on_open(
    tmp_path: Path, source_guard, monkeypatch
) -> None:
    source = source_guard.root
    (source / "Before").mkdir()
    app_data = tmp_path / "application-data"
    runtime = create_runtime(app_data)
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=(Slot("KeyW", "Before", "#4488CC"),),
    )
    source_guard.seal(allowed_destinations={"Before", "After"})
    runtime.service.open_folder(source)
    state = runtime.service.state_store
    original_start = state.start_folder_renames

    def start_then_crash(*args, **kwargs):
        original_start(*args, **kwargs)
        raise SimulatedCrash

    monkeypatch.setattr(state, "start_folder_renames", start_then_crash)
    with pytest.raises(SimulatedCrash):
        _save_rename(runtime, "Before", "After")
    runtime.shutdown()

    recovered_runtime = create_runtime(app_data)
    try:
        view = recovered_runtime.service.open_folder(source)
        assert not view.snapshot.recovery_pending
        assert view.snapshot.profile.slots[0].destination_name == "Before"
        assert (source / "Before").is_dir()
        assert not (source / "After").exists()
        assert recovered_runtime.service.state_store.unfinished_folder_renames() == ()
    finally:
        recovered_runtime.shutdown()


def test_interrupted_physical_rename_is_recovered_before_session_use(
    tmp_path: Path, source_guard, monkeypatch
) -> None:
    source = source_guard.root
    (source / "Before").mkdir()
    app_data = tmp_path / "application-data"
    runtime = create_runtime(app_data)
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=(Slot("KeyW", "Before", "#4488CC"),),
    )
    source_guard.seal(allowed_destinations={"Before", "After"})
    runtime.service.open_folder(source)
    filesystem = runtime.service.filesystem
    original = filesystem.rename_destination_folder

    def rename_then_crash(*args, **kwargs):
        original(*args, **kwargs)
        raise SimulatedCrash

    monkeypatch.setattr(filesystem, "rename_destination_folder", rename_then_crash)
    with pytest.raises(SimulatedCrash):
        _save_rename(runtime, "Before", "After")
    runtime.shutdown()

    recovered_runtime = create_runtime(app_data)
    try:
        view = recovered_runtime.service.open_folder(source)
        assert not view.snapshot.recovery_pending
        assert recovered_runtime.service.state_store.unfinished_folder_renames() == ()
        assert view.snapshot.profile.slots[0].destination_name == "After"
        assert (source / "After").is_dir()
        assert not (source / "Before").exists()
        assert recovered_runtime.service.state_store.unfinished_folder_renames() == ()
    finally:
        recovered_runtime.shutdown()
