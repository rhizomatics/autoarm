"""Tests that all translation files match the structure of strings.json."""

import json
from pathlib import Path
from typing import Any, cast

import pytest

STRINGS_PATH = Path("custom_components/autoarm/strings.json")
TRANSLATIONS_DIR = Path("custom_components/autoarm/translations")
EXPECTED_LOCALES = {"en", "de", "fr", "it", "ja", "es", "hi", "nl", "pl", "pt", "zh-Hans"}


def _key_paths(obj: object, prefix: str = "") -> set[str]:
    """Recursively collect all key paths in a nested dict."""
    if not isinstance(obj, dict):
        return {prefix}
    paths: set[str] = set()
    for key, value in obj.items():
        child = f"{prefix}.{key}" if prefix else key
        paths |= _key_paths(value, child)
    return paths


def _leaf_values(obj: object, prefix: str = "") -> dict[str, Any]:
    """Recursively collect {key path: leaf value} for a nested dict."""
    if not isinstance(obj, dict):
        return {prefix: obj}
    values: dict[str, Any] = {}
    for key, value in obj.items():
        child = f"{prefix}.{key}" if prefix else key
        values.update(_leaf_values(value, child))
    return values


# Key paths where identical text across locales is expected, either because the term is a
# brand name (never translated) or a genuine cognate in that specific language.
GLOBAL_UNTRANSLATED_PATHS = {"title"}
LOCALE_COGNATE_PATHS: dict[str, set[str]] = {
    "fr": {"options.step.init.sections.notify_options.name"},
}


@pytest.fixture(scope="module")
def strings() -> dict[str, str]:
    return cast("dict[str,str]", json.loads(STRINGS_PATH.read_text()))


@pytest.fixture(scope="module")
def translations() -> dict[str, dict[str, Any]]:
    result = {}
    for path in TRANSLATIONS_DIR.glob("*.json"):
        result[path.stem] = json.loads(path.read_text())
    return result


def test_all_locales_present(translations: dict[str, dict[str, Any]]) -> None:
    """All expected locale files exist."""
    assert translations.keys() >= EXPECTED_LOCALES, f"Missing locales: {EXPECTED_LOCALES - translations.keys()}"


@pytest.mark.parametrize("locale", sorted(EXPECTED_LOCALES))
def test_translation_keys_match_strings(locale: str, strings: dict[str, Any], translations: dict[str, dict[str, Any]]) -> None:
    """Every translation has exactly the same keys as strings.json."""
    assert locale in translations, f"Translation file {locale}.json not found"
    strings_paths = _key_paths(strings)
    locale_paths = _key_paths(translations[locale])

    missing = strings_paths - locale_paths
    extra = locale_paths - strings_paths

    assert not missing, f"{locale}.json is missing keys: {sorted(missing)}"
    assert not extra, f"{locale}.json has extra keys not in strings.json: {sorted(extra)}"


@pytest.mark.parametrize("locale", sorted(EXPECTED_LOCALES - {"en"}))
def test_translations_differ_from_english(locale: str, translations: dict[str, dict[str, Any]]) -> None:
    """Non-English translations should actually be translated, not copied from English."""
    en_values = _leaf_values(translations["en"])
    locale_values = _leaf_values(translations[locale])
    allowed = GLOBAL_UNTRANSLATED_PATHS | LOCALE_COGNATE_PATHS.get(locale, set())

    untranslated = {
        path: value
        for path, value in locale_values.items()
        if path not in allowed and path in en_values and value == en_values[path]
    }

    assert not untranslated, f"{locale}.json has untranslated text copied from English: {untranslated}"
