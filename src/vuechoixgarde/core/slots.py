"""Model and validate slot profiles for FR-031, FR-032 and FR-033."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from vuechoixgarde.core.comparison import comparison_key
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


DEFAULT_SLOTS = (
    Slot("KeyW", None, "#E57373"),
    Slot("KeyA", None, "#64B5F6"),
    Slot("KeyS", None, "#81C784"),
    Slot("KeyD", None, "#FFD54F"),
)


def validate_slot_profile(slots: Sequence[Slot]) -> tuple[ProfileError, ...]:
    """Return all FR-032/FR-033 profile errors without mutating slot data."""
    errors: list[ProfileError] = []
    if not 1 <= len(slots) <= 12:
        errors.append(ProfileError.TOO_FEW_SLOTS if not slots else ProfileError.TOO_MANY_SLOTS)

    keys = [slot.key_position for slot in slots]
    if any(not is_allowed_slot_key(key) for key in keys):
        errors.append(ProfileError.INVALID_KEY)
    if len(set(keys)) != len(keys):
        errors.append(ProfileError.DUPLICATE_KEY)

    names = [
        comparison_key(slot.destination_name) for slot in slots if slot.destination_name is not None
    ]
    if len(set(names)) != len(names):
        errors.append(ProfileError.DUPLICATE_NAME)
    return tuple(errors)
