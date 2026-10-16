"""Define physical slot positions and initial labels for FR-081 and FR-082."""

from string import ascii_uppercase, digits

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
