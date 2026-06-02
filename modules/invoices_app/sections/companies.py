"""Companies — card grid showing each configured invoicing entity.

Replaces the old read-only text dump in InvoiceCreator with a scannable
two-column card layout.
"""

from __future__ import annotations

import tkinter as tk

from invoices_app.sections.base import Section
from invoices_app.theme import PALETTE, FONTS
from invoices_app.widgets.buttons import secondary_button
from invoices_app.widgets.card import Card


class CompaniesSection(Section):
    title = "Companies"
    sidebar_key = "companies"
    sidebar_icon = "🏢"

    COLUMNS = 2  # cards per row

    def build(self, root: tk.Frame) -> None:
        C = PALETTE
        root.configure(bg=C["bg"])
        wrap = tk.Frame(root, bg=C["bg"], padx=20, pady=14)
        wrap.pack(fill="both", expand=True)

        # Toolbar
        bar = tk.Frame(wrap, bg=C["bg"])
        bar.pack(fill="x")
        tk.Label(bar, text=f"{len(self.state.config.companies)} companies configured",
                 fg=C["text_dim"], bg=C["bg"], font=FONTS["small"]
                 ).pack(side="left")
        secondary_button(bar, "Open config.json",
                         lambda: self.state.resolve_pdf_open(self.state.config.source_path)
                         ).pack(side="right")

        # Card grid
        grid = tk.Frame(wrap, bg=C["bg"])
        grid.pack(fill="both", expand=True, pady=(12, 0))
        for i in range(self.COLUMNS):
            grid.columnconfigure(i, weight=1, uniform="co")

        for idx, co in enumerate(self.state.config.companies):
            r, c = divmod(idx, self.COLUMNS)
            card = Card(grid, title=f"{co.key} · {co.display_name}")
            card.grid(row=r, column=c, sticky="nsew",
                      padx=(0 if c == 0 else 6, 0 if c == self.COLUMNS - 1 else 6),
                      pady=(0 if r == 0 else 8, 0))
            self._fill_card(card.body, co)

    def _fill_card(self, parent: tk.Frame, co) -> None:
        C = PALETTE
        rows = [
            ("Legal name",   co.legal_name),
            ("VAT",          co.vat),
            ("Address",      co.address_block.replace("\n", " / ")),
            ("Email",        co.email),
            ("IBAN",         co.iban),
            ("Output prefix", co.output_prefix),
            ("Default VAT",  f"{co.default_vat_rate}%"),
            ("Template",     str(co.template_path or "(none — WooCommerce)")),
            ("WC binding",   "● yes" if co.wc_binding else "○ no"),
        ]
        for label, value in rows:
            row = tk.Frame(parent, bg=C["card_bg"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, fg=C["text_dim"], bg=C["card_bg"],
                     font=FONTS["small"], width=16, anchor="w").pack(side="left")
            tk.Label(row, text=value or "—", fg=C["text"], bg=C["card_bg"],
                     font=FONTS["body"], anchor="w", justify="left", wraplength=320
                     ).pack(side="left", fill="x", expand=True)

    def summary(self) -> str:
        return f"Companies · {len(self.state.config.companies)} configured"
