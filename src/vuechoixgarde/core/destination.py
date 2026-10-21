"""Stable keys for direct destination folders stored in the copy register."""

from pathlib import Path


def destination_folder_key(source_root: Path, exact_name: str) -> str:
    """Return the exact folder path representation shared by copy and rename records."""
    return str(source_root / exact_name)
