import pytest

from vuechoixgarde.core.slots import DEFAULT_SLOTS, ProfileError, Slot, validate_slot_profile


@pytest.mark.parametrize(
    ("slots", "expected"),
    [
        ((), ProfileError.TOO_FEW_SLOTS),
        (
            tuple(Slot(f"Key{letter}", None, "#000000") for letter in "ABCDEFGHIJKLM"),
            ProfileError.TOO_MANY_SLOTS,
        ),
    ],
)
def test_slot_count_limits(slots: tuple[Slot, ...], expected: ProfileError) -> None:
    assert expected in validate_slot_profile(slots)


def test_default_slots_have_unique_keys_distinct_colors_and_no_names() -> None:
    assert [slot.key_position for slot in DEFAULT_SLOTS] == ["KeyW", "KeyA", "KeyS", "KeyD"]
    assert len({slot.color for slot in DEFAULT_SLOTS}) == 4
    assert all(slot.destination_name is None for slot in DEFAULT_SLOTS)
    assert validate_slot_profile(DEFAULT_SLOTS) == ()


def test_twelve_slots_are_allowed() -> None:
    from vuechoixgarde.core.keys import ALLOWED_SLOT_CODES

    slots = tuple(Slot(code, None, "#000000") for code in sorted(ALLOWED_SLOT_CODES)[:12])
    assert validate_slot_profile(slots) == ()


def test_duplicate_key_is_rejected() -> None:
    slots = (Slot("KeyW", "Best", "#111111"), Slot("KeyW", "Other", "#222222"))
    assert validate_slot_profile(slots) == (ProfileError.DUPLICATE_KEY,)


def test_duplicate_names_use_casefolded_nfc_comparison() -> None:
    slots = (Slot("KeyW", "Best", "#111111"), Slot("KeyA", "best", "#222222"))
    assert validate_slot_profile(slots) == (ProfileError.DUPLICATE_NAME,)


def test_disallowed_key_is_rejected() -> None:
    assert validate_slot_profile((Slot("ArrowLeft", None, "#111111"),)) == (
        ProfileError.INVALID_KEY,
    )
