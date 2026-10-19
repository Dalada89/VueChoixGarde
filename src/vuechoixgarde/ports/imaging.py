"""Qt-free image decoding contract and immutable RGB(A) transfer value."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class DecodedImage:
    """A tightly packed RGB or RGBA pixel buffer with no GUI toolkit dependency."""

    width: int
    height: int
    has_alpha: bool
    data: bytes


class ImageDecoder(Protocol):
    """Decode one still image into a bounded RGB(A) buffer."""

    def decode(self, path: Path, max_width: int, max_height: int) -> DecodedImage:
        """Return the first frame, EXIF-oriented and never enlarged beyond its source."""
        ...
