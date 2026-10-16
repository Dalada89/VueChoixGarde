"""Resolve the supported startup language from an operating-system locale (FR-085)."""

from typing import Literal, cast

SupportedLanguage = Literal["de", "en", "fr"]
_SUPPORTED_LANGUAGES = frozenset({"de", "en", "fr"})


def default_language(locale_name: str | None) -> SupportedLanguage:
    """Return a supported locale language code, falling back to English (FR-085)."""
    if not locale_name:
        return "en"
    language = locale_name.split(".", maxsplit=1)[0].replace("-", "_").split("_", maxsplit=1)[0]
    normalized = language.casefold()
    return cast(SupportedLanguage, normalized) if normalized in _SUPPORTED_LANGUAGES else "en"
