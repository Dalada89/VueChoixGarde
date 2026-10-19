"""Pillow-backed, read-only image decoding with orientation and bomb handling."""

import warnings
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from vuechoixgarde.ports.errors import ImageDecodeError, ImageDecodeErrorReason
from vuechoixgarde.ports.imaging import DecodedImage

_SUPPORTED_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".heic", ".heif"}
)
_HEIC_EXTENSIONS = frozenset({".heic", ".heif"})
_HEIF_AVAILABLE = False
try:
    from pi_heif import register_heif_opener

    register_heif_opener()
    _HEIF_AVAILABLE = True
except Exception:
    pass


class PillowImageDecoder:
    """Decode the first frame/page from an image without ever writing to its source."""

    def decode(self, path: Path, max_width: int, max_height: int) -> DecodedImage:
        """Orient, downscale and return packed RGB(A) bytes for the UI thread."""
        if max_width < 1 or max_height < 1:
            raise ValueError("maximum dimensions must be positive")
        if not path.is_file():
            raise ImageDecodeError(ImageDecodeErrorReason.MISSING, path)
        extension = path.suffix.casefold()
        if extension not in _SUPPORTED_EXTENSIONS:
            raise ImageDecodeError(ImageDecodeErrorReason.UNSUPPORTED, path)
        if extension in _HEIC_EXTENSIONS and not _HEIF_AVAILABLE:
            raise ImageDecodeError(ImageDecodeErrorReason.HEIC_UNAVAILABLE, path)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as source:
                    source.seek(0)
                    if source.format == "JPEG":
                        source.draft("RGB", (max_width, max_height))
                    oriented = ImageOps.exif_transpose(source)
                    oriented.load()
                    has_alpha = "A" in oriented.getbands() or "transparency" in oriented.info
                    rendered = oriented.convert("RGBA" if has_alpha else "RGB")
                    rendered.thumbnail(
                        (max_width, max_height), Image.Resampling.LANCZOS, reducing_gap=3.0
                    )
                    return DecodedImage(
                        rendered.width,
                        rendered.height,
                        has_alpha,
                        rendered.tobytes(),
                    )
        except Image.DecompressionBombError as error:
            raise ImageDecodeError(ImageDecodeErrorReason.TOO_LARGE, path) from error
        except Image.DecompressionBombWarning as error:
            raise ImageDecodeError(ImageDecodeErrorReason.TOO_LARGE, path) from error
        except FileNotFoundError as error:
            raise ImageDecodeError(ImageDecodeErrorReason.MISSING, path) from error
        except UnidentifiedImageError as error:
            raise ImageDecodeError(ImageDecodeErrorReason.CORRUPT, path) from error
        except OSError as error:
            if not path.exists():
                reason = ImageDecodeErrorReason.MISSING
            else:
                reason = ImageDecodeErrorReason.CORRUPT
            raise ImageDecodeError(reason, path) from error
        except Exception as error:
            if extension in _HEIC_EXTENSIONS and not _HEIF_AVAILABLE:
                reason = ImageDecodeErrorReason.HEIC_UNAVAILABLE
            else:
                reason = ImageDecodeErrorReason.CORRUPT
            raise ImageDecodeError(reason, path) from error
