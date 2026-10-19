"""Per-source-folder lock contract for NFR-043."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self


class FolderLockFactory(Protocol):
    """Create a lock for a canonical source-folder identity."""

    def create(self, identity: str) -> FolderLock:
        """Return an unacquired lock for `identity`."""
        ...


class FolderLock(Protocol):
    """Acquire/release one source-folder lock and support context management."""

    def acquire(self) -> None:
        """Acquire the lock or raise a typed `FOLDER_LOCKED` error."""
        ...

    def release(self) -> None:
        """Release the held lock; repeated release is safe."""
        ...

    def __enter__(self) -> Self:
        """Acquire and return this lock."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release this lock on leaving a context."""
        ...
