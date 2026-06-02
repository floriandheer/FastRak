"""Bottom status bar — section-contextual summary text + transient flash."""

from __future__ import annotations

import tkinter as tk

from invoices_app.theme import PALETTE, FONTS


class StatusBar(tk.Frame):
    HEIGHT = 28

    def __init__(self, parent: tk.Widget):
        C = PALETTE
        super().__init__(parent, bg=C["card_border"], height=self.HEIGHT)
        self.pack_propagate(False)
        self.text = tk.StringVar(value="")
        tk.Label(
            self, textvariable=self.text, anchor="w",
            font=FONTS["small"], fg=C["text"], bg=C["card_border"],
            padx=14,
        ).pack(side="left", fill="y", expand=True)
        self._flash_after = None

    def set(self, text: str) -> None:
        if self._flash_after is not None:
            self.after_cancel(self._flash_after)
            self._flash_after = None
        self.text.set(text)

    def flash(self, text: str, restore_to: str = "", ms: int = 2000) -> None:
        self.text.set(text)
        if self._flash_after is not None:
            self.after_cancel(self._flash_after)
        self._flash_after = self.after(ms, lambda: self.set(restore_to))
