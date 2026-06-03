"""Compose — unified Manual + WooCommerce-project invoice authoring.

Mode toggle at the top switches between two layouts:

  Manual:
    Left  — invoice header + customer fields + next-number card
    Right — Notebook { Items | Expenses } + totals + actions

  WC Project:
    Single form — customer fields + description + amount + project folder
"""

from __future__ import annotations

import tempfile
import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional

from invoice_manager.core.config import DATA_DIR
from invoice_manager.core.debug_mode import debug_boekhouding_base
from invoice_manager.core.filer import file_pdf
from invoice_manager.core.models import (
    Company, LineItem, format_money, format_money_plain,
)
from invoice_manager.core.pdf_export import PdfExportError, odt_to_pdf
from invoice_manager.core.template_engine import TemplateError, render_odt
from invoice_manager.core.wc_bridge import WCBridgeError, WooCommerceBridge
from shared_logging import get_logger

from invoice_manager.sections.base import Section
from invoice_manager.theme import PALETTE, FONTS
from invoice_manager.widgets.buttons import primary_button, secondary_button
from invoice_manager.widgets.card import Card
from invoice_manager.widgets.chip import ChipGroup
from invoice_manager.widgets.inputs import make_entry, make_spinbox, make_text, form_label
from invoice_manager.widgets.line_item_dialog import LineItemDialog
from invoice_manager.widgets.tree import make_treeview

logger = get_logger("invoice_manager.compose")


class ComposeSection(Section):
    title = "Compose"
    sidebar_key = "compose"
    sidebar_icon = "➕"

    MODE_MANUAL = "manual"
    MODE_WC = "wc"

    def __init__(self, parent, state):
        super().__init__(parent, state)
        self._mode = self.MODE_MANUAL
        self._line_items: List[LineItem] = []
        self._expense_items: List[LineItem] = []
        self._manual_pane: Optional[tk.Frame] = None
        self._wc_pane: Optional[tk.Frame] = None

    # ----- build -------------------------------------------------------

    def build(self, root: tk.Frame) -> None:
        C = PALETTE
        root.configure(bg=C["bg"])
        wrap = tk.Frame(root, bg=C["bg"], padx=20, pady=14)
        wrap.pack(fill="both", expand=True)

        # Mode toggle
        toggle_row = tk.Frame(wrap, bg=C["bg"])
        toggle_row.pack(fill="x", pady=(0, 12))
        tk.Label(toggle_row, text="Mode", fg=C["text_dim"], bg=C["bg"],
                 font=FONTS["small"]).pack(side="left", padx=(0, 8))
        self._mode_chips = ChipGroup(toggle_row, on_change=self._switch_mode)
        self._mode_chips.add(self.MODE_MANUAL, "Manual invoice", selected=True)
        self._mode_chips.add(self.MODE_WC,     "WooCommerce project")
        self._mode_chips.pack(side="left")

        # Mode panes — only one visible at a time
        self._pane_host = tk.Frame(wrap, bg=C["bg"])
        self._pane_host.pack(fill="both", expand=True)

        self._build_manual_pane(self._pane_host)
        self._build_wc_pane(self._pane_host)
        self._switch_mode(self.MODE_MANUAL)

    # ===== Manual mode =================================================

    def _build_manual_pane(self, parent: tk.Widget) -> None:
        C = PALETTE
        pane = tk.Frame(parent, bg=C["bg"])
        self._manual_pane = pane

        left_card = Card(pane, title="Invoice")
        left_card.pack(side="left", fill="y", padx=(0, 10), anchor="n")
        self._build_manual_form(left_card.body)

        right = tk.Frame(pane, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)

        items_card = Card(right)
        items_card.pack(fill="both", expand=True)
        self._build_items_tabs(items_card.body)

        totals_card = Card(right)
        totals_card.pack(fill="x", pady=(10, 0))
        self._build_totals(totals_card.body)

        actions = tk.Frame(right, bg=C["bg"])
        actions.pack(fill="x", pady=(10, 0))
        secondary_button(actions, "Reset", self._reset_manual).pack(side="left")
        primary_button(actions, "⚡  Generate PDF",
                       self._generate_invoice).pack(side="right")

    def _build_manual_form(self, body: tk.Frame) -> None:
        C = PALETTE
        # Card.body uses pack for the title; grid needs its own container.
        parent = tk.Frame(body, bg=C["card_bg"])
        parent.pack(fill="both", expand=True)
        self._m_company = tk.StringVar()
        self._m_year = tk.StringVar(value=str(self.state.year))
        self._m_date = tk.StringVar(value=date.today().isoformat())
        self._m_customer = tk.StringVar()
        self._m_vat = tk.StringVar()
        self._m_email = tk.StringVar()
        self._m_notes = tk.StringVar()

        # Helper for grid layout with right padding between label & field
        def add_row(r, label_text, widget):
            form_label(parent, label_text).grid(row=r, column=0, sticky="w",
                                                pady=(0, 6), padx=(0, 10))
            widget.grid(row=r, column=1, sticky="we", pady=(0, 6))

        parent.columnconfigure(1, weight=1)

        # Company picker — restricted to libreoffice-rendered companies
        row = 0
        company_values = [
            f"{c.key} — {c.display_name}"
            for c in self.state.config.companies if c.uses_libreoffice
        ]
        co_cb = ttk.Combobox(
            parent, textvariable=self._m_company, state="readonly", width=32,
            values=company_values, style="InvApp.TCombobox",
        )
        if company_values:
            co_cb.current(0)
        add_row(row, "Company", co_cb); row += 1

        add_row(row, "Year", make_entry(parent, self._m_year, width=8)); row += 1
        add_row(row, "Date", make_entry(parent, self._m_date, width=18)); row += 1

        # Customer block
        sep = tk.Frame(parent, bg=C["card_border"], height=1)
        sep.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 10)); row += 1
        tk.Label(parent, text="Customer", fg=C["text"], bg=C["card_bg"],
                 font=FONTS["h3"]
                 ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1

        for label, var in [
            ("Name",  self._m_customer),
            ("VAT",   self._m_vat),
            ("Email", self._m_email),
        ]:
            add_row(row, label, make_entry(parent, var, width=32)); row += 1

        form_label(parent, "Address").grid(row=row, column=0, sticky="nw",
                                           pady=(2, 6), padx=(0, 10))
        self._m_address = make_text(parent, height=4, width=32)
        self._m_address.grid(row=row, column=1, sticky="we", pady=(0, 6))
        row += 1

        add_row(row, "Notes", make_entry(parent, self._m_notes, width=32)); row += 1

        # Next-number card — uses bg_panel (a step up from card_bg) for elevation
        nn_frame = tk.Frame(parent, bg=C["bg_panel"], padx=14, pady=12,
                            highlightthickness=1,
                            highlightbackground=C["card_border"])
        nn_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        tk.Label(nn_frame, text="Next number", fg=C["text_dim"],
                 bg=C["bg_panel"], font=FONTS["small"]).pack(anchor="w")
        self._m_next_var = tk.StringVar(value="—")
        tk.Label(nn_frame, textvariable=self._m_next_var,
                 fg=C["accent"], bg=C["bg_panel"], font=FONTS["mono_big"]
                 ).pack(anchor="w")
        self._m_year.trace_add("write", lambda *_: self._refresh_preview())

    def _build_items_tabs(self, parent: tk.Frame) -> None:
        nb = ttk.Notebook(parent, style="InvApp.TNotebook")
        nb.pack(fill="both", expand=True)

        # Items tab
        items_tab = tk.Frame(nb, bg=PALETTE["card_bg"])
        nb.add(items_tab, text="  Work items  ")
        self._li_tree = self._build_item_tree(items_tab, self._line_items,
                                              add=self._add_line_item,
                                              edit=self._edit_line_item,
                                              remove=self._remove_line_item)

        # Expenses tab
        exp_tab = tk.Frame(nb, bg=PALETTE["card_bg"])
        nb.add(exp_tab, text="  Expenses (Onkosten)  ")
        self._exp_tree = self._build_item_tree(exp_tab, self._expense_items,
                                               add=self._add_expense_item,
                                               edit=self._edit_expense_item,
                                               remove=self._remove_expense_item)

    def _build_item_tree(self, parent: tk.Frame, items: List[LineItem],
                         add, edit, remove):
        C = PALETTE
        inner = tk.Frame(parent, bg=C["card_bg"], padx=8, pady=8)
        inner.pack(fill="both", expand=True)

        cols = ("description", "qty", "unit_price", "vat_rate", "line_total")
        tree = make_treeview(inner, cols, height=8, show="headings")
        for c, w, anchor in [
            ("description", 320, "w"), ("qty", 60, "e"),
            ("unit_price", 110, "e"), ("vat_rate", 70, "e"),
            ("line_total", 110, "e"),
        ]:
            tree.heading(c, text=c.replace("_", " ").capitalize())
            tree.column(c, width=w, anchor=anchor, stretch=(c == "description"))
        tree.bind("<Double-1>", lambda _e: edit())

        btns = tk.Frame(parent, bg=C["card_bg"])
        btns.pack(fill="x", padx=8, pady=(0, 6))
        secondary_button(btns, "+ Add line", add, padx=10, pady=3).pack(side="left")
        secondary_button(btns, "Edit", edit, padx=10, pady=3).pack(side="left", padx=(6, 0))
        secondary_button(btns, "Remove", remove, padx=10, pady=3).pack(side="left", padx=(6, 0))
        return tree

    def _build_totals(self, parent: tk.Frame) -> None:
        C = PALETTE
        self._t_sub = tk.StringVar(value=format_money(0))
        self._t_vat = tk.StringVar(value=format_money(0))
        self._t_total = tk.StringVar(value=format_money(0))
        for label, var, font in [
            ("Subtotal", self._t_sub,   FONTS["body"]),
            ("VAT",      self._t_vat,   FONTS["body"]),
            ("Total",    self._t_total, FONTS["mono_big"]),
        ]:
            row = tk.Frame(parent, bg=C["card_bg"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, fg=C["text_dim"], bg=C["card_bg"],
                     font=FONTS["body"], width=10, anchor="w").pack(side="left")
            tk.Label(row, textvariable=var, fg=C["text"], bg=C["card_bg"],
                     font=font, anchor="e").pack(side="right")

    # ----- Manual mode item handlers ----------------------------------

    def _current_company(self) -> Optional[Company]:
        sel = self._m_company.get()
        if not sel:
            return None
        key = sel.split(" — ", 1)[0]
        try:
            return self.state.config.get_company(key)
        except KeyError:
            return None

    def _add_line_item(self):
        c = self._current_company()
        default_rate = c.default_vat_rate if c else 21.0
        item = LineItemDialog(self.frame, default_vat_rate=default_rate).result
        if item:
            self._line_items.append(item)
            self._refresh_items()

    def _edit_line_item(self):
        sel = self._li_tree.selection()
        if not sel: return
        idx = int(sel[0])
        item = LineItemDialog(self.frame, existing=self._line_items[idx]).result
        if item:
            self._line_items[idx] = item
            self._refresh_items()

    def _remove_line_item(self):
        sel = self._li_tree.selection()
        if not sel: return
        del self._line_items[int(sel[0])]
        self._refresh_items()

    def _add_expense_item(self):
        c = self._current_company()
        default_rate = c.default_vat_rate if c else 21.0
        item = LineItemDialog(self.frame, default_vat_rate=default_rate,
                              title="Expense item").result
        if item:
            self._expense_items.append(item)
            self._refresh_items()

    def _edit_expense_item(self):
        sel = self._exp_tree.selection()
        if not sel: return
        idx = int(sel[0])
        item = LineItemDialog(self.frame, existing=self._expense_items[idx],
                              title="Expense item").result
        if item:
            self._expense_items[idx] = item
            self._refresh_items()

    def _remove_expense_item(self):
        sel = self._exp_tree.selection()
        if not sel: return
        del self._expense_items[int(sel[0])]
        self._refresh_items()

    def _refresh_items(self):
        for iid in self._li_tree.get_children():
            self._li_tree.delete(iid)
        for idx, li in enumerate(self._line_items):
            self._li_tree.insert("", "end", iid=str(idx), values=(
                li.description, f"{li.quantity:g}",
                format_money_plain(li.unit_price_cents),
                f"{li.vat_rate:g}%",
                format_money_plain(li.line_total_cents),
            ))
        for iid in self._exp_tree.get_children():
            self._exp_tree.delete(iid)
        for idx, li in enumerate(self._expense_items):
            self._exp_tree.insert("", "end", iid=str(idx), values=(
                li.description, f"{li.quantity:g}",
                format_money_plain(li.unit_price_cents),
                f"{li.vat_rate:g}%",
                format_money_plain(li.line_total_cents),
            ))
        all_items = self._line_items + self._expense_items
        sub = sum(li.line_subtotal_cents for li in all_items)
        vat = sum(li.line_vat_cents for li in all_items)
        self._t_sub.set(format_money(sub))
        self._t_vat.set(format_money(vat))
        self._t_total.set(format_money(sub + vat))

    def _reset_manual(self):
        self._m_customer.set("")
        self._m_vat.set("")
        self._m_email.set("")
        self._m_notes.set("")
        self._m_address.delete("1.0", "end")
        self._m_date.set(date.today().isoformat())
        self._m_year.set(str(self.state.year))
        self._line_items = []
        self._expense_items = []
        self._refresh_items()
        self._refresh_preview()

    def _refresh_preview(self):
        try:
            year = int(self._m_year.get())
        except (ValueError, AttributeError):
            return
        nxt = self.state.registry.get_next_preview(year)
        self._m_next_var.set(f"#{nxt:03d}    ({year})")

    # ----- Manual mode generation -------------------------------------

    def _generate_invoice(self):
        company = self._current_company()
        if not company:
            messagebox.showerror("New invoice", "Please pick a company.")
            return
        if not company.uses_libreoffice:
            messagebox.showerror("New invoice",
                                 f"Company {company.key} is not configured for LibreOffice rendering.")
            return
        customer = self._m_customer.get().strip()
        if not customer:
            messagebox.showerror("New invoice", "Customer name is required.")
            return
        if not self._line_items:
            messagebox.showerror("New invoice", "Add at least one line item.")
            return
        try:
            year = int(self._m_year.get())
            invoice_date_str = self._m_date.get().strip()
            datetime.strptime(invoice_date_str, "%Y-%m-%d")
        except ValueError as e:
            messagebox.showerror("New invoice", f"Invalid year or date: {e}")
            return

        cur_year = datetime.now().year
        if year < cur_year - self.state.config.year_change_confirm_threshold:
            if not messagebox.askyesno(
                "Confirm old year",
                f"You picked year {year}, more than "
                f"{self.state.config.year_change_confirm_threshold} year(s) before "
                f"the current year ({cur_year}).\n\nProceed?",
            ):
                return

        template_path = self.state.config.resolve_template_path(company)
        if not template_path or not template_path.exists():
            messagebox.showerror(
                "Template missing",
                f"Template not found for {company.display_name}.\nExpected: {template_path}",
            )
            return

        debug_mode = self.state.debug_session.is_active()
        try:
            self.frame.configure(cursor="watch")
        except tk.TclError:
            pass
        threading.Thread(
            target=self._generate_worker,
            args=(company, year, invoice_date_str, customer, template_path, debug_mode),
            daemon=True,
        ).start()

    def _generate_worker(self, company: Company, year: int, invoice_date_str: str,
                         customer: str, template_path: Path, debug_mode: bool):
        try:
            draft = {
                "company_key": company.key,
                "invoice_date": invoice_date_str,
                "customer_name": customer,
                "customer_vat": self._m_vat.get().strip(),
                "customer_email": self._m_email.get().strip(),
                "customer_address": self._m_address.get("1.0", "end").strip(),
                "line_items": self._line_items,
                "expense_items": self._expense_items,
                "currency": self.state.config.currency,
                "source": "manual",
                "source_ref": None,
                "notes": self._m_notes.get().strip(),
            }
            row = self.state.registry.reserve_and_return_row(year, draft)
            invoice_id = row["id"]
            sequence = row["sequence"]
            logger.info(f"Reserved #{sequence:03d} ({year}) for {company.key}/{customer}")

            ctx = self._template_context(company, row)

            def _li_ctx(items):
                return [{
                    "desc": li.description, "qty": f"{li.quantity:g}",
                    "unit_price": format_money_plain(li.unit_price_cents),
                    "vat_rate": f"{li.vat_rate:g}%",
                    "line_total": format_money_plain(li.line_total_cents),
                } for li in items]

            with tempfile.TemporaryDirectory(prefix="invapp_render_") as td:
                tmp_odt = Path(td) / f"{template_path.stem}_{sequence:03d}.odt"
                render_odt(
                    template_path, tmp_odt, ctx,
                    _li_ctx(self._line_items),
                    expense_items=_li_ctx(self._expense_items),
                )
                soffice = self.state.config.resolve_soffice_path()
                pdf_tmp = odt_to_pdf(tmp_odt, Path(td), soffice_path=soffice)
                boek = self.state.config.resolve_boekhouding_base()
                if debug_mode:
                    boek = debug_boekhouding_base(boek)
                final_pdf = file_pdf(
                    pdf_tmp, boek, company.output_prefix,
                    invoice_date_str, sequence, customer, move=True,
                )
            self.state.registry.finalize_invoice(invoice_id, str(final_pdf))
            self.frame.after(0, self._on_generated, final_pdf, debug_mode)
        except (TemplateError, PdfExportError) as e:
            logger.exception("Render failed")
            self.frame.after(0, messagebox.showerror, "Generate invoice",
                             f"Rendering failed:\n\n{e}\n\nDraft row kept.")
        except Exception as e:
            logger.exception("Generate failed")
            self.frame.after(0, messagebox.showerror, "Generate invoice",
                             f"Failed:\n\n{e}")
        finally:
            try:
                self.frame.after(0, lambda: self.frame.configure(cursor=""))
            except tk.TclError:
                pass

    def _on_generated(self, final_pdf: Path, debug_mode: bool):
        if debug_mode and self.state.debug_session.is_active():
            try:
                self.state.debug_session.record_pdf(final_pdf)
            except Exception:
                pass
        if self.state.config.auto_open_pdf_after_generate:
            self.state.resolve_pdf_open(final_pdf)
        else:
            messagebox.showinfo("Invoice generated", f"Saved to:\n{final_pdf}")
        self._reset_manual()

    def _template_context(self, company: Company, row: Dict[str, Any]) -> Dict[str, str]:
        addr_lines = [l for l in (row["customer_address"] or "").splitlines() if l.strip()]
        addr1 = addr_lines[0] if len(addr_lines) > 0 else ""
        addr2 = addr_lines[1] if len(addr_lines) > 1 else ""
        addr3 = addr_lines[2] if len(addr_lines) > 2 else ""
        inv_date = datetime.strptime(row["invoice_date"], "%Y-%m-%d").date()
        due_date = (inv_date + timedelta(days=30)).strftime("%d/%m/%Y")
        return {
            "invoice_number": f"{row['sequence']:03d}",
            "invoice_year":   str(row["year"]),
            "invoice_date":   inv_date.strftime("%d/%m/%Y"),
            "due_date":       due_date,
            "company_legal_name": company.legal_name,
            "company_vat":        company.vat,
            "company_address":    company.address_block,
            "company_email":      company.email,
            "company_iban":       company.iban,
            "company_bic":        company.bic,
            "customer_name":    row["customer_name"],
            "customer_vat":     row["customer_vat"] or "",
            "customer_address": row["customer_address"] or "",
            "customer_address_1": addr1,
            "customer_address_2": addr2,
            "customer_address_3": addr3,
            "customer_email":   row["customer_email"] or "",
            "subtotal": format_money(row["subtotal_cents"], row["currency"]),
            "vat":      format_money(row["vat_cents"], row["currency"]),
            "total":    format_money(row["total_cents"], row["currency"]),
            "currency": row["currency"],
            "notes":    row.get("notes", ""),
        }

    # ===== WC Project mode =============================================

    def _build_wc_pane(self, parent: tk.Widget) -> None:
        C = PALETTE
        pane = tk.Frame(parent, bg=C["bg"])
        self._wc_pane = pane

        creds = self.state.config.get_wc_credentials_for_alles3d()
        if not creds or not creds.get("consumer_key"):
            warn_card = Card(pane, title="WooCommerce not configured")
            warn_card.pack(fill="x")
            tk.Label(
                warn_card.body,
                text="Configure company '3D' with a wc_binding in config.json,\n"
                     "or set up the WooCommerce Order Monitor first.",
                fg=C["dot_partial"], bg=C["card_bg"],
                font=FONTS["body"], justify="left",
            ).pack(anchor="w")
            secondary_button(
                warn_card.body, "Open config.json",
                lambda: self.state.resolve_pdf_open(self.state.config.source_path),
            ).pack(anchor="w", pady=(10, 0))
            return

        form_card = Card(pane, title="WooCommerce project invoice")
        form_card.pack(fill="x")
        self._build_wc_form(form_card.body)

    def _build_wc_form(self, body: tk.Frame) -> None:
        C = PALETTE
        # Same wrap-in-frame pattern as the manual form.
        parent = tk.Frame(body, bg=C["card_bg"])
        parent.pack(fill="both", expand=True)
        parent.columnconfigure(1, weight=1)
        self._wc_fields: Dict[str, tk.StringVar] = {}
        customer_rows = [
            ("First name", "first_name"),
            ("Last name",  "last_name"),
            ("Email",      "email"),
            ("Address",    "address_1"),
            ("Postcode",   "postcode"),
            ("City",       "city"),
            ("Country",    "country"),
        ]
        tk.Label(parent, text="Customer", fg=C["text"], bg=C["card_bg"],
                 font=FONTS["h3"]
                 ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        for i, (label, key) in enumerate(customer_rows, start=1):
            form_label(parent, label).grid(row=i, column=0, sticky="w",
                                           pady=4, padx=(0, 10))
            var = tk.StringVar(value="BE" if key == "country" else "")
            make_entry(parent, var, width=36).grid(
                row=i, column=1, sticky="ew", pady=4)
            self._wc_fields[key] = var

        off = len(customer_rows) + 1
        sep = tk.Frame(parent, bg=C["card_border"], height=1)
        sep.grid(row=off, column=0, columnspan=2, sticky="ew", pady=(12, 10))
        off += 1
        tk.Label(parent, text="Invoice item", fg=C["text"], bg=C["card_bg"],
                 font=FONTS["h3"]
                 ).grid(row=off, column=0, columnspan=2, sticky="w", pady=(0, 8))
        off += 1

        form_label(parent, "Description").grid(row=off, column=0, sticky="w",
                                                pady=4, padx=(0, 10))
        self._wc_desc = tk.StringVar()
        make_entry(parent, self._wc_desc, width=36).grid(
            row=off, column=1, sticky="ew", pady=4)
        off += 1

        form_label(parent, "Amount (EUR)").grid(row=off, column=0, sticky="w",
                                                 pady=4, padx=(0, 10))
        self._wc_amount = tk.StringVar()
        make_entry(parent, self._wc_amount, width=18).grid(
            row=off, column=1, sticky="w", pady=4)
        off += 1

        form_label(parent, "Project folder").grid(row=off, column=0, sticky="w",
                                                   pady=4, padx=(0, 10))
        folder_row = tk.Frame(parent, bg=C["card_bg"])
        folder_row.grid(row=off, column=1, sticky="ew", pady=4)
        folder_row.columnconfigure(0, weight=1)
        self._wc_folder = tk.StringVar()
        make_entry(folder_row, self._wc_folder, width=10).grid(
            row=0, column=0, sticky="ew")
        secondary_button(folder_row, "Browse…", self._wc_browse_folder,
                         padx=10).grid(row=0, column=1, padx=(8, 0))
        off += 1

        self._wc_status = tk.StringVar(value="")
        tk.Label(parent, textvariable=self._wc_status,
                 fg=C["text_dim"], bg=C["card_bg"], font=FONTS["small"]
                 ).grid(row=off, column=0, columnspan=2, sticky="w", pady=(8, 4))
        off += 1

        btns = tk.Frame(parent, bg=C["card_bg"])
        btns.grid(row=off, column=0, columnspan=2, sticky="w", pady=(6, 0))
        primary_button(btns, "Create invoice", self._wc_create).pack(side="left")
        secondary_button(btns, "Clear", self._wc_reset).pack(side="left", padx=(8, 0))

    def _wc_browse_folder(self):
        d = filedialog.askdirectory(parent=self.frame)
        if d:
            self._wc_folder.set(d)

    def _wc_reset(self):
        for var in self._wc_fields.values():
            var.set("")
        if "country" in self._wc_fields:
            self._wc_fields["country"].set("BE")
        self._wc_desc.set("")
        self._wc_amount.set("")
        self._wc_folder.set("")
        self._wc_status.set("")

    def _wc_create(self):
        customer = {k: v.get().strip() for k, v in self._wc_fields.items()}
        desc = self._wc_desc.get().strip()
        amount_str = self._wc_amount.get().strip()
        folder_str = self._wc_folder.get().strip()

        if not customer.get("last_name") and not customer.get("first_name"):
            messagebox.showerror("WC project invoice", "Customer name is required.")
            return
        if not desc or not amount_str:
            messagebox.showerror("WC project invoice", "Description and amount are required.")
            return
        try:
            float(amount_str.replace(",", "."))
        except ValueError:
            messagebox.showerror("WC project invoice", f"Invalid amount: {amount_str!r}")
            return
        project_folder = Path(folder_str) if folder_str else None
        if project_folder and not project_folder.exists():
            messagebox.showerror("WC project invoice", "Project folder does not exist.")
            return

        creds = self.state.config.get_wc_credentials_for_alles3d()
        try:
            bridge = WooCommerceBridge(creds)
        except WCBridgeError as e:
            messagebox.showerror("WC project invoice", str(e))
            return

        self._wc_status.set("Creating WooCommerce order…")
        threading.Thread(
            target=self._wc_worker,
            args=(bridge, customer, desc, amount_str, project_folder),
            daemon=True,
        ).start()

    def _wc_worker(self, bridge, customer, desc, amount_str, project_folder):
        try:
            line_items = [{"name": desc, "quantity": 1,
                           "total": amount_str.replace(",", ".")}]
            order = bridge.create_order(customer, line_items)
            if not order:
                self.frame.after(0, self._wc_done, None, "Failed to create order.")
                return
            order_number = order.get("number", order["id"])
            order_id = order["id"]
            self.frame.after(0, self._wc_status.set,
                             f"Order #{order_number} created. Filing invoice…")

            filed_pdf: Optional[Path] = None
            if project_folder:
                from invoice_manager.core.wc_bridge import extract_wc_invoice_info
                from invoice_manager.core.filer import file_pdf as _file_pdf, create_shortcut
                boek = self.state.config.resolve_boekhouding_base()
                invoice_info = extract_wc_invoice_info(order)
                if invoice_info and bridge.monitor_secret_key:
                    with tempfile.TemporaryDirectory(prefix="wcp_") as td:
                        tmp_pdf = Path(td) / f"invoice_{order_id}.pdf"
                        if bridge.download_invoice_pdf(order_id, tmp_pdf):
                            billing = order.get("billing") or {}
                            client_name = (billing.get("last_name") or
                                           billing.get("first_name") or
                                           f"Order{order_id}")
                            try:
                                company = self.state.config.get_company("3D")
                                prefix = company.output_prefix
                            except KeyError:
                                prefix = "3D"
                            invoice_date = invoice_info.get(
                                "invoice_date", order.get("date_created", "")[:10])
                            sequence = invoice_info.get("sequence", 0)
                            filed_pdf = _file_pdf(
                                tmp_pdf, boek, prefix, invoice_date,
                                sequence, client_name, move=False,
                            )
                    if filed_pdf and project_folder:
                        outgoing = project_folder / "03_Outgoing"
                        outgoing.mkdir(parents=True, exist_ok=True)
                        try:
                            create_shortcut(outgoing / (filed_pdf.stem + ".lnk"),
                                            filed_pdf)
                        except Exception as e:
                            logger.warning(f"Could not create shortcut: {e}")
            self.frame.after(0, self._wc_done, filed_pdf, None)
        except Exception as e:
            logger.exception("WC project failed")
            self.frame.after(0, self._wc_done, None, str(e))

    def _wc_done(self, filed_pdf: Optional[Path], error: Optional[str]):
        if error:
            self._wc_status.set(f"Error: {error}")
            messagebox.showerror("WC project invoice", error)
            return
        if filed_pdf:
            self._wc_status.set(f"✓ Filed: {filed_pdf.name}")
            if messagebox.askyesno("WC project invoice",
                                   f"Invoice filed to:\n{filed_pdf}\n\nOpen PDF?"):
                self.state.resolve_pdf_open(filed_pdf)
        else:
            self._wc_status.set("✓ Order created (PDF will be available shortly).")
            messagebox.showinfo("WC project invoice",
                                "WooCommerce order created. Use Outgoing → File quarter "
                                "to archive the invoice PDF once it's generated.")

    # ===== Mode switching =============================================

    def _switch_mode(self, mode: str) -> None:
        self._mode = mode
        if self._manual_pane:
            self._manual_pane.pack_forget()
        if self._wc_pane:
            self._wc_pane.pack_forget()
        if mode == self.MODE_MANUAL and self._manual_pane:
            self._manual_pane.pack(fill="both", expand=True)
        elif mode == self.MODE_WC and self._wc_pane:
            self._wc_pane.pack(fill="both", expand=True)

    # ----- Section lifecycle ------------------------------------------

    def on_show(self) -> None:
        self._refresh_preview()
        self._refresh_items()

    def on_year_change(self, year: int) -> None:
        self._m_year.set(str(year))
        self._refresh_preview()

    def summary(self) -> str:
        if self._mode == self.MODE_MANUAL:
            return (f"Compose · {len(self._line_items)} item(s)"
                    + (f" · {len(self._expense_items)} expense(s)"
                       if self._expense_items else ""))
        return "Compose · WooCommerce project"
