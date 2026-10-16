import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest


class SourceFolderGuard:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._sealed = False
        self._allowed_destinations: frozenset[str] = frozenset()
        self._expected: dict[str, tuple[str, str]] = {}

    def seal(self, *, allowed_destinations: set[str] | None = None) -> None:
        self._allowed_destinations = frozenset(allowed_destinations or ())
        self._expected = self._snapshot()
        self._sealed = True

    def assert_unchanged(self) -> None:
        if not self._sealed:
            raise AssertionError("SourceFolderGuard.seal() was not called")
        actual = self._snapshot()
        if actual != self._expected:
            raise AssertionError(
                f"source folder changed: expected={self._expected!r}, actual={actual!r}"
            )

    def _snapshot(self) -> dict[str, tuple[str, str]]:
        snapshot: dict[str, tuple[str, str]] = {}
        for path in sorted(self.root.rglob("*")):
            relative = path.relative_to(self.root)
            if relative.parts and relative.parts[0] in self._allowed_destinations:
                continue
            key = relative.as_posix()
            if path.is_symlink():
                target = path.readlink().as_posix()
                try:
                    resolved_target = path.resolve(strict=True)
                    resolved_target.relative_to(self.root.parent.resolve())
                    if resolved_target.is_file():
                        target += ":" + hashlib.sha256(resolved_target.read_bytes()).hexdigest()
                except (OSError, ValueError, RuntimeError):
                    target += ":unavailable"
                snapshot[key] = ("symlink", target)
            elif path.is_dir():
                snapshot[key] = ("directory", "")
            elif path.is_file():
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                snapshot[key] = ("file", digest)
        return snapshot


@pytest.fixture
def source_guard(tmp_path: Path) -> Iterator[SourceFolderGuard]:
    root = tmp_path / "source"
    root.mkdir()
    guard = SourceFolderGuard(root)
    yield guard
    guard.assert_unchanged()


class FixedClock:
    def now_utc(self) -> datetime:
        return datetime(2025, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)


@pytest.fixture
def fixed_clock() -> FixedClock:
    return FixedClock()
