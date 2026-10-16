from dataclasses import replace

import pytest

from vuechoixgarde.core.slots import DEFAULT_SLOTS, Slot
from vuechoixgarde.ports.errors import SettingsErrorReason, SettingsStoreError
from vuechoixgarde.ports.models import Settings
from vuechoixgarde.store.settings import JsonSettingsStore


def _valid_settings() -> Settings:
    return Settings(
        schema_version=1,
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
