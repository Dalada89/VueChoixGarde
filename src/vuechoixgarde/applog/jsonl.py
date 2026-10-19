"""Rotating UTF-8 JSON Lines event logger (FR-091/FR-092)."""

from __future__ import annotations

import hashlib
import json
import logging
import logging.handlers
import threading
from enum import Enum
from pathlib import Path
from typing import override

from vuechoixgarde.ports.clock import Clock
from vuechoixgarde.ports.log import LogEvent, LogLevel

_registry_lock = threading.Lock()
_registry: dict[str, tuple[logging.Logger, logging.Handler, int]] = {}


def _safe_repr(value: object) -> str:
    try:
        return repr(value)
    except Exception:
        return "<unrepresentable>"


def _json_value(value: object) -> object:
    if isinstance(value, Path | Enum):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, set | frozenset):
        return [_json_value(item) for item in sorted(value, key=str)]
    try:
        json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError, OverflowError):
        return _safe_repr(value)
    return value


class JsonlFormatter(logging.Formatter):
    """Serialize each structured log record as one privacy-neutral JSON object."""

    def __init__(self, clock: Clock) -> None:
        super().__init__()
        self.clock = clock

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.clock.now_utc()
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware timestamp")
        payload: dict[str, object] = {
            "ts": timestamp.isoformat(),
            "level": record.levelname.lower(),
            "event": str(getattr(record, "event", LogEvent.ERROR.value)),
            "msg": record.getMessage(),
        }
        fields = getattr(record, "fields", {})
        if isinstance(fields, dict):
            payload.update({str(key): _json_value(value) for key, value in fields.items()})
        return json.dumps(payload, ensure_ascii=False, default=_safe_repr, separators=(",", ":"))


class _QuietRotatingFileHandler(logging.handlers.RotatingFileHandler):
    @override
    def handleError(self, record: logging.LogRecord) -> None:
        return


class JsonlEventLogger:
    """Write structured events to a bounded rotating JSONL file."""

    def __init__(
        self,
        log_dir: Path,
        *,
        clock: Clock,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 4,
    ) -> None:
        self.log_dir = log_dir
        self.path = log_dir / "vuechoixgarde.jsonl"
        self._registry_key = str(self.path.absolute())
        self._closed = False
        with _registry_lock:
            registered = _registry.get(self._registry_key)
            if registered is not None:
                logger, handler, references = registered
                _registry[self._registry_key] = (logger, handler, references + 1)
                self._logger = logger
                self._handler: logging.Handler | None = handler
                return

            logger_id = hashlib.sha256(self._registry_key.encode("utf-8")).hexdigest()
            logger = logging.getLogger(f"vuechoixgarde.applog.{logger_id}")
            logger.setLevel(logging.DEBUG)
            logger.propagate = False
            for existing in tuple(logger.handlers):
                logger.removeHandler(existing)
                existing.close()
            handler: logging.Handler | None = None
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                handler = _QuietRotatingFileHandler(
                    self.path,
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                    encoding="utf-8",
                    delay=False,
                )
                handler.setFormatter(JsonlFormatter(clock))
                logger.addHandler(handler)
                _registry[self._registry_key] = (logger, handler, 1)
            except Exception:
                if handler is not None:
                    handler.close()
            self._logger = logger
            self._handler = handler

    def log(self, level: LogLevel, event: LogEvent, message: str, **fields: object) -> None:
        """Record an event; logger or disk errors never escape into the application."""
        if self._closed:
            return
        levels = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
        }
        try:
            self._logger.log(
                levels.get(level, logging.INFO),
                message,
                extra={"event": str(event), "fields": fields},
            )
        except Exception:
            return

    def close(self) -> None:
        """Release this instance's handler reference and close it when no users remain."""
        if self._closed:
            return
        self._closed = True
        with _registry_lock:
            registered = _registry.get(self._registry_key)
            if registered is None:
                return
            logger, handler, references = registered
            if references > 1:
                _registry[self._registry_key] = (logger, handler, references - 1)
                return
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                return
            finally:
                del _registry[self._registry_key]

    def __enter__(self) -> JsonlEventLogger:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
