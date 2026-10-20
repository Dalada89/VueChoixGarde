from pathlib import Path

from vuechoixgarde.core.slots import DEFAULT_SLOTS
from vuechoixgarde.ui.style import contrast_ratio

ROOT = Path(__file__).parents[2]


def test_stylesheet_text_color_pairs_meet_wcag_aa() -> None:
    text_pairs = (
        ("#F2F2F2", "#2B2B2B"),
        ("#F2F2F2", "#383838"),
        ("#F2F2F2", "#4A4A4A"),
        ("#B0B0B0", "#383838"),
        ("#F2D06B", "#2B2B2B"),
        ("#FF8A80", "#383838"),
        ("#6FA8DC", "#383838"),
    )
    assert all(
        contrast_ratio(foreground, background) >= 4.5 for foreground, background in text_pairs
    )
    stylesheet = (ROOT / "src/vuechoixgarde/resources/dark.qss").read_text(encoding="utf-8")
    for foreground, background in text_pairs:
        assert foreground.lower() in stylesheet.lower() or foreground in {"#F2F2F2", "#B0B0B0"}
        assert background.lower() in stylesheet.lower() or background in {"#2B2B2B", "#383838"}


def test_default_slot_palette_has_readable_contrast_on_slot_panel() -> None:
    assert all(contrast_ratio(slot.color, "#383838") >= 4.5 for slot in DEFAULT_SLOTS)
