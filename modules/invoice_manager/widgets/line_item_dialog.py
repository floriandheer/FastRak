"""Modal dialog for adding / editing one LineItem."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Optional

from invoice_manager.core.models import LineItem, to_cents
from invoice_manager.theme import PALETTE, FONTS
from invoice_manager.widgets.buttons import primary_button, secondary_button
from invoice_manager.widgets.inputs import make_entry


class LineItemDialog:
    """Modal returning a LineItem in self.result, or None if cancelled."""

    def __init__(self, parent: tk.Widget,
                 existing: Optional[LineItem] = None,
                 default_vat_rate: float = 21.0,
                 title: str = "Line item"):
        C = PALETTE
        self.result: Optional[LineItem] = None

        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.configure(bg=C["bg"])
        self.win.transient(parent)
        self.win.resizable(False, False)
        self.win.grab_set()

        frame = tk.Frame(self.win, bg=C["bg"], padx=18, pady=16)
        frame.pack()

        self.desc = tk.StringVar(value=existing.description if existing else "")
        self.qty = tk.StringVar(value=str(existing.quantity) if existing else "1")
        self.unit = tk.StringVar(
            value=(f"{existing.unit_price_cents / 100:.2f}".replace(".", ",")
                   if existing else "0,00")
        )
        self.vat_rate = tk.StringVar(
            value=str(existing.vat_rate if existing else default_vat_rate)
        )

        for i, (label, var, width) in enumerate([
            ("Description",                 self.desc,     42),
            ("Quantity",                    self.qty,      10),
            ("Unit price (excl. VAT, EUR)", self.unit,     14),
            ("VAT rate (%)",                self.vat_rate,  8),
        ]):
            tk.Label(frame, text=label, fg=C["label_fg"], bg=C["bg"],
                     font=FONTS["label"]
                     ).grid(row=i, column=0, sticky="w", pady=5, padx=(0, 12))
            make_entry(frame, var, width=width).grid(
                row=i, column=1, sticky="we", pady=5)

        btns = tk.Frame(frame, bg=C["bg"])
        btns.grid(row=99, column=0, columnspan=2, pady=(14, 0), sticky="e")
        secondary_button(btns, "Cancel", self._cancel).pack(side="right", padx=(8, 0))
        primary_button(btns, "OK", self._ok).pack(side="right")
        self.win.bind("<Return>", lambda _e: self._ok())
        self.win.bind("<Escape>", lambda _e: self._cancel())

        self.win.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.win.winfo_width(), self.win.winfo_height()
        self.win.geometry(f"+{px - w // 2}+{py - h // 2}")
        parent.wait_window(self.win)

    def _ok(self):
        desc = self.desc.get().strip()
        if not desc:
            messagebox.showerror("Line item", "Description is required.", parent=self.win)
            return
        try:
            qty = float(self.qty.get().replace(",", "."))
            unit_cents = to_cents(self.unit.get())
            vat_rate = float(self.vat_rate.get().replace(",", "."))
        except ValueError as e:
            messagebox.showerror("Line item", f"Invalid number: {e}", parent=self.win)
            return
        self.result = LineItem(
            description=desc, quantity=qty,
            unit_price_cents=unit_cents, vat_rate=vat_rate,
        )
        self.win.destroy()

    def _cancel(self):
        self.win.destroy()
