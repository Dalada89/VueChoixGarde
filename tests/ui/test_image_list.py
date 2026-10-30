from pathlib import Path
from time import monotonic

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.slots import Slot
from vuechoixgarde.ui.image_list import ImageListModel, ImageListPanel
from vuechoixgarde.ui.main_window import MainWindow


def test_image_list_model_handles_ten_thousand_rows_without_row_widgets(
    qtbot: QtBot,
) -> None:
    panel = ImageListPanel()
    qtbot.addWidget(panel)
    names = [f"image-{index:05}.png" for index in range(10_000)]
    slot_info = [()] * len(names)

    started_at = monotonic()
    panel.set_images(names, slot_info)
    elapsed = monotonic() - started_at

    assert panel.image_model.rowCount() == 10_000
    assert elapsed < 1.0
    assert len(panel.findChildren(QWidget)) < 20


def test_click_requests_the_selected_image_index(qtbot: QtBot) -> None:
    panel = ImageListPanel()
    qtbot.addWidget(panel)
    panel.resize(320, 160)
    panel.set_images(["first.png", "second.png"])
    panel.show()
    requested: list[int] = []
    panel.image_requested.connect(requested.append)

    index = panel.image_model.index(1, 0)
    qtbot.waitUntil(lambda: panel.view.visualRect(index).isValid())
    QTest.mouseClick(
        panel.view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=panel.view.visualRect(index).center(),
    )

    assert requested == [1]


def test_image_list_does_not_take_keyboard_focus(qtbot: QtBot) -> None:
    panel = ImageListPanel()
    qtbot.addWidget(panel)

    assert panel.view.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_slot_markers_are_limited_to_three_and_tooltip_keeps_slot_names(
    qtbot: QtBot,
) -> None:
    panel = ImageListPanel()
    qtbot.addWidget(panel)
    panel.set_images(
        ["four-slots.png", "two-slots.png"],
        [
            [
                ("#ff0000", "Red slot"),
                ("#00ff00", "Green slot"),
                ("#0000ff", "Blue slot"),
                ("#ffff00", "Yellow slot"),
            ],
            [("#ff0000", "Red slot"), ("#00ff00", "Green slot")],
        ],
    )
    four_slots = panel.image_model.index(0, 0)
    two_slots = panel.image_model.index(1, 0)

    assert panel.image_model.data(four_slots, ImageListModel.SlotColorsRole) == (
        "#ff0000",
        "#00ff00",
        "#0000ff",
    )
    assert panel.image_model.data(four_slots, ImageListModel.HasMoreSlotsRole) is True
    assert panel.image_model.data(four_slots, Qt.ItemDataRole.ToolTipRole) == (
        "Red slot, Green slot, Blue slot, Yellow slot"
    )
    assert panel.image_model.data(two_slots, ImageListModel.SlotColorsRole) == (
        "#ff0000",
        "#00ff00",
    )
    assert panel.image_model.data(two_slots, ImageListModel.HasMoreSlotsRole) is False


def test_slot_star_updates_after_toggle_on_and_off(qtbot: QtBot, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    image_name = "photo.png"
    Image.new("RGB", (8, 8), "blue").save(source / image_name)
    runtime = create_runtime(tmp_path / "app-data")
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=(Slot("KeyW", "Managed", "#aabbcc"),),
    )
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()

    window._open_folder(source)
    qtbot.waitUntil(lambda: window.view is not None, timeout=5000)
    qtbot.waitUntil(lambda: window.image_list.image_model.rowCount() == 1, timeout=5000)
    index = window.image_list.image_model.index(0, 0)

    window._slot_pressed(0, image_name)
    qtbot.waitUntil(
        lambda: (
            window.image_list.image_model.data(index, ImageListModel.SlotColorsRole) == ("#aabbcc",)
        ),
        timeout=5000,
    )
    window._slot_pressed(0, image_name)
    qtbot.waitUntil(
        lambda: window.image_list.image_model.data(index, ImageListModel.SlotColorsRole) == (),
        timeout=5000,
    )

    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)
