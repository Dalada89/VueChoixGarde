import pytest

from vuechoixgarde.core.sorting import sort_names


def test_natural_sort_orders_numbers_naturally() -> None:
    assert sort_names(["IMG_10.jpg", "IMG_2.jpg"]) == ["IMG_2.jpg", "IMG_10.jpg"]


@pytest.mark.parametrize("descending", [False, True])
def test_equal_casefolded_names_use_exact_name_as_tiebreaker(descending: bool) -> None:
    names = ["image.jpg", "IMAGE.jpg", "Image.jpg"]
    expected = (
        ["image.jpg", "Image.jpg", "IMAGE.jpg"]
        if descending
        else [
            "IMAGE.jpg",
            "Image.jpg",
            "image.jpg",
        ]
    )
    assert sort_names(names, descending=descending) == expected
    assert sort_names(list(reversed(names)), descending=descending) == expected


def test_sort_direction_reverses_natural_order() -> None:
    names = ["IMG_2.jpg", "IMG_10.jpg", "IMG_1.jpg"]
    assert sort_names(names, descending=True) == ["IMG_10.jpg", "IMG_2.jpg", "IMG_1.jpg"]
