"""Folder-safe name lookup against the contacts directory.

Used by callers outside the Invoice Manager (e.g. the project folder
creator) to translate a typed client name like "Mike Morraye" into the
abbreviation the user prefers for paths ("MikeMorraye"). Falls back to
the input unchanged if no contact matches, or if invoice_manager isn't
configured yet on this machine.

Lookups are case-insensitive and consider both ``display_name`` and
``abbreviation``, so typing either form resolves to the same folder
identifier.

Module-level cache: contacts are loaded once per process. If the user
adds contacts in the standalone Contacts window (a separate process),
this process won't see them until restart. Call ``invalidate_cache()``
to drop the cache if you do edit contacts within the same process.
"""

from __future__ import annotations

from typing import Dict, List, Optional


# Cache: lowercased name → abbreviation. None = not yet loaded; {} =
# loaded but registry unavailable, returns the input unchanged.
_CACHE: Optional[Dict[str, str]] = None


def resolve_client_folder_name(typed_value: str) -> str:
    """Return the folder-safe abbreviation for a typed client name.

    Match order:
      1. exact display_name (case-insensitive)
      2. exact abbreviation (case-insensitive)
    Returns ``typed_value.strip()`` unchanged if no contact matches.
    Empty input is returned as-is.
    """
    if not typed_value:
        return typed_value
    needle = typed_value.strip()
    if not needle:
        return typed_value
    cache = _ensure_cache()
    hit = cache.get(needle.lower())
    return hit if hit else needle


def curated_client_labels(category: Optional[str] = None,
                          exclude_personal: bool = False) -> Optional[List[str]]:
    """Display labels for the project-creation client autocomplete,
    sourced entirely from the Contacts directory rather than the
    project DB's raw (and inconsistent) folder-derived client list.

    Each contact contributes its human ``display_name`` — e.g. "Walking
    the Dog", "Tijs Joos" — so what you see while typing matches what you
    stored. The abbreviation ("WTD", "TJS") is applied later, at
    folder-creation time, by `resolve_client_folder_name`; you never need
    to type it. Contacts without a display name (e.g. freshly bulk-
    imported, not yet filled in) fall back to their abbreviation so they
    still show up.

    Optionally narrowed to contacts that opted into `category` via their
    "Show in" checkboxes — a contact with no categories checked matches
    every category (the default for contacts that predate this feature).

    Returns ``None`` if the registry isn't available — callers should
    treat that as "can't curate, fall back to the project DB" rather than
    "show nothing".
    """
    try:
        from invoice_manager.core.config import load_config
        from invoice_manager.core.registry import InvoiceRegistry
        config = load_config()
        registry = InvoiceRegistry(config.resolve_db_path())
        contacts = registry.list_contacts()
    except Exception:
        return None

    labels: set = set()
    for c in contacts:
        if category:
            cats = c.get("project_categories") or []
            if cats and category not in cats:
                continue
        label = (c.get("display_name") or "").strip() or (c.get("abbreviation") or "").strip()
        if not label:
            continue
        if exclude_personal and label.lower() == "personal":
            continue
        labels.add(label)
    return sorted(labels, key=str.lower)


def invalidate_cache() -> None:
    """Drop the in-process cache so the next lookup re-reads the table."""
    global _CACHE
    _CACHE = None


def _ensure_cache() -> Dict[str, str]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    _CACHE = _build_cache()
    return _CACHE


def _build_cache() -> Dict[str, str]:
    # Lazy imports so callers don't pay invoice_manager startup cost
    # unless they actually need contact resolution. Wrapped in a broad
    # try/except so a missing config or unreadable DB silently degrades
    # to "no abbreviation rewriting" rather than breaking project
    # creation.
    try:
        from invoice_manager.core.config import load_config
        from invoice_manager.core.registry import InvoiceRegistry
        config = load_config()
        registry = InvoiceRegistry(config.resolve_db_path())
        contacts = registry.list_contacts()
    except Exception:
        return {}

    cache: Dict[str, str] = {}
    for c in contacts:
        abbr = (c.get("abbreviation") or "").strip()
        if not abbr:
            continue
        display = (c.get("display_name") or "").strip()
        if display:
            cache.setdefault(display.lower(), abbr)
        cache.setdefault(abbr.lower(), abbr)
    return cache
