import pytest

from vuechoixgarde.ui.zoom import ZoomState


def test_zoom_stays_between_one_and_eight() -> None:
    zoom = ZoomState()

    for _ in range(20):
        zoom.zoom_at((100.0, 80.0), 1.25)
    assert zoom.scale == 8.0

    for _ in range(20):
        zoom.zoom_at((100.0, 80.0), 0.8)
    assert zoom.scale == pytest.approx(1.0)

    zoom.zoom_at((100.0, 80.0), 0.5)
    assert zoom.scale == 1.0


def test_zoom_keeps_the_image_point_under_the_anchor_fixed() -> None:
    zoom = ZoomState()
    zoom.offset = (12.0, -7.0)
    anchor = (90.0, 55.0)
    image_point_before = (
        (anchor[0] - zoom.offset[0]) / zoom.scale,
        (anchor[1] - zoom.offset[1]) / zoom.scale,
    )

    zoom.zoom_at(anchor, 1.5)

    image_point_after = (
        (anchor[0] - zoom.offset[0]) / zoom.scale,
        (anchor[1] - zoom.offset[1]) / zoom.scale,
    )
    assert image_point_after == pytest.approx(image_point_before)


def test_reset_restores_the_default_scale_and_offset() -> None:
    zoom = ZoomState()
    zoom.zoom_at((100.0, 80.0), 2.0)

    zoom.reset()

    assert zoom.scale == 1.0
    assert zoom.offset == (0.0, 0.0)


@pytest.mark.parametrize(
    ("offset", "expected"),
    [((1000.0, 1000.0), (0.0, 0.0)), ((-1000.0, -1000.0), (-200.0, -150.0))],
)
def test_offset_is_clamped_so_the_viewport_stays_covered(
    offset: tuple[float, float], expected: tuple[float, float]
) -> None:
    zoom = ZoomState()
    zoom.scale = 2.0
    zoom.offset = offset

    zoom.clamp_offset((200.0, 150.0), (200.0, 150.0))

    assert zoom.offset == pytest.approx(expected)
