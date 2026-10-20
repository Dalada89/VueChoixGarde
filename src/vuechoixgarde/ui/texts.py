"""Localized UI message lookup backed by packaged JSON catalogs."""

import json
import logging
from functools import lru_cache
from importlib.resources import files

_LANGUAGE = "en"
_LOGGED_MISSING: set[tuple[str, str]] = set()


@lru_cache(maxsize=3)
def _catalog(code: str) -> dict[str, str]:
    resource = files("vuechoixgarde.i18n").joinpath(f"{code}.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def set_language(code: str) -> None:
    """Select the active UI catalog."""
    global _LANGUAGE
    if code not in {"de", "en", "fr"}:
        raise ValueError("language must be de, en, or fr")
    _LANGUAGE = code


def text(message_key: str, **values: object) -> str:
    """Look up a localized message, falling back to English for missing translations."""
    catalog = _catalog(_LANGUAGE)
    message = catalog.get(message_key)
    if message is None and _LANGUAGE != "en":
        missing = (_LANGUAGE, message_key)
        if missing not in _LOGGED_MISSING:
            logging.getLogger(__name__).warning(
                "missing translation for %s in %s", message_key, _LANGUAGE
            )
            _LOGGED_MISSING.add(missing)
        message = _catalog("en").get(message_key)
    if message is None:
        raise KeyError(f"unknown UI message key: {message_key}")
    return message.format(**values) if values else message
