"""Validate portable destination folder names for FR-034."""

from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath

from vuechoixgarde.core.comparison import comparison_key


class FolderNameError(StrEnum):
    """Stable validation reasons suitable for translation by the UI."""

    EMPTY = "empty"
    ONLY_SPACES_AND_DOTS = "only_spaces_and_dots"
    DOT_SEGMENT = "dot_segment"
    ABSOLUTE_PATH = "absolute_path"
    PATH_SEPARATOR = "path_separator"
    INVALID_CHARACTER = "invalid_character"
    TRAILING_SPACE_OR_DOT = "trailing_space_or_dot"
    RESERVED_DEVICE_NAME = "reserved_device_name"


_INVALID_CHARACTERS = frozenset('<>:"/\\|?*')
_RESERVED_NAMES = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{digit}" for digit in "123456789¹²³"),
        *(f"lpt{digit}" for digit in "123456789¹²³"),
    }
)


def validate_folder_name(name: str) -> FolderNameError | None:
    """Return a distinct FR-034 error reason, or None when the name is valid."""
    if not name:
        return FolderNameError.EMPTY
    if name in {".", ".."}:
        return FolderNameError.DOT_SEGMENT
    if all(character in " ." for character in name):
        return FolderNameError.ONLY_SPACES_AND_DOTS
    if PurePosixPath(name).is_absolute() or PureWindowsPath(name).is_absolute():
        return FolderNameError.ABSOLUTE_PATH
    if "/" in name or "\\" in name:
        return FolderNameError.PATH_SEPARATOR
    if name.endswith((" ", ".")):
        return FolderNameError.TRAILING_SPACE_OR_DOT
    if any(character in _INVALID_CHARACTERS or ord(character) < 32 for character in name):
        return FolderNameError.INVALID_CHARACTER
    device_base = name.split(".", maxsplit=1)[0].rstrip(" .")
    if comparison_key(device_base) in _RESERVED_NAMES:
        return FolderNameError.RESERVED_DEVICE_NAME
    return None
