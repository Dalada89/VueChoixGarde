"""Explicit quarantine of damaged app-data files after user confirmation (FR-063)."""

import os
from datetime import UTC
from pathlib import Path

from vuechoixgarde.ports.clock import Clock
from vuechoixgarde.ports.errors import SettingsErrorReason, SettingsStoreError


def quarantine_damaged(path: Path, clock: Clock) -> Path:
    """Move a damaged regular file to a unique timestamped sibling without replacement."""
    try:
        path.lstat()
        if not path.is_file() or path.is_symlink():
            raise OSError("damaged data must be a regular file")
        timestamp = clock.now_utc()
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("clock must return timezone-aware UTC time")
        stamp = timestamp.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        base = path.with_name(f"{path.name}.damaged-{stamp}")
        candidate = base
        index = 1
        while True:
            try:
                os.link(path, candidate, follow_symlinks=False)
                break
            except FileExistsError:
                candidate = path.with_name(f"{base.name}-{index}")
                index += 1
        path.unlink()
        return candidate
    except (OSError, ValueError) as error:
        raise SettingsStoreError(
            SettingsErrorReason.IO_ERROR, path=path, detail=str(error)
        ) from error
