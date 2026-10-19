from pathlib import Path

import pytest
from PIL import Image

from vuechoixgarde.imaging.cache import DecodedImageCache
from vuechoixgarde.imaging.decoder import PillowImageDecoder
from vuechoixgarde.ports.errors import ImageDecodeError, ImageDecodeErrorReason
from vuechoixgarde.ports.imaging import DecodedImage


def test_decoder_applies_exif_orientation_and_never_upscales(tmp_path: Path) -> None:
    path = tmp_path / "oriented.jpg"
    source = Image.new("RGB", (8, 4), "red")
    exif = Image.Exif()
    exif[274] = 6
    source.save(path, exif=exif)

    decoded = PillowImageDecoder().decode(path, 100, 100)

    assert (decoded.width, decoded.height) == (4, 8)
    assert PillowImageDecoder().decode(path, 2, 2).width <= 2


def test_decoder_preserves_png_alpha_and_decodes_only_first_frame(tmp_path: Path) -> None:
    alpha_path = tmp_path / "alpha.png"
    Image.new("RGBA", (3, 2), (20, 30, 40, 100)).save(alpha_path)
    animated_path = tmp_path / "animated.gif"
    Image.new("RGB", (2, 2), "red").save(
        animated_path,
        save_all=True,
        append_images=[Image.new("RGB", (2, 2), "blue")],
        duration=100,
        loop=0,
    )

    alpha = PillowImageDecoder().decode(alpha_path, 20, 20)
    first_frame = PillowImageDecoder().decode(animated_path, 20, 20)

    assert alpha.has_alpha
    assert len(alpha.data) == 3 * 2 * 4
    assert not first_frame.has_alpha
    assert first_frame.data[:3] == bytes((255, 0, 0))

    webp_path = tmp_path / "animated.webp"
    Image.new("RGB", (2, 2), "red").save(
        webp_path,
        format="WEBP",
        save_all=True,
        append_images=[Image.new("RGB", (2, 2), "blue")],
        duration=100,
        loop=0,
    )
    first_webp_frame = PillowImageDecoder().decode(webp_path, 20, 20)
    red, green, blue = first_webp_frame.data[:3]
    assert red > 240 and green < 20 and blue < 20


def test_decoder_returns_typed_missing_unsupported_corrupt_and_bomb_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    decoder = PillowImageDecoder()
    missing = tmp_path / "missing.jpg"
    unsupported = tmp_path / "unsupported.raw"
    unsupported.write_bytes(b"data")
    corrupt = tmp_path / "corrupt.jpg"
    corrupt.write_bytes(b"not an image")
    empty = tmp_path / "empty.jpg"
    empty.touch()

    for path, reason in (
        (missing, ImageDecodeErrorReason.MISSING),
        (unsupported, ImageDecodeErrorReason.UNSUPPORTED),
        (corrupt, ImageDecodeErrorReason.CORRUPT),
        (empty, ImageDecodeErrorReason.CORRUPT),
    ):
        with pytest.raises(ImageDecodeError) as error:
            decoder.decode(path, 20, 20)
        assert error.value.reason is reason

    large = tmp_path / "large.png"
    Image.new("RGB", (20, 20)).save(large)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(ImageDecodeError) as error:
        decoder.decode(large, 20, 20)
    assert error.value.reason is ImageDecodeErrorReason.TOO_LARGE


def test_heic_without_plugin_has_a_specific_unavailable_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vuechoixgarde.imaging import decoder

    heic = tmp_path / "unavailable.heic"
    heic.touch()
    monkeypatch.setattr(decoder, "_HEIF_AVAILABLE", False)

    with pytest.raises(ImageDecodeError) as error:
        PillowImageDecoder().decode(heic, 20, 20)

    assert error.value.reason is ImageDecodeErrorReason.HEIC_UNAVAILABLE


def test_cache_enforces_count_bytes_and_generation() -> None:
    cache = DecodedImageCache(max_entries=2, max_bytes=30)
    first, second, third = (Path(name) for name in ("one", "two", "three"))
    generation = cache.begin_generation((first, second, third))
    image = DecodedImage(2, 2, False, b"123456789012")

    assert cache.put(first, generation, image)
    assert cache.put(second, generation, image)
    assert cache.byte_count == 24
    assert cache.get(first) is image
    assert cache.put(third, generation, image)
    assert cache.get(second) is None
    assert cache.byte_count <= 30
    assert not cache.put(second, generation - 1, image)
    assert not cache.put(Path("old"), generation, image)

    next_generation = cache.begin_generation((second,))
    assert cache.get(first) is None
    assert cache.get(third) is None
    assert not cache.put(second, generation, image)
    assert cache.put(second, next_generation, image)


def test_cache_rejects_an_image_larger_than_total_budget() -> None:
    cache = DecodedImageCache(max_entries=2, max_bytes=4)
    path = Path("big")
    generation = cache.begin_generation((path,))

    assert not cache.put(path, generation, DecodedImage(2, 2, False, b"12345"))
    assert cache.byte_count == 0
