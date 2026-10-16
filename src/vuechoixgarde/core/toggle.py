"""Decide copy-toggle actions from verified file states for FR-044 through FR-050 and FR-063."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class FileClass(StrEnum):
    """Actual target-file class after stale register entries become absent."""

    ABSENT = "absent"
    VERIFIED = "verified"
    MODIFIED = "modified"
    FOREIGN = "foreign"


class ToggleAction(StrEnum):
    """Possible pure outcomes of a slot activation."""

    TOGGLE_ON = "toggle_on"
    TOGGLE_OFF = "toggle_off"
    TOGGLE_OFF_CONFIRM = "toggle_off_confirm"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class TogglePlan:
    """Decision and indexes of absent sidecars to copy during toggle-on."""

    action: ToggleAction
    sidecar_indexes_to_copy: tuple[int, ...] = ()


def decide_toggle(
    image: FileClass,
    sidecars: Sequence[FileClass],
    *,
    register_available: bool = True,
) -> TogglePlan:
    """Choose the FR-044 through FR-050 action without performing I/O."""
    if not register_available:
        image = FileClass.ABSENT if image is FileClass.ABSENT else FileClass.FOREIGN
        sidecars = tuple(
            FileClass.ABSENT if state is FileClass.ABSENT else FileClass.FOREIGN
            for state in sidecars
        )

    if image is FileClass.FOREIGN:
        return TogglePlan(ToggleAction.CONFLICT)
    if image is FileClass.MODIFIED:
        return TogglePlan(ToggleAction.TOGGLE_OFF_CONFIRM)
    if image is FileClass.VERIFIED:
        action = (
            ToggleAction.TOGGLE_OFF_CONFIRM
            if FileClass.MODIFIED in sidecars
            else ToggleAction.TOGGLE_OFF
        )
        return TogglePlan(action)
    if any(state in {FileClass.FOREIGN, FileClass.MODIFIED} for state in sidecars):
        return TogglePlan(ToggleAction.CONFLICT)
    return TogglePlan(
        ToggleAction.TOGGLE_ON,
        tuple(index for index, state in enumerate(sidecars) if state is FileClass.ABSENT),
    )
