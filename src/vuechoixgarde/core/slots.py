"""Model and validate slot profiles for FR-031, FR-032 and FR-033."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from vuechoixgarde.core.comparison import comparison_key
from vuechoixgarde.core.folder_names import FolderNameError, validate_folder_name
from vuechoixgarde.core.keys import is_allowed_slot_key


@dataclass(frozen=True)
class Slot:
    """One destination slot with a physical key position, optional name and color."""

    key_position: str
    destination_name: str | None
    color: str


@dataclass(frozen=True)
class SlotProfile:
    """An immutable ordered profile of destination slots."""

    slots: tuple[Slot, ...]


class ProfileError(StrEnum):
    """Stable slot-profile validation reasons suitable for translation."""

    TOO_FEW_SLOTS = "too_few_slots"
    TOO_MANY_SLOTS = "too_many_slots"
    INVALID_KEY = "invalid_key"
    DUPLICATE_KEY = "duplicate_key"
    DUPLICATE_NAME = "duplicate_name"
    INVALID_NAME = "invalid_name"


@dataclass(frozen=True)
class ProfileIssue:
    """A profile validation issue with the slot indexes that caused it."""

    error: ProfileError
    slot_indexes: tuple[int, ...]
    name_error: FolderNameError | None = None


DEFAULT_SLOTS = (
    Slot("KeyW", None, "#E57373"),
    Slot("KeyA", None, "#64B5F6"),
    Slot("KeyS", None, "#81C784"),
    Slot("KeyD", None, "#FFD54F"),
)


def validate_slot_profile(slots: Sequence[Slot]) -> tuple[ProfileIssue, ...]:
    """Return all FR-032/FR-033 validation issues with affected slot indexes."""
    issues: list[ProfileIssue] = []
    if not 1 <= len(slots) <= 12:
        error = ProfileError.TOO_FEW_SLOTS if not slots else ProfileError.TOO_MANY_SLOTS
        issues.append(ProfileIssue(error, ()))

    keys: dict[str, list[int]] = {}
    names: dict[str, list[int]] = {}
    for index, slot in enumerate(slots):
        if not is_allowed_slot_key(slot.key_position):
            issues.append(ProfileIssue(ProfileError.INVALID_KEY, (index,)))
        keys.setdefault(slot.key_position, []).append(index)
        if slot.destination_name is not None:
            name_error = validate_folder_name(slot.destination_name)
            if name_error is not None:
                issues.append(ProfileIssue(ProfileError.INVALID_NAME, (index,), name_error))
            names.setdefault(comparison_key(slot.destination_name), []).append(index)

    issues.extend(
        ProfileIssue(ProfileError.DUPLICATE_KEY, tuple(indexes))
        for indexes in keys.values()
        if len(indexes) > 1
    )
    issues.extend(
        ProfileIssue(ProfileError.DUPLICATE_NAME, tuple(indexes))
        for indexes in names.values()
        if len(indexes) > 1
    )
    return tuple(issues)
