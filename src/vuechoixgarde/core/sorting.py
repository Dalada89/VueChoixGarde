"""Provide deterministic natural filename sorting for FR-008 and FR-009."""

import re
from collections.abc import Sequence

from vuechoixgarde.core.comparison import comparison_key

NaturalSortKey = tuple[tuple[tuple[int, int | str], ...], str]


def natural_sort_key(name: str) -> NaturalSortKey:
    """Build a case-insensitive natural key with an exact-name tie-breaker."""
    parts = tuple(
        (0, int(part)) if part.isdecimal() else (1, comparison_key(part))
        for part in re.split(r"(\d+)", name)
    )
    return parts, name


def sort_names(names: Sequence[str], *, descending: bool = False) -> list[str]:
    """Sort filenames naturally in either direction while keeping ties deterministic."""
    return sorted(names, key=natural_sort_key, reverse=descending)
