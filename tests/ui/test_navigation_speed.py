from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock
from time import monotonic, sleep

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from pytestqt.qtbot import QtBot

from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.ports.imaging import DecodedImage, ImageDecoder
from vuechoixgarde.ui.main_window import MainWindow


class SlowDecoder:
    def __init__(self, decoder: ImageDecoder) -> None:
        self.decoder = decoder
        self.lock = Lock()
        self.started: list[tuple[str, float]] = []

    def decode(self, path: Path, max_width: int, max_height: int) -> DecodedImage:
        with self.lock:
            self.started.append((path.name, monotonic()))
        sleep(0.2)
        return self.decoder.decode(path, max_width, max_height)


@dataclass
class NavigationHarness:
    window: MainWindow
    decoder: SlowDecoder
    status_lock: Lock
    status_calls: list[tuple[str | None, bool, float]]


@pytest.fixture
def slow_navigation(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[NavigationHarness]:
    source = tmp_path / "source"
    source.mkdir()
    for index in range(50):
        Image.new("RGB", (8, 8), (index, 0, 0)).save(source / f"image-{index:03}.png")

    original_runtime = create_runtime(tmp_path / "app-data")
    decoder = SlowDecoder(original_runtime.decoder)
    runtime = replace(original_runtime, decoder=decoder)
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    status_lock = Lock()
    status_calls: list[tuple[str | None, bool, float]] = []
    original_slot_status = runtime.service.slot_status

    def tracked_slot_status(image_name: str | None, generation: int):
        with status_lock:
            status_calls.append((image_name, window._navigation_in_flight, monotonic()))
        return original_slot_status(image_name, generation)

    monkeypatch.setattr(runtime.service, "slot_status", tracked_slot_status)
    window.show()
    window._open_folder(source)
    qtbot.waitUntil(lambda: window.view is not None, timeout=5000)
    qtbot.waitUntil(
        lambda: window.image_view.image is not None and not window.image_view.image.isNull(),
        timeout=5000,
    )
    qtbot.waitUntil(
        lambda: (
            not window._slot_status_in_flight
            and window._slot_status_requested is None
            and window.workers.image_decoding.active_count == 0
        ),
        timeout=5000,
    )
    with decoder.lock:
        decoder.started.clear()
    with status_lock:
        status_calls.clear()

    yield NavigationHarness(window, decoder, status_lock, status_calls)

    window.close()
    qtbot.waitUntil(lambda: runtime.service.session is None, timeout=5000)


def _press_right_thirty_times(window: MainWindow) -> float:
    for _ in range(30):
        QTest.keyClick(window.open_button, Qt.Key.Key_Right)
    return monotonic()


def test_rapid_navigation_decodes_only_final_image_within_one_second(
    slow_navigation: NavigationHarness, qtbot: QtBot
) -> None:
    window = slow_navigation.window
    last_key_at = _press_right_thirty_times(window)
    target_name = "image-030.png"

    def target_is_visible() -> bool:
        image = window.image_view.image
        return (
            window.filename_label.toolTip() == target_name
            and image is not None
            and not image.isNull()
        )

    qtbot.waitUntil(target_is_visible, timeout=1000)
    target_visible_at = monotonic()
    assert target_visible_at - last_key_at <= 1.0
    qtbot.waitUntil(
        lambda: (
            window.workers.image_decoding.active_count == 0 and not window._navigation_in_flight
        ),
        timeout=10000,
    )
    with slow_navigation.decoder.lock:
        started_before_target = sum(
            started_at <= target_visible_at for _name, started_at in slow_navigation.decoder.started
        )
    assert started_before_target <= 3


def test_slot_status_is_deferred_until_navigation_settles(
    slow_navigation: NavigationHarness, qtbot: QtBot
) -> None:
    window = slow_navigation.window
    last_key_at = _press_right_thirty_times(window)
    target_name = "image-030.png"
    qtbot.waitUntil(
        lambda: (
            window.view is not None
            and window.view.snapshot.current_name == target_name
            and not window._navigation_in_flight
        ),
        timeout=5000,
    )
    qtbot.waitUntil(lambda: bool(slow_navigation.status_calls), timeout=5000)
    qtbot.waitUntil(
        lambda: not window._slot_status_in_flight and window._slot_status_requested is None,
        timeout=5000,
    )
    with slow_navigation.status_lock:
        observed_status = tuple(slow_navigation.status_calls)

    assert len(observed_status) == 1
    assert observed_status[0][0] == target_name
    assert observed_status[0][1] is False
    assert observed_status[0][2] >= last_key_at + 0.15
