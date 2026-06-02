"""Toggleable filter chip (Q1/Q2/Q3/Q4, company keys, status).

Renders as a flat rounded-ish label; click toggles its bound BooleanVar
(or a single-select group via ChipGroup).
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, List, Optional

from invoices_app.theme import PALETTE, FONTS


class Chip(tk.Label):
    """A clickable label that flips between active / inactive states."""

    def __init__(self, parent: tk.Widget, text: str,
                 on_click: Optional[Callable[[bool], None]] = None,
                 active: bool = False, count: Optional[int] = None):
        self._active = active
        self._base_text = text
        self._count = count
        self._on_click = on_click
        super().__init__(
            parent, text=self._formatted(),
            font=FONTS["body_bold"], padx=12, pady=4, cursor="hand2",
        )
        self._apply_state()
        self.bind("<Button-1>", self._handle_click)
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))

    def _formatted(self) -> str:
        if self._count is None:
            return self._base_text
        return f"{self._base_text} ({self._count})"

    def set_count(self, count: Optional[int]) -> None:
        self._count = count
        self.configure(text=self._formatted())

    def set_active(self, active: bool) -> None:
        if self._active == active:
            return
        self._active = active
        self._apply_state()

    def is_active(self) -> bool:
        return self._active

    def _apply_state(self) -> None:
        C = PALETTE
        if self._active:
            self.configure(bg=C["chip_active_bg"], fg="#ffffff")
        else:
            self.configure(bg=C["chip_bg"], fg=C["chip_text"])

    def _hover(self, on: bool) -> None:
        C = PALETTE
        if self._active:
            return
        self.configure(bg=C["bg_hover"] if on else C["chip_bg"])

    def _handle_click(self, _event) -> None:
        if self._on_click:
            self._on_click(not self._active)
        else:
            self.set_active(not self._active)


class ChipGroup(tk.Frame):
    """A row of mutually-exclusive chips (radio-like)."""

    def __init__(self, parent: tk.Widget,
                 on_change: Optional[Callable[[str], None]] = None):
        super().__init__(parent, bg=PALETTE["bg"])
        self._chips: Dict[str, Chip] = {}
        self._selected: Optional[str] = None
        self._on_change = on_change

    def add(self, key: str, label: str, count: Optional[int] = None,
            selected: bool = False) -> Chip:
        chip = Chip(self, label, on_click=lambda _: self.select(key),
                    active=selected, count=count)
        chip.pack(side="left", padx=(0, 6))
        self._chips[key] = chip
        if selected:
            self._selected = key
        return chip

    def select(self, key: str) -> None:
        if key not in self._chips:
            return
        if self._selected == key:
            return
        if self._selected and self._selected in self._chips:
            self._chips[self._selected].set_active(False)
        self._chips[key].set_active(True)
        self._selected = key
        if self._on_change:
            self._on_change(key)

    def selected(self) -> Optional[str]:
        return self._selected

    def set_counts(self, counts: Dict[str, Optional[int]]) -> None:
        for k, n in counts.items():
            if k in self._chips:
                self._chips[k].set_count(n)
