"""Match companion filenames according to FR-043 without filesystem access."""

from collections.abc import Sequence

from vuechoixgarde.core.comparison import comparison_key
from vuechoixgarde.core.sorting import natural_sort_key

RAW_SIDECAR_EXTENSIONS = (
    ".nef",
    ".nrw",
    ".cr2",
    ".cr3",
    ".crw",
    ".arw",
    ".srf",
    ".sr2",
    ".dng",
    ".orf",
    ".rw2",
    ".raf",
    ".pef",
    ".srw",
    ".x3f",
    ".rwl",
    ".3fr",
    ".raw",
)


def sidecars_for_image(image_name: str, filenames: Sequence[str]) -> tuple[str, ...]:
    """Return matching XMP, AAE and RAW names, preserving their exact spellings."""
    stem, separator, extension = image_name.rpartition(".")
    if not separator or not stem or not extension:
        return ()

    wanted = {
        comparison_key(f"{stem}.xmp"),
        comparison_key(f"{image_name}.xmp"),
        comparison_key(f"{stem}.aae"),
        *(comparison_key(f"{stem}{extension}") for extension in RAW_SIDECAR_EXTENSIONS),
    }
    matches = {name for name in filenames if comparison_key(name) in wanted}
    return tuple(sorted(matches, key=natural_sort_key))
