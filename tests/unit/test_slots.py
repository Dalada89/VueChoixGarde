import pytest

from vuechoixgarde.core.folder_names import FolderNameError
from vuechoixgarde.core.slots import (
    DEFAULT_SLOTS,
    ProfileError,
    Slot,
    validate_slot_profile,
)


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
    assert any(issue.error is expected for issue in validate_slot_profile(slots))


def test_default_slots_have_unique_keys_distinct_colors_and_no_names() -> None:
    assert [slot.key_position for slot in DEFAULT_SLOTS] == ["KeyW", "KeyA", "KeyS", "KeyD"]
    assert len({slot.color for slot in DEFAULT_SLOTS}) == 4
    assert all(slot.destination_name is None for slot in DEFAULT_SLOTS)
    assert validate_slot_profile(DEFAULT_SLOTS) == ()


def test_twelve_slots_are_allowed() -> None:
    from vuechoixgarde.core.keys import ALLOWED_SLOT_CODES

    slots = tuple(Slot(code, None, "#000000") for code in sorted(ALLOWED_SLOT_CODES)[:12])
    assert validate_slot_profile(slots) == ()


def test_duplicate_key_issue_reports_all_colliding_indexes() -> None:
    slots = (Slot("KeyW", "Best", "#111111"), Slot("KeyW", "Other", "#222222"))
    (issue,) = validate_slot_profile(slots)
    assert issue.error is ProfileError.DUPLICATE_KEY
    assert issue.slot_indexes == (0, 1)
    assert issue.name_error is None


def test_duplicate_names_use_casefolded_nfc_comparison_and_report_indexes() -> None:
    slots = (Slot("KeyW", "Best", "#111111"), Slot("KeyA", "best", "#222222"))
    (issue,) = validate_slot_profile(slots)
    assert issue.error is ProfileError.DUPLICATE_NAME
    assert issue.slot_indexes == (0, 1)


def test_disallowed_key_issue_reports_its_slot_index() -> None:
    (issue,) = validate_slot_profile((Slot("ArrowLeft", None, "#111111"),))
    assert issue.error is ProfileError.INVALID_KEY
    assert issue.slot_indexes == (0,)


def test_invalid_destination_name_reports_folder_error_and_slot_index() -> None:
    (issue,) = validate_slot_profile((Slot("KeyW", "CON.txt", "#111111"),))
    assert issue.error is ProfileError.INVALID_NAME
    assert issue.slot_indexes == (0,)
    assert issue.name_error is FolderNameError.RESERVED_DEVICE_NAME


def test_each_invalid_name_has_a_separate_issue() -> None:
    slots = (Slot("KeyW", "", "#111111"), Slot("KeyA", "Good", "#222222"))
    issues = validate_slot_profile(slots)
    assert [(issue.error, issue.slot_indexes, issue.name_error) for issue in issues] == [
        (ProfileError.INVALID_NAME, (0,), FolderNameError.EMPTY)
    ]
