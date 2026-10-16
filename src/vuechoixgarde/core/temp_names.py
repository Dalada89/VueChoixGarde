"""Generate and recognize owned temporary filenames for FR-046."""

import re
from uuid import UUID

from vuechoixgarde.core.comparison import comparison_key

_TEMP_NAME_PATTERN = re.compile(r"\.vuechoixgarde-([0-9a-f]{32})-(0|[1-9][0-9]*)\.tmp")


def temp_file_name(operation_id: str, index: int) -> str:
    """Build a reserved temp filename from a canonical UUID4 hex operation ID."""
    try:
        parsed = UUID(hex=operation_id)
    except (AttributeError, ValueError) as error:
        raise ValueError("operation_id must be a canonical UUID4 hex string") from error
    if parsed.hex != operation_id or parsed.version != 4:
        raise ValueError("operation_id must be a canonical UUID4 hex string")
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise ValueError("index must be a non-negative integer")
    return f".vuechoixgarde-{operation_id}-{index}.tmp"


def is_reserved_temp_name(name: str) -> bool:
    """Return whether a name matches the application's reserved temp pattern."""
    match = _TEMP_NAME_PATTERN.fullmatch(comparison_key(name))
    if match is None:
        return False
    try:
        return UUID(hex=match.group(1)).version == 4
    except ValueError:
        return False
