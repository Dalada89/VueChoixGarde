import json
from datetime import UTC, datetime
from pathlib import Path

from pytest import MonkeyPatch

from vuechoixgarde.applog.jsonl import JsonlEventLogger
from vuechoixgarde.ports.log import LogEvent, LogLevel


class TestClock:
    def now_utc(self) -> datetime:
        return datetime(2025, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)


def test_jsonl_writes_unicode_and_injected_timestamp(tmp_path: Path) -> None:
    logger = JsonlEventLogger(tmp_path / "logs", clock=TestClock())
    try:
        logger.log(LogLevel.INFO, LogEvent.COPY, "copie réussie", count=2)
    finally:
        logger.close()

    rows = [
        json.loads(line)
        for line in (tmp_path / "logs" / "vuechoixgarde.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert rows == [
        {
            "ts": "2025-01-02T03:04:05.123456+00:00",
            "level": "info",
            "event": "copy",
            "msg": "copie réussie",
            "count": 2,
        }
    ]


def test_jsonl_rotation_is_bounded_to_configured_file_count(tmp_path: Path) -> None:
    logger = JsonlEventLogger(tmp_path / "logs", clock=TestClock(), max_bytes=120, backup_count=2)
    try:
        for index in range(20):
            logger.log(LogLevel.INFO, LogEvent.ERROR, "x" * 60, sequence=index)
    finally:
        logger.close()

    files = tuple((tmp_path / "logs").glob("vuechoixgarde.jsonl*"))
    assert len(files) <= 3
    assert all(file.read_bytes().endswith(b"\n") for file in files)


def test_logger_contains_directory_and_write_failures(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    not_a_directory = tmp_path / "file"
    not_a_directory.write_text("x", encoding="utf-8")
    logger = JsonlEventLogger(not_a_directory / "logs", clock=TestClock())
    logger.log(LogLevel.ERROR, LogEvent.ERROR, "failure")
    logger.close()

    write_logger = JsonlEventLogger(tmp_path / "write-failure", clock=TestClock())
    handler = write_logger._handler
    assert handler is not None
    monkeypatch.setattr(handler, "emit", lambda record: (_ for _ in ()).throw(OSError("disk")))
    write_logger.log(LogLevel.ERROR, LogEvent.ERROR, "failure")
    write_logger.close()


def test_logger_does_not_persist_image_or_metadata_payloads(tmp_path: Path) -> None:
    logger = JsonlEventLogger(tmp_path / "logs", clock=TestClock())
    try:
        logger.log(LogLevel.INFO, LogEvent.RECONCILE, "reconciled", verified=3, modified=0)
    finally:
        logger.close()

    payload = (tmp_path / "logs" / "vuechoixgarde.jsonl").read_text(encoding="utf-8")
    assert "GPS" not in payload
    assert "EXIF" not in payload
    assert "image-bytes" not in payload
    parsed = json.loads(payload)
    assert set(parsed) == {"ts", "level", "event", "msg", "verified", "modified"}
