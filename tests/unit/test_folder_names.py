import pytest

from vuechoixgarde.core.folder_names import FolderNameError, validate_folder_name


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("", FolderNameError.EMPTY),
        ("...", FolderNameError.ONLY_SPACES_AND_DOTS),
        (". ", FolderNameError.ONLY_SPACES_AND_DOTS),
        (".", FolderNameError.DOT_SEGMENT),
        ("..", FolderNameError.DOT_SEGMENT),
        ("/absolute", FolderNameError.ABSOLUTE_PATH),
        ("C:\\absolute", FolderNameError.ABSOLUTE_PATH),
        ("a/b", FolderNameError.PATH_SEPARATOR),
        ("a\\b", FolderNameError.PATH_SEPARATOR),
        ("bad:name", FolderNameError.INVALID_CHARACTER),
        ("bad\x01name", FolderNameError.INVALID_CHARACTER),
        ("name.", FolderNameError.TRAILING_SPACE_OR_DOT),
        ("name ", FolderNameError.TRAILING_SPACE_OR_DOT),
        ("CON", FolderNameError.RESERVED_DEVICE_NAME),
        ("con.txt", FolderNameError.RESERVED_DEVICE_NAME),
        ("LPT3.log", FolderNameError.RESERVED_DEVICE_NAME),
        ("COM¹.dat", FolderNameError.RESERVED_DEVICE_NAME),
    ],
)
def test_invalid_folder_names_report_distinct_reasons(name: str, reason: FolderNameError) -> None:
    assert validate_folder_name(name) is reason


@pytest.mark.parametrize("name", ["Best", "holiday photos", "camera_01", "folder-1"])
def test_valid_folder_names_are_accepted(name: str) -> None:
    assert validate_folder_name(name) is None
