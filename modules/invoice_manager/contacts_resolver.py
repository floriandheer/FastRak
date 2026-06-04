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

from typing import Dict, Optional


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
