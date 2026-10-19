from dataclasses import replace
from pathlib import Path
from threading import Event

from PIL import Image
from pytestqt.qtbot import QtBot

from vuechoixgarde.app.results import SlotState
from vuechoixgarde.app.service import SessionView, SlotStatusResult
from vuechoixgarde.app.session import FolderSession
from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.ui.main_window import MainWindow


def test_image_is_displayed_while_slot_status_lookup_is_blocked(
    qtbot: QtBot, tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (24, 16), "purple").save(source / "one.png")
    runtime = create_runtime(tmp_path / "application-data")
    started = Event()
    release = Event()
    original = FolderSession.slot_states

    def delayed(self: FolderSession, image_name: str | None = None) -> tuple[SlotState, ...]:
        started.set()
        release.wait(5)
        return original(self, image_name)

    monkeypatch.setattr(FolderSession, "slot_states", delayed)
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()
    window._open_folder(source)

    try:
        qtbot.waitUntil(lambda: window.view is not None, timeout=5000)
        qtbot.waitUntil(started.is_set, timeout=5000)
        qtbot.waitUntil(
            lambda: (
                window.image_label.pixmap() is not None and not window.image_label.pixmap().isNull()
            ),
            timeout=5000,
        )
        assert not release.is_set()
    finally:
        release.set()
    qtbot.waitUntil(
        lambda: window.view is not None and SlotState.CHECKING not in window.view.slot_states,
        timeout=5000,
    )
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)


def test_stale_slot_status_result_is_discarded(qtbot: QtBot, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (8, 8), "red").save(source / "one.png")
    runtime = create_runtime(tmp_path / "application-data")
    view = runtime.service.open_folder(source)
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.view = view
    newer_view: SessionView = replace(view, generation=view.generation + 1)
    window.view = newer_view
    stale = SlotStatusResult(
        view.snapshot.current_name,
        view.generation,
        (SlotState.SELECTED,) * len(view.snapshot.profile.slots),
        9,
    )

    window._slot_status_finished((stale, None), None)

    assert window.view is newer_view
    assert window.view.slot_states == view.slot_states
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)
