"""Filter supported filename extensions for FR-004 and NFR-031."""

SUPPORTED_IMAGE_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".heic", ".heif"}
)


def is_supported_image(filename: str) -> bool:
    """Return whether the filename ends in a supported extension, without reading content."""
    _, separator, extension = filename.rpartition(".")
    return bool(separator) and f".{extension.casefold()}" in SUPPORTED_IMAGE_EXTENSIONS
