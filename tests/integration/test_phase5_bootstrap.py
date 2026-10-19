from pathlib import Path

from PIL import Image

from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.fsops.clock import SystemClock
from vuechoixgarde.store.settings import JsonSettingsStore


def test_damaged_sqlite_is_kept_unchanged_and_folder_opens_view_only(tmp_path: Path) -> None:
    data_dir = tmp_path / "app-data"
    settings = JsonSettingsStore(data_dir, SystemClock())
    settings.save(settings.defaults())
    state_path = data_dir / "state.sqlite3"
    damaged_bytes = b"not a sqlite database"
    state_path.write_bytes(damaged_bytes)
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (4, 3), "red").save(source / "one.png")

    runtime = create_runtime(data_dir, damaged_choice=False)
    view = runtime.service.open_folder(source)

    assert not runtime.register_available
    assert view.snapshot.current_name == "one.png"
    assert all(slot.destination_name is None for slot in view.snapshot.profile.slots)
    assert state_path.read_bytes() == damaged_bytes
    runtime.shutdown()
    assert state_path.read_bytes() == damaged_bytes


def test_accepting_only_damaged_sqlite_keeps_settings_and_quarantines_database(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "app-data"
    settings_store = JsonSettingsStore(data_dir, SystemClock())
    original_settings = settings_store.defaults()
    settings_store.save(original_settings)
    state_path = data_dir / "state.sqlite3"
    damaged_bytes = b"corrupted sqlite bytes"
    state_path.write_bytes(damaged_bytes)

    runtime = create_runtime(data_dir, damaged_choice=True)

    quarantined = tuple(data_dir.glob("state.sqlite3.damaged-*"))
    assert runtime.register_available
    assert runtime.settings == original_settings
    assert settings_store.load().settings == original_settings
    assert len(quarantined) == 1
    assert quarantined[0].read_bytes() == damaged_bytes
    assert state_path.read_bytes() != damaged_bytes
    runtime.shutdown()
