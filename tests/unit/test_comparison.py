import pytest

from vuechoixgarde.core.comparison import comparison_key


@pytest.mark.parametrize(
    ("left", "right"),
    [("Best", "best"), ("é", "e\u0301"), ("Straße", "STRASSE")],
)
def test_comparison_key_normalizes_and_casefolds_names(left: str, right: str) -> None:
    assert comparison_key(left) == comparison_key(right)


def test_comparison_key_keeps_distinct_names_distinct() -> None:
    assert comparison_key("Best") != comparison_key("Better")
