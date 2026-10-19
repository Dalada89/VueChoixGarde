"""Pure color-contrast helpers for UI accessibility checks."""


def contrast_ratio(foreground: str, background: str) -> float:
    """Return the WCAG contrast ratio of two ``#RRGGBB`` colors."""
    first = _luminance(foreground)
    second = _luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def _luminance(color: str) -> float:
    value = color.removeprefix("#")
    if len(value) != 6:
        raise ValueError("colors must use #RRGGBB notation")
    try:
        channels = tuple(int(value[index : index + 2], 16) / 255 for index in (0, 2, 4))
    except ValueError as error:
        raise ValueError("colors must use #RRGGBB notation") from error
    linear = tuple(
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    )
    return sum(
        weight * channel for weight, channel in zip((0.2126, 0.7152, 0.0722), linear, strict=True)
    )
