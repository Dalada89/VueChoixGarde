import pytest

from vuechoixgarde.core.sidecars import sidecars_for_image


@pytest.mark.parametrize("image_name", ["IMG_1.jpg", "IMG_1.png"])
def test_shared_stem_sidecars_belong_to_each_image(image_name: str) -> None:
    names = [
        "IMG_1.xmp",
        "IMG_1.JPG.XMP",
        "IMG_1.PNG.XMP",
        "IMG_1.aae",
        "IMG_1.CR2",
        "IMG_1.MOV",
    ]
    expected_full_sidecar = "IMG_1.JPG.XMP" if image_name.endswith("jpg") else "IMG_1.PNG.XMP"
    assert set(sidecars_for_image(image_name, names)) == {
        "IMG_1.xmp",
        expected_full_sidecar,
        "IMG_1.aae",
    }


def test_sidecar_extension_matching_is_case_insensitive() -> None:
    assert sidecars_for_image("IMG_1.jpg", ["IMG_1.XMP", "IMG_1.JpG.XmP"]) == (
        "IMG_1.JpG.XmP",
        "IMG_1.XMP",
    )


def test_unrelated_files_are_not_sidecars() -> None:
    assert sidecars_for_image("IMG_1.jpg", ["IMG_1.CR2", "IMG_1.MOV", "IMG_1.txt"]) == ()
