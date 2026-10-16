"""Define physical slot positions, labels and label learning for FR-081 and FR-082."""

from collections.abc import Mapping
from string import ascii_uppercase, digits
from types import MappingProxyType
from unicodedata import category, combining

_ALLOWED_PUNCTUATION_CODES = frozenset(
    {
        "Backquote",
        "Minus",
        "Equal",
        "BracketLeft",
        "BracketRight",
        "Backslash",
        "IntlBackslash",
        "Semicolon",
        "Quote",
        "Comma",
        "Period",
        "Slash",
    }
)
ALLOWED_SLOT_CODES = (
    frozenset(
        {*(f"Key{letter}" for letter in ascii_uppercase), *(f"Digit{digit}" for digit in digits)}
    )
    | _ALLOWED_PUNCTUATION_CODES
)

_QWERTY_LABELS = {
    "Backquote": "`",
    "Minus": "-",
    "Equal": "=",
    "BracketLeft": "[",
    "BracketRight": "]",
    "Backslash": "\\",
    "IntlBackslash": "\\",
    "Semicolon": ";",
    "Quote": "'",
    "Comma": ",",
    "Period": ".",
    "Slash": "/",
}


def is_allowed_slot_key(code: str) -> bool:
    """Return whether a W3C code is a main-block slot position (FR-082)."""
    return code in ALLOWED_SLOT_CODES


def is_slot_key_triggered(code: str, *, modifier_active: bool) -> bool:
    """Reject reserved positions and all modified key presses (FR-082)."""
    return is_allowed_slot_key(code) and not modifier_active


def initial_key_label(code: str) -> str | None:
    """Return the US-QWERTY startup label for a position, as required by FR-081."""
    if code.startswith("Key") and code[3:] in ascii_uppercase:
        return code[3:]
    if code.startswith("Digit") and code[5:] in digits:
        return code[5:]
    return _QWERTY_LABELS.get(code)


def printable_key_label(text: str) -> str | None:
    """Return a single printable key label, upper-cased when it remains one character (FR-081)."""
    if len(text) != 1 or not text.isprintable():
        return None
    if category(text).startswith("C") or combining(text):
        return None
    upper = text.upper()
    return upper if len(upper) == 1 else text


def update_learned_key_labels(
    labels: Mapping[str, str],
    position: str,
    text: str,
    *,
    modifier_active: bool,
) -> Mapping[str, str]:
    """Return immutable learned labels updated only for an eligible position (FR-081/FR-082)."""
    updated = dict(labels)
    label = printable_key_label(text)
    if is_allowed_slot_key(position) and not modifier_active and label is not None:
        updated[position] = label
    return MappingProxyType(updated)


def displayed_key_label(position: str, labels: Mapping[str, str]) -> str | None:
    """Return a learned label, falling back to the US-QWERTY position label (FR-081)."""
    return labels.get(position, initial_key_label(position))
