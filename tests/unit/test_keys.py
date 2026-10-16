from typing import cast

import pytest

from vuechoixgarde.core.keys import (
    ALLOWED_SLOT_CODES,
    displayed_key_label,
    initial_key_label,
    is_allowed_slot_key,
    is_slot_key_triggered,
    printable_key_label,
    update_learned_key_labels,
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


def test_azerty_labels_are_learned_from_printed_characters() -> None:
    labels = update_learned_key_labels({}, "KeyW", "z", modifier_active=False)
    assert [displayed_key_label(code, labels) for code in ("KeyW", "KeyA", "KeyS", "KeyD")] == [
        "Z",
        "A",
        "S",
        "D",
    ]
    labels = update_learned_key_labels(labels, "KeyA", "q", modifier_active=False)
    assert [displayed_key_label(code, labels) for code in ("KeyW", "KeyA", "KeyS", "KeyD")] == [
        "Z",
        "Q",
        "S",
        "D",
    ]


def test_uppercase_expansion_preserves_the_original_character() -> None:
    assert printable_key_label("ß") == "ß"
    assert update_learned_key_labels({}, "KeyS", "ß", modifier_active=False)["KeyS"] == "ß"


@pytest.mark.parametrize("text", ["", "\u0301", "\x01", "ab", "\n"])
def test_unprintable_or_multi_character_text_does_not_learn(text: str) -> None:
    existing = {"KeyW": "Z"}
    labels = update_learned_key_labels(existing, "KeyW", text, modifier_active=False)
    assert labels == existing


@pytest.mark.parametrize(
    ("position", "text", "modifier_active"),
    [("KeyW", "x", True), ("ArrowLeft", "x", False)],
)
def test_modifier_or_disallowed_position_does_not_learn(
    position: str, text: str, modifier_active: bool
) -> None:
    existing = {"KeyW": "Z"}
    labels = update_learned_key_labels(existing, position, text, modifier_active=modifier_active)
    assert labels == existing


def test_label_mappings_are_immutable() -> None:
    labels = update_learned_key_labels({}, "KeyW", "z", modifier_active=False)
    with pytest.raises(TypeError):
        cast(dict[str, str], labels)["KeyW"] = "A"
