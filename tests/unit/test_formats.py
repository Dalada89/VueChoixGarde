import pytest

from vuechoixgarde.core.formats import SUPPORTED_IMAGE_EXTENSIONS, is_supported_image


@pytest.mark.parametrize("extension", sorted(SUPPORTED_IMAGE_EXTENSIONS))
def test_supported_extensions_are_case_insensitive(extension: str) -> None:
    assert is_supported_image(f"photo{extension.upper()}")


@pytest.mark.parametrize("filename", ["photo.cr2", "photo.mov", "photo", "photo.jpg.txt"])
def test_unsupported_extensions_are_rejected(filename: str) -> None:
    assert not is_supported_image(filename)


def test_heic_and_heif_are_in_the_fixed_extension_list() -> None:
    assert ".heic" in SUPPORTED_IMAGE_EXTENSIONS
    assert ".heif" in SUPPORTED_IMAGE_EXTENSIONS
