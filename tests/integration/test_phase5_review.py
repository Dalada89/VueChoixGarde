from pathlib import Path
from typing import Any, cast

import pytest

from vuechoixgarde.app.results import RecoveryReport, SlotState
from vuechoixgarde.app.session import FolderSession
from vuechoixgarde.app.toggle import execute_toggle, plan_toggle
from vuechoixgarde.core.slots import Slot
from vuechoixgarde.fsops.filesystem import LocalFileSystem
from vuechoixgarde.fsops.lock import LocalFolderLockFactory
from vuechoixgarde.ports.models import Settings
from vuechoixgarde.ports.settings import SettingsStore
from vuechoixgarde.store.settings import JsonSettingsStore
from vuechoixgarde.store.state import SQLiteStateStore


class FailedSaveSettingsStore:
    def __init__(self, inner: JsonSettingsStore) -> None:
        self.inner = inner

    def load(self, locale_name: str | None = None):
        return self.inner.load(locale_name)

    def save(self, settings: Settings) -> None:
        raise OSError("settings storage is unavailable")

    def reset_damaged(self) -> Path | None:
        return self.inner.reset_damaged()


def test_slot_state_reconciliation_is_scoped_to_destination_folder(
    tmp_path: Path, fixed_clock: Any, source_guard: Any
) -> None:
    root = source_guard.root
    source = root / "IMG_1.jpg"
    source.write_bytes(b"same-image-bytes")
    app_data = tmp_path / "app-data"
    filesystem = LocalFileSystem()
    state = SQLiteStateStore(app_data, fixed_clock)
    state.load()
    settings_store = JsonSettingsStore(app_data, fixed_clock)
    settings = settings_store.defaults()
    profile = state.create_profile_from_template(
        filesystem.folder_identity(root),
        str(root),
        (
            Slot("KeyW", "Red", "#ff0000"),
            Slot("KeyA", "Blue", "#0000ff"),
        ),
    )
    session = FolderSession.open(
        root,
        filesystem,
        filesystem,
        state,
        settings_store,
        settings,
        LocalFolderLockFactory(app_data),
    )
    for index in (0, 1):
        plan = plan_toggle(profile, root, source.name, index, filesystem, filesystem, state)
        execute_toggle(plan, profile, filesystem, filesystem, state, fixed_clock, session.gate)
    (root / "Red" / source.name).write_bytes(b"modified-copy!!")
    source_guard.seal(allowed_destinations={"Red", "Blue"})

    assert session.reconcile(automatic=False)
    assert session.slot_states() == (SlotState.MODIFIED, SlotState.SELECTED)
    session.close()


def test_recovery_pending_survives_reconciliation_in_session_snapshot(
    tmp_path: Path, fixed_clock: Any, source_guard: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = source_guard.root
    (root / "one.jpg").write_bytes(b"image")
    app_data = tmp_path / "app-data"
    filesystem = LocalFileSystem()
    state = SQLiteStateStore(app_data, fixed_clock)
    state.load()
    settings_store = JsonSettingsStore(app_data, fixed_clock)
    monkeypatch.setattr(
        "vuechoixgarde.app.session.recover_operations",
        lambda *_args, **_kwargs: RecoveryReport((), ("pending-operation",), ()),
    )
    source_guard.seal()

    session = FolderSession.open(
        root,
        filesystem,
        filesystem,
        state,
        settings_store,
        settings_store.defaults(),
        LocalFolderLockFactory(app_data),
    )

    assert not session.checking
    assert session.snapshot().recovery_pending
    assert session.slot_states() == (SlotState.CHECKING,) * len(session.profile.slots)
    session.close()


def test_sort_direction_save_failure_leaves_navigation_and_settings_unchanged(
    tmp_path: Path, fixed_clock: Any, source_guard: Any
) -> None:
    root = source_guard.root
    (root / "one.jpg").write_bytes(b"one")
    (root / "two.jpg").write_bytes(b"two")
    app_data = tmp_path / "app-data"
    filesystem = LocalFileSystem()
    state = SQLiteStateStore(app_data, fixed_clock)
    state.load()
    original_store = JsonSettingsStore(app_data, fixed_clock)
    settings = original_store.defaults()
    session = FolderSession.open(
        root,
        filesystem,
        filesystem,
        state,
        cast(SettingsStore, FailedSaveSettingsStore(original_store)),
        settings,
        LocalFolderLockFactory(app_data),
    )
    source_guard.seal()
    original = session.snapshot()

    with pytest.raises(OSError):
        session.set_sort_direction(descending=True)

    current = session.snapshot()
    assert current.current_name == original.current_name
    assert current.descending is False
    assert current.profile == original.profile
    assert session.settings.sort_direction == "asc"
    session.close()
