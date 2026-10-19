"""Minimal English UI text source; keys are intended for Phase 6 catalog migration."""

TEXTS = {
    "app_title": "VueChoixGarde",
    "open_folder": "Open folder…",
    "sort_ascending": "Sort: ascending",
    "sort_descending": "Sort: descending",
    "refresh": "Refresh",
    "reconcile": "Reconcile",
    "settings": "Settings",
    "help": "Help",
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
    """Return a named UI string and interpolate named values where provided."""
    return TEXTS[message_key].format(**values) if values else TEXTS[message_key]
