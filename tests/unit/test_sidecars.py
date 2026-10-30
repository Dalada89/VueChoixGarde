import pytest

from vuechoixgarde.core.sidecars import sidecars_for_image


@pytest.mark.parametrize("image_name", ["IMG_1.jpg", "IMG_1.png"])
def test_shared_stem_sidecars_belong_to_each_image(image_name: str) -> None:
    names = [
        "IMG_1.xmp",
        "IMG_1.JPG.XMP",
        "IMG_1.PNG.XMP",
        "IMG_1.aae",
        "IMG_1.NEF",
        "IMG_1.MOV",
    ]
    expected_full_sidecar = "IMG_1.JPG.XMP" if image_name.endswith("jpg") else "IMG_1.PNG.XMP"
    assert set(sidecars_for_image(image_name, names)) == {
        "IMG_1.xmp",
        expected_full_sidecar,
        "IMG_1.aae",
        "IMG_1.NEF",
    }


@pytest.mark.parametrize("raw_name", ["IMG_1.nef", "IMG_1.NEF"])
def test_raw_sidecar_extension_matching_is_case_insensitive(raw_name: str) -> None:
    assert sidecars_for_image("IMG_1.jpg", [raw_name]) == (raw_name,)


def test_raw_sidecars_with_a_different_stem_are_not_matched() -> None:
    assert sidecars_for_image("IMG_1.jpg", ["IMG_2.NEF"]) == ()


def test_sidecar_extension_matching_is_case_insensitive() -> None:
    assert sidecars_for_image("IMG_1.jpg", ["IMG_1.XMP", "IMG_1.JpG.XmP"]) == (
        "IMG_1.JpG.XmP",
        "IMG_1.XMP",
    )


def test_unrelated_files_are_not_sidecars() -> None:
    filenames = ["IMG_1.xyz", "IMG_1.MOV", "IMG_1.txt", "IMG_2.NEF"]
    assert sidecars_for_image("IMG_1.jpg", filenames) == ()
