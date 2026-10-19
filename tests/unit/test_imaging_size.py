import pytest

from vuechoixgarde.imaging.size import screen_decode_bounds


def test_decode_bounds_include_device_pixel_ratio_without_upscaling_logic() -> None:
    assert screen_decode_bounds(1920, 1080, 2.0) == (3840, 2160)
    assert screen_decode_bounds(1920, 1080, 1.25) == (2400, 1350)


def test_decode_bounds_cap_largest_dimension_and_preserve_aspect_ratio() -> None:
    assert screen_decode_bounds(7680, 4320, 2.0, max_dimension=8192) == (8192, 4608)


@pytest.mark.parametrize(
    ("width", "height", "ratio", "maximum"),
    [(0, 1, 1.0, 8192), (1, 0, 1.0, 8192), (1, 1, 0.0, 8192), (1, 1, 1.0, 0)],
)
def test_decode_bounds_reject_invalid_inputs(
    width: int, height: int, ratio: float, maximum: int
) -> None:
    with pytest.raises(ValueError):
        screen_decode_bounds(width, height, ratio, max_dimension=maximum)
