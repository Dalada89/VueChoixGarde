"""Small Qt worker pools that deliver immutable results to the UI thread."""

from collections.abc import Callable
from itertools import count

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot

Callback = Callable[[object, Exception | None], None]


class _Dispatcher(QObject):
    delivered = Signal(int, object, object, object)

    def __init__(self, release_task: Callable[[int], None]) -> None:
        super().__init__()
        self.release_task = release_task
        self.delivered.connect(self._deliver, Qt.ConnectionType.QueuedConnection)

    @Slot(int, object, object, object)
    def _deliver(self, task_id: int, callback: Callback, result: object, error: object) -> None:
        try:
            callback(result, error if isinstance(error, Exception) else None)
        finally:
            self.release_task(task_id)


class _Task(QRunnable):
    def __init__(
        self,
        task_id: int,
        function: Callable[[], object],
        callback: Callback,
        dispatcher: _Dispatcher,
    ) -> None:
        super().__init__()
        self.task_id = task_id
        self.function = function
        self.callback = callback
        self.dispatcher = dispatcher

    def run(self) -> None:
        try:
            result = self.function()
        except Exception as error:
            self.dispatcher.delivered.emit(self.task_id, self.callback, None, error)
        else:
            self.dispatcher.delivered.emit(self.task_id, self.callback, result, None)


class WorkerPool:
    """A bounded Qt thread pool with callback delivery through queued Qt signals."""

    def __init__(self, max_threads: int) -> None:
        if max_threads < 1:
            raise ValueError("max_threads must be positive")
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(max_threads)
        self._tasks: dict[int, _Task] = {}
        self._ids = count()
        self._dispatcher = _Dispatcher(self._release_task)

    def _release_task(self, task_id: int) -> None:
        self._tasks.pop(task_id, None)

    def submit(self, function: Callable[[], object], callback: Callback) -> None:
        """Schedule work without blocking the caller or invoking callbacks on workers."""
        task_id = next(self._ids)
        task = _Task(task_id, function, callback, self._dispatcher)
        self._tasks[task_id] = task
        self._pool.start(task)

    def wait_for_done(self) -> None:
        """Wait for running work; used only during orderly application shutdown."""
        self._pool.waitForDone()

    @property
    def active_count(self) -> int:
        """Number of tasks currently executing or queued."""
        return self._pool.activeThreadCount()

    def shutdown(self) -> None:
        """Drain pending work before releasing the pool."""
        self._pool.waitForDone()


class WorkerPools:
    """Own the serialized file-operation worker and the two-thread decode pool."""

    def __init__(self) -> None:
        self.file_operations = WorkerPool(1)
        self.image_decoding = WorkerPool(2)

    def shutdown(self) -> None:
        self.file_operations.shutdown()
        self.image_decoding.shutdown()
