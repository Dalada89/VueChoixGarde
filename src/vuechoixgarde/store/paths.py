"""Resolve and prepare per-user application data paths (Technical Design 6.1)."""

from pathlib import Path

from platformdirs import user_data_dir


def application_data_dir(root: Path | None = None) -> Path:
    """Return an injected root for tests or the platform-specific app-data root."""
    return (
        root
        if root is not None
        else Path(user_data_dir("VueChoixGarde", appauthor=False, roaming=False))
    )


def prepare_application_data(root: Path) -> None:
    """Create the app-data root and its locks/logs directories."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "locks").mkdir(exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
