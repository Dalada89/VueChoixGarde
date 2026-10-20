"""General settings, slot editing, and explicit profile management dialog."""

from collections.abc import Callable
from pathlib import Path
from typing import override

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from vuechoixgarde.app.service import ProfileSummary
from vuechoixgarde.core.folder_names import FolderNameError
from vuechoixgarde.core.keys import (
    ALLOWED_SLOT_CODES,
    displayed_key_label,
    printable_key_label,
)
from vuechoixgarde.core.slots import ProfileError, Slot, validate_slot_profile
from vuechoixgarde.ports.models import ProfileRecord, Settings
from vuechoixgarde.ui.keyboard import keyboard_event_data
from vuechoixgarde.ui.style import contrast_ratio
from vuechoixgarde.ui.texts import text

_NAME_ERROR_TEXT = {
    FolderNameError.EMPTY: "name_empty",
    FolderNameError.ONLY_SPACES_AND_DOTS: "name_spaces_dots",
    FolderNameError.DOT_SEGMENT: "name_dot_segment",
    FolderNameError.ABSOLUTE_PATH: "name_absolute",
    FolderNameError.PATH_SEPARATOR: "name_separator",
    FolderNameError.INVALID_CHARACTER: "name_character",
    FolderNameError.TRAILING_SPACE_OR_DOT: "name_trailing",
    FolderNameError.RESERVED_DEVICE_NAME: "name_reserved",
}


class _KeyCaptureButton(QPushButton):
    captured = Signal()

    def __init__(self, position: str, labels: dict[str, str], parent: QWidget) -> None:
        super().__init__(displayed_key_label(position, labels) or "?", parent)
        self.position = position
        self.labels = labels
        self.capturing = False
        self.clicked.connect(self.start_capture)

    def start_capture(self) -> None:
        self.capturing = True
        self.setText(text("press_key"))
        self.setFocus()

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self.capturing:
            super().keyPressEvent(event)
            return
        data = keyboard_event_data(event)
        if event.key() == Qt.Key.Key_Escape:
            self.capturing = False
            self.setText(displayed_key_label(self.position, self.labels) or "?")
            self.captured.emit()
            event.accept()
            return
        if not data.triggers_slot or data.position not in ALLOWED_SLOT_CODES:
            self.setText(text("invalid_captured_key"))
            event.accept()
            return
        self.position = data.position
        learned = printable_key_label(data.text)
        if learned is not None:
            self.labels[self.position] = learned
        self.capturing = False
        self.setText(displayed_key_label(self.position, self.labels) or "?")
        self.captured.emit()
        event.accept()


class _SlotEditor(QWidget):
    validation_changed = Signal(bool)

    def __init__(self, slots: tuple[Slot, ...], labels: dict[str, str], read_only: bool) -> None:
        super().__init__()
        self.labels = labels
        self.read_only = read_only
        self.rows: list[tuple[_KeyCaptureButton, QLineEdit, QPushButton, QLabel]] = []
        self.row_layout = QVBoxLayout()
        self.rows_host = QWidget()
        self.rows_host.setLayout(self.row_layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.rows_host)
        self.validation = QLabel()
        self.validation.setObjectName("validationMessage")
        controls = QHBoxLayout()
        self.add_button = QPushButton(text("add_slot"))
        self.remove_button = QPushButton(text("remove_slot"))
        self.add_button.clicked.connect(self.add_row)
        self.remove_button.clicked.connect(self.remove_row)
        controls.addWidget(self.add_button)
        controls.addWidget(self.remove_button)
        controls.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.validation)
        layout.addLayout(controls)
        for slot in slots:
            self._append_row(slot)
        self.set_read_only(read_only)
        self._update_validation()

    def slots(self) -> tuple[Slot, ...]:
        return tuple(
            Slot(key.position, name.text() or None, str(color.property("slotColor")))
            for key, name, color, _ in self.rows
        )

    def set_read_only(self, value: bool) -> None:
        self.read_only = value
        self.add_button.setEnabled(not value and len(self.rows) < 12)
        self.remove_button.setEnabled(not value and len(self.rows) > 1)
        for key, name, color, _ in self.rows:
            key.setEnabled(not value)
            name.setReadOnly(value)
            color.setEnabled(not value)

    def add_row(self) -> None:
        if len(self.rows) >= 12:
            return
        existing = {key.position for key, _, _, _ in self.rows}
        position = next((code for code in ALLOWED_SLOT_CODES if code not in existing), "KeyW")
        self._append_row(Slot(position, None, "#64B5F6"))
        self._update_validation()

    def remove_row(self) -> None:
        if len(self.rows) <= 1:
            return
        row = self.rows.pop()
        for widget in row:
            widget.deleteLater()
        self._update_validation()

    def _append_row(self, slot: Slot) -> None:
        row_widget = QFrame()
        row_widget.setObjectName("slotEditorRow")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(4, 3, 4, 3)
        key = _KeyCaptureButton(slot.key_position, self.labels, row_widget)
        key.setObjectName("keyCaptureButton")
        name = QLineEdit(slot.destination_name or "", row_widget)
        name.setPlaceholderText(text("destination_name"))
        color = QPushButton(text("choose_color"), row_widget)
        color.setObjectName("colorButton")
        color.setProperty("slotColor", slot.color)
        color.setToolTip(slot.color)
        sample = QLabel()
        sample.setMinimumWidth(78)
        sample.setObjectName("colorSample")
        _set_sample_color(sample, slot.color)
        ratio = contrast_ratio(slot.color, "#383838")
        sample.setToolTip(
            text("color_contrast_warning", ratio=f"{ratio:.1f}") if ratio < 4.5 else slot.color
        )
        color.clicked.connect(
            lambda _checked=False, button=color, label=sample: self._choose_color(button, label)
        )
        errors = QLabel()
        errors.setObjectName("validationMessage")
        row.addWidget(key)
        row.addWidget(name, 1)
        row.addWidget(color)
        row.addWidget(sample)
        row.addWidget(errors, 1)
        self.row_layout.addWidget(row_widget)
        self.rows.append((key, name, color, errors))
        name.textChanged.connect(self._update_validation)
        key.clicked.connect(self._update_validation)
        key.captured.connect(self._update_validation)
        self.add_button.setEnabled(not self.read_only and len(self.rows) < 12)
        self.remove_button.setEnabled(not self.read_only and len(self.rows) > 1)

    def _choose_color(self, button: QPushButton, sample: QLabel) -> None:
        current = str(button.property("slotColor"))
        selected = QColorDialog.getColor(parent=self, title=text("choose_color"))
        if not selected.isValid():
            return
        color = selected.name().upper()
        button.setProperty("slotColor", color)
        button.setToolTip(color)
        _set_sample_color(sample, color)
        ratio = contrast_ratio(color, "#383838")
        warning = text("color_contrast_warning", ratio=f"{ratio:.1f}") if ratio < 4.5 else ""
        sample.setToolTip(warning or color)
        if current != color:
            self._update_validation()

    def _update_validation(self, *_args: object) -> None:
        values = self.slots()
        issues = validate_slot_profile(values)
        row_messages: list[list[str]] = [[] for _ in values]
        for issue in issues:
            message = (
                text(_NAME_ERROR_TEXT[issue.name_error])
                if issue.name_error is not None
                else _issue_text(issue.error)
            )
            for index in issue.slot_indexes:
                if index < len(row_messages):
                    row_messages[index].append(message)
        for index, (_, _, _, label) in enumerate(self.rows):
            label.setText("; ".join(dict.fromkeys(row_messages[index])))
        self.validation.setText(text("slot_profile_invalid") if issues else "")
        self.add_button.setEnabled(not self.read_only and len(self.rows) < 12)
        self.remove_button.setEnabled(not self.read_only and len(self.rows) > 1)
        self.validation_changed.emit(not issues)


def _set_sample_color(sample: QLabel, color: str) -> None:
    sample.setStyleSheet(f"background-color: {color};")


def _issue_text(issue: ProfileError) -> str:
    return {
        ProfileError.TOO_FEW_SLOTS: text("slot_minimum"),
        ProfileError.TOO_MANY_SLOTS: text("slot_maximum"),
        ProfileError.INVALID_KEY: text("slot_invalid_key"),
        ProfileError.DUPLICATE_KEY: text("slot_duplicate_key"),
        ProfileError.DUPLICATE_NAME: text("slot_duplicate_name"),
        ProfileError.INVALID_NAME: text("slot_invalid_name"),
    }[issue]


class SettingsDialog(QDialog):
    """Edit general options and slots and manage known profiles explicitly."""

    def __init__(
        self,
        settings: Settings,
        profile: ProfileRecord | None,
        profiles: tuple[ProfileSummary, ...],
        log_directory: Path,
        *,
        read_only: bool,
        on_save: Callable[[bool, str, str, tuple[Slot, ...], tuple[tuple[str, str], ...]], None],
        on_profile_action: Callable[[str, str | None], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.profile = profile
        self.profiles = profiles
        self.log_directory = log_directory
        self.read_only = read_only
        self.on_save = on_save
        self.on_profile_action = on_profile_action
        self.setWindowTitle(text("settings"))
        self.resize(900, 620)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        self.general_tab = self._build_general(settings)
        self.tabs.addTab(self.general_tab, text("general_tab"))
        self.slot_tab = self._build_slots(settings, profile, read_only)
        self.tabs.addTab(self.slot_tab, text("slots_tab"))
        self.profiles_tab = self._build_profiles(profile, profiles, read_only)
        self.tabs.addTab(self.profiles_tab, text("profiles_tab"))
        layout.addWidget(self.tabs, 1)
        self.message = QLabel()
        self.message.setObjectName("validationMessage")
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        for editor in self.slot_editors.values():
            editor.validation_changed.connect(self._set_save_enabled)
        if self.save_button is not None:
            self.save_button.setEnabled(not read_only)
        self._set_save_enabled()
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_save_enabled(self, _valid: bool | None = None) -> None:
        if self.save_button is not None:
            valid = all(
                not validate_slot_profile(editor.slots()) for editor in self.slot_editors.values()
            )
            self.save_button.setEnabled(not self.read_only and valid)

    def refresh_profiles(self, profiles: tuple[ProfileSummary, ...]) -> None:
        self.profiles = profiles
        self._populate_profiles()
        self._update_delete_enabled()
        self.action_buttons["assign_orphan"].setEnabled(
            not self.read_only
            and self.profile is not None
            and any(not summary.folder_exists for summary in profiles)
        )

    def set_message(self, value: str) -> None:
        self.message.setText(value)

    def _build_general(self, settings: Settings) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.reopen_checkbox = QCheckBox(text("reopen_last_folder"))
        self.reopen_checkbox.setChecked(settings.reopen_last_folder)
        self.reopen_checkbox.setEnabled(not self.read_only)
        self.sort_combo = QComboBox()
        self.sort_combo.addItem(text("sort_ascending"), "asc")
        self.sort_combo.addItem(text("sort_descending"), "desc")
        self.sort_combo.setCurrentIndex(1 if settings.sort_direction == "desc" else 0)
        self.sort_combo.setEnabled(not self.read_only)
        self.language_combo = QComboBox()
        for code, label in (("de", "Deutsch"), ("en", "English"), ("fr", "Français")):
            self.language_combo.addItem(label, code)
        self.language_combo.setCurrentIndex({"de": 0, "en": 1, "fr": 2}[settings.language])
        self.language_combo.setEnabled(not self.read_only)
        self.sound_checkbox = QCheckBox(text("sound"))
        self.sound_checkbox.setChecked(settings.sound_enabled)
        self.sound_checkbox.setEnabled(not self.read_only)
        self.log_button = QPushButton(text("open_log_folder"))
        self.log_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_directory)))
        )
        form.addRow(self.reopen_checkbox)
        form.addRow(text("language"), self.language_combo)
        form.addRow(self.sound_checkbox)
        form.addRow(text("default_sort_direction"), self.sort_combo)
        form.addRow(self.log_button)
        return page

    def _build_slots(
        self, settings: Settings, profile: ProfileRecord | None, read_only: bool
    ) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.slot_editor_layout = layout
        self.slot_target = QComboBox()
        self.slot_target.addItem(text("global_template"), "template")
        if profile is not None:
            self.slot_target.addItem(text("current_profile"), "profile")
        layout.addWidget(self.slot_target)
        self.slot_editors = {
            "template": _SlotEditor(
                settings.global_slot_template, dict(settings.learned_key_labels), read_only
            )
        }
        if profile is not None:
            self.slot_editors["profile"] = _SlotEditor(
                profile.slots, dict(settings.learned_key_labels), read_only
            )
        self.slot_stack = QStackedWidget(page)
        for editor in self.slot_editors.values():
            self.slot_stack.addWidget(editor)
        self.slot_editor = self.slot_editors["template"]
        layout.addWidget(self.slot_stack, 1)
        self.slot_target.currentIndexChanged.connect(self._change_slot_target)
        return page

    def _change_slot_target(self, index: int) -> None:
        target = str(self.slot_target.itemData(index))
        self.slot_editor = self.slot_editors[target]
        self.slot_stack.setCurrentWidget(self.slot_editor)
        self._set_save_enabled()

    def _build_profiles(
        self, profile: ProfileRecord | None, profiles: tuple[ProfileSummary, ...], read_only: bool
    ) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.profile_table = QTableWidget(0, 3, page)
        self.profile_table.setHorizontalHeaderLabels(
            [text("profile_source"), text("profile_status"), text("profile_created")]
        )
        self.profile_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.profile_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.profile_table.currentCellChanged.connect(lambda *_args: self._update_delete_enabled())
        layout.addWidget(self.profile_table, 1)
        self.profile_actions = QHBoxLayout()
        actions = (
            ("save_profile_template", "save_profile_as_template"),
            ("reset_global_template", "reset_global_template"),
            ("reset_current_profile", "reset_current_profile"),
            ("assign_orphan", "assign_orphan"),
            ("delete_profile", "delete_profile"),
        )
        self.action_buttons: dict[str, QPushButton] = {}
        for key, action in actions:
            button = QPushButton(text(key))
            button.setEnabled(not read_only)
            button.clicked.connect(lambda _checked=False, name=action: self._profile_action(name))
            self.profile_actions.addWidget(button)
            self.action_buttons[action] = button
        layout.addLayout(self.profile_actions)
        self.profiles = profiles
        self._populate_profiles()
        self.action_buttons["save_profile_as_template"].setEnabled(
            not read_only and profile is not None
        )
        self.action_buttons["reset_current_profile"].setEnabled(
            not read_only and profile is not None
        )
        self.action_buttons["assign_orphan"].setEnabled(
            not read_only
            and profile is not None
            and any(not summary.folder_exists for summary in profiles)
        )
        self._update_delete_enabled()
        return page

    def _update_delete_enabled(self) -> None:
        selected_id = self._selected_profile_id()
        active_id = self.profile.id if self.profile is not None else None
        enabled = not self.read_only and selected_id is not None and selected_id != active_id
        self.action_buttons["delete_profile"].setEnabled(enabled)

    def _populate_profiles(self) -> None:
        table = self.profile_table
        table.setRowCount(len(self.profiles))
        for row, summary in enumerate(self.profiles):
            profile = summary.profile
            status = text("profile_exists") if summary.folder_exists else text("profile_orphaned")
            for column, value in enumerate((profile.display_path, status, profile.created_at)):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, profile.id)
                table.setItem(row, column, item)
        table.resizeColumnsToContents()

    def _profile_action(self, action: str) -> None:
        profile_id = self._selected_profile_id()
        if action in {
            "reset_global_template",
            "reset_current_profile",
            "assign_orphan",
            "delete_profile",
        }:
            if action == "assign_orphan":
                selected = next(
                    (item for item in self.profiles if item.profile.id == profile_id), None
                )
                if selected is None or selected.folder_exists:
                    self.set_message(text("select_orphan_profile"))
                    return
            if action == "delete_profile" and profile_id is None:
                self.set_message(text("select_profile"))
                return
            if (
                action == "delete_profile"
                and self.profile is not None
                and profile_id == self.profile.id
            ):
                return
            if action == "assign_orphan" and profile_id is None:
                self.set_message(text("select_orphan_profile"))
                return
            if not self._confirm(action):
                return
        self.set_message(text("profile_action_working"))
        self.on_profile_action(action, profile_id)

    def _confirm(self, action: str) -> bool:
        message = {
            "reset_global_template": text("confirm_reset_template"),
            "reset_current_profile": text("confirm_reset_profile"),
            "assign_orphan": text("confirm_assign_orphan"),
            "delete_profile": text("confirm_delete_profile"),
        }[action]
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(text("confirm_title"))
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _selected_profile_id(self) -> str | None:
        row = self.profile_table.currentRow()
        item = self.profile_table.item(row, 0) if row >= 0 else None
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def _save(self) -> None:
        target = self.slot_target.currentData()
        slots = self.slot_editor.slots()
        invalid_target = next(
            (
                name
                for name, editor in self.slot_editors.items()
                if validate_slot_profile(editor.slots())
            ),
            None,
        )
        if invalid_target is not None:
            self.slot_target.setCurrentIndex(self.slot_target.findData(invalid_target))
            self.tabs.setCurrentWidget(self.slot_tab)
            self.set_message(text("slot_profile_invalid"))
            return
        direction = str(self.sort_combo.currentData())
        self.on_save(
            self.reopen_checkbox.isChecked(),
            direction,
            str(target),
            slots,
            tuple(sorted(self.slot_editor.labels.items())),
        )

    def open_log_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_directory)))
