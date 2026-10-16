from uuid import uuid4

import pytest

from vuechoixgarde.core.temp_names import is_reserved_temp_name, temp_file_name


def test_temp_file_name_uses_reserved_pattern() -> None:
    operation_id = uuid4().hex
    name = temp_file_name(operation_id, 3)
    assert name == f".vuechoixgarde-{operation_id}-3.tmp"
    assert is_reserved_temp_name(name)


def test_reserved_temp_name_comparison_is_case_insensitive() -> None:
    name = temp_file_name(uuid4().hex, 0)
    assert is_reserved_temp_name(name.upper())


@pytest.mark.parametrize("operation_id", ["", "not-a-uuid", "0" * 32, str(uuid4())])
def test_temp_file_name_rejects_noncanonical_or_non_v4_operation_ids(operation_id: str) -> None:
    with pytest.raises(ValueError):
        temp_file_name(operation_id, 0)


@pytest.mark.parametrize("index", [-1, True, 1.0])
def test_temp_file_name_rejects_invalid_indexes(index: int) -> None:
    with pytest.raises(ValueError):
        temp_file_name(uuid4().hex, index)


@pytest.mark.parametrize(
    "name",
    [".vuechoixgarde-nope-0.tmp", ".vuechoixgarde-00000000000000000000000000000000-0.tmp", "x.tmp"],
)
def test_non_reserved_temp_names_are_rejected(name: str) -> None:
    assert not is_reserved_temp_name(name)
