"""Card frame — a titled, slightly-elevated container.

Tkinter has no real shadow/elevation primitives, so a card is rendered
as a Frame with a darker inner area + a thin 1px border simulated by
nesting two frames.
"""

from __future__ import annotations

import tkinter as tk
from typing import Optional

from invoices_app.theme import PALETTE, FONTS


class Card(tk.Frame):
    """Outer container that gives sections a uniform look."""

    def __init__(self, parent: tk.Widget, title: Optional[str] = None,
                 padding: int = 14):
        C = PALETTE
        super().__init__(parent, bg=C["card_border"], padx=1, pady=1)
        self.inner = tk.Frame(self, bg=C["card_bg"], padx=padding, pady=padding)
        self.inner.pack(fill="both", expand=True)
        if title:
            tk.Label(
                self.inner, text=title, font=FONTS["h3"],
                fg=C["text"], bg=C["card_bg"], anchor="w",
            ).pack(fill="x", pady=(0, 8))

    @property
    def body(self) -> tk.Frame:
        return self.inner
