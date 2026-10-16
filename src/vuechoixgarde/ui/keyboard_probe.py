"""Run a lightweight manual keyboard inspection window (FR-081, FR-082)."""

import sys
from collections.abc import Mapping
from typing import override

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QListWidget, QVBoxLayout, QWidget

from vuechoixgarde.core.keys import displayed_key_label, update_learned_key_labels
from vuechoixgarde.ui.keyboard import keyboard_event_data

_DEFAULT_POSITIONS = ("KeyW", "KeyA", "KeyS", "KeyD")


class KeyboardProbeWindow(QWidget):
    """Display native Qt key data and in-memory labels for the four default slots (FR-081)."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VueChoixGarde Keyboard Probe")
        self.setMinimumSize(900, 520)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._learned_labels: Mapping[str, str] = {}
        self._slot_labels: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Press keys in this window. Labels are learned in memory only."))
        slots = QHBoxLayout()
        for position in _DEFAULT_POSITIONS:
            label = QLabel()
            label.setMinimumWidth(120)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("border: 1px solid #777; padding: 12px; font-size: 18px;")
            self._slot_labels[position] = label
            slots.addWidget(label)
        layout.addLayout(slots)
        self._events = QListWidget()
        layout.addWidget(self._events)
        self._refresh_slot_labels()

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Record every key press and learn eligible printable labels (FR-081/FR-082)."""
        data = keyboard_event_data(event)
        if data.triggers_slot and data.position is not None:
            self._learned_labels = update_learned_key_labels(
                self._learned_labels,
                data.position,
                data.text,
                modifier_active=data.modifier_active,
            )
            self._refresh_slot_labels()

        label = displayed_key_label(data.position, self._learned_labels) if data.position else None
        details = (
            f"Qt-Key={event.key()} | text={event.text()!r} | "
            f"nativeScanCode={event.nativeScanCode()} | "
            f"nativeVirtualKey={event.nativeVirtualKey()} | "
            f"nativeModifiers={event.nativeModifiers()} | "
            f"modifier active={data.modifier_active} | auto-repeat={data.auto_repeat} | "
            f"position={data.position or '—'} | current label={label or '—'}"
        )
        self._events.addItem(details)
        self._events.scrollToBottom()
        event.accept()

    def _refresh_slot_labels(self) -> None:
        """Refresh the four default-slot captions from the current in-memory labels (FR-081)."""
        for position, widget in self._slot_labels.items():
            label = displayed_key_label(position, self._learned_labels)
            widget.setText(f"{position}: {label or '—'}")


def main() -> int:
    """Launch the standalone keyboard probe (FR-081/FR-082)."""
    application = QApplication(sys.argv)
    window = KeyboardProbeWindow()
    window.show()
    window.setFocus()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
