import pytest

from vuechoixgarde.core.keys import (
    ALLOWED_SLOT_CODES,
    initial_key_label,
    is_allowed_slot_key,
    is_slot_key_triggered,
)


@pytest.mark.parametrize("code", sorted(ALLOWED_SLOT_CODES))
def test_every_main_block_code_is_allowed(code: str) -> None:
    assert is_allowed_slot_key(code)
    assert is_slot_key_triggered(code, modifier_active=False)


@pytest.mark.parametrize(
    "code",
    ["ArrowLeft", "F1", "Escape", "Enter", "Tab", "Space", "Backspace", "Delete", "ShiftLeft"],
)
def test_reserved_positions_are_not_slot_keys(code: str) -> None:
    assert not is_allowed_slot_key(code)
    assert not is_slot_key_triggered(code, modifier_active=False)


@pytest.mark.parametrize("modifier_active", [True, False])
def test_modifier_blocks_slot_activation(modifier_active: bool) -> None:
    assert is_slot_key_triggered("KeyW", modifier_active=modifier_active) is (not modifier_active)


def test_default_startup_labels_follow_us_qwerty_positions() -> None:
    assert [initial_key_label(code) for code in ("KeyW", "KeyA", "KeyS", "KeyD")] == [
        "W",
        "A",
        "S",
        "D",
    ]


def test_punctuation_positions_have_us_qwerty_labels() -> None:
    assert initial_key_label("Minus") == "-"
    assert initial_key_label("IntlBackslash") == "\\"
    assert initial_key_label("ArrowLeft") is None
