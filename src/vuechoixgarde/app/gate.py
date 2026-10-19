"""A non-blocking gate for serialized file operations (FR-051)."""

import threading


class OperationGate:
    """Allow at most one operation without queueing or waiting."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def try_acquire(self, *, auto_repeat: bool = False) -> bool:
        """Acquire immediately, rejecting held-key repeats and concurrent operations."""
        return not auto_repeat and self._lock.acquire(blocking=False)

    def release(self) -> None:
        """Release a previously acquired gate."""
        self._lock.release()

    @property
    def busy(self) -> bool:
        """Return whether the gate is currently held."""
        acquired = self._lock.acquire(blocking=False)
        if acquired:
            self._lock.release()
            return False
        return True
