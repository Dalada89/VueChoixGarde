"""Persist eligible learned physical-key labels through global settings (FR-060/081)."""

from collections.abc import Mapping

from vuechoixgarde.core.keys import update_learned_key_labels
from vuechoixgarde.ports.models import Settings
from vuechoixgarde.ports.settings import SettingsStore


def learn_key_label(
    settings: Settings,
    settings_store: SettingsStore,
    position: str,
    text: str,
    *,
    modifier_active: bool,
) -> Settings:
    """Save settings only when an eligible key press changes its learned label."""
    labels: Mapping[str, str] = dict(settings.learned_key_labels)
    updated = update_learned_key_labels(labels, position, text, modifier_active=modifier_active)
    normalized = tuple(sorted(updated.items()))
    if normalized == settings.learned_key_labels:
        return settings
    changed = Settings(
        settings.schema_version,
        settings.language,
        settings.sound_enabled,
        settings.sort_direction,
        settings.reopen_last_folder,
        settings.last_folder,
        settings.global_slot_template,
        normalized,
    )
    settings_store.save(changed)
    return changed
