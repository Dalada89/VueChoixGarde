"""Contextual keyboard and slot help dialog."""

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from vuechoixgarde.app.service import SessionView
from vuechoixgarde.core.keys import displayed_key_label
from vuechoixgarde.ui.texts import text


class HelpDialog(QDialog):
    """Show fixed shortcuts and the current, persisted slot configuration."""

    def __init__(self, view: SessionView | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(text("help"))
        self.setModal(True)
        layout = QVBoxLayout(self)
        fixed = QLabel(text("help_shortcuts"), self)
        fixed.setWordWrap(True)
        layout.addWidget(fixed)
        if view is not None:
            labels = dict(view.settings.learned_key_labels)
            for slot in view.snapshot.profile.slots:
                key = displayed_key_label(slot.key_position, labels) or "?"
                name = slot.destination_name or text("no_name")
                entry = QLabel(f"{key} — {name}", self)
                entry.setAccessibleName(text("help_slot_accessible", key=key, name=name))
                layout.addWidget(entry)
        details = QLabel(text("help_behavior"), self)
        details.setWordWrap(True)
        layout.addWidget(details)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        self.resize(520, max(280, self.sizeHint().height()))
