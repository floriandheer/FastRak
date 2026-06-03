"""Themed Treeview factory + shared row tags.

Every section that shows a treeview goes through here so dot colors,
selection styling, and scrollbar behaviour stay consistent.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Iterable

from invoice_manager.theme import PALETTE, FONTS


_ITALIC_BODY = (FONTS["body"][0], FONTS["body"][1], "italic")
_ITALIC_SMALL = (FONTS["small"][0], FONTS["small"][1], "italic")

# Tag → (foreground, font tweak)
ROW_TAGS = {
    "category":         (PALETTE["accent"],        FONTS["body_bold"]),
    "filed":            (PALETTE["dot_filed"],     None),
    "needs_dl":         (PALETTE["dot_partial"],   None),
    "missing":          (PALETTE["dot_missing"],   None),
    "voided":           (PALETTE["dot_neutral"],   None),
    "draft":            (PALETTE["dot_partial"],   None),
    "in_registry":      (PALETTE["dot_filed"],     None),
    "new":              (PALETTE["text"],          None),
    "duplicate":        (PALETTE["dot_partial"],   None),
    "no_import":        (PALETTE["dot_neutral"],   None),
    "dim":              (PALETTE["text_dim"],      None),
    # Legacy rows — italic + dim to read clearly as "from old archive"
    "legacy":           (PALETTE["text_dim"],      _ITALIC_BODY),
    "legacy_separator": (PALETTE["text_dim"],      _ITALIC_SMALL),
}


def make_treeview(parent: tk.Widget, columns: Iterable[str],
                  height: int = 18, show: str = "tree headings") -> ttk.Treeview:
    """Build a Treeview inside its own frame with a vertical scrollbar."""
    C = PALETTE
    wrap = tk.Frame(parent, bg=C["bg"])
    wrap.pack(fill="both", expand=True)

    tree = ttk.Treeview(
        wrap, columns=tuple(columns), show=show, height=height,
        style="InvApp.Treeview",
    )
    sb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview,
                       style="InvApp.Vertical.TScrollbar")
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    for tag, (fg, font) in ROW_TAGS.items():
        if font:
            tree.tag_configure(tag, foreground=fg, font=font)
        else:
            tree.tag_configure(tag, foreground=fg)

    return tree
