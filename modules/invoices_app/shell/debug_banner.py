"""Red banner shown above the top bar when a debug session is active."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from invoices_app.state import AppState
from invoices_app.theme import PALETTE, FONTS


class DebugBanner(tk.Frame):
    HEIGHT = 34

    def __init__(self, parent: tk.Widget, state: AppState,
                 on_exit_debug: Callable[[], None]):
        C = PALETTE
        super().__init__(parent, bg=C["danger_bg"], height=self.HEIGHT)
        self.pack_propagate(False)
        self.state = state

        self.text = tk.StringVar(value="")
        tk.Label(
            self, textvariable=self.text, font=FONTS["body_bold"],
            fg="white", bg=C["danger_bg"], anchor="w",
        ).pack(side="left", padx=16, pady=4)

        tk.Button(
            self, text="Exit debug mode", command=on_exit_debug,
            bg="white", fg=C["danger_bg"],
            activebackground="#fee2e2", activeforeground=C["danger_bg"],
            relief=tk.FLAT, font=FONTS["body_bold"],
            cursor="hand2", padx=10, pady=2,
        ).pack(side="right", padx=14, pady=4)

    def refresh(self) -> None:
        """Update visible text and own pack state from AppState."""
        ds = self.state.debug_session
        if ds.is_active():
            self.text.set(
                f"DEBUG MODE ACTIVE — started {ds.started_at or '?'} · "
                f"{len(ds.created_pdfs)} test PDF(s). Exit restores DB."
            )
        else:
            self.text.set("")
