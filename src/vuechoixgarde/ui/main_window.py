"""Minimal keyboard-driven Qt main window for image review and safe slot toggling."""

import sys
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar, cast, override

from PySide6.QtCore import QCoreApplication, QLibraryInfo, Qt, QTimer, QTranslator
from PySide6.QtGui import (
    QCloseEvent,
    QFontMetrics,
    QImage,
    QKeyEvent,
    QKeySequence,
    QPixmap,
    QResizeEvent,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from vuechoixgarde.app.results import SlotState, UseCaseStatus
from vuechoixgarde.app.service import (
    PartialSettingsSaveError,
    ProfileSummary,
    SessionView,
    SlotStatusResult,
)
from vuechoixgarde.app.toggle import TogglePlan, ToggleResult
from vuechoixgarde.bootstrap import Runtime
from vuechoixgarde.core.comparison import comparison_key
from vuechoixgarde.core.folder_names import FolderNameError, validate_folder_name
from vuechoixgarde.core.keys import displayed_key_label, update_learned_key_labels
from vuechoixgarde.core.navigation import NavigationDirection
from vuechoixgarde.core.slots import Slot
from vuechoixgarde.core.sorting import sort_names
from vuechoixgarde.imaging.cache import DecodedImageCache
from vuechoixgarde.imaging.size import screen_decode_bounds
from vuechoixgarde.ports.errors import ImageDecodeError, ImageDecodeErrorReason
from vuechoixgarde.ports.imaging import DecodedImage
from vuechoixgarde.ports.log import LogEvent, LogLevel
from vuechoixgarde.ports.models import Settings
from vuechoixgarde.ui.help_dialog import HelpDialog
from vuechoixgarde.ui.keyboard import keyboard_event_data, main_window_key_filter_enabled
from vuechoixgarde.ui.settings_dialog import SettingsDialog
from vuechoixgarde.ui.sound import SoundPlayer
from vuechoixgarde.ui.texts import set_language, text
from vuechoixgarde.ui.workers import WorkerPools

_Result = TypeVar("_Result")


_STATE_PRESENTATION = {
    SlotState.NO_DESTINATION: ("○", "state_none"),
    SlotState.READY: ("·", "state_ready"),
    SlotState.CHECKING: ("◌", "state_checking"),
    SlotState.SELECTED: ("★", "state_selected"),
    SlotState.MODIFIED: ("!", "state_modified"),
    SlotState.CONFLICT: ("⚠", "state_conflict"),
    SlotState.FAULTY: ("x", "state_faulty"),
}
_DECODE_TEXT = {
    ImageDecodeErrorReason.MISSING: "decode_missing",
    ImageDecodeErrorReason.UNSUPPORTED: "decode_unsupported",
    ImageDecodeErrorReason.CORRUPT: "decode_corrupt",
    ImageDecodeErrorReason.TOO_LARGE: "decode_too_large",
    ImageDecodeErrorReason.HEIC_UNAVAILABLE: "decode_heic_unavailable",
}


class _ElidingLabel(QLabel):
    """Display an elided slot name while retaining full accessible and tooltip text."""

    def __init__(self, value: str) -> None:
        super().__init__()
        self._full_text = ""
        self.setFullText(value)

    def setFullText(self, value: str) -> None:  # noqa: N802
        self._full_text = value
        self.setAccessibleName(value)
        self.setToolTip(value)
        self._update_elided_text()

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        self.setText(
            QFontMetrics(self.font()).elidedText(
                self._full_text,
                Qt.TextElideMode.ElideMiddle,
                max(0, self.contentsRect().width()),
            )
        )


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


class MainWindow(QMainWindow):
    """Review images, navigate without wrapping and run slot actions off the UI thread."""

    def __init__(self, runtime: Runtime) -> None:
        super().__init__()
        self.runtime = runtime
        set_language(runtime.settings.language)
        self.workers = WorkerPools()
        self.cache = DecodedImageCache(max_entries=5, max_bytes=256 * 1024 * 1024)
        self.sound_player = SoundPlayer(self)
        self.view: SessionView | None = None
        self._pending_operations = 0
        self._slot_operation_pending = False
        self._slot_status_in_flight = False
        self._slot_status_requested: SessionView | None = None
        self._navigation_in_flight = False
        self._queued_navigation: list[NavigationDirection] = []
        self._closing = False
        self._ready_to_close = False
        self._shutdown_started = False
        self._last_direction = NavigationDirection.NEXT
        self._close_busy_timer = QTimer(self)
        self._close_busy_timer.setSingleShot(True)
        self._close_busy_timer.setInterval(1000)
        self._close_busy_timer.timeout.connect(lambda: self.busy_label.show())
        self._build_ui()
        self._load_qt_translation(runtime.settings.language)
        self.settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        self.settings_shortcut.activated.connect(
            lambda: self._open_settings() if main_window_key_filter_enabled() else None
        )
        self.open_shortcut = QShortcut(QKeySequence.StandardKey.Open, self)
        self.open_shortcut.activated.connect(
            lambda: self._choose_folder() if main_window_key_filter_enabled() else None
        )
        self.setWindowTitle(text("app_title"))
        self.setMinimumSize(1000, 650)
        self.resize(1100, 760)
        stylesheet = Path(__file__).parents[1] / "resources" / "dark.qss"
        if stylesheet.exists():
            self.setStyleSheet(stylesheet.read_text(encoding="utf-8"))
        self._set_open_state(False)
        if runtime.settings.reopen_last_folder and runtime.settings.last_folder:
            QTimer.singleShot(
                0, lambda: self._open_folder(Path(runtime.settings.last_folder or ""))
            )

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top = QHBoxLayout()
        self.profile_label = QLabel(text("empty"))
        self.profile_label.setMinimumWidth(160)
        self.profile_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top.addWidget(self.profile_label, 1)
        self.open_button = QPushButton(text("open_folder"))
        self.open_button.clicked.connect(self._choose_folder)
        top.addWidget(self.open_button)
        self.sort_button = QPushButton(text("sort_ascending"))
        self.sort_button.clicked.connect(self._toggle_sort)
        top.addWidget(self.sort_button)
        self.refresh_button = QPushButton(text("refresh"))
        self.refresh_button.clicked.connect(lambda: self._run_file(self.runtime.service.refresh))
        top.addWidget(self.refresh_button)
        self.reconcile_button = QPushButton(text("reconcile"))
        self.reconcile_button.clicked.connect(
            lambda: self._run_file(self.runtime.service.reconcile)
        )
        top.addWidget(self.reconcile_button)
        self.settings_button = QPushButton(text("settings"))
        self.settings_button.clicked.connect(self._open_settings)
        top.addWidget(self.settings_button)
        self.help_button = QPushButton(text("help"))
        self.help_button.clicked.connect(self._show_help)
        top.addWidget(self.help_button)
        layout.addLayout(top)

        self.image_label = QLabel(text("empty"))
        self.image_label.setObjectName("panel")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setAccessibleName(text("image_accessible"))
        self.image_label.setMinimumSize(320, 240)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.image_label, 1)

        info = QHBoxLayout()
        self.filename_label = QLabel(text("filename"))
        self.filename_label.setMinimumWidth(120)
        self.filename_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        info.addWidget(self.filename_label, 1)
        self.star_label = QLabel("★")
        self.star_label.setAccessibleName(text("selected_accessible"))
        self.star_label.hide()
        info.addWidget(self.star_label)
        self.selected_label = QLabel(text("selected_count", count=0))
        info.addWidget(self.selected_label)
        self.progress_text = QLabel(text("progress", current=0, total=0))
        info.addWidget(self.progress_text)
        self.progress = QProgressBar()
        self.progress.setAccessibleName(text("progress_accessible"))
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setMaximumWidth(180)
        info.addWidget(self.progress)
        layout.addLayout(info)

        self.slot_panel = QFrame()
        self.slot_panel.setObjectName("panel")
        self.slot_layout = QGridLayout(self.slot_panel)
        self.slot_layout.setContentsMargins(8, 8, 8, 8)
        self.slot_layout.setHorizontalSpacing(8)
        self.slot_layout.setVerticalSpacing(6)
        layout.addWidget(self.slot_panel)
        self.busy_label = QLabel(text("busy"))
        self.busy_label.setObjectName("busyLabel")
        self.busy_label.hide()
        layout.addWidget(self.busy_label)
        self.setCentralWidget(root)
        self.profile_label.setAccessibleName(text("current_profile"))
        self.open_button.setAccessibleName(text("open_folder"))
        self.sort_button.setAccessibleName(text("sort_ascending"))
        self.refresh_button.setAccessibleName(text("refresh"))
        self.reconcile_button.setAccessibleName(text("reconcile"))
        self.settings_button.setAccessibleName(text("settings"))
        self.help_button.setAccessibleName(text("help"))
        self.filename_label.setAccessibleName(text("filename"))
        self.selected_label.setAccessibleName(text("selected_count", count=0))
        self.progress_text.setAccessibleName(text("progress", current=0, total=0))

    def _set_open_state(self, opened: bool) -> None:
        self.sort_button.setEnabled(opened)
        self.refresh_button.setEnabled(opened)
        self.reconcile_button.setEnabled(opened and self.runtime.register_available)

    def _load_qt_translation(self, language: str) -> None:
        application = QApplication.instance()
        if application is None:
            return
        translator = getattr(self, "_qt_translator", None)
        if translator is not None:
            application.removeTranslator(translator)
        self._qt_translator = None
        if language == "en":
            return
        directories = [Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))]
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root is not None:
            directories.extend(
                (
                    Path(bundle_root) / "PySide6" / "Qt" / "translations",
                    Path(bundle_root) / "translations",
                )
            )
        directories.append(
            Path(QCoreApplication.applicationDirPath()) / "PySide6" / "Qt" / "translations"
        )
        for directory in directories:
            translator = QTranslator(self)
            if translator.load(f"qtbase_{language}", str(directory)):
                application.installTranslator(translator)
                self._qt_translator = translator
                return

    def _retranslate(self) -> None:
        self.setWindowTitle(text("app_title"))
        self.open_button.setText(text("open_folder"))
        self.sort_button.setText(
            text(
                "sort_descending"
                if self.view and self.view.snapshot.descending
                else "sort_ascending"
            )
        )
        self.refresh_button.setText(text("refresh"))
        self.reconcile_button.setText(text("reconcile"))
        self.settings_button.setText(text("settings"))
        self.help_button.setText(text("help"))
        self.busy_label.setText(text("busy"))
        self.profile_label.setAccessibleName(text("current_profile"))
        self.open_button.setAccessibleName(text("open_folder"))
        self.sort_button.setAccessibleName(self.sort_button.text())
        self.refresh_button.setAccessibleName(text("refresh"))
        self.reconcile_button.setAccessibleName(text("reconcile"))
        self.settings_button.setAccessibleName(text("settings"))
        self.help_button.setAccessibleName(text("help"))
        self.star_label.setAccessibleName(text("selected_accessible"))
        self.image_label.setAccessibleName(text("image_accessible"))
        self.filename_label.setAccessibleName(text("filename"))
        self.selected_label.setAccessibleName(text("selected_count", count=0))
        self.progress_text.setAccessibleName(text("progress", current=0, total=0))
        self.progress.setAccessibleName(text("progress_accessible"))
        if self.view is not None:
            self._apply_view(self.view)
        else:
            self.profile_label.setText(text("empty"))
            self.profile_label.setToolTip("")
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText(text("empty"))
            self.filename_label.setText(text("filename"))
            self.filename_label.setToolTip("")
            self.selected_label.setText(text("selected_count", count=0))
            self.progress_text.setText(text("progress", current=0, total=0))
            self.progress.setValue(0)
            self.star_label.hide()

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, text("open_dialog_title"))
        if folder:
            self._open_folder(Path(folder))

    def _open_folder(self, path: Path) -> None:
        self._run_file(lambda: self.runtime.service.open_folder(path))

    def _show_help(self) -> None:
        HelpDialog(self.view, self).exec()

    def _open_settings(self) -> None:
        if self._pending_operations or self._slot_operation_pending:
            self.statusBar().showMessage(text("settings_busy"), 2500)
            return
        if self.runtime.register_available:
            self._run_file(self.runtime.service.profile_catalog, self._show_settings)
        else:
            self._show_settings((), None)

    def _show_settings(self, profiles: tuple[ProfileSummary, ...], error: Exception | None) -> None:
        if error is not None:
            self._show_error(error)
            return
        current_profile = (
            self.view.snapshot.profile
            if self.runtime.register_available and self.view is not None
            else None
        )
        dialog: SettingsDialog

        def save_preferences(
            reopen: bool,
            direction: str,
            target: str,
            typed_slots: tuple[Slot, ...],
            learned_labels: tuple[tuple[str, str], ...],
        ) -> None:
            def save() -> tuple[SessionView | None, Settings, Exception | None]:
                try:
                    template_slots = dialog.slot_editors["template"].slots()
                    profile_slots = (
                        dialog.slot_editors["profile"].slots()
                        if "profile" in dialog.slot_editors
                        else None
                    )
                    all_labels = dict(learned_labels)
                    for editor in dialog.slot_editors.values():
                        all_labels.update(editor.labels)
                    view = self.runtime.service.save_settings_and_profile_slots(
                        reopen_last_folder=reopen,
                        sort_direction=direction,
                        language=str(dialog.language_combo.currentData()),
                        sound_enabled=dialog.sound_checkbox.isChecked(),
                        global_slot_template=template_slots,
                        profile_slots=profile_slots,
                        learned_key_labels=tuple(sorted(all_labels.items())),
                    )
                    return view, self.runtime.service.settings, None
                except Exception as error:
                    return None, self.runtime.service.settings, error

            def saved(
                value: tuple[SessionView | None, Settings, Exception | None],
                _error: Exception | None,
            ) -> None:
                view, _settings, error = value
                if error is not None:
                    dialog.set_message(
                        text("partial_settings_save_failed")
                        if isinstance(error, PartialSettingsSaveError)
                        else text("settings_save_failed")
                    )
                    self._show_error(error)
                    return
                set_language(self.runtime.service.settings.language)
                self._load_qt_translation(self.runtime.service.settings.language)
                self._retranslate()
                if view is not None:
                    self._apply_view(view)
                dialog.accept()
                self.statusBar().showMessage(text("settings_saved"), 2500)

            self._run_file(save, saved)

        def profile_action(action: str, profile_id: str | None) -> None:
            def update() -> tuple[
                tuple[ProfileSummary, ...] | None, SessionView | None, Exception | None
            ]:
                try:
                    service = self.runtime.service
                    if action == "save_profile_as_template":
                        service.save_profile_as_template()
                    elif action == "reset_global_template":
                        service.reset_global_template()
                    elif action == "reset_current_profile":
                        service.reset_profile_to_template()
                    elif action == "assign_orphan" and profile_id is not None:
                        service.reassign_orphan(profile_id)
                    elif action == "delete_profile" and profile_id is not None:
                        service.delete_profile(profile_id)
                    return service.profile_catalog(), service.current_view(), None
                except Exception as error:
                    return None, None, error

            def updated(
                value: tuple[
                    tuple[ProfileSummary, ...] | None, SessionView | None, Exception | None
                ],
                _error: Exception | None,
            ) -> None:
                updated_profiles, view, error = value
                if error is not None:
                    dialog.set_message(text("profile_action_failed"))
                    self._show_error(error)
                    return
                if view is not None:
                    self._apply_view(view)
                if updated_profiles is not None:
                    dialog.refresh_profiles(updated_profiles)
                dialog.set_message(text("profile_action_done"))
                self.statusBar().showMessage(text("profile_action_done"), 3000)

            self._run_file(update, updated)

        dialog = SettingsDialog(
            self.runtime.service.settings,
            current_profile,
            profiles,
            self.runtime.log_directory,
            read_only=not self.runtime.settings_writable,
            on_save=save_preferences,
            on_profile_action=profile_action,
            parent=self,
        )
        dialog.exec()

    def _toggle_sort(self) -> None:
        if self.view is None:
            return
        descending = not self.view.snapshot.descending
        self._run_file(lambda: self.runtime.service.set_sort_direction(descending))

    def _run_file(
        self,
        function: Callable[[], _Result],
        callback: Callable[[_Result, Exception | None], None] | None = None,
    ) -> None:
        if self._closing:
            return
        self._pending_operations += 1
        self.busy_label.hide()
        self._close_busy_timer.start()

        def finished(result: object, error: Exception | None) -> None:
            self._pending_operations = max(0, self._pending_operations - 1)
            if self._pending_operations == 0:
                self._close_busy_timer.stop()
                self.busy_label.hide()
            if self._closing:
                return
            if error is not None:
                self._show_error(error)
                if self._slot_operation_pending:
                    self._finish_slot_action()
                return
            if isinstance(result, SessionView):
                self._apply_view(result)
            if callback is not None:
                callback(cast(_Result, result), error)

        self.workers.file_operations.submit(cast(Callable[[], object], function), finished)

    def _apply_view(self, view: SessionView) -> None:
        self.view = view
        snapshot = view.snapshot
        self._set_open_state(True)
        self.profile_label.setText(Path(snapshot.source_path).name or snapshot.source_path)
        self.profile_label.setToolTip(text("source_folder", path=snapshot.source_path))
        self.sort_button.setText(
            text("sort_descending" if snapshot.descending else "sort_ascending")
        )
        self.sort_button.setEnabled(self.runtime.settings_writable)
        current_name = snapshot.current_name
        if current_name is None:
            self.filename_label.setText(text("filename"))
            self.filename_label.setToolTip("")
            self.selected_label.setText(text("selected_count", count=view.selected_image_count))
            self.progress_text.setText(text("progress", current=0, total=snapshot.image_count))
            self.progress.setRange(0, 0)
            self.star_label.hide()
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText(text("empty_folder"))
        else:
            metrics = QFontMetrics(self.filename_label.font())
            display_name = metrics.elidedText(
                current_name, Qt.TextElideMode.ElideMiddle, max(80, self.filename_label.width())
            )
            self.filename_label.setText(display_name)
            self.filename_label.setToolTip(current_name)
            self.selected_label.setText(text("selected_count", count=view.selected_image_count))
            self.progress_text.setText(
                text("progress", current=snapshot.image_index, total=snapshot.image_count)
            )
            self.progress.setRange(0, max(1, snapshot.image_count))
            self.progress.setValue(snapshot.image_index)
            self.star_label.setVisible(SlotState.SELECTED in view.slot_states)
            self._request_neighborhood(view)
        if snapshot.recovery_pending or snapshot.checking:
            self.statusBar().showMessage(text("checking"))
        elif snapshot.boundary_reached:
            cue = (
                "boundary"
                if self._last_direction is NavigationDirection.NEXT
                else "previous_boundary"
            )
            self.statusBar().showMessage(text(cue), 1800)
        if view.warning is not None:
            self.statusBar().showMessage(text(view.warning), 5000)
        self.selected_label.setAccessibleName(self.selected_label.text())
        self.progress_text.setAccessibleName(self.progress_text.text())
        self._render_slots(view)
        self._schedule_slot_status(view)

    def _schedule_slot_status(self, view: SessionView) -> None:
        self._slot_status_requested = view
        if not self._slot_status_in_flight:
            QTimer.singleShot(0, self._dispatch_slot_status)

    def _dispatch_slot_status(self) -> None:
        if self._closing or self._slot_status_in_flight or self._slot_status_requested is None:
            return
        view, self._slot_status_requested = self._slot_status_requested, None
        if self.view is None or view.generation != self.view.generation:
            return
        self._slot_status_in_flight = True

        def load() -> tuple[SlotStatusResult | None, str | None]:
            try:
                return (
                    self.runtime.service.slot_status(view.snapshot.current_name, view.generation),
                    None,
                )
            except Exception:
                return None, "slot_status_failed"

        self._run_file(load, self._slot_status_finished)

    def _slot_status_finished(
        self, value: tuple[SlotStatusResult | None, str | None], _error: Exception | None
    ) -> None:
        self._slot_status_in_flight = False
        result, warning = value
        view = self.view
        if (
            result is not None
            and view is not None
            and result.generation == view.generation
            and result.image_name == view.snapshot.current_name
            and len(result.slot_states) == len(view.snapshot.profile.slots)
        ):
            self.view = SessionView(
                view.snapshot,
                result.slot_states,
                result.selected_image_count,
                view.settings,
                view.generation,
                result.warning,
            )
            self.selected_label.setText(text("selected_count", count=result.selected_image_count))
            self.star_label.setVisible(SlotState.SELECTED in result.slot_states)
            self._render_slots(self.view)
            warning = result.warning
        if warning is not None:
            self.statusBar().showMessage(text(warning), 5000)
        if self._slot_status_requested is not None:
            QTimer.singleShot(0, self._dispatch_slot_status)

    def _render_slots(self, view: SessionView) -> None:
        while self.slot_layout.count():
            item = self.slot_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        snapshot = view.snapshot
        labels = dict(view.settings.learned_key_labels)
        for index, slot in enumerate(snapshot.profile.slots):
            container = QFrame()
            row = QHBoxLayout(container)
            row.setContentsMargins(4, 2, 4, 2)
            stripe = QFrame()
            stripe.setObjectName("slotStripe")
            stripe.setFixedWidth(6)
            stripe.setStyleSheet(f"background-color: {slot.color};")
            row.addWidget(stripe)
            key_label = displayed_key_label(slot.key_position, labels) or "?"
            key_widget = QLabel(key_label)
            key_widget.setObjectName("keyLabel")
            key_widget.setMinimumWidth(24)
            row.addWidget(key_widget)
            name_widget = _ElidingLabel(slot.destination_name or "—")
            name_widget.setObjectName("slotName")
            name_widget.setMinimumWidth(0)
            row.addWidget(name_widget, 1)
            state = view.slot_states[index]
            symbol, label_key = _STATE_PRESENTATION[state]
            state_text = text(label_key)
            state_widget = QLabel(f"{symbol} {state_text}")
            state_widget.setObjectName("slotState")
            state_widget.setAccessibleName(
                text(
                    "slot_accessible",
                    key=key_label,
                    name=slot.destination_name or text("no_name"),
                    state=state_text,
                )
            )
            row.addWidget(state_widget)
            columns = 6
            self.slot_layout.addWidget(container, index // columns, index % columns)
        slot_actions_enabled = self.runtime.register_available and not self._slot_operation_pending
        self.slot_panel.setEnabled(slot_actions_enabled)

    def _request_neighborhood(self, view: SessionView) -> None:
        snapshot = view.snapshot
        current_name = snapshot.current_name
        if current_name is None:
            self.cache.clear()
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText(text("empty_folder"))
            return
        ordered = sort_names(snapshot.scan.images, descending=snapshot.descending)
        try:
            index = ordered.index(current_name)
        except ValueError:
            self.image_label.setText(text("decode_missing"))
            return
        names = ordered[max(0, index - 2) : index + 3]
        paths = tuple(Path(snapshot.source_path) / name for name in names)
        generation = self.cache.begin_generation(paths)
        current_path = Path(snapshot.source_path) / current_name
        cached = self.cache.get(current_path)
        if cached is not None:
            self._show_decoded(cached)
        else:
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText(text("busy"))
        decoder = self.runtime.decoder
        max_width, max_height = self._decode_bounds()
        for path in paths:
            if self.cache.get(path) is not None:
                continue

            def decode(path: Path = path) -> DecodedImage:
                return decoder.decode(path, max_width, max_height)

            self.workers.image_decoding.submit(
                decode,
                lambda result, error, path=path, generation=generation: self._decode_finished(
                    path, generation, result, error
                ),
            )

    def _decode_bounds(self) -> tuple[int, int]:
        screens = QApplication.screens()
        if not screens:
            return screen_decode_bounds(
                max(1, self.image_label.width()),
                max(1, self.image_label.height()),
                max(1.0, self.devicePixelRatioF()),
            )
        width = max(screen.geometry().width() for screen in screens)
        height = max(screen.geometry().height() for screen in screens)
        ratio = max(screen.devicePixelRatio() for screen in screens)
        return screen_decode_bounds(width, height, ratio)

    def _decode_finished(
        self, path: Path, generation: int, result: object, error: Exception | None
    ) -> None:
        if self._closing or generation != self.cache.generation:
            return
        current = self.view.snapshot.current_name if self.view is not None else None
        current_path = (
            Path(self.view.snapshot.source_path) / current
            if self.view is not None and current is not None
            else None
        )
        if error is not None:
            if path == current_path:
                self.image_label.setPixmap(QPixmap())
                self.image_label.setText(_decode_message(error))
            return
        if isinstance(result, DecodedImage):
            self.cache.put(path, generation, result)
            if path == current_path:
                self._show_decoded(result)

    def _show_decoded(self, image: DecodedImage) -> None:
        pixel_format = (
            QImage.Format.Format_RGBA8888 if image.has_alpha else QImage.Format.Format_RGB888
        )
        channels = 4 if image.has_alpha else 3
        qimage = QImage(
            image.data,
            image.width,
            image.height,
            image.width * channels,
            pixel_format,
        ).copy()
        pixmap = QPixmap.fromImage(qimage)
        factor = min(
            1.0,
            self.image_label.width() / max(1, image.width),
            self.image_label.height() / max(1, image.height),
        )
        scaled = pixmap.scaled(
            max(1, round(image.width * factor)),
            max(1, round(image.height * factor)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setText("")
        self.image_label.setPixmap(scaled)

    def _slot_pressed(self, slot_index: int, image_name: str) -> None:
        if self._slot_operation_pending:
            self.statusBar().showMessage(text("busy_slot"), 1200)
            return
        if not self.runtime.register_available:
            return
        self._slot_operation_pending = True
        self._run_file(
            lambda: self.runtime.service.plan_slot(image_name, slot_index),
            lambda result, _: self._handle_plan(result, image_name, slot_index),
        )

    def _handle_plan(self, plan: TogglePlan, image_name: str, slot_index: int) -> None:
        if plan.status is UseCaseStatus.NAME_REQUIRED:
            name = self._ask_destination_name(slot_index)
            if name is None:
                self._finish_slot_action()
                return
            self._run_file(
                lambda: self.runtime.service.name_slot_and_plan(image_name, slot_index, name),
                lambda result, _: self._handle_plan(result, image_name, slot_index),
            )
            return
        if plan.status is UseCaseStatus.MODIFIED_CONFIRMATION_REQUIRED:
            self._ask_modified_confirmation(plan)
            return
        if plan.status not in {UseCaseStatus.OK, UseCaseStatus.CONFLICT}:
            self._show_error(RuntimeError(plan.detail or plan.status.value))
            self._finish_slot_action()
            return
        self._run_execute(plan, confirmed_modified=False)

    def _run_execute(self, plan: TogglePlan, *, confirmed_modified: bool) -> None:
        self._run_file(
            lambda: self.runtime.service.execute_plan(plan, confirmed_modified=confirmed_modified),
            lambda result, _: self._handle_toggle_result(result, plan),
        )

    def _handle_toggle_result(
        self, value: tuple[ToggleResult, SessionView], plan: TogglePlan
    ) -> None:
        result, view = value
        self._apply_view(view)
        if result.status is UseCaseStatus.MODIFIED_CONFIRMATION_REQUIRED:
            self._ask_modified_confirmation(plan, names=result.conflict_names)
            return
        if result.status is UseCaseStatus.OK:
            slot = view.snapshot.profile.slots[plan.slot_index]
            key = (
                displayed_key_label(slot.key_position, dict(view.settings.learned_key_labels))
                or "?"
            )
            was_added = result.action is not None and result.action.value == "toggle_on"
            key_name = "added" if was_added else "removed"
            if was_added and view.settings.sound_enabled:
                self.sound_player.play_added()
            self.statusBar().showMessage(
                text(key_name, key=key, name=slot.destination_name or ""), 2200
            )
        elif result.status is UseCaseStatus.BUSY:
            self.statusBar().showMessage(text("busy_slot"), 1200)
        else:
            details = ", ".join(result.conflict_names) or result.error_reason or result.status.value
            title_key = (
                "conflict_title" if result.status is UseCaseStatus.CONFLICT else "error_title"
            )
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(text(title_key))
            box.setText(text(title_key))
            informative = (
                text("conflict_message", names=details)
                if result.status is UseCaseStatus.CONFLICT
                else text("operation_error", details=details.replace("_", " "))
            )
            box.setInformativeText(informative)
            box.setDetailedText(details)
            box.exec()
        self._finish_slot_action()

    def _ask_modified_confirmation(self, plan: TogglePlan, *, names: tuple[str, ...] = ()) -> None:
        affected = names or tuple(
            target.classification.actual_name or target.source_name
            for target in plan.targets
            if target.classification.file_class.value == "modified"
        )
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(text("modified_title"))
        box.setText(text("modified_prompt"))
        box.setDetailedText("\n".join(affected))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() == QMessageBox.StandardButton.Yes:
            self._run_execute(plan, confirmed_modified=True)
        else:
            self._finish_slot_action()

    def _ask_destination_name(self, slot_index: int) -> str | None:
        dialog = QDialog(self)
        dialog.setWindowTitle(text("name_dialog_title"))
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(text("name_prompt")))
        editor = QLineEdit(dialog)
        layout.addWidget(editor)
        validation = QLabel(dialog)
        validation.setObjectName("validationMessage")
        layout.addWidget(validation)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        layout.addWidget(buttons)
        accept_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if accept_button is None:
            raise RuntimeError("name dialog did not create its confirmation button")
        accept_button.setEnabled(False)

        def validate(value: str) -> None:
            issue = validate_folder_name(value)
            snapshot = self.view.snapshot if self.view is not None else None
            duplicate = snapshot is not None and any(
                index != slot_index
                and slot.destination_name is not None
                and comparison_key(slot.destination_name) == comparison_key(value)
                for index, slot in enumerate(snapshot.profile.slots)
            )
            message = (
                text(_NAME_ERROR_TEXT[issue])
                if issue is not None
                else text("name_duplicate")
                if duplicate
                else ""
            )
            validation.setText(message)
            accept_button.setEnabled(issue is None and not duplicate)

        editor.textChanged.connect(validate)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return editor.text()
        return None

    def _finish_slot_action(self) -> None:
        self._slot_operation_pending = False
        if self.view is not None:
            self._render_slots(self.view)

    def _show_error(self, error: Exception) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(text("error_title"))
        box.setText(text("error_title"))
        reason = getattr(error, "reason", None)
        path = getattr(error, "path", None)
        if isinstance(error, ImageDecodeError):
            summary = text(_DECODE_TEXT.get(error.reason, "decode_generic"))
        elif isinstance(path, Path):
            reason_text = str(reason or error).replace("_", " ")
            summary = f"{reason_text}: {path.name}"
        else:
            summary = str(error).replace("_", " ")
        box.setInformativeText(summary)
        box.setDetailedText(str(error))
        box.exec()

    def _queue_navigation(self, direction: NavigationDirection) -> None:
        self._last_direction = direction
        if self._navigation_in_flight:
            self._queued_navigation.append(direction)
            return
        self._navigation_in_flight = True
        self._run_file(
            lambda: self.runtime.service.navigate(direction),
            self._navigation_finished,
        )

    def _navigation_finished(self, _view: SessionView, _error: Exception | None) -> None:
        self._navigation_in_flight = False
        if not self._queued_navigation or self._closing:
            return
        directions = tuple(self._queued_navigation)
        self._queued_navigation.clear()
        self._navigation_in_flight = True
        self._run_file(
            lambda: self.runtime.service.navigate_batch(directions),
            self._navigation_finished,
        )

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not main_window_key_filter_enabled():
            super().keyPressEvent(event)
            return
        if (
            event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Left)
            and not event.modifiers()
            and self.view is not None
        ):
            direction = (
                NavigationDirection.NEXT
                if event.key() == Qt.Key.Key_Right
                else NavigationDirection.PREVIOUS
            )
            self._queue_navigation(direction)
            event.accept()
            return
        if event.key() == Qt.Key.Key_F1 and not event.modifiers():
            self._show_help()
            event.accept()
            return
        if event.key() == Qt.Key.Key_F5 and not event.modifiers() and self.view is not None:
            self._run_file(self.runtime.service.refresh)
            event.accept()
            return
        event_data = keyboard_event_data(event)
        if event_data.position is not None and event_data.triggers_slot:
            if self.runtime.settings_writable and self.view is not None:
                labels = dict(self.view.settings.learned_key_labels)
                updated_labels = update_learned_key_labels(
                    labels, event_data.position, event_data.text, modifier_active=False
                )
                if dict(updated_labels) != labels:
                    self._run_file(
                        lambda: self.runtime.service.learn_key(
                            event_data.position or "",
                            event_data.text,
                            modifier_active=False,
                        ),
                        lambda view, _error: self._apply_view(view) if view is not None else None,
                    )
            if self.view is not None:
                for index, slot in enumerate(self.view.snapshot.profile.slots):
                    if slot.key_position == event_data.position:
                        current_name = self.view.snapshot.current_name
                        if current_name is not None:
                            self._slot_pressed(index, current_name)
                        break
            event.accept()
            return
        super().keyPressEvent(event)

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.view is not None and self.view.snapshot.current_name is not None:
            snapshot = self.view.snapshot
            path = Path(snapshot.source_path) / (snapshot.current_name or "")
            image = self.cache.get(path)
            if image is not None:
                self._show_decoded(image)

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        if self._ready_to_close:
            self.cache.clear()
            self.workers.shutdown()
            event.accept()
            return
        event.ignore()
        if self._shutdown_started:
            return
        self._closing = True
        self._shutdown_started = True
        self.busy_label.setText(text("busy"))
        self.busy_label.show()
        self.workers.file_operations.submit(self.runtime.shutdown, self._shutdown_complete)

    def _shutdown_complete(self, _result: object, error: Exception | None) -> None:
        if error is not None:
            self.runtime.logger.log(LogLevel.ERROR, LogEvent.ERROR, "shutdown failed")
        self._ready_to_close = True
        self.workers.shutdown()
        self.close()


def _decode_message(error: Exception) -> str:
    if isinstance(error, ImageDecodeError):
        return text(_DECODE_TEXT.get(error.reason, "decode_generic"))
    return text("decode_generic")
