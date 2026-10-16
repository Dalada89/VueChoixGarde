import pytest

from vuechoixgarde.core.navigation import (
    ImageNavigation,
    NavigationDirection,
    change_sort_direction,
    create_navigation,
    navigate,
    refresh_navigation,
)


@pytest.mark.parametrize(
    ("direction", "expected"),
    [
        (NavigationDirection.PREVIOUS, "IMG_1.jpg"),
        (NavigationDirection.NEXT, "IMG_2.jpg"),
    ],
)
def test_navigation_stays_within_first_image(direction: NavigationDirection, expected: str) -> None:
    state = create_navigation(["IMG_1.jpg", "IMG_2.jpg"], current="IMG_1.jpg")
    assert navigate(state, direction).current == expected


def test_navigation_stays_within_last_image() -> None:
    state = create_navigation(["IMG_1.jpg", "IMG_2.jpg"], current="IMG_2.jpg")
    assert navigate(state, NavigationDirection.NEXT).current == "IMG_2.jpg"


def test_direction_change_keeps_the_current_image() -> None:
    state = create_navigation(["IMG_1.jpg", "IMG_2.jpg", "IMG_10.jpg"], current="IMG_2.jpg")
    changed = change_sort_direction(state, descending=True)
    assert changed.current == "IMG_2.jpg"
    assert changed.images == ("IMG_10.jpg", "IMG_2.jpg", "IMG_1.jpg")


def test_refresh_keeps_current_image_if_it_still_exists() -> None:
    state = create_navigation(["IMG_1.jpg", "IMG_2.jpg"], current="IMG_2.jpg")
    refreshed = refresh_navigation(state, ["IMG_1.jpg", "IMG_2.jpg", "IMG_3.jpg"])
    assert refreshed.current == "IMG_2.jpg"


@pytest.mark.parametrize(
    ("descending", "current", "filenames", "expected"),
    [
        (False, "IMG_2.jpg", ("IMG_1.jpg", "IMG_3.jpg", "IMG_4.jpg"), "IMG_3.jpg"),
        (True, "IMG_4.jpg", ("IMG_1.jpg", "IMG_2.jpg", "IMG_3.jpg"), "IMG_3.jpg"),
    ],
)
def test_refresh_selects_the_nearest_following_image_when_current_was_removed(
    descending: bool, current: str, filenames: tuple[str, ...], expected: str
) -> None:
    state = ImageNavigation((), current, descending)
    refreshed = refresh_navigation(state, filenames)
    assert refreshed.current == expected


@pytest.mark.parametrize(
    ("descending", "current", "filenames", "expected"),
    [
        (False, "IMG_9.jpg", ("IMG_1.jpg", "IMG_2.jpg"), "IMG_2.jpg"),
        (True, "IMG_1.jpg", ("IMG_2.jpg", "IMG_9.jpg"), "IMG_2.jpg"),
    ],
)
def test_refresh_falls_back_to_last_image_when_no_following_image_exists(
    descending: bool, current: str, filenames: tuple[str, ...], expected: str
) -> None:
    state = ImageNavigation((), current, descending)
    refreshed = refresh_navigation(state, filenames)
    assert refreshed.current == expected


def test_refresh_sets_current_to_none_for_an_empty_list() -> None:
    state = create_navigation(["IMG_1.jpg"], current="IMG_1.jpg")
    refreshed = refresh_navigation(state, [])
    assert refreshed.current is None
    assert refreshed.images == ()


@pytest.mark.parametrize("direction", list(NavigationDirection))
def test_navigation_on_an_empty_list_is_a_no_op(direction: NavigationDirection) -> None:
    state = create_navigation([])
    assert navigate(state, direction) == state
