"""Pure screen-based bounds for cached image decoding."""

from math import ceil, isfinite


def screen_decode_bounds(
    width: int,
    height: int,
    device_pixel_ratio: float,
    *,
    max_dimension: int = 8192,
) -> tuple[int, int]:
    """Return a capped physical-pixel decode bound for a logical display size."""
    if width < 1 or height < 1 or max_dimension < 1:
        raise ValueError("display and maximum dimensions must be positive")
    if not isfinite(device_pixel_ratio) or device_pixel_ratio <= 0:
        raise ValueError("device pixel ratio must be finite and positive")
    scale = min(device_pixel_ratio, max_dimension / max(width, height))
    return min(max_dimension, ceil(width * scale)), min(max_dimension, ceil(height * scale))
