"""Bounded decoded-image cache with generation checks and deterministic eviction."""

from collections import OrderedDict
from pathlib import Path

from vuechoixgarde.ports.imaging import DecodedImage


class DecodedImageCache:
    """Keep only requested image buffers within fixed entry and byte budgets."""

    def __init__(self, *, max_entries: int = 5, max_bytes: int = 256 * 1024 * 1024) -> None:
        if max_entries < 1 or max_bytes < 1:
            raise ValueError("cache limits must be positive")
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.generation = 0
        self._required: frozenset[Path] = frozenset()
        self._items: OrderedDict[Path, DecodedImage] = OrderedDict()
        self._byte_count = 0

    @property
    def byte_count(self) -> int:
        """Current decoded pixel-buffer storage in bytes."""
        return self._byte_count

    def begin_generation(self, paths: tuple[Path, ...]) -> int:
        """Advance the request generation and discard buffers outside the new neighborhood."""
        self.generation += 1
        self._required = frozenset(paths)
        for path in tuple(self._items):
            if path not in self._required:
                self._remove(path)
        return self.generation

    def get(self, path: Path) -> DecodedImage | None:
        """Return and mark a cached image as recently used."""
        image = self._items.get(path)
        if image is not None:
            self._items.move_to_end(path)
        return image

    def put(self, path: Path, generation: int, image: DecodedImage) -> bool:
        """Store only a current, wanted result that fits the byte limit."""
        if generation != self.generation or path not in self._required:
            return False
        size = len(image.data)
        if size > self.max_bytes:
            return False
        self._remove(path)
        self._items[path] = image
        self._byte_count += size
        while len(self._items) > self.max_entries or self._byte_count > self.max_bytes:
            self._remove(next(iter(self._items)))
        return path in self._items

    def clear(self) -> None:
        """Release all cached image buffers and invalidate outstanding decode results."""
        self.generation += 1
        self._required = frozenset()
        self._items.clear()
        self._byte_count = 0

    def _remove(self, path: Path) -> None:
        image = self._items.pop(path, None)
        if image is not None:
            self._byte_count -= len(image.data)
