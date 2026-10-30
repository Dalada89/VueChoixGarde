import hashlib
from pathlib import Path
from time import monotonic
from uuid import uuid4

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from vuechoixgarde.bootstrap import create_runtime
from vuechoixgarde.core.slots import Slot, SlotMode
from vuechoixgarde.core.temp_names import temp_file_name
from vuechoixgarde.ports.models import CopyRecord, OperationFileRecord
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


def test_replacing_images_after_move_selects_the_new_current_row(qtbot: QtBot) -> None:
    panel = ImageListPanel()
    qtbot.addWidget(panel)
    panel.set_images(["first.png", "moved.png", "last.png"])
    panel.set_current_index(1)

    panel.set_images(["first.png", "last.png"])
    panel.set_current_index(1)

    selected = panel.image_model.index(1, 0)
    previous = panel.image_model.index(0, 0)
    assert panel.image_model.rowCount() == 2
    assert panel.image_model.data(selected) == "last.png"
    assert panel.image_model.data(selected, Qt.ItemDataRole.BackgroundRole) is not None
    assert panel.image_model.data(previous, Qt.ItemDataRole.BackgroundRole) is None


def test_move_slot_with_registered_copy_does_not_show_a_star(qtbot: QtBot, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    image_name = "photo.png"
    image_data = b"verified-image-data"
    source_file = source / image_name
    source_file.write_bytes(image_data)
    slots = (
        Slot("KeyW", "Copied", "#aabbcc", SlotMode.COPY),
        Slot("KeyR", "Moved", "#FF7B7B", SlotMode.MOVE),
    )
    runtime = create_runtime(tmp_path / "app-data")
    runtime.service.save_preferences(
        reopen_last_folder=False,
        sort_direction="asc",
        global_slot_template=slots,
    )

    try:
        view = runtime.service.open_folder(source)
        profile_id = view.snapshot.profile.id
        store = runtime.service.state_store
        digest = hashlib.sha256(image_data).hexdigest()
        mtime_ns = source_file.stat().st_mtime_ns
        for slot in slots:
            assert slot.destination_name is not None
            destination = source / slot.destination_name
            destination.mkdir()
            (destination / image_name).write_bytes(image_data)
            operation_id = uuid4().hex
            store.start_operation(
                operation_id,
                profile_id,
                slot.destination_name,
                (
                    OperationFileRecord(
                        0,
                        temp_file_name(operation_id, 0),
                        image_name,
                        len(image_data),
                        digest,
                    ),
                ),
            )
            store.complete_operation(
                operation_id,
                (
                    CopyRecord(
                        profile_id,
                        str(source),
                        image_name,
                        str(destination),
                        image_name,
                        len(image_data),
                        digest,
                        mtime_ns,
                        "2025-01-02T03:04:05.123456Z",
                    ),
                ),
            )
        runtime.service.reconcile()
        panel = ImageListPanel()
        qtbot.addWidget(panel)
        panel.set_images([image_name], runtime.service.image_slot_info())
        index = panel.image_model.index(0, 0)

        assert panel.image_model.data(index, ImageListModel.SlotColorsRole) == ("#aabbcc",)
        assert panel.image_model.data(index, Qt.ItemDataRole.ToolTipRole) == "Copied"
    finally:
        runtime.shutdown()


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
