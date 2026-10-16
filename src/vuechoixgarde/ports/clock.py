"""Clock boundary shared by application and persistence adapters."""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Provide the current timezone-aware UTC time."""

    def now_utc(self) -> datetime:
        """Return the current time as an aware UTC datetime."""
        ...
