from vuechoixgarde.ui.style import contrast_ratio
from vuechoixgarde.ui.texts import TEXTS, text


def test_ui_color_pairs_meet_body_text_contrast_target() -> None:
    assert contrast_ratio("#F2F2F2", "#2B2B2B") >= 4.5
    assert contrast_ratio("#F2F2F2", "#383838") >= 4.5
    assert contrast_ratio("#B0B0B0", "#2B2B2B") >= 4.5
    assert contrast_ratio("#F2D06B", "#2B2B2B") >= 4.5
    assert contrast_ratio("#FF8A80", "#2B2B2B") >= 4.5


def test_ui_text_source_uses_named_placeholders() -> None:
    assert text("progress", current=3, total=8) == "3 of 8"
    assert "{current}" in TEXTS["progress"]
    assert "{total}" in TEXTS["progress"]
