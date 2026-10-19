"""Structured event logging contract for FR-091 and FR-092."""

from enum import StrEnum
from typing import Protocol


class LogLevel(StrEnum):
    """Supported severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class LogEvent(StrEnum):
    """Stable structured event names emitted by application use cases."""

    APP_START = "app_start"
    APP_STOP = "app_stop"
    FOLDER_OPEN = "folder_open"
    FOLDER_OPEN_FAILED = "folder_open_failed"
    FOLDER_CLOSE = "folder_close"
    COPY = "copy"
    DELETE = "delete"
    CONFLICT = "conflict"
    ROLLBACK = "rollback"
    RECOVERY = "recovery"
    RECONCILE = "reconcile"
    DAMAGED_DATA = "damaged_data"
    ERROR = "error"


class EventLogger(Protocol):
    """Write a structured event without imposing a concrete logging backend."""

    def log(self, level: LogLevel, event: LogEvent, message: str, **fields: object) -> None:
        """Record an event and its privacy-safe optional fields."""
        ...
