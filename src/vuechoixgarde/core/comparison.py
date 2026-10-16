"""Normalize and case-fold names for FR-033 and NFR-041 comparisons."""

import unicodedata


def comparison_key(name: str) -> str:
    """Return NFC(casefold(NFC(name))) as required by NFR-041."""
    normalized = unicodedata.normalize("NFC", name)
    return unicodedata.normalize("NFC", normalized.casefold())
