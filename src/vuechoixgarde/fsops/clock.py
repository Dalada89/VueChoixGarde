"""System clock implementation for the `Clock` port."""

from datetime import UTC, datetime


class SystemClock:
    """Return the current timezone-aware UTC time."""

    def now_utc(self) -> datetime:
        """Return current UTC time with timezone information."""
        return datetime.now(UTC)
