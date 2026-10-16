import pytest

from vuechoixgarde.core.toggle import FileClass, ToggleAction, TogglePlan, decide_toggle


@pytest.mark.parametrize(
    ("image", "sidecars", "expected"),
    [
        (FileClass.ABSENT, (), TogglePlan(ToggleAction.TOGGLE_ON)),
        (
            FileClass.ABSENT,
            (FileClass.ABSENT, FileClass.ABSENT),
            TogglePlan(ToggleAction.TOGGLE_ON, (0, 1)),
        ),
        (FileClass.ABSENT, (FileClass.VERIFIED,), TogglePlan(ToggleAction.TOGGLE_ON)),
        (FileClass.ABSENT, (FileClass.FOREIGN,), TogglePlan(ToggleAction.CONFLICT)),
        (FileClass.ABSENT, (FileClass.MODIFIED,), TogglePlan(ToggleAction.CONFLICT)),
        (FileClass.VERIFIED, (), TogglePlan(ToggleAction.TOGGLE_OFF)),
        (FileClass.VERIFIED, (FileClass.MODIFIED,), TogglePlan(ToggleAction.TOGGLE_OFF_CONFIRM)),
        (FileClass.MODIFIED, (), TogglePlan(ToggleAction.TOGGLE_OFF_CONFIRM)),
        (FileClass.FOREIGN, (), TogglePlan(ToggleAction.CONFLICT)),
    ],
)
def test_toggle_decision_table(
    image: FileClass, sidecars: tuple[FileClass, ...], expected: TogglePlan
) -> None:
    assert decide_toggle(image, sidecars) == expected


def test_verified_sidecar_is_not_scheduled_for_copy() -> None:
    plan = decide_toggle(FileClass.ABSENT, (FileClass.ABSENT, FileClass.VERIFIED))
    assert plan.action is ToggleAction.TOGGLE_ON
    assert plan.sidecar_indexes_to_copy == (0,)


@pytest.mark.parametrize(
    ("image", "sidecars", "expected"),
    [
        (FileClass.VERIFIED, (), TogglePlan(ToggleAction.CONFLICT)),
        (FileClass.ABSENT, (FileClass.VERIFIED,), TogglePlan(ToggleAction.CONFLICT)),
        (FileClass.ABSENT, (), TogglePlan(ToggleAction.TOGGLE_ON)),
    ],
)
def test_missing_register_treats_every_present_file_as_foreign(
    image: FileClass, sidecars: tuple[FileClass, ...], expected: TogglePlan
) -> None:
    assert decide_toggle(image, sidecars, register_available=False) == expected
