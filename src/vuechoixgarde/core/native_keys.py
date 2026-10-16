"""Map native keyboard codes to W3C positions (FR-081, FR-082).

Values are transcribed from Chromium's ui/events/keycodes/dom/dom_code_data.inc:
https://github.com/chromium/chromium/blob/main/ui/events/keycodes/dom/dom_code_data.inc
Its columns provide Linux evdev/XKB, Windows PC/AT Set 1, and macOS kVK_* values.
The Linux table uses the XKB column (equal to evdev + 8). The macOS ISO-keyboard
Backquote/IntlBackslash swap is documented upstream and is intentionally not adjusted here.
"""

from enum import StrEnum
from types import MappingProxyType
from typing import Final

from vuechoixgarde.core.keys import ALLOWED_SLOT_CODES


class NativeKeyPlatform(StrEnum):
    """Supported platform-specific native keyboard code families."""

    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"


WINDOWS_NATIVE_KEYS: Final = MappingProxyType(
    {
        0x1E: "KeyA",
        0x30: "KeyB",
        0x2E: "KeyC",
        0x20: "KeyD",
        0x12: "KeyE",
        0x21: "KeyF",
        0x22: "KeyG",
        0x23: "KeyH",
        0x17: "KeyI",
        0x24: "KeyJ",
        0x25: "KeyK",
        0x26: "KeyL",
        0x32: "KeyM",
        0x31: "KeyN",
        0x18: "KeyO",
        0x19: "KeyP",
        0x10: "KeyQ",
        0x13: "KeyR",
        0x1F: "KeyS",
        0x14: "KeyT",
        0x16: "KeyU",
        0x2F: "KeyV",
        0x11: "KeyW",
        0x2D: "KeyX",
        0x15: "KeyY",
        0x2C: "KeyZ",
        0x02: "Digit1",
        0x03: "Digit2",
        0x04: "Digit3",
        0x05: "Digit4",
        0x06: "Digit5",
        0x07: "Digit6",
        0x08: "Digit7",
        0x09: "Digit8",
        0x0A: "Digit9",
        0x0B: "Digit0",
        0x29: "Backquote",
        0x0C: "Minus",
        0x0D: "Equal",
        0x1A: "BracketLeft",
        0x1B: "BracketRight",
        0x2B: "Backslash",
        0x56: "IntlBackslash",
        0x27: "Semicolon",
        0x28: "Quote",
        0x33: "Comma",
        0x34: "Period",
        0x35: "Slash",
    }
)

LINUX_NATIVE_KEYS: Final = MappingProxyType(
    {
        0x26: "KeyA",
        0x38: "KeyB",
        0x36: "KeyC",
        0x28: "KeyD",
        0x1A: "KeyE",
        0x29: "KeyF",
        0x2A: "KeyG",
        0x2B: "KeyH",
        0x1F: "KeyI",
        0x2C: "KeyJ",
        0x2D: "KeyK",
        0x2E: "KeyL",
        0x3A: "KeyM",
        0x39: "KeyN",
        0x20: "KeyO",
        0x21: "KeyP",
        0x18: "KeyQ",
        0x1B: "KeyR",
        0x27: "KeyS",
        0x1C: "KeyT",
        0x1E: "KeyU",
        0x37: "KeyV",
        0x19: "KeyW",
        0x35: "KeyX",
        0x1D: "KeyY",
        0x34: "KeyZ",
        0x0A: "Digit1",
        0x0B: "Digit2",
        0x0C: "Digit3",
        0x0D: "Digit4",
        0x0E: "Digit5",
        0x0F: "Digit6",
        0x10: "Digit7",
        0x11: "Digit8",
        0x12: "Digit9",
        0x13: "Digit0",
        0x31: "Backquote",
        0x14: "Minus",
        0x15: "Equal",
        0x22: "BracketLeft",
        0x23: "BracketRight",
        0x33: "Backslash",
        0x5E: "IntlBackslash",
        0x2F: "Semicolon",
        0x30: "Quote",
        0x3B: "Comma",
        0x3C: "Period",
        0x3D: "Slash",
    }
)

MACOS_NATIVE_KEYS: Final = MappingProxyType(
    {
        0x00: "KeyA",
        0x0B: "KeyB",
        0x08: "KeyC",
        0x02: "KeyD",
        0x0E: "KeyE",
        0x03: "KeyF",
        0x05: "KeyG",
        0x04: "KeyH",
        0x22: "KeyI",
        0x26: "KeyJ",
        0x28: "KeyK",
        0x25: "KeyL",
        0x2E: "KeyM",
        0x2D: "KeyN",
        0x1F: "KeyO",
        0x23: "KeyP",
        0x0C: "KeyQ",
        0x0F: "KeyR",
        0x01: "KeyS",
        0x11: "KeyT",
        0x20: "KeyU",
        0x09: "KeyV",
        0x0D: "KeyW",
        0x07: "KeyX",
        0x10: "KeyY",
        0x06: "KeyZ",
        0x12: "Digit1",
        0x13: "Digit2",
        0x14: "Digit3",
        0x15: "Digit4",
        0x17: "Digit5",
        0x16: "Digit6",
        0x1A: "Digit7",
        0x1C: "Digit8",
        0x19: "Digit9",
        0x1D: "Digit0",
        0x32: "Backquote",
        0x1B: "Minus",
        0x18: "Equal",
        0x21: "BracketLeft",
        0x1E: "BracketRight",
        0x2A: "Backslash",
        0x0A: "IntlBackslash",
        0x29: "Semicolon",
        0x27: "Quote",
        0x2B: "Comma",
        0x2F: "Period",
        0x2C: "Slash",
    }
)

_NATIVE_KEY_TABLES: Final = {
    NativeKeyPlatform.WINDOWS: WINDOWS_NATIVE_KEYS,
    NativeKeyPlatform.LINUX: LINUX_NATIVE_KEYS,
    NativeKeyPlatform.MACOS: MACOS_NATIVE_KEYS,
}


def position_for_native_code(platform: NativeKeyPlatform, native_code: int) -> str | None:
    """Return the allowed W3C position for a platform code, or ``None`` (FR-081/FR-082)."""
    position = _NATIVE_KEY_TABLES[platform].get(native_code)
    return position if position in ALLOWED_SLOT_CODES else None
