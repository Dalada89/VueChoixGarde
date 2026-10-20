from pathlib import Path

import pytest

from vuechoixgarde.app.service import PartialSettingsSaveError
from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.slots import Slot


def test_profile_save_failure_identifies_settings_already_persisted(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    runtime = create_runtime(tmp_path / "application-data")
    runtime.service.open_folder(source)
    previous_template = runtime.service.settings.global_slot_template

    def fail_replace(*_args, **_kwargs):
        raise OSError("profile store unavailable")

    monkeypatch.setattr(runtime.service.state_store, "replace_profile_slots", fail_replace)
    try:
        with pytest.raises(PartialSettingsSaveError, match="Global settings were saved"):
            runtime.service.save_settings_and_profile_slots(
                reopen_last_folder=False,
                sort_direction="asc",
                language="de",
                sound_enabled=False,
                global_slot_template=(Slot("KeyW", "Favorite", "#4488CC"),),
                profile_slots=(Slot("KeyA", "Other", "#CC8844"),),
                learned_key_labels=(),
            )
        assert runtime.service.settings.language == "de"
        assert runtime.service.settings.global_slot_template != previous_template
        assert runtime.service.current_view() is not None
    finally:
        runtime.shutdown()
