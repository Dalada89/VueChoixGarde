"""Settings persistence contract for Section 6.2 and FR-060."""

from typing import Protocol

from vuechoixgarde.ports.models import Settings, SettingsLoadResult


class SettingsStore(Protocol):
    """Load validated global settings or atomically save them."""

    def load(self, locale_name: str | None = None) -> SettingsLoadResult:
        """Load, create defaults if missing, or report damaged data without replacing it."""
        ...

    def save(self, settings: Settings) -> None:
        """Validate and atomically persist settings."""
        ...
