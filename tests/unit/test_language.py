import pytest

from vuechoixgarde.core.language import default_language


@pytest.mark.parametrize(
    ("locale_name", "expected"),
    [("de_DE.UTF-8", "de"), ("fr-FR", "fr"), ("en_US", "en"), ("EN", "en")],
)
def test_supported_locale_language_is_selected(locale_name: str, expected: str) -> None:
    assert default_language(locale_name) == expected


@pytest.mark.parametrize("locale_name", [None, "", "es_ES", "C.UTF-8", "POSIX"])
def test_missing_or_unsupported_locale_falls_back_to_english(locale_name: str | None) -> None:
    assert default_language(locale_name) == "en"
