"""Localized UI message lookup backed by packaged JSON catalogs."""

import json
import logging
from functools import lru_cache
from importlib.resources import files

_LANGUAGE = "en"
_LOGGED_MISSING: set[tuple[str, str]] = set()


@lru_cache(maxsize=3)
def _catalog(code: str) -> dict[str, str]:
    resource = files("vuechoixgarde.i18n").joinpath(f"{code}.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def set_language(code: str) -> None:
    """Select the active UI catalog."""
    global _LANGUAGE
    if code not in {"de", "en", "fr"}:
        raise ValueError("language must be de, en, or fr")
    _LANGUAGE = code


TEXTS = {
    "app_title": "VueChoixGarde",
    "open_folder": "Open folder…",
    "sort_ascending": "Sort: ascending",
    "sort_descending": "Sort: descending",
    "refresh": "Refresh",
    "reconcile": "Reconcile",
    "settings": "Settings",
    "settings_busy": "Wait until the current file operation finishes before opening settings.",
    "selected_accessible": "Selected in a destination",
    "image_accessible": "Current image preview",
    "progress_accessible": "Image position and total count",
    "slot_accessible": "Slot {key}, destination {name}, state {state}",
    "general_tab": "General",
    "slots_tab": "Slots",
    "profiles_tab": "Profiles",
    "reopen_last_folder": "Reopen the last source folder at startup",
    "default_sort_direction": "Default sort direction",
    "open_log_folder": "Open log folder",
    "global_template": "Global slot template",
    "current_profile": "Current folder profile",
    "add_slot": "Add slot",
    "remove_slot": "Remove last slot",
    "destination_name": "Destination folder name (optional)",
    "choose_color": "Choose color…",
    "press_key": "Press a key…",
    "invalid_captured_key": "Use an unmodified character-block key",
    "color_contrast_warning": "Low contrast against slot panel ({ratio}:1)",
    "slot_profile_invalid": "Fix the slot errors before saving.",
    "slot_minimum": "At least one slot is required.",
    "slot_maximum": "At most 12 slots are allowed.",
    "slot_invalid_key": "This physical key position is not allowed.",
    "slot_duplicate_key": "This key is already assigned to another slot.",
    "slot_duplicate_name": "This destination name is already used.",
    "slot_invalid_name": "Enter a valid destination folder name.",
    "profile_source": "Source folder",
    "profile_status": "Status",
    "profile_created": "Created",
    "profile_exists": "Available",
    "profile_orphaned": "Orphaned — folder missing",
    "save_profile_template": "Save current as template",
    "reset_global_template": "Reset template",
    "reset_current_profile": "Reset current profile",
    "assign_orphan": "Assign orphan to current folder",
    "delete_profile": "Delete selected profile",
    "select_profile": "Select a profile first.",
    "select_orphan_profile": "Select a profile whose source folder is missing.",
    "profile_action_working": "Updating profile data…",
    "confirm_title": "Confirm profile change",
    "confirm_reset_template": "Reset the global slot template to the four default slots?",
    "confirm_reset_profile": "Replace the current profile slots with the global template?",
    "confirm_assign_orphan": "Assign this orphaned profile and its register to the current folder?",
    "confirm_delete_profile": (
        "Delete this profile and its register? Image files will not be changed."
    ),
    "settings_saved": "Settings saved.",
    "settings_save_failed": "Settings could not be saved; the previous values remain active.",
    "partial_settings_save_failed": (
        "Global settings were saved, but profile slots were not. "
        "Review the profile slots and save again."
    ),
    "slot_status_failed": "Some destination statuses could not be checked.",
    "destination_renamed": "A destination folder was renamed; it was not moved or changed.",
    "selection_count_failed": "The selected-image count could not be checked.",
    "profile_action_failed": "The profile change failed. No image files were changed.",
    "profile_action_done": "Profile change completed.",
    "help": "Help",
    "help_shortcuts": (
        "→ / ←: next / previous image\\nF1: help\\nF5: refresh\\n"
        "Esc: close this dialog\\nCtrl+,: settings\\nCtrl+O: open a source folder"
    ),
    "help_behavior": (
        "A slot key adds or removes a copy. Source files are never changed. "
        "Modified copies require confirmation. On non-US layouts, press each key once "
        "so its label is learned; a dead key may briefly learn a composed character. "
        "Open the log folder from Settings → General."
    ),
    "help_slot_accessible": "Slot {key}, destination {name}",
    "no_name": "No name",
    "language": "Language",
    "sound": "Sound",
    "empty": "Open a folder to review images.",
    "empty_folder": "No supported images in this folder.",
    "filename": "No image",
    "progress": "{current} of {total}",
    "selected_count": "Selected images: {count}",
    "open_dialog_title": "Open source folder",
    "name_dialog_title": "Choose destination folder name",
    "name_prompt": "Folder name",
    "invalid_name": "Enter a valid folder name.",
    "name_empty": "A folder name is required.",
    "name_spaces_dots": "The name cannot contain only spaces or dots.",
    "name_dot_segment": "The name cannot be . or ..",
    "name_absolute": "Enter a folder name, not an absolute path.",
    "name_separator": "Folder names cannot contain path separators.",
    "name_character": "The name contains a character that is not allowed.",
    "name_trailing": "The name cannot end with a space or dot.",
    "name_reserved": "This name is reserved by Windows.",
    "name_duplicate": "Another slot already uses this destination name.",
    "operation_error": "The operation could not be completed: {details}",
    "conflict_message": "These destination files are already occupied: {names}",
    "cancel": "Cancel",
    "ok": "OK",
    "added": "Added {key} → {name}",
    "removed": "Removed {key} → {name}",
    "busy": "Working…",
    "busy_slot": "Busy — slot action ignored",
    "boundary": "You are at the end of the image list.",
    "previous_boundary": "You are at the beginning of the image list.",
    "checking": "Checking…",
    "state_none": "No destination name",
    "state_ready": "Ready",
    "state_selected": "Selected",
    "state_modified": "Modified copy",
    "state_conflict": "Conflict",
    "state_faulty": "Faulty destination",
    "state_checking": "Checking…",
    "decode_missing": "This image is missing or cannot be accessed.",
    "decode_unsupported": "This image format is not supported.",
    "decode_corrupt": "This image is damaged or cannot be decoded.",
    "decode_too_large": "This image is too large to display safely.",
    "decode_heic_unavailable": "HEIC/HEIF display is unavailable on this platform.",
    "decode_generic": "This image cannot be displayed.",
    "error_title": "Operation failed",
    "conflict_title": "File conflict",
    "modified_title": "Confirm removal of modified copies",
    "modified_prompt": "These managed copies were changed. Remove them anyway?",
    "damaged_title": "Damaged application data",
    "damaged_prompt": (
        "Application data is damaged. Continue with defaults, or keep it unchanged and "
        "continue in view-only mode?"
    ),
    "defaults": "Continue with defaults",
    "view_only": "View only",
    "help_text": (
        "Right / Left: next / previous image\n"
        "F5: refresh the image list\n"
        "Slot keys: toggle a byte-identical copy in that destination\n"
        "The source images are never changed. Slot labels are learned from the active layout."
    ),
    "source_folder": "Source folder: {path}",
    "image_progress": "Image {current} of {total}",
}


def text(message_key: str, **values: object) -> str:
    """Look up a localized message, falling back to English for missing translations."""
    catalog = _catalog(_LANGUAGE)
    message = catalog.get(message_key)
    if message is None and _LANGUAGE != "en":
        missing = (_LANGUAGE, message_key)
        if missing not in _LOGGED_MISSING:
            logging.getLogger(__name__).warning(
                "missing translation for %s in %s", message_key, _LANGUAGE
            )
            _LOGGED_MISSING.add(missing)
        message = _catalog("en").get(message_key)
    if message is None:
        raise KeyError(f"unknown UI message key: {message_key}")
    return message.format(**values) if values else message
