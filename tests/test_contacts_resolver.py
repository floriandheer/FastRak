"""Tests for invoice_manager.contacts_resolver.

The resolver is a pure lookup against in-memory contact rows once
the cache is built, so we exercise it by stubbing the loader directly.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "modules"))

from invoice_manager import contacts_resolver  # noqa: E402


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch):
    """Each test gets a fresh cache + stubbed loader."""
    contacts_resolver.invalidate_cache()
    yield
    contacts_resolver.invalidate_cache()


def _stub_contacts(monkeypatch, rows):
    monkeypatch.setattr(contacts_resolver, "_build_cache",
                        lambda: _to_cache(rows))


def _to_cache(rows):
    cache = {}
    for r in rows:
        abbr = (r.get("abbreviation") or "").strip()
        if not abbr:
            continue
        display = (r.get("display_name") or "").strip()
        if display:
            cache.setdefault(display.lower(), abbr)
        cache.setdefault(abbr.lower(), abbr)
    return cache


def test_resolves_by_display_name(monkeypatch):
    _stub_contacts(monkeypatch, [
        {"display_name": "Mike Morraye", "abbreviation": "MikeMorraye"},
    ])
    assert contacts_resolver.resolve_client_folder_name("Mike Morraye") == "MikeMorraye"


def test_resolves_case_insensitive(monkeypatch):
    _stub_contacts(monkeypatch, [
        {"display_name": "Mike Morraye", "abbreviation": "MikeMorraye"},
    ])
    assert contacts_resolver.resolve_client_folder_name("mike morraye") == "MikeMorraye"
    assert contacts_resolver.resolve_client_folder_name("MIKE MORRAYE") == "MikeMorraye"


def test_resolves_by_abbreviation(monkeypatch):
    _stub_contacts(monkeypatch, [
        {"display_name": "Mike Morraye", "abbreviation": "MikeMorraye"},
    ])
    assert contacts_resolver.resolve_client_folder_name("MikeMorraye") == "MikeMorraye"
    assert contacts_resolver.resolve_client_folder_name("mikemorraye") == "MikeMorraye"


def test_unknown_value_passes_through(monkeypatch):
    _stub_contacts(monkeypatch, [
        {"display_name": "Mike Morraye", "abbreviation": "MikeMorraye"},
    ])
    # Unknown clients (no contact yet) keep whatever the user typed,
    # stripped — so legacy/ad-hoc projects still work.
    assert contacts_resolver.resolve_client_folder_name("Unknown Co") == "Unknown Co"
    assert contacts_resolver.resolve_client_folder_name("  spaced  ") == "spaced"


def test_empty_input_passes_through(monkeypatch):
    _stub_contacts(monkeypatch, [])
    assert contacts_resolver.resolve_client_folder_name("") == ""
    assert contacts_resolver.resolve_client_folder_name("   ") == "   "


def test_contact_without_abbreviation_ignored(monkeypatch):
    _stub_contacts(monkeypatch, [
        {"display_name": "No Folder", "abbreviation": ""},
        {"display_name": "Real Client", "abbreviation": "RC"},
    ])
    # Lookup for the no-abbreviation contact returns the typed value
    # unchanged — there's no folder identifier to substitute.
    assert contacts_resolver.resolve_client_folder_name("No Folder") == "No Folder"
    assert contacts_resolver.resolve_client_folder_name("Real Client") == "RC"


def test_blank_name_still_resolves_by_abbreviation(monkeypatch):
    """A bulk-imported contact has display_name='' until the user fills
    it in. Until then, lookup by the abbreviation must still work."""
    _stub_contacts(monkeypatch, [
        {"display_name": "", "abbreviation": "MikeMorraye"},
    ])
    assert contacts_resolver.resolve_client_folder_name("MikeMorraye") == "MikeMorraye"


def test_cache_is_invalidatable(monkeypatch):
    _stub_contacts(monkeypatch, [
        {"display_name": "A", "abbreviation": "Aa"},
    ])
    assert contacts_resolver.resolve_client_folder_name("A") == "Aa"

    # Swap the contact set and invalidate — next lookup picks up new data.
    _stub_contacts(monkeypatch, [
        {"display_name": "B", "abbreviation": "Bb"},
    ])
    contacts_resolver.invalidate_cache()
    assert contacts_resolver.resolve_client_folder_name("A") == "A"   # stale
    assert contacts_resolver.resolve_client_folder_name("B") == "Bb"  # new
