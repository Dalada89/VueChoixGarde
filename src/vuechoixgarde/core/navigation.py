"""Implement bounded navigation and list refresh for FR-007, FR-009, FR-024 and FR-025."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from vuechoixgarde.core.comparison import comparison_key
from vuechoixgarde.core.sorting import natural_sort_key, sort_names


class NavigationDirection(StrEnum):
    """Direction in the current sorted image list."""

    PREVIOUS = "previous"
    NEXT = "next"


@dataclass(frozen=True)
class ImageNavigation:
    """Immutable image list, current filename and sort direction."""

    images: tuple[str, ...]
    current: str | None
    descending: bool = False


def create_navigation(
    filenames: Sequence[str], *, current: str | None = None, descending: bool = False
) -> ImageNavigation:
    """Create a sorted navigation state, preserving a matching current image when possible."""
    images = tuple(sort_names(filenames, descending=descending))
    selected = _matching_name(images, current) if current is not None else None
    return ImageNavigation(images, selected or (images[0] if images else None), descending)


def navigate(state: ImageNavigation, direction: NavigationDirection) -> ImageNavigation:
    """Move one image without wrapping at either list boundary."""
    if not state.images or state.current is None:
        return state
    try:
        index = state.images.index(state.current)
    except ValueError:
        index = 0
    step = 1 if direction is NavigationDirection.NEXT else -1
    target = min(max(index + step, 0), len(state.images) - 1)
    return ImageNavigation(state.images, state.images[target], state.descending)


def change_sort_direction(state: ImageNavigation, *, descending: bool) -> ImageNavigation:
    """Change ordering while keeping the same current image selected (FR-009)."""
    images = tuple(sort_names(state.images, descending=descending))
    selected = _matching_name(images, state.current)
    return ImageNavigation(images, selected or (images[0] if images else None), descending)


def refresh_navigation(state: ImageNavigation, filenames: Sequence[str]) -> ImageNavigation:
    """Preserve the current image or select its nearest following refreshed image (FR-007)."""
    images = tuple(sort_names(filenames, descending=state.descending))
    if not images:
        return ImageNavigation((), None, state.descending)
    existing = _matching_name(images, state.current)
    if existing is not None:
        return ImageNavigation(images, existing, state.descending)
    if state.current is None:
        return ImageNavigation(images, images[0], state.descending)

    current_key = natural_sort_key(state.current)
    if state.descending:
        following = [name for name in images if natural_sort_key(name) < current_key]
        selected = max(following, key=natural_sort_key) if following else images[-1]
    else:
        following = [name for name in images if natural_sort_key(name) > current_key]
        selected = min(following, key=natural_sort_key) if following else images[-1]
    return ImageNavigation(images, selected, state.descending)


def _matching_name(filenames: Sequence[str], current: str | None) -> str | None:
    if current is None:
        return None
    if current in filenames:
        return current
    key = comparison_key(current)
    return next((name for name in filenames if comparison_key(name) == key), None)
