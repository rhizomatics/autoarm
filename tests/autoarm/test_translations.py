"""Tests that all translation files match the structure of strings.json."""

import json
from pathlib import Path

import pytest

STRINGS_PATH = Path("custom_components/autoarm/strings.json")
TRANSLATIONS_DIR = Path("custom_components/autoarm/translations")
EXPECTED_LOCALES = {"en", "de", "fr", "it", "ja"}


def _key_paths(obj: object, prefix: str = "") -> set[str]:
    """Recursively collect all key paths in a nested dict."""
    if not isinstance(obj, dict):
        return {prefix}
    paths: set[str] = set()
    for key, value in obj.items():
        child = f"{prefix}.{key}" if prefix else key
        paths |= _key_paths(value, child)
    return paths


@pytest.fixture(scope="module")
def strings() -> dict:
    return json.loads(STRINGS_PATH.read_text())


@pytest.fixture(scope="module")
def translations() -> dict[str, dict]:
    result = {}
    for path in TRANSLATIONS_DIR.glob("*.json"):
        result[path.stem] = json.loads(path.read_text())
    return result


def test_all_locales_present(translations: dict[str, dict]) -> None:
    """All expected locale files exist."""
    assert translations.keys() >= EXPECTED_LOCALES, f"Missing locales: {EXPECTED_LOCALES - translations.keys()}"


@pytest.mark.parametrize("locale", sorted(EXPECTED_LOCALES))
def test_translation_keys_match_strings(locale: str, strings: dict, translations: dict[str, dict]) -> None:
    """Every translation has exactly the same keys as strings.json."""
    assert locale in translations, f"Translation file {locale}.json not found"
    strings_paths = _key_paths(strings)
    locale_paths = _key_paths(translations[locale])

    missing = strings_paths - locale_paths
    extra = locale_paths - strings_paths

    assert not missing, f"{locale}.json is missing keys: {sorted(missing)}"
    assert not extra, f"{locale}.json has extra keys not in strings.json: {sorted(extra)}"
