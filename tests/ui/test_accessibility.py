from pathlib import Path

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QLabel, QPushButton
from pytestqt.qtbot import QtBot

from vuechoixgarde.app.results import SessionSnapshot, SlotState
from vuechoixgarde.app.service import SessionView
from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.keys import ALLOWED_SLOT_CODES
from vuechoixgarde.core.slots import DEFAULT_SLOTS, Slot
from vuechoixgarde.ports.models import ProfileRecord, SourceScan
from vuechoixgarde.ui.main_window import MainWindow
from vuechoixgarde.ui.texts import set_language, text


def test_main_controls_have_accessible_names(qtbot: QtBot, tmp_path: Path) -> None:
    window = MainWindow(create_runtime(tmp_path / "app-data"))
    qtbot.addWidget(window)

    for button in window.findChildren(QPushButton):
        assert button.accessibleName(), button.text()
    for widget in (window.profile_label, window.image_label, window.filename_label):
        assert widget.accessibleName()
    assert window.progress.accessibleName()

    window.close()


@pytest.mark.parametrize("language", ("de", "en", "fr"))
def test_twelve_slots_fit_at_minimum_window_size(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, language: str
) -> None:
    set_language(language)
    runtime = create_runtime(tmp_path / "app-data")
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    positions = sorted(ALLOWED_SLOT_CODES)[:12]
    slots = tuple(
        Slot(
            positions[index],
            f"An exceptionally long destination folder name {index + 1} "
            "remains available in the tooltip",
            DEFAULT_SLOTS[index % 4].color,
        )
        for index in range(12)
    )
    profile = ProfileRecord("test", "/source", "/source", "now", "now", slots)
    snapshot = SessionSnapshot(
        source_path="/source",
        folder_identity="/source",
        profile=profile,
        scan=SourceScan((), (), ()),
        current_name=None,
        image_index=0,
        image_count=0,
        descending=False,
        boundary_reached=False,
        checking=False,
        register_available=True,
        reconciled=(),
    )
    view = SessionView(snapshot, (SlotState.READY,) * 12, 0, runtime.settings)
    monkeypatch.setattr(window, "_schedule_slot_status", lambda _view: None)
    window._apply_view(view)
    for code in ("de", "en", "fr"):
        set_language(code)
        window._retranslate()
        assert window.open_button.text() == text("open_folder")
        assert window.open_button.accessibleName() == text("open_folder")
        assert window.profile_label.accessibleName() == text("current_profile")
        assert window.selected_label.accessibleName() == window.selected_label.text()
        assert window.progress_text.accessibleName() == window.progress_text.text()

    window.resize(window.minimumSize())
    window.show()
    qtbot.waitExposed(window)
    qtbot.wait(20)

    tiles = window.slot_panel.findChildren(QLabel)
    names = window.slot_panel.findChildren(QLabel, "slotName")
    states = window.slot_panel.findChildren(QLabel, "slotState")
    assert window.slot_layout.count() == 12
    assert len(tiles) >= 36
    assert len(names) == len(states) == 12
    for slot, label in zip(slots, names, strict=True):
        assert "…" in label.text()
        assert label.toolTip() == slot.destination_name
        assert label.accessibleName() == slot.destination_name
    assert all(state.accessibleName() for state in states)
    panel_rect = QRect(window.slot_panel.rect())
    for index in range(window.slot_layout.count()):
        item = window.slot_layout.itemAt(index)
        assert item is not None
        tile = item.widget()
        assert tile is not None
        assert panel_rect.contains(tile.geometry())

    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)
