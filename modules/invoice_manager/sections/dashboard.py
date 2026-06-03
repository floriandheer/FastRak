"""Dashboard — landing screen.

Layout (top-to-bottom):
  1. Year strip — four quarter cards + YTD totals row
  2. Needs attention  |  Quick actions  (two-column row)
  3. Recent activity table
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from invoice_manager.core.filer import quarter_for
from invoice_manager.core.models import format_money
from invoice_manager.sections.base import Section
from invoice_manager.theme import PALETTE, FONTS
from invoice_manager.widgets.buttons import primary_button, secondary_button, link_label
from invoice_manager.widgets.card import Card


class DashboardSection(Section):
    title = "Dashboard"
    sidebar_key = "dashboard"
    sidebar_icon = "▣"

    # nav callbacks injected by the app so quick actions can switch sections
    nav_to: Callable[[str], None]

    def __init__(self, parent, state, *, nav_to: Callable[[str], None]):
        super().__init__(parent, state)
        self.nav_to = nav_to
        self._quarter_cards: Dict[int, Dict[str, tk.StringVar]] = {}
        self._attention_box: tk.Frame | None = None
        self._activity_tree = None
        self._ytd_var = tk.StringVar(value="")
        self.state.on_year_change(lambda _y: self._refresh_data())

    # ----- build -------------------------------------------------------

    def build(self, root: tk.Frame) -> None:
        C = PALETTE
        root.configure(bg=C["bg"])
        wrap = tk.Frame(root, bg=C["bg"], padx=20, pady=16)
        wrap.pack(fill="both", expand=True)

        # ----- 1. Year strip -----
        year_card = Card(wrap, title=f"Year {self.state.year}")
        year_card.pack(fill="x")
        self._year_card = year_card  # so we can re-title on year change

        cards_row = tk.Frame(year_card.body, bg=C["card_bg"])
        cards_row.pack(fill="x", pady=(2, 6))
        for q in (1, 2, 3, 4):
            self._build_quarter_card(cards_row, q)

        tk.Label(
            year_card.body, textvariable=self._ytd_var,
            fg=C["text_dim"], bg=C["card_bg"], font=FONTS["small"], anchor="w",
        ).pack(fill="x", pady=(4, 0))

        # ----- 2. Needs attention | Quick actions -----
        row2 = tk.Frame(wrap, bg=C["bg"])
        row2.pack(fill="x", pady=(14, 0))
        row2.columnconfigure(0, weight=2, uniform="r2")
        row2.columnconfigure(1, weight=1, uniform="r2")

        attn_card = Card(row2, title="Needs attention")
        attn_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._attention_box = tk.Frame(attn_card.body, bg=C["card_bg"])
        self._attention_box.pack(fill="both", expand=True)

        actions_card = Card(row2, title="Quick actions")
        actions_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self._build_quick_actions(actions_card.body)

        # ----- 3. Recent activity -----
        act_card = Card(wrap, title="Recent activity")
        act_card.pack(fill="both", expand=True, pady=(14, 0))
        self._build_activity(act_card.body)

    def _build_quarter_card(self, parent: tk.Frame, q: int) -> None:
        C = PALETTE
        cell = tk.Frame(parent, bg=C["bg_panel"], padx=14, pady=12)
        cell.pack(side="left", fill="both", expand=True, padx=4)

        tk.Label(
            cell, text=f"Q{q}", font=FONTS["h2"],
            fg=C["text"], bg=C["bg_panel"],
        ).pack(anchor="w")

        count_var = tk.StringVar(value="—")
        total_var = tk.StringVar(value="")
        status_var = tk.StringVar(value="")
        tk.Label(cell, textvariable=count_var, font=FONTS["mono_big"],
                 fg=C["text"], bg=C["bg_panel"]).pack(anchor="w", pady=(4, 0))
        tk.Label(cell, textvariable=total_var, font=FONTS["body"],
                 fg=C["text_dim"], bg=C["bg_panel"]).pack(anchor="w")
        tk.Label(cell, textvariable=status_var, font=FONTS["small"],
                 fg=C["dot_partial"], bg=C["bg_panel"]).pack(anchor="w", pady=(6, 0))

        self._quarter_cards[q] = {
            "count": count_var, "total": total_var, "status": status_var,
        }

    def _build_quick_actions(self, parent: tk.Frame) -> None:
        actions = [
            ("➕  New invoice",          lambda: self.nav_to("compose")),
            ("🛒  WC project invoice",   lambda: self.nav_to("compose")),
            ("📤  Browse outgoing",     lambda: self.nav_to("outgoing")),
            ("🔄  Sync from WooCommerce", self._run_wc_sync),
            ("📁  Create quarter folders", lambda: self.nav_to("settings")),
            ("✓  Run health check",      self._run_health_check),
        ]
        for text, cmd in actions:
            secondary_button(parent, text, cmd).pack(fill="x", pady=3)

    def _build_activity(self, parent: tk.Frame) -> None:
        from invoice_manager.widgets.tree import make_treeview
        cols = ("date", "number", "company", "customer", "total", "status")
        tree = make_treeview(parent, cols, height=10, show="headings")
        for col, w, anchor in [
            ("date",     100, "w"),
            ("number",   65,  "center"),
            ("company",  80,  "center"),
            ("customer", 320, "w"),
            ("total",    120, "e"),
            ("status",   120, "w"),
        ]:
            tree.heading(col, text=col.capitalize())
            tree.column(col, width=w, anchor=anchor)
        self._activity_tree = tree

    # ----- data --------------------------------------------------------

    def on_show(self) -> None:
        self._refresh_data()

    def reload(self) -> None:
        self._refresh_data()

    def on_year_change(self, year: int) -> None:
        # Re-title the year card
        try:
            # rewrite first label inside the card body
            for child in self._year_card.body.winfo_children():
                if isinstance(child, tk.Label) and child.cget("font") == str(FONTS["h3"]):
                    child.configure(text=f"Year {year}")
                    break
        except Exception:
            pass
        self._refresh_data()

    def _refresh_data(self) -> None:
        year = self.state.year
        invoices = self.state.registry.list_invoices(year=year, limit=9999)

        # Quarter totals
        per_q: Dict[int, List[Dict]] = {1: [], 2: [], 3: [], 4: []}
        for inv in invoices:
            if inv.get("status") == "draft":
                continue
            try:
                m = int((inv.get("invoice_date") or "")[:7].split("-")[1])
            except (IndexError, ValueError):
                continue
            per_q.setdefault(quarter_for(m), []).append(inv)

        current_q = quarter_for(datetime.now().month) if datetime.now().year == year else 0
        ytd_count = 0
        ytd_subtotal = 0
        ytd_vat = 0
        ytd_total = 0

        for q in (1, 2, 3, 4):
            rows = per_q.get(q, [])
            count = len(rows)
            total = sum(r.get("total_cents", 0) for r in rows)
            sub = sum(r.get("subtotal_cents", 0) for r in rows)
            vat = sum(r.get("vat_cents", 0) for r in rows)
            ytd_count += count
            ytd_subtotal += sub
            ytd_vat += vat
            ytd_total += total

            card = self._quarter_cards[q]
            if count == 0:
                if q == current_q:
                    card["count"].set("—")
                    card["total"].set("")
                    card["status"].set("(current)")
                else:
                    card["count"].set("—")
                    card["total"].set("")
                    card["status"].set("")
            else:
                card["count"].set(f"{count} inv.")
                card["total"].set(format_money(total))
                needs_dl = sum(1 for r in rows if self._filing_tag(r) == "needs_dl")
                missing = sum(1 for r in rows if self._filing_tag(r) == "missing")
                bits = []
                if needs_dl: bits.append(f"⚠ {needs_dl} need DL")
                if missing:  bits.append(f"⚠ {missing} missing PDF")
                if not bits: bits.append("✓ all filed")
                card["status"].set("  ·  ".join(bits))

        self._ytd_var.set(
            f"YTD: {ytd_count} invoices · {format_money(ytd_subtotal)} net · "
            f"{format_money(ytd_vat)} VAT · {format_money(ytd_total)} gross"
        )

        # Needs attention
        self._render_attention(invoices)
        # Recent activity
        self._render_activity(invoices)

    def _filing_tag(self, inv: Dict) -> str:
        if inv.get("status") == "voided":
            return "voided"
        source = inv.get("source", "")
        path = inv.get("pdf_path")
        if path and Path(path).exists():
            return "filed"
        if source == "woocommerce":
            return "needs_dl"
        return "missing"

    def _render_attention(self, invoices: List[Dict]) -> None:
        C = PALETTE
        box = self._attention_box
        if box is None:
            return
        for child in box.winfo_children():
            child.destroy()

        needs_dl = [i for i in invoices if self._filing_tag(i) == "needs_dl"]
        missing = [i for i in invoices if self._filing_tag(i) == "missing"]
        gaps = self.state.registry.health_check()

        if not needs_dl and not missing and not gaps:
            tk.Label(
                box, text="✓  Everything looks good.",
                fg=C["dot_filed"], bg=C["card_bg"], font=FONTS["body_bold"],
            ).pack(anchor="w", pady=8)
            return

        if needs_dl:
            self._attention_row(
                box,
                f"⚠ {len(needs_dl)} WC invoice(s) not yet filed",
                f"orders {', '.join('#' + str(i.get('source_ref', '?')) for i in needs_dl[:3])}"
                + ("…" if len(needs_dl) > 3 else ""),
                "File now",
                lambda: self.nav_to("outgoing"),
            )
        if missing:
            self._attention_row(
                box,
                f"⚠ {len(missing)} invoice(s) missing their PDF",
                ", ".join(f"#{i.get('sequence', 0):03d} {i.get('customer_name', '')}"
                          for i in missing[:3])
                + ("…" if len(missing) > 3 else ""),
                "Show",
                lambda: self.nav_to("outgoing"),
            )
        if gaps:
            self._attention_row(
                box,
                f"⚠ Numbering gaps detected",
                gaps[0] if gaps else "",
                "Health check",
                self._run_health_check,
            )

    def _attention_row(self, parent: tk.Frame, headline: str, detail: str,
                       action_text: str, action: Callable) -> None:
        C = PALETTE
        row = tk.Frame(parent, bg=C["card_bg"])
        row.pack(fill="x", pady=6)
        left = tk.Frame(row, bg=C["card_bg"])
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=headline, fg=C["text"], bg=C["card_bg"],
                 font=FONTS["body_bold"], anchor="w").pack(anchor="w")
        if detail:
            tk.Label(left, text=detail, fg=C["text_dim"], bg=C["card_bg"],
                     font=FONTS["small"], anchor="w").pack(anchor="w")
        link_label(row, action_text, action, bg=C["card_bg"]).pack(side="right", padx=8)

    def _render_activity(self, invoices: List[Dict]) -> None:
        tree = self._activity_tree
        if tree is None:
            return
        for iid in tree.get_children():
            tree.delete(iid)
        items = sorted(
            invoices,
            key=lambda r: (r.get("invoice_date") or "", r.get("sequence", 0)),
            reverse=True,
        )[:30]
        for inv in items:
            tag = self._filing_tag(inv)
            status_label = {
                "filed":    "✓ filed",
                "needs_dl": "⬇ needs download",
                "missing":  "⚠ missing PDF",
                "voided":   "— voided",
            }.get(tag, "")
            tree.insert(
                "", "end",
                values=(
                    inv.get("invoice_date", "—"),
                    f"{inv.get('sequence', 0):03d}",
                    inv.get("company_key", ""),
                    inv.get("customer_name", ""),
                    format_money(inv.get("total_cents", 0), inv.get("currency", "EUR")),
                    status_label,
                ),
                tags=(tag,),
            )

    # ----- actions -----------------------------------------------------

    def _run_health_check(self) -> None:
        from tkinter import messagebox
        warnings = self.state.registry.health_check()
        if not warnings:
            messagebox.showinfo("Health check", "✓  All years have gapless numbering.")
        else:
            messagebox.showwarning("Health check — warnings", "\n\n".join(warnings))

    def _run_wc_sync(self) -> None:
        # Delegate to the Outgoing section's WC sync (defined there) by
        # navigating to it; users can hit Sync there. Direct sync from
        # the dashboard would duplicate that logic.
        self.nav_to("outgoing")

    def summary(self) -> str:
        return f"Dashboard · year {self.state.year}"
