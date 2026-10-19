"""Per-source-folder locking backed by `filelock` (NFR-043)."""

import hashlib
from pathlib import Path
from types import TracebackType
from typing import Self

from filelock import FileLock, Timeout

from vuechoixgarde.ports.errors import FolderLockError, FolderLockErrorReason
from vuechoixgarde.ports.lock import FolderLock


class LocalFolderLock:
    """Hold one application-data lock for the lifetime of an open source folder."""

    def __init__(self, app_data_dir: Path, identity: str) -> None:
        self._locks_dir = app_data_dir / "locks"
        self._locks_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        self.path = self._locks_dir / f"{digest}.lock"
        self._lock = FileLock(str(self.path))
        self._acquired = False

    def acquire(self) -> None:
        """Acquire without waiting, raising a typed error if another instance holds it."""
        if self._acquired:
            return
        try:
            self._lock.acquire(timeout=0)
        except Timeout as error:
            raise FolderLockError(FolderLockErrorReason.FOLDER_LOCKED, path=self.path) from error
        except OSError as error:
            raise FolderLockError(
                FolderLockErrorReason.LOCK_IO_ERROR, path=self.path, detail=str(error)
            ) from error
        self._acquired = True

    def release(self) -> None:
        """Release the lock if held; repeated calls are safe."""
        if self._acquired:
            self._lock.release()
            self._acquired = False

    def __enter__(self) -> Self:
        """Acquire this lock and return it."""
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release the lock when the context exits."""
        self.release()


class LocalFolderLockFactory:
    """Create concrete folder locks without coupling app use cases to `fsops`."""

    def __init__(self, app_data_dir: Path) -> None:
        self.app_data_dir = app_data_dir

    def create(self, identity: str) -> FolderLock:
        """Return an unacquired lock for the supplied folder identity."""
        return LocalFolderLock(self.app_data_dir, identity)
