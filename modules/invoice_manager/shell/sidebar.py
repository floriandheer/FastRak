"""Left sidebar — vertical nav between sections."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, Optional

from invoice_manager.theme import PALETTE, FONTS


class Sidebar(tk.Frame):
    """Vertical nav with bigger type. Each item is a row Frame holding
    an icon column (emoji), a label column, and an optional right-aligned
    badge for counts (e.g. unprocessed orders).
    """

    WIDTH = 230

    def __init__(self, parent: tk.Widget,
                 on_select: Callable[[str], None]):
        C = PALETTE
        super().__init__(parent, bg=C["sidebar_bg"], width=self.WIDTH)
        self.pack_propagate(False)
        self._on_select = on_select
        self._items: Dict[str, tk.Frame] = {}
        self._icons: Dict[str, tk.Label] = {}
        self._labels: Dict[str, tk.Label] = {}
        self._badges: Dict[str, tk.Label] = {}
        self._active: Optional[str] = None

        # Brand block
        brand = tk.Frame(self, bg=C["sidebar_bg"])
        brand.pack(fill="x", padx=18, pady=(22, 24))
        tk.Label(
            brand, text="Invoices", font=FONTS["sidebar_brand"],
            fg=C["text"], bg=C["sidebar_bg"], anchor="w",
        ).pack(fill="x")
        tk.Label(
            brand, text="Business operations", font=FONTS["sidebar_sub"],
            fg=C["text_dim"], bg=C["sidebar_bg"], anchor="w",
        ).pack(fill="x", pady=(2, 0))

    # ----- nav items ---------------------------------------------------

    def add(self, key: str, label: str, icon: str = "") -> None:
        C = PALETTE
        row = tk.Frame(self, bg=C["sidebar_bg"], cursor="hand2")
        row.pack(fill="x", padx=8, pady=1)

        icon_lbl = tk.Label(
            row, text=icon or "  ", font=FONTS["sidebar_icon"],
            fg=C["text"], bg=C["sidebar_bg"], width=2,
        )
        icon_lbl.pack(side="left", padx=(10, 4), pady=8)

        text_lbl = tk.Label(
            row, text=label, font=FONTS["sidebar_nav"],
            fg=C["text"], bg=C["sidebar_bg"], anchor="w",
        )
        text_lbl.pack(side="left", fill="x", expand=True, pady=8)

        # Badge — hidden until set_badge() puts a count on it
        badge = tk.Label(
            row, text="", font=FONTS["small"],
            fg="white", bg=C["sidebar_bg"],   # will be repainted when shown
            padx=8, pady=1,
        )
        # Don't pack yet — packed dynamically in set_badge()

        # Bind everything on the row so any click works
        for w in (row, icon_lbl, text_lbl, badge):
            w.bind("<Button-1>", lambda _e, k=key: self._on_select(k))
            w.bind("<Enter>",    lambda _e, k=key: self._hover(k, True))
            w.bind("<Leave>",    lambda _e, k=key: self._hover(k, False))

        self._items[key] = row
        self._icons[key] = icon_lbl
        self._labels[key] = text_lbl
        self._badges[key] = badge

    def set_badge(self, key: str, count: Optional[int]) -> None:
        """Show or hide the badge for a nav item.

        count of 0 / None → hide
        count > 0          → show as a pill on the right
        """
        if key not in self._badges:
            return
        badge = self._badges[key]
        if not count:
            badge.pack_forget()
            return
        text = str(count) if count < 100 else "99+"
        badge.configure(text=text)
        # Match the row's current background so the badge sits cleanly
        bg = self._items[key].cget("bg")
        # Use the danger color for the pill itself so it always pops
        badge.configure(bg=PALETTE["danger_bg"])
        if not badge.winfo_ismapped():
            badge.pack(side="right", padx=(0, 12), pady=6)

    def add_separator(self) -> None:
        sep = tk.Frame(self, bg=PALETTE["card_border"], height=1)
        sep.pack(fill="x", padx=20, pady=12)

    def set_active(self, key: str) -> None:
        if self._active == key:
            return
        if self._active and self._active in self._items:
            self._paint(self._active, active=False)
        if key in self._items:
            self._paint(key, active=True)
        self._active = key

    # ----- internals ---------------------------------------------------

    def _paint(self, key: str, *, active: bool) -> None:
        C = PALETTE
        bg = C["sidebar_active"] if active else C["sidebar_bg"]
        fg = "#ffffff" if active else C["text"]
        font = FONTS["sidebar_nav_bold"] if active else FONTS["sidebar_nav"]
        self._items[key].configure(bg=bg)
        self._icons[key].configure(bg=bg, fg=fg)
        self._labels[key].configure(bg=bg, fg=fg, font=font)
        # badge keeps its own bg (the danger pill), don't recolor

    def _hover(self, key: str, on: bool) -> None:
        if key == self._active:
            return
        C = PALETTE
        bg = C["sidebar_hover"] if on else C["sidebar_bg"]
        self._items[key].configure(bg=bg)
        self._icons[key].configure(bg=bg)
        self._labels[key].configure(bg=bg)
