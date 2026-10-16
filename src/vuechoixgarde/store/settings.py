"""Strict JSON settings persistence with atomic replacement (Technical Design 6.2)."""

import contextlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import cast

from vuechoixgarde.core.folder_names import validate_folder_name
from vuechoixgarde.core.keys import ALLOWED_SLOT_CODES
from vuechoixgarde.core.language import default_language
from vuechoixgarde.core.slots import DEFAULT_SLOTS, Slot, validate_slot_profile
from vuechoixgarde.ports.clock import Clock
from vuechoixgarde.ports.errors import SettingsErrorReason, SettingsStoreError
from vuechoixgarde.ports.models import LoadStatus, Settings, SettingsLoadResult
from vuechoixgarde.store.paths import prepare_application_data

_COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{6}")
_SETTINGS_FIELDS = frozenset(
    {
        "schema_version",
        "language",
        "sound_enabled",
        "sort_direction",
        "reopen_last_folder",
        "last_folder",
        "global_slot_template",
        "learned_key_labels",
    }
)


class JsonSettingsStore:
    """Load and atomically save schema-version-1 settings in application data."""

    def __init__(self, root: Path, clock: Clock) -> None:
        self.root = root
        self.path = root / "settings.json"
        self.clock = clock
        prepare_application_data(root)

    def defaults(self, locale_name: str | None = None) -> Settings:
        """Build validated first-run defaults for the supplied operating-system locale."""
        return Settings(
            schema_version=1,
            language=default_language(locale_name),
            sound_enabled=True,
            sort_direction="asc",
            reopen_last_folder=False,
            last_folder=None,
            global_slot_template=DEFAULT_SLOTS,
            learned_key_labels=(),
        )

    def load(self, locale_name: str | None = None) -> SettingsLoadResult:
        """Load settings, creating defaults only when the settings file is missing."""
        if not self.path.exists():
            settings = self.defaults(locale_name)
            try:
                self.save(settings)
            except SettingsStoreError as error:
                return SettingsLoadResult(
                    LoadStatus.DAMAGED, reason=SettingsErrorReason.IO_ERROR, detail=str(error)
                )
            return SettingsLoadResult(LoadStatus.CREATED_DEFAULTS, settings)
        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError as error:
            return SettingsLoadResult(
                LoadStatus.DAMAGED, reason=SettingsErrorReason.IO_ERROR, detail=str(error)
            )
        try:
            parsed = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError) as error:
            return SettingsLoadResult(
                LoadStatus.DAMAGED, reason=SettingsErrorReason.INVALID_JSON, detail=str(error)
            )
        try:
            settings = self._parse_settings(parsed)
        except (TypeError, ValueError, KeyError) as error:
            return SettingsLoadResult(
                LoadStatus.DAMAGED, reason=SettingsErrorReason.INVALID_SETTINGS, detail=str(error)
            )
        return SettingsLoadResult(LoadStatus.LOADED, settings)

    def save(self, settings: Settings) -> None:
        """Validate and atomically persist settings with a same-directory fsynced temp file."""
        self.validate_settings(settings)
        payload = {
            "schema_version": settings.schema_version,
            "language": settings.language,
            "sound_enabled": settings.sound_enabled,
            "sort_direction": settings.sort_direction,
            "reopen_last_folder": settings.reopen_last_folder,
            "last_folder": settings.last_folder,
            "global_slot_template": [
                {
                    "key_position": slot.key_position,
                    "destination_name": slot.destination_name,
                    "color": slot.color,
                }
                for slot in settings.global_slot_template
            ],
            "learned_key_labels": dict(settings.learned_key_labels),
        }
        temp_path = self.root / f".settings-{uuid.uuid4().hex}.tmp"
        descriptor: int | None = None
        try:
            encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            descriptor = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
                descriptor = None
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            temp_path.replace(self.path)
        except OSError as error:
            if descriptor is not None:
                os.close(descriptor)
            with contextlib.suppress(OSError):
                temp_path.unlink(missing_ok=True)
            raise SettingsStoreError(
                SettingsErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def _parse_settings(self, value: object) -> Settings:
        if not isinstance(value, dict) or set(value) != _SETTINGS_FIELDS:
            raise ValueError("settings object has missing or unknown fields")
        data = cast(dict[str, object], value)
        schema_version = data["schema_version"]
        if type(schema_version) is not int or schema_version != 1:
            raise ValueError("schema_version must be integer 1")
        language = data["language"]
        if not isinstance(language, str) or language not in {"de", "en", "fr"}:
            raise ValueError("language must be de, en, or fr")
        sound_enabled = data["sound_enabled"]
        if type(sound_enabled) is not bool:
            raise ValueError("sound_enabled must be a boolean")
        sort_direction = data["sort_direction"]
        if not isinstance(sort_direction, str) or sort_direction not in {"asc", "desc"}:
            raise ValueError("sort_direction must be asc or desc")
        reopen = data["reopen_last_folder"]
        if type(reopen) is not bool:
            raise ValueError("reopen_last_folder must be a boolean")
        last_folder = data["last_folder"]
        if last_folder is not None and not isinstance(last_folder, str):
            raise ValueError("last_folder must be a string or null")
        raw_slots = data["global_slot_template"]
        if not isinstance(raw_slots, list):
            raise ValueError("global_slot_template must be a list")
        slots: list[Slot] = []
        for raw_slot in raw_slots:
            if not isinstance(raw_slot, dict) or set(raw_slot) != {
                "key_position",
                "destination_name",
                "color",
            }:
                raise ValueError("slot has missing or unknown fields")
            slot_data = cast(dict[str, object], raw_slot)
            key_position = slot_data["key_position"]
            destination_name = slot_data["destination_name"]
            color = slot_data["color"]
            if not isinstance(key_position, str):
                raise ValueError("slot key_position must be a string")
            if destination_name is not None and not isinstance(destination_name, str):
                raise ValueError("slot destination_name must be a string or null")
            if not isinstance(color, str) or _COLOR_PATTERN.fullmatch(color) is None:
                raise ValueError("slot color must match #RRGGBB")
            slots.append(Slot(key_position, destination_name, color))
        issues = validate_slot_profile(slots)
        if issues:
            raise ValueError(f"invalid slot profile: {issues!r}")
        labels = data["learned_key_labels"]
        if not isinstance(labels, dict):
            raise ValueError("learned_key_labels must be an object")
        learned: list[tuple[str, str]] = []
        for position, label in cast(dict[object, object], labels).items():
            if not isinstance(position, str) or position not in ALLOWED_SLOT_CODES:
                raise ValueError("learned label position is not allowed")
            if not isinstance(label, str) or len(label) != 1:
                raise ValueError("learned labels must be strings of length 1")
            learned.append((position, label))
        settings = Settings(
            schema_version=1,
            language=language,
            sound_enabled=sound_enabled,
            sort_direction=sort_direction,
            reopen_last_folder=reopen,
            last_folder=last_folder,
            global_slot_template=tuple(slots),
            learned_key_labels=tuple(sorted(learned)),
        )
        self.validate_settings(settings)
        return settings

    @staticmethod
    def validate_settings(settings: Settings) -> None:
        if type(settings.schema_version) is not int or settings.schema_version != 1:
            raise SettingsStoreError(
                SettingsErrorReason.INVALID_SETTINGS, detail="schema_version must be 1"
            )
        if not isinstance(settings.language, str) or settings.language not in {"de", "en", "fr"}:
            raise SettingsStoreError(
                SettingsErrorReason.INVALID_SETTINGS, detail="unsupported language"
            )
        if (
            type(settings.sound_enabled) is not bool
            or type(settings.reopen_last_folder) is not bool
        ):
            raise SettingsStoreError(
                SettingsErrorReason.INVALID_SETTINGS, detail="boolean setting has invalid type"
            )
        if not isinstance(settings.sort_direction, str) or settings.sort_direction not in {
            "asc",
            "desc",
        }:
            raise SettingsStoreError(
                SettingsErrorReason.INVALID_SETTINGS, detail="invalid sort direction"
            )
        if settings.last_folder is not None and not isinstance(settings.last_folder, str):
            raise SettingsStoreError(
                SettingsErrorReason.INVALID_SETTINGS, detail="last_folder must be string or null"
            )
        if not isinstance(settings.global_slot_template, tuple) or any(
            not isinstance(slot, Slot) for slot in settings.global_slot_template
        ):
            raise SettingsStoreError(
                SettingsErrorReason.INVALID_SETTINGS, detail="global slot template has invalid type"
            )
        for slot in settings.global_slot_template:
            if not isinstance(slot.key_position, str):
                raise SettingsStoreError(
                    SettingsErrorReason.INVALID_SETTINGS,
                    detail="slot key_position must be a string",
                )
            if slot.destination_name is not None and not isinstance(slot.destination_name, str):
                raise SettingsStoreError(
                    SettingsErrorReason.INVALID_SETTINGS,
                    detail="slot destination_name must be a string or null",
                )
            if not isinstance(slot.color, str) or _COLOR_PATTERN.fullmatch(slot.color) is None:
                raise SettingsStoreError(
                    SettingsErrorReason.INVALID_SETTINGS, detail="slot color must match #RRGGBB"
                )
            if (
                slot.destination_name is not None
                and validate_folder_name(slot.destination_name) is not None
            ):
                raise SettingsStoreError(
                    SettingsErrorReason.INVALID_SETTINGS, detail="invalid destination name"
                )
        if validate_slot_profile(settings.global_slot_template):
            raise SettingsStoreError(
                SettingsErrorReason.INVALID_SETTINGS, detail="invalid slot profile"
            )
        if not isinstance(settings.learned_key_labels, tuple):
            raise SettingsStoreError(
                SettingsErrorReason.INVALID_SETTINGS, detail="learned labels have invalid type"
            )
        positions: set[str] = set()
        for item in settings.learned_key_labels:
            if not isinstance(item, tuple) or len(item) != 2:
                raise SettingsStoreError(
                    SettingsErrorReason.INVALID_SETTINGS, detail="invalid learned key label"
                )
            position, label = item
            if (
                not isinstance(position, str)
                or position not in ALLOWED_SLOT_CODES
                or not isinstance(label, str)
                or len(label) != 1
                or position in positions
            ):
                raise SettingsStoreError(
                    SettingsErrorReason.INVALID_SETTINGS, detail="invalid learned key label"
                )
            positions.add(position)
