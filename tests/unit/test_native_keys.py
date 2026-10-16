from collections.abc import Mapping
from typing import cast

import pytest

from vuechoixgarde.core.keys import ALLOWED_SLOT_CODES
from vuechoixgarde.core.native_keys import (
    LINUX_NATIVE_KEYS,
    MACOS_NATIVE_KEYS,
    WINDOWS_NATIVE_KEYS,
    NativeKeyPlatform,
    position_for_native_code,
)

TABLES: dict[NativeKeyPlatform, Mapping[int, str]] = {
    NativeKeyPlatform.WINDOWS: WINDOWS_NATIVE_KEYS,
    NativeKeyPlatform.LINUX: LINUX_NATIVE_KEYS,
    NativeKeyPlatform.MACOS: MACOS_NATIVE_KEYS,
}


@pytest.mark.parametrize(("platform", "table"), TABLES.items())
def test_native_key_table_covers_exactly_all_allowed_positions(
    platform: NativeKeyPlatform, table: Mapping[int, str]
) -> None:
    assert set(table.values()) == ALLOWED_SLOT_CODES


@pytest.mark.parametrize("table", TABLES.values())
def test_native_key_codes_are_unique(table: Mapping[int, str]) -> None:
    assert len(table) == len(set(table.values()))


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        (
            "KeyW",
            {
                NativeKeyPlatform.WINDOWS: 0x11,
                NativeKeyPlatform.LINUX: 25,
                NativeKeyPlatform.MACOS: 0x0D,
            },
        ),
        (
            "KeyA",
            {
                NativeKeyPlatform.WINDOWS: 0x1E,
                NativeKeyPlatform.LINUX: 38,
                NativeKeyPlatform.MACOS: 0x00,
            },
        ),
        (
            "KeyS",
            {
                NativeKeyPlatform.WINDOWS: 0x1F,
                NativeKeyPlatform.LINUX: 39,
                NativeKeyPlatform.MACOS: 0x01,
            },
        ),
        (
            "KeyD",
            {
                NativeKeyPlatform.WINDOWS: 0x20,
                NativeKeyPlatform.LINUX: 40,
                NativeKeyPlatform.MACOS: 0x02,
            },
        ),
        (
            "Digit1",
            {
                NativeKeyPlatform.WINDOWS: 0x02,
                NativeKeyPlatform.LINUX: 10,
                NativeKeyPlatform.MACOS: 0x12,
            },
        ),
        (
            "Minus",
            {
                NativeKeyPlatform.WINDOWS: 0x0C,
                NativeKeyPlatform.LINUX: 20,
                NativeKeyPlatform.MACOS: 0x1B,
            },
        ),
        (
            "IntlBackslash",
            {
                NativeKeyPlatform.WINDOWS: 0x56,
                NativeKeyPlatform.LINUX: 94,
                NativeKeyPlatform.MACOS: 0x0A,
            },
        ),
    ],
)
def test_reference_sample_codes(position: str, expected: dict[NativeKeyPlatform, int]) -> None:
    for platform, native_code in expected.items():
        assert position_for_native_code(platform, native_code) == position


@pytest.mark.parametrize("platform", list(NativeKeyPlatform))
def test_unknown_native_code_returns_none(platform: NativeKeyPlatform) -> None:
    assert position_for_native_code(platform, -1) is None


def test_native_key_tables_are_immutable() -> None:
    with pytest.raises(TypeError):
        cast(dict[int, str], WINDOWS_NATIVE_KEYS)[0x11] = "KeyA"
