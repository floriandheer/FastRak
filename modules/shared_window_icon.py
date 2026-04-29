"""
Per-category window icon helper for module subprocesses.

Each ``PipelineScript_<Category>_*.py`` module calls ``apply_category_icon(root)``
right after creating its Tk root. The helper derives the category from the
calling script's filename prefix and applies ``assets/category_icons/<Category>.ico``
so the module's taskbar/title-bar icon matches its hub category colour.
"""

import os
import sys
from typing import Optional

_ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "category_icons",
)

_KNOWN_CATEGORIES = {
    "Visual", "RealTime", "Audio", "Physical",
    "Photo", "Web", "Business", "Global",
    "Bookkeeping",
}

# Filename-prefix categories that don't have their own .ico (fall back to a
# semantically-related category icon).
_CATEGORY_FALLBACK = {
    "Bookkeeping": "Business",
}


def _category_from_filename(path: str) -> Optional[str]:
    base = os.path.basename(path)
    name, _ = os.path.splitext(base)
    parts = name.split("_")
    if len(parts) >= 3 and parts[0] == "PipelineScript" and parts[1] in _KNOWN_CATEGORIES:
        return parts[1]
    return None


def category_icon_path(category: str) -> Optional[str]:
    resolved = _CATEGORY_FALLBACK.get(category, category)
    path = os.path.join(_ASSETS_DIR, f"{resolved}.ico")
    return path if os.path.exists(path) else None


def apply_category_icon(root, category: Optional[str] = None) -> Optional[str]:
    """Apply the category-coloured .ico to a Tk root window.

    Returns the icon path used, or None if nothing was applied. Silent on
    failure — module windows must keep working if assets are missing.
    """
    try:
        if category is None:
            caller = sys.argv[0] if sys.argv and sys.argv[0] else __file__
            category = _category_from_filename(caller)
        if not category:
            return None
        icon_path = category_icon_path(category)
        if not icon_path:
            return None
        root.iconbitmap(default=icon_path)
        return icon_path
    except Exception:
        return None
