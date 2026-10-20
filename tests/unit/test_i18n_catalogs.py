import ast
import json
import re
from pathlib import Path

from vuechoixgarde.ui import texts

_CATALOG_DIR = Path(texts.__file__).parents[1] / "i18n"
_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
_UNTRANSLATED_ALLOWLIST = {"app_title", "ok", "profile_status", "slots_tab"}


def _catalog(code: str) -> dict[str, str]:
    return json.loads((_CATALOG_DIR / f"{code}.json").read_text(encoding="utf-8"))


def test_catalogs_have_same_keys_and_named_placeholders() -> None:
    catalogs = {code: _catalog(code) for code in ("de", "en", "fr")}
    keys = set(catalogs["en"])
    assert set(catalogs["de"]) == keys
    assert set(catalogs["fr"]) == keys
    for key in keys:
        expected = set(_PLACEHOLDER.findall(catalogs["en"][key]))
        assert set(_PLACEHOLDER.findall(catalogs["de"][key])) == expected, key
        assert set(_PLACEHOLDER.findall(catalogs["fr"][key])) == expected, key


def test_translations_do_not_repeat_english_without_allowlisting() -> None:
    english = _catalog("en")
    for language in ("de", "fr"):
        untranslated = {
            key
            for key, value in _catalog(language).items()
            if value == english[key] and key not in _UNTRANSLATED_ALLOWLIST
        }
        assert untranslated == set()


def test_help_shortcuts_use_real_line_breaks() -> None:
    for language in ("de", "en", "fr"):
        shortcuts = _catalog(language)["help_shortcuts"]
        assert "\n" in shortcuts
        assert "\\n" not in shortcuts


def test_literal_text_calls_resolve_in_english_catalog() -> None:
    source = Path(texts.__file__).parents[1] / "ui"
    referenced: set[str] = set()
    for path in source.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "text"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                referenced.add(node.args[0].value)
    assert referenced <= set(_catalog("en"))
