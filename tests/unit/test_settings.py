import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from vuechoixgarde.core.keys import ALLOWED_SLOT_CODES
from vuechoixgarde.core.slots import DEFAULT_SLOTS, Slot, SlotMode
from vuechoixgarde.ports.errors import SettingsErrorReason, SettingsStoreError
from vuechoixgarde.ports.models import LoadStatus, Settings
from vuechoixgarde.store.settings import JsonSettingsStore


class _FixedClock:
    def now_utc(self) -> datetime:
        return datetime(2025, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)


@pytest.fixture
def fixed_clock() -> _FixedClock:
    return _FixedClock()


def _valid_settings() -> Settings:
    return Settings(
        schema_version=2,
        language="en",
        sound_enabled=True,
        sort_direction="asc",
        reopen_last_folder=False,
        last_folder=None,
        global_slot_template=DEFAULT_SLOTS,
        learned_key_labels=(("KeyW", "Z"),),
    )


def test_valid_settings_pass_strict_validation() -> None:
    JsonSettingsStore.validate_settings(_valid_settings())


@pytest.mark.parametrize(
    "settings",
    [
        replace(_valid_settings(), language="es"),
        replace(_valid_settings(), sort_direction="forward"),
        replace(_valid_settings(), global_slot_template=(Slot("ArrowLeft", None, "#112233"),)),
        replace(_valid_settings(), global_slot_template=(Slot("KeyW", "CON.txt", "#112233"),)),
        replace(_valid_settings(), global_slot_template=(Slot("KeyW", None, "red"),)),
        replace(
            _valid_settings(),
            global_slot_template=(Slot("KeyW", None, "#112233"), Slot("KeyW", None, "#445566")),
        ),
        replace(_valid_settings(), global_slot_template=()),
        replace(_valid_settings(), learned_key_labels=(("ArrowLeft", "A"),)),
        replace(_valid_settings(), learned_key_labels=(("KeyW", "long"),)),
        replace(
            _valid_settings(),
            learned_key_labels=(("KeyW", "W"), ("KeyW", "Z")),
        ),
    ],
)
def test_invalid_setting_values_raise_a_typed_error(settings: Settings) -> None:
    with pytest.raises(SettingsStoreError) as caught:
        JsonSettingsStore.validate_settings(settings)
    assert caught.value.reason is SettingsErrorReason.INVALID_SETTINGS


def test_slot_modes_roundtrip_in_json_settings(tmp_path, fixed_clock) -> None:
    store = JsonSettingsStore(tmp_path / "app", fixed_clock)
    settings = replace(
        store.defaults("en"),
        global_slot_template=(Slot("KeyR", "trash", "#FF7B7B", SlotMode.MOVE),),
    )

    store.save(settings)
    loaded = store.load()

    assert loaded.settings is not None
    assert loaded.settings.global_slot_template == settings.global_slot_template


def _legacy_settings_payload(slots: tuple[Slot, ...], schema_version: int = 1) -> dict:
    return {
        "schema_version": schema_version,
        "language": "en",
        "sound_enabled": True,
        "sort_direction": "asc",
        "reopen_last_folder": False,
        "last_folder": None,
        "global_slot_template": [
            {
                "key_position": slot.key_position,
                "destination_name": slot.destination_name,
                "color": slot.color,
                **({"mode": slot.mode.value} if schema_version >= 2 else {}),
            }
            for slot in slots
        ],
        "learned_key_labels": {},
    }


def test_legacy_settings_migration_adds_move_slot_once(tmp_path, fixed_clock) -> None:
    store = JsonSettingsStore(tmp_path / "app", fixed_clock)
    old_slots = tuple(Slot(key, None, "#123456") for key in ("KeyW", "KeyA", "KeyS", "KeyD"))
    store.root.mkdir(parents=True, exist_ok=True)
    store.path.write_text(json.dumps(_legacy_settings_payload(old_slots)), encoding="utf-8")

    loaded = store.load()

    assert loaded.settings is not None
    assert loaded.settings.schema_version == 2
    assert loaded.settings.global_slot_template == (
        *old_slots,
        Slot("KeyR", "trash", "#FF7B7B", SlotMode.MOVE),
    )
    assert json.loads(store.path.read_text(encoding="utf-8"))["schema_version"] == 2
    assert store.load().settings == loaded.settings


@pytest.mark.parametrize(
    "slots",
    [
        (Slot("KeyR", None, "#123456"),),
        (Slot("KeyQ", "Trash", "#123456"),),
        tuple(Slot(key, None, "#123456") for key in sorted(ALLOWED_SLOT_CODES)[:12]),
    ],
    ids=("key-occupied", "name-occupied", "twelve-slots"),
)
def test_legacy_settings_migration_skips_when_slot_cannot_be_added(
    tmp_path, fixed_clock, slots: tuple[Slot, ...]
) -> None:
    store = JsonSettingsStore(tmp_path / "app", fixed_clock)
    store.root.mkdir(parents=True, exist_ok=True)
    store.path.write_text(json.dumps(_legacy_settings_payload(slots)), encoding="utf-8")

    loaded = store.load()

    assert loaded.settings is not None
    assert loaded.settings.schema_version == 2
    assert len(loaded.settings.global_slot_template) == len(slots)
    assert all(slot.mode is SlotMode.COPY for slot in loaded.settings.global_slot_template)


def test_current_settings_do_not_restore_removed_move_slot(tmp_path, fixed_clock) -> None:
    store = JsonSettingsStore(tmp_path / "app", fixed_clock)
    current_slots = tuple(Slot(key, None, "#123456") for key in ("KeyW", "KeyA", "KeyS", "KeyD"))
    store.root.mkdir(parents=True, exist_ok=True)
    store.path.write_text(json.dumps(_legacy_settings_payload(current_slots, 2)), encoding="utf-8")

    loaded = store.load()

    assert loaded.settings is not None
    assert loaded.settings.global_slot_template == current_slots
    assert store.load().settings == loaded.settings


def test_damaged_legacy_settings_are_not_overwritten(tmp_path, fixed_clock) -> None:
    store = JsonSettingsStore(tmp_path / "app", fixed_clock)
    store.root.mkdir(parents=True, exist_ok=True)
    damaged = json.dumps(_legacy_settings_payload((Slot("KeyW", None, "not-a-color"),))).encode()
    store.path.write_bytes(damaged)

    loaded = store.load()

    assert loaded.status is LoadStatus.DAMAGED
    assert loaded.settings is None
    assert store.path.read_bytes() == damaged
