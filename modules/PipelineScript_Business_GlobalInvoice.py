"""Global Invoice — centralised invoice numbering across Florian D'heer,
Hyphen-V, and Alles3D.

Provides:
- Dashboard listing invoices from the shared SQLite registry.
- New Invoice form that reserves the next global number, fills a
  LibreOffice template, exports a PDF, and files it into Boekhouding.
- Settings for the soffice binary, Boekhouding base path, and a health
  check that confirms gapless year-by-year numbering.

The WooCommerce integration lives in the existing
PipelineScript_Physical_WooCommerceOrderMonitor.py — this UI just
displays the resulting rows.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Dict, List, Optional

# Allow `import shared_*` when run directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared_form_keyboard import FORM_COLORS
from shared_logging import get_logger, setup_logging as setup_shared_logging
from shared_window_icon import apply_category_icon

from global_invoice.config import ConfigError, DATA_DIR, load_config
from global_invoice.debug_mode import (
    DEBUG_SUBFOLDER_NAME,
    DebugSession,
    cleanup_debug_pdfs,
    debug_boekhouding_base,
)
from global_invoice.filer import file_pdf
from global_invoice.models import (
    Company, Invoice, LineItem,
    format_money, format_money_plain, to_cents,
)
from global_invoice.pdf_export import PdfExportError, odt_to_pdf
from global_invoice.registry import InvoiceRegistry
from global_invoice.template_engine import TemplateError, render_odt
from global_invoice.wc_bridge import WCBridgeError, WooCommerceBridge
from global_invoice.wc_sync import sync_woocommerce_invoices

logger = get_logger("global_invoice")


# ============================================================================
# Main GUI
# ============================================================================

class GlobalInvoiceGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Global Invoice")
        self.root.geometry("1200x780")
        self.root.minsize(960, 600)
        self.root.configure(bg=FORM_COLORS["bg"])

        try:
            self.config = load_config()
        except ConfigError as e:
            messagebox.showerror(
                "Global Invoice — Configuration",
                f"Cannot start: {e}",
            )
            self.root.destroy()
            return

        self.registry = InvoiceRegistry(self.config.resolve_db_path())
        self.debug_session = DebugSession(DATA_DIR / "debug_session.json")

        self._build_styles()
        self._build_ui()
        self._refresh_dashboard()
        self._refresh_debug_ui()
        self.root.after(50, self._check_orphaned_debug_session)

    # --- styling -------------------------------------------------------------

    def _build_styles(self):
        C = FORM_COLORS
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Invoice.Treeview",
            background=C["bg_input"], foreground=C["text"],
            fieldbackground=C["bg_input"], rowheight=26,
            font=("Arial", 10),
        )
        style.configure(
            "Invoice.Treeview.Heading",
            background=C["border"], foreground=C["text"],
            font=("Arial", 10, "bold"),
        )
        style.map(
            "Invoice.Treeview",
            background=[("selected", C["accent_dark"])],
            foreground=[("selected", "white")],
        )

        style.configure("Invoice.TNotebook", background=C["bg"])
        style.configure(
            "Invoice.TNotebook.Tab",
            background=C["bg_input"], foreground=C["text"],
            padding=[14, 6],
        )
        style.map(
            "Invoice.TNotebook.Tab",
            background=[("selected", C["accent_dark"])],
            foreground=[("selected", "#ffffff")],
        )

        style.configure(
            "Invoice.TCombobox",
            fieldbackground=C["bg_input"],
            background=C["bg_input"],
            foreground=C["text"],
        )

    # --- top-level layout ---------------------------------------------------

    def _build_ui(self):
        C = FORM_COLORS

        # Header
        header = tk.Frame(self.root, bg=C["accent_dark"], height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="🧾  Global Invoice",
            font=("Arial", 15, "bold"),
            fg="white", bg=C["accent_dark"],
        ).pack(side="left", padx=16)
        tk.Label(
            header,
            text=f"DB: {self.config.resolve_db_path()}",
            font=("Arial", 9),
            fg="#cfe2ff", bg=C["accent_dark"],
        ).pack(side="right", padx=16)

        # Debug-mode banner (shown only while a debug session is active).
        self._debug_banner = tk.Frame(self.root, bg="#b91c1c", height=32)
        self._debug_banner_label = tk.Label(
            self._debug_banner,
            text="",
            font=("Arial", 11, "bold"),
            fg="white", bg="#b91c1c",
        )
        self._debug_banner_label.pack(side="left", padx=16, pady=4)
        tk.Button(
            self._debug_banner, text="Exit debug mode",
            command=self._exit_debug_mode,
            bg="white", fg="#b91c1c",
            activebackground="#fee2e2", activeforeground="#b91c1c",
            relief=tk.FLAT, font=("Arial", 10, "bold"),
            cursor="hand2", padx=10, pady=2,
        ).pack(side="right", padx=12, pady=4)

        # Notebook
        self.notebook = ttk.Notebook(self.root, style="Invoice.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(8, 8))

        self._build_dashboard_tab()
        self._build_new_invoice_tab()
        self._build_companies_tab()
        self._build_settings_tab()

    # =====================================================================
    # Dashboard tab
    # =====================================================================

    def _build_dashboard_tab(self):
        C = FORM_COLORS
        tab = tk.Frame(self.notebook, bg=C["bg"])
        self.notebook.add(tab, text="📋  Dashboard")

        # Filter row
        ctrl = tk.Frame(tab, bg=C["bg"])
        ctrl.pack(fill="x", padx=8, pady=(8, 4))

        tk.Label(ctrl, text="Year:", fg=C["text"], bg=C["bg"]).pack(side="left")
        self.dash_year = tk.StringVar(value=str(datetime.now().year))
        years = [str(y) for y in (self.registry.list_years()
                                   or [datetime.now().year])]
        # Always include current year in the list
        cur = str(datetime.now().year)
        if cur not in years:
            years.insert(0, cur)
        ttk.Combobox(
            ctrl, textvariable=self.dash_year, values=["(all)"] + years,
            width=8, state="readonly",
        ).pack(side="left", padx=(4, 12))

        tk.Label(ctrl, text="Company:", fg=C["text"], bg=C["bg"]).pack(side="left")
        self.dash_company = tk.StringVar(value="(all)")
        ttk.Combobox(
            ctrl, textvariable=self.dash_company,
            values=["(all)"] + self.config.company_keys(),
            width=10, state="readonly",
        ).pack(side="left", padx=(4, 12))

        tk.Label(ctrl, text="Status:", fg=C["text"], bg=C["bg"]).pack(side="left")
        self.dash_status = tk.StringVar(value="(all)")
        ttk.Combobox(
            ctrl, textvariable=self.dash_status,
            values=["(all)", "draft", "issued", "voided"],
            width=10, state="readonly",
        ).pack(side="left", padx=(4, 12))

        tk.Label(ctrl, text="Search:", fg=C["text"], bg=C["bg"]).pack(side="left")
        self.dash_search = tk.StringVar()
        search_entry = tk.Entry(
            ctrl, textvariable=self.dash_search, width=20,
            bg=C["bg_input"], fg=C["text"], insertbackground=C["text"],
            relief=tk.FLAT,
        )
        search_entry.pack(side="left", padx=(4, 12))
        search_entry.bind("<Return>", lambda e: self._refresh_dashboard())

        self._mk_button(ctrl, "Apply", self._refresh_dashboard).pack(side="left")
        self._mk_button(ctrl, "↻ Reload", self._refresh_dashboard).pack(side="left", padx=(8, 0))
        self._mk_button(ctrl, "Health check", self._run_health_check).pack(side="left", padx=(8, 0))
        self._mk_button(ctrl, "🔄  Sync from WooCommerce",
                        self._sync_from_woocommerce
                        ).pack(side="left", padx=(8, 0))

        # Treeview
        tree_frame = tk.Frame(tab, bg=C["bg"])
        tree_frame.pack(fill="both", expand=True, padx=8, pady=4)

        cols = ("number", "year", "company", "date", "customer", "total",
                "status", "source")
        self.dash_tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings",
            style="Invoice.Treeview",
        )
        for c, w, anchor in [
            ("number", 80, "center"),
            ("year", 60, "center"),
            ("company", 90, "center"),
            ("date", 100, "w"),
            ("customer", 280, "w"),
            ("total", 110, "e"),
            ("status", 80, "center"),
            ("source", 100, "center"),
        ]:
            self.dash_tree.heading(c, text=c.capitalize())
            self.dash_tree.column(c, width=w, anchor=anchor, stretch=(c == "customer"))

        self.dash_tree.tag_configure("draft", foreground="#d29922")
        self.dash_tree.tag_configure("issued", foreground="#3fb950")
        self.dash_tree.tag_configure("voided", foreground="#8b949e",
                                     font=("Arial", 10, "overstrike"))

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.dash_tree.yview)
        self.dash_tree.configure(yscrollcommand=sb.set)
        self.dash_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.dash_tree.bind("<Double-1>", self._on_dashboard_row_activate)

        # Action bar
        actions = tk.Frame(tab, bg=C["bg"])
        actions.pack(fill="x", padx=8, pady=(4, 8))
        self._mk_button(actions, "Open PDF", self._open_selected_pdf).pack(side="left")
        self._mk_button(actions, "Open folder",
                        self._open_selected_folder).pack(side="left", padx=(8, 0))
        self._mk_button(actions, "Void…",
                        self._void_selected).pack(side="left", padx=(8, 0))

    def _refresh_dashboard(self):
        year_s = self.dash_year.get()
        year = int(year_s) if year_s.isdigit() else None
        company = (self.dash_company.get()
                   if self.dash_company.get() != "(all)" else None)
        status = (self.dash_status.get()
                  if self.dash_status.get() != "(all)" else None)
        search = self.dash_search.get().strip() or None

        for iid in self.dash_tree.get_children():
            self.dash_tree.delete(iid)

        rows = self.registry.list_invoices(
            year=year, company_key=company, status=status, search=search,
        )
        for r in rows:
            number = f"{r['sequence']:03d}"
            self.dash_tree.insert(
                "", "end", iid=str(r["id"]),
                values=(
                    number, r["year"], r["company_key"], r["invoice_date"],
                    r["customer_name"],
                    format_money(r["total_cents"], r["currency"]),
                    r["status"], r["source"],
                ),
                tags=(r["status"],),
            )

    def _selected_invoice_id(self) -> Optional[int]:
        sel = self.dash_tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except (TypeError, ValueError):
            return None

    def _on_dashboard_row_activate(self, _event):
        self._open_selected_pdf()

    def _open_selected_pdf(self):
        inv_id = self._selected_invoice_id()
        if inv_id is None:
            return
        inv = self.registry.get_by_id(inv_id)
        if not inv or not inv.get("pdf_path"):
            messagebox.showinfo("Open PDF", "This invoice has no filed PDF.")
            return
        _open_path(inv["pdf_path"])

    def _open_selected_folder(self):
        inv_id = self._selected_invoice_id()
        if inv_id is None:
            return
        inv = self.registry.get_by_id(inv_id)
        if not inv or not inv.get("pdf_path"):
            messagebox.showinfo("Open folder", "This invoice has no filed PDF.")
            return
        _open_path(Path(inv["pdf_path"]).parent)

    def _void_selected(self):
        inv_id = self._selected_invoice_id()
        if inv_id is None:
            return
        inv = self.registry.get_by_id(inv_id)
        if not inv:
            return
        if inv["status"] == "voided":
            messagebox.showinfo("Void", "This invoice is already voided.")
            return
        reason = simpledialog.askstring(
            "Void invoice",
            f"Void invoice {inv['sequence']:03d} (year {inv['year']})?\n"
            f"Belgian law requires keeping the number — it will be marked "
            f"voided but not removed.\n\nReason:",
            parent=self.root,
        )
        if not reason:
            return
        self.registry.void_invoice(inv_id, reason)
        self._refresh_dashboard()

    def _run_health_check(self):
        warnings = self.registry.health_check()
        if not warnings:
            messagebox.showinfo("Health check", "✅ All years have gapless numbering.")
        else:
            messagebox.showwarning(
                "Health check — warnings",
                "\n\n".join(warnings),
            )

    def _sync_from_woocommerce(self):
        """Import invoices that already exist in WooCommerce into the registry.

        Safe to re-run: the import is keyed on (source='woocommerce',
        source_ref=order_id), so already-imported orders are skipped.
        """
        creds = self.config.get_wc_credentials_for_alles3d()
        if not creds:
            messagebox.showerror(
                "Sync from WooCommerce",
                "No WooCommerce credentials configured.\n\n"
                "Company '3D' must have a wc_binding in config.json "
                "(set use_monitor_config=true to share credentials with "
                "the WooCommerce monitor).",
            )
            return

        ok = messagebox.askyesno(
            "Sync from WooCommerce",
            "This will fetch every WooCommerce order and import any that "
            "already have a WCPDF invoice number into the registry, using "
            "the original WC number.\n\n"
            "It is idempotent — already-imported invoices are skipped.\n\n"
            "Continue?",
        )
        if not ok:
            return

        try:
            bridge = WooCommerceBridge(creds)
        except WCBridgeError as e:
            messagebox.showerror("Sync from WooCommerce", str(e))
            return

        try:
            default_vat_rate = self.config.get_company("3D").default_vat_rate
        except KeyError:
            default_vat_rate = 21.0

        self._set_busy(True)
        threading.Thread(
            target=self._sync_worker,
            args=(bridge, default_vat_rate),
            daemon=True,
        ).start()

    def _sync_worker(self, bridge: WooCommerceBridge, default_vat_rate: float):
        try:
            report = sync_woocommerce_invoices(
                self.registry, bridge,
                company_key="3D",
                default_vat_rate=default_vat_rate,
                progress=lambda msg: logger.info(msg),
            )
            self.root.after(0, self._on_sync_done, report, None)
        except Exception as e:
            logger.exception("WooCommerce sync failed")
            self.root.after(0, self._on_sync_done, None, str(e))
        finally:
            self.root.after(0, self._set_busy, False)

    def _on_sync_done(self, report, error: Optional[str]):
        if error:
            messagebox.showerror(
                "Sync from WooCommerce",
                f"Sync failed:\n\n{error}",
            )
            return
        self._refresh_dashboard()
        self._refresh_preview()
        title = "Sync from WooCommerce — done"
        if report.conflicts or report.errors:
            messagebox.showwarning(title, report.as_text())
        else:
            messagebox.showinfo(title, report.as_text())

    # =====================================================================
    # New Invoice tab
    # =====================================================================

    def _build_new_invoice_tab(self):
        C = FORM_COLORS
        tab = tk.Frame(self.notebook, bg=C["bg"])
        self.notebook.add(tab, text="➕  New Invoice")

        # Two columns: left = customer/meta, right = line items + totals
        left = tk.Frame(tab, bg=C["bg"])
        left.pack(side="left", fill="both", expand=False, padx=8, pady=8)

        right = tk.Frame(tab, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        # --- left column ---
        self._new_company = tk.StringVar()
        self._new_year = tk.StringVar(value=str(datetime.now().year))
        self._new_date = tk.StringVar(value=date.today().isoformat())
        self._new_customer = tk.StringVar()
        self._new_customer_vat = tk.StringVar()
        self._new_customer_email = tk.StringVar()
        self._new_notes = tk.StringVar()

        row = 0
        tk.Label(left, text="Company", fg=C["text"], bg=C["bg"]
                 ).grid(row=row, column=0, sticky="w", pady=(0, 2))
        company_combo = ttk.Combobox(
            left, textvariable=self._new_company, state="readonly", width=28,
            values=[f"{c.key} — {c.display_name}" for c in self.config.companies
                    if c.uses_libreoffice],
        )
        company_combo.grid(row=row, column=1, sticky="we", pady=(0, 2))
        if company_combo["values"]:
            company_combo.current(0)
        row += 1

        tk.Label(left, text="Invoice year", fg=C["text"], bg=C["bg"]
                 ).grid(row=row, column=0, sticky="w", pady=(8, 2))
        spin = tk.Spinbox(
            left, textvariable=self._new_year, from_=2000, to=2100, width=8,
            bg=C["bg_input"], fg=C["text"], insertbackground=C["text"],
            relief=tk.FLAT,
        )
        spin.grid(row=row, column=1, sticky="w", pady=(8, 2))
        row += 1

        tk.Label(left, text="Invoice date (YYYY-MM-DD)", fg=C["text"], bg=C["bg"]
                 ).grid(row=row, column=0, sticky="w", pady=(8, 2))
        tk.Entry(left, textvariable=self._new_date, width=20,
                 bg=C["bg_input"], fg=C["text"], insertbackground=C["text"],
                 relief=tk.FLAT,
                 ).grid(row=row, column=1, sticky="w", pady=(8, 2))
        row += 1

        tk.Label(left, text="Customer", fg=C["text"], bg=C["bg"]
                 ).grid(row=row, column=0, sticky="w", pady=(12, 2))
        tk.Entry(left, textvariable=self._new_customer, width=36,
                 bg=C["bg_input"], fg=C["text"], insertbackground=C["text"],
                 relief=tk.FLAT,
                 ).grid(row=row, column=1, sticky="we", pady=(12, 2))
        row += 1

        tk.Label(left, text="Customer VAT", fg=C["text"], bg=C["bg"]
                 ).grid(row=row, column=0, sticky="w", pady=(4, 2))
        tk.Entry(left, textvariable=self._new_customer_vat, width=36,
                 bg=C["bg_input"], fg=C["text"], insertbackground=C["text"],
                 relief=tk.FLAT,
                 ).grid(row=row, column=1, sticky="we", pady=(4, 2))
        row += 1

        tk.Label(left, text="Customer email", fg=C["text"], bg=C["bg"]
                 ).grid(row=row, column=0, sticky="w", pady=(4, 2))
        tk.Entry(left, textvariable=self._new_customer_email, width=36,
                 bg=C["bg_input"], fg=C["text"], insertbackground=C["text"],
                 relief=tk.FLAT,
                 ).grid(row=row, column=1, sticky="we", pady=(4, 2))
        row += 1

        tk.Label(left, text="Customer address", fg=C["text"], bg=C["bg"]
                 ).grid(row=row, column=0, sticky="nw", pady=(4, 2))
        self._new_addr = tk.Text(
            left, height=4, width=36, wrap="word",
            bg=C["bg_input"], fg=C["text"], insertbackground=C["text"],
            relief=tk.FLAT,
        )
        self._new_addr.grid(row=row, column=1, sticky="we", pady=(4, 2))
        row += 1

        tk.Label(left, text="Notes", fg=C["text"], bg=C["bg"]
                 ).grid(row=row, column=0, sticky="w", pady=(4, 2))
        tk.Entry(left, textvariable=self._new_notes, width=36,
                 bg=C["bg_input"], fg=C["text"], insertbackground=C["text"],
                 relief=tk.FLAT,
                 ).grid(row=row, column=1, sticky="we", pady=(4, 2))
        row += 1

        # Next-number preview
        self._preview_var = tk.StringVar(value="")
        self._refresh_preview()
        tk.Label(left, textvariable=self._preview_var,
                 fg=C["accent"], bg=C["bg"], font=("Arial", 11, "bold"),
                 ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(16, 4))
        self._new_year.trace_add("write", lambda *_: self._refresh_preview())
        row += 1

        # --- right column: line items grid + totals ---
        tk.Label(right, text="Work items",
                 fg=C["text"], bg=C["bg"], font=("Arial", 11, "bold"),
                 ).pack(anchor="w")

        li_frame = tk.Frame(right, bg=C["bg"])
        li_frame.pack(fill="both", expand=True, pady=(4, 0))

        li_cols = ("description", "qty", "unit_price", "vat_rate", "line_total")
        self.li_tree = ttk.Treeview(
            li_frame, columns=li_cols, show="headings",
            style="Invoice.Treeview", height=7,
        )
        for c, w, anchor in [
            ("description", 280, "w"),
            ("qty", 60, "e"),
            ("unit_price", 110, "e"),
            ("vat_rate", 70, "e"),
            ("line_total", 110, "e"),
        ]:
            self.li_tree.heading(c, text=c.replace("_", " ").capitalize())
            self.li_tree.column(c, width=w, anchor=anchor,
                                stretch=(c == "description"))
        li_sb = ttk.Scrollbar(li_frame, orient="vertical",
                              command=self.li_tree.yview)
        self.li_tree.configure(yscrollcommand=li_sb.set)
        self.li_tree.pack(side="left", fill="both", expand=True)
        li_sb.pack(side="right", fill="y")
        self.li_tree.bind("<Double-1>", lambda _e: self._edit_line_item())

        self._line_items: List[LineItem] = []

        li_btns = tk.Frame(right, bg=C["bg"])
        li_btns.pack(fill="x", pady=(4, 4))
        self._mk_button(li_btns, "Add", self._add_line_item).pack(side="left")
        self._mk_button(li_btns, "Edit", self._edit_line_item
                        ).pack(side="left", padx=(6, 0))
        self._mk_button(li_btns, "Remove", self._remove_line_item
                        ).pack(side="left", padx=(6, 0))

        # --- Onkosten (expenses) section ---
        sep = tk.Frame(right, bg=C["text_dim"], height=1)
        sep.pack(fill="x", pady=(6, 4))

        self._show_onkosten = tk.BooleanVar(value=False)
        tk.Checkbutton(
            right, text="Include expenses (Onkosten)",
            variable=self._show_onkosten,
            command=self._toggle_onkosten,
            fg=C["text"], bg=C["bg"],
            activeforeground=C["text"], activebackground=C["bg"],
            selectcolor=C["bg_input"],
        ).pack(anchor="w")

        # Container that is always packed; content is shown/hidden inside it.
        self._exp_wrapper = tk.Frame(right, bg=C["bg"])
        self._exp_wrapper.pack(fill="both", expand=False)

        self._exp_items_frame = tk.Frame(self._exp_wrapper, bg=C["bg"])
        tk.Label(self._exp_items_frame, text="Expense items",
                 fg=C["text"], bg=C["bg"], font=("Arial", 11, "bold"),
                 ).pack(anchor="w", pady=(4, 0))

        exp_tree_frame = tk.Frame(self._exp_items_frame, bg=C["bg"])
        exp_tree_frame.pack(fill="both", expand=True, pady=(4, 0))

        self.exp_tree = ttk.Treeview(
            exp_tree_frame, columns=li_cols, show="headings",
            style="Invoice.Treeview", height=5,
        )
        for c, w, anchor in [
            ("description", 280, "w"),
            ("qty", 60, "e"),
            ("unit_price", 110, "e"),
            ("vat_rate", 70, "e"),
            ("line_total", 110, "e"),
        ]:
            self.exp_tree.heading(c, text=c.replace("_", " ").capitalize())
            self.exp_tree.column(c, width=w, anchor=anchor,
                                 stretch=(c == "description"))
        exp_sb = ttk.Scrollbar(exp_tree_frame, orient="vertical",
                               command=self.exp_tree.yview)
        self.exp_tree.configure(yscrollcommand=exp_sb.set)
        self.exp_tree.pack(side="left", fill="both", expand=True)
        exp_sb.pack(side="right", fill="y")
        self.exp_tree.bind("<Double-1>", lambda _e: self._edit_expense_item())

        self._expense_items: List[LineItem] = []

        exp_btns = tk.Frame(self._exp_items_frame, bg=C["bg"])
        exp_btns.pack(fill="x", pady=(4, 4))
        self._mk_button(exp_btns, "Add", self._add_expense_item).pack(side="left")
        self._mk_button(exp_btns, "Edit", self._edit_expense_item
                        ).pack(side="left", padx=(6, 0))
        self._mk_button(exp_btns, "Remove", self._remove_expense_item
                        ).pack(side="left", padx=(6, 0))

        # Totals
        totals = tk.Frame(right, bg=C["bg"])
        totals.pack(fill="x", pady=(4, 8))
        self._tot_subtotal = tk.StringVar(value=format_money(0))
        self._tot_vat = tk.StringVar(value=format_money(0))
        self._tot_total = tk.StringVar(value=format_money(0))
        for label, var, font in [
            ("Subtotal:", self._tot_subtotal, ("Arial", 10)),
            ("VAT:", self._tot_vat, ("Arial", 10)),
            ("Total:", self._tot_total, ("Arial", 12, "bold")),
        ]:
            row_frame = tk.Frame(totals, bg=C["bg"])
            row_frame.pack(fill="x")
            tk.Label(row_frame, text=label,
                     fg=C["text_dim"], bg=C["bg"], font=font, width=12,
                     anchor="w").pack(side="left")
            tk.Label(row_frame, textvariable=var,
                     fg=C["text"], bg=C["bg"], font=font,
                     anchor="e").pack(side="right")

        # Action footer
        actions = tk.Frame(right, bg=C["bg"])
        actions.pack(fill="x", pady=(8, 0))
        self._mk_button(actions, "Generate PDF",
                        self._generate_invoice, primary=True).pack(side="right")
        self._mk_button(actions, "Reset form",
                        self._reset_new_invoice_form).pack(side="right", padx=(0, 8))

    def _refresh_preview(self):
        try:
            year = int(self._new_year.get())
        except ValueError:
            self._preview_var.set("Next number: —")
            return
        nxt = self.registry.get_next_preview(year)
        self._preview_var.set(f"Next number for {year}: {nxt:03d}")

    def _add_line_item(self):
        company = self._current_company()
        default_rate = company.default_vat_rate if company else 21.0
        item = LineItemDialog(self.root, default_vat_rate=default_rate).result
        if item is None:
            return
        self._line_items.append(item)
        self._refresh_line_items()

    def _edit_line_item(self):
        sel = self.li_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        existing = self._line_items[idx]
        item = LineItemDialog(self.root, existing=existing).result
        if item is None:
            return
        self._line_items[idx] = item
        self._refresh_line_items()

    def _remove_line_item(self):
        sel = self.li_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        del self._line_items[idx]
        self._refresh_line_items()

    # --- Onkosten toggle ---

    def _toggle_onkosten(self):
        if self._show_onkosten.get():
            self._exp_items_frame.pack(fill="both", expand=True)
        else:
            self._exp_items_frame.pack_forget()
            self._expense_items = []
            self._refresh_expense_items()

    # --- Expense item CRUD ---

    def _add_expense_item(self):
        company = self._current_company()
        default_rate = company.default_vat_rate if company else 21.0
        item = LineItemDialog(self.root, default_vat_rate=default_rate).result
        if item is None:
            return
        self._expense_items.append(item)
        self._refresh_expense_items()

    def _edit_expense_item(self):
        sel = self.exp_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        item = LineItemDialog(self.root, existing=self._expense_items[idx]).result
        if item is None:
            return
        self._expense_items[idx] = item
        self._refresh_expense_items()

    def _remove_expense_item(self):
        sel = self.exp_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        del self._expense_items[idx]
        self._refresh_expense_items()

    def _refresh_expense_items(self):
        for iid in self.exp_tree.get_children():
            self.exp_tree.delete(iid)
        for idx, li in enumerate(self._expense_items):
            self.exp_tree.insert(
                "", "end", iid=str(idx),
                values=(
                    li.description,
                    f"{li.quantity:g}",
                    format_money_plain(li.unit_price_cents),
                    f"{li.vat_rate:g}%",
                    format_money_plain(li.line_total_cents),
                ),
            )
        self._refresh_totals()

    def _refresh_line_items(self):
        for iid in self.li_tree.get_children():
            self.li_tree.delete(iid)
        for idx, li in enumerate(self._line_items):
            self.li_tree.insert(
                "", "end", iid=str(idx),
                values=(
                    li.description,
                    f"{li.quantity:g}",
                    format_money_plain(li.unit_price_cents),
                    f"{li.vat_rate:g}%",
                    format_money_plain(li.line_total_cents),
                ),
            )
        self._refresh_totals()

    def _refresh_totals(self):
        all_items = self._line_items + self._expense_items
        subtotal = sum(li.line_subtotal_cents for li in all_items)
        vat = sum(li.line_vat_cents for li in all_items)
        total = subtotal + vat
        self._tot_subtotal.set(format_money(subtotal))
        self._tot_vat.set(format_money(vat))
        self._tot_total.set(format_money(total))

    def _reset_new_invoice_form(self):
        self._new_customer.set("")
        self._new_customer_vat.set("")
        self._new_customer_email.set("")
        self._new_notes.set("")
        self._new_addr.delete("1.0", "end")
        self._new_date.set(date.today().isoformat())
        self._new_year.set(str(datetime.now().year))
        self._line_items = []
        self._expense_items = []
        self._show_onkosten.set(False)
        self._exp_items_frame.pack_forget()
        self._refresh_line_items()
        self._refresh_expense_items()
        self._refresh_preview()

    def _current_company(self) -> Optional[Company]:
        sel = self._new_company.get()
        if not sel:
            return None
        key = sel.split(" — ", 1)[0]
        try:
            return self.config.get_company(key)
        except KeyError:
            return None

    # ----- Generate PDF flow -----

    def _generate_invoice(self):
        company = self._current_company()
        if not company:
            messagebox.showerror("New invoice", "Please pick a company.")
            return
        if not company.uses_libreoffice:
            messagebox.showerror(
                "New invoice",
                f"Company {company.key} is not configured for LibreOffice "
                f"rendering. Use the WooCommerce flow instead.",
            )
            return

        customer = self._new_customer.get().strip()
        if not customer:
            messagebox.showerror("New invoice", "Customer name is required.")
            return
        if not self._line_items:
            messagebox.showerror("New invoice", "Add at least one line item.")
            return

        try:
            year = int(self._new_year.get())
            invoice_date_str = self._new_date.get().strip()
            datetime.strptime(invoice_date_str, "%Y-%m-%d")
        except ValueError as e:
            messagebox.showerror("New invoice", f"Invalid year or date: {e}")
            return

        cur_year = datetime.now().year
        if year < cur_year - self.config.year_change_confirm_threshold:
            ok = messagebox.askyesno(
                "Confirm old year",
                f"You picked year {year}, which is more than "
                f"{self.config.year_change_confirm_threshold} year(s) before "
                f"the current year ({cur_year}).\n\nProceed?",
            )
            if not ok:
                return

        template_path = self.config.resolve_template_path(company)
        if not template_path or not template_path.exists():
            messagebox.showerror(
                "Template missing",
                f"Template not found for {company.display_name}.\n"
                f"Expected: {template_path}\n\n"
                f"Place a .ott file there with the placeholders described in "
                f"templates/invoice_templates_ott/README.txt.",
            )
            return

        # Disable the button to prevent re-entry while soffice runs
        # (use threading; the registry write is fast but the conversion is slow)
        debug_mode = self.debug_session.is_active()
        self._set_busy(True)
        threading.Thread(
            target=self._generate_invoice_worker,
            args=(company, year, invoice_date_str, customer, template_path,
                  debug_mode),
            daemon=True,
        ).start()

    def _generate_invoice_worker(
        self,
        company: Company,
        year: int,
        invoice_date_str: str,
        customer: str,
        template_path: Path,
        debug_mode: bool = False,
    ):
        try:
            draft = {
                "company_key": company.key,
                "invoice_date": invoice_date_str,
                "customer_name": customer,
                "customer_vat": self._new_customer_vat.get().strip(),
                "customer_email": self._new_customer_email.get().strip(),
                "customer_address": self._new_addr.get("1.0", "end").strip(),
                "line_items": self._line_items,
                "expense_items": self._expense_items,
                "currency": self.config.currency,
                "source": "manual",
                "source_ref": None,
                "notes": self._new_notes.get().strip(),
            }
            # 1) Atomically reserve the next number + persist a draft row
            row = self.registry.reserve_and_return_row(year, draft)
            invoice_id = row["id"]
            sequence = row["sequence"]
            logger.info(
                f"Reserved invoice #{sequence:03d} ({year}) for "
                f"{company.key} / {customer}"
            )

            # 2) Build template context + render to ODT in temp dir
            ctx = self._build_template_context(company, row)

            def _li_ctx(items):
                return [
                    {
                        "desc": li.description,
                        "qty": f"{li.quantity:g}",
                        "unit_price": format_money_plain(li.unit_price_cents),
                        "vat_rate": f"{li.vat_rate:g}%",
                        "line_total": format_money_plain(li.line_total_cents),
                    }
                    for li in items
                ]

            with tempfile.TemporaryDirectory(prefix="gi_render_") as td:
                tmp_odt = Path(td) / f"{template_path.stem}_{sequence:03d}.odt"
                render_odt(
                    template_path, tmp_odt, ctx,
                    _li_ctx(self._line_items),
                    expense_items=_li_ctx(self._expense_items),
                )

                # 3) Convert to PDF
                soffice = self.config.resolve_soffice_path()
                pdf_tmp = odt_to_pdf(tmp_odt, Path(td), soffice_path=soffice)

                # 4) File into Boekhouding (or its _DEBUG sibling in debug mode)
                boekhouding_base = self.config.resolve_boekhouding_base()
                if debug_mode:
                    boekhouding_base = debug_boekhouding_base(boekhouding_base)
                final_pdf = file_pdf(
                    pdf_tmp, boekhouding_base, company.output_prefix,
                    invoice_date_str, sequence, customer, move=True,
                )

            # 5) Mark issued
            self.registry.finalize_invoice(invoice_id, str(final_pdf))

            # 6) Notify on the UI thread
            self.root.after(0, self._on_generate_success, final_pdf, debug_mode)
        except (TemplateError, PdfExportError) as e:
            logger.exception("Render failed")
            self.root.after(0, self._on_generate_failure,
                            f"Rendering failed:\n\n{e}\n\nThe draft row was "
                            f"kept in the registry — fix the issue and retry "
                            f"with the same number via Dashboard.")
        except Exception as e:
            logger.exception("Generate invoice failed")
            self.root.after(0, self._on_generate_failure,
                            f"Failed to generate invoice:\n\n{e}")
        finally:
            self.root.after(0, self._set_busy, False)

    def _build_template_context(self, company: Company, row: Dict[str, Any]
                                ) -> Dict[str, str]:
        addr_lines = [l for l in (row["customer_address"] or "").splitlines() if l.strip()]
        addr1 = addr_lines[0] if len(addr_lines) > 0 else ""
        addr2 = addr_lines[1] if len(addr_lines) > 1 else ""
        addr3 = addr_lines[2] if len(addr_lines) > 2 else ""

        inv_date = datetime.strptime(row["invoice_date"], "%Y-%m-%d").date()
        from datetime import timedelta
        due_date = (inv_date + timedelta(days=30)).strftime("%d/%m/%Y")

        return {
            "invoice_number": f"{row['sequence']:03d}",
            "invoice_year": str(row["year"]),
            "invoice_date": inv_date.strftime("%d/%m/%Y"),
            "due_date": due_date,
            "company_legal_name": company.legal_name,
            "company_vat": company.vat,
            "company_address": company.address_block,
            "company_email": company.email,
            "company_iban": company.iban,
            "company_bic": company.bic,
            "customer_name": row["customer_name"],
            "customer_vat": row["customer_vat"] or "",
            "customer_address": row["customer_address"] or "",
            "customer_address_1": addr1,
            "customer_address_2": addr2,
            "customer_address_3": addr3,
            "customer_email": row["customer_email"] or "",
            "subtotal": format_money(row["subtotal_cents"], row["currency"]),
            "vat": format_money(row["vat_cents"], row["currency"]),
            "total": format_money(row["total_cents"], row["currency"]),
            "currency": row["currency"],
            "notes": row.get("notes", ""),
        }

    def _on_generate_success(self, final_pdf: Path, debug_mode: bool = False):
        if debug_mode and self.debug_session.is_active():
            try:
                self.debug_session.record_pdf(final_pdf)
            except Exception as e:
                logger.warning(f"Could not record debug PDF {final_pdf}: {e}")
        self._refresh_dashboard()
        self._refresh_preview()
        if self.config.auto_open_pdf_after_generate:
            _open_path(final_pdf)
        else:
            messagebox.showinfo(
                "Invoice generated",
                f"Saved to:\n{final_pdf}",
            )
        self._reset_new_invoice_form()

    def _on_generate_failure(self, msg: str):
        self._refresh_dashboard()
        self._refresh_preview()
        messagebox.showerror("Generate invoice", msg)

    def _set_busy(self, busy: bool):
        cursor = "watch" if busy else ""
        try:
            self.root.configure(cursor=cursor)
        except tk.TclError:
            pass

    # =====================================================================
    # Companies tab
    # =====================================================================

    def _build_companies_tab(self):
        C = FORM_COLORS
        tab = tk.Frame(self.notebook, bg=C["bg"])
        self.notebook.add(tab, text="🏢  Companies")

        wrap = tk.Frame(tab, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=12, pady=12)

        text = tk.Text(wrap, wrap="word",
                       bg=C["bg_input"], fg=C["text"],
                       insertbackground=C["text"], relief=tk.FLAT)
        text.pack(fill="both", expand=True)

        lines = []
        for c in self.config.companies:
            lines.append(f"━━━ {c.key} — {c.display_name} ━━━")
            lines.append(f"  Legal name:  {c.legal_name}")
            lines.append(f"  VAT:         {c.vat}")
            lines.append(f"  Address:     {c.address_block.replace(chr(10), ' / ')}")
            lines.append(f"  Email:       {c.email}")
            lines.append(f"  IBAN:        {c.iban}")
            lines.append(f"  Output prefix: {c.output_prefix}")
            lines.append(f"  Default VAT:   {c.default_vat_rate}%")
            lines.append(f"  Template:    {c.template_path or '(none — uses WooCommerce)'}")
            lines.append(f"  WC binding:  {bool(c.wc_binding)}")
            lines.append("")
        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")

        actions = tk.Frame(tab, bg=C["bg"])
        actions.pack(fill="x", padx=12, pady=(0, 12))
        self._mk_button(
            actions, "Open config.json in editor",
            lambda: _open_path(self.config.source_path),
        ).pack(side="left")

    # =====================================================================
    # Settings tab
    # =====================================================================

    def _build_settings_tab(self):
        C = FORM_COLORS
        tab = tk.Frame(self.notebook, bg=C["bg"])
        self.notebook.add(tab, text="⚙  Settings")

        wrap = tk.Frame(tab, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=20, pady=20)

        soffice = self.config.resolve_soffice_path()
        boek = self.config.resolve_boekhouding_base()
        db = self.config.resolve_db_path()

        rows = [
            ("DB path", str(db), db.exists()),
            ("Boekhouding base", str(boek), boek.exists()),
            ("soffice binary", str(soffice or "(not found)"),
             bool(soffice and soffice.exists())),
        ]
        for label, value, ok in rows:
            r = tk.Frame(wrap, bg=C["bg"])
            r.pack(fill="x", pady=4)
            tk.Label(r, text=label, fg=C["text_dim"], bg=C["bg"],
                     width=22, anchor="w").pack(side="left")
            tk.Label(r, text=value,
                     fg=(C["success"] if ok else C["warning"]),
                     bg=C["bg"], anchor="w").pack(side="left")

        self._mk_button(wrap, "Open config.json",
                        lambda: _open_path(self.config.source_path)
                        ).pack(anchor="w", pady=(16, 4))
        self._mk_button(wrap, "Open data folder",
                        lambda: _open_path(self.config.source_path.parent)
                        ).pack(anchor="w", pady=4)
        self._mk_button(wrap, "Open templates folder",
                        self._open_templates_folder).pack(anchor="w", pady=4)
        self._mk_button(wrap, "Run health check",
                        self._run_health_check).pack(anchor="w", pady=4)

        # --- Debug mode section ----------------------------------------
        sep = tk.Frame(wrap, bg=C["border"], height=1)
        sep.pack(fill="x", pady=(20, 12))

        tk.Label(wrap, text="Debug mode",
                 fg=C["text"], bg=C["bg"], font=("Arial", 12, "bold")
                 ).pack(anchor="w")
        tk.Label(
            wrap,
            text=("Snapshots the invoice DB and files test invoices into "
                  f"Boekhouding/{DEBUG_SUBFOLDER_NAME}/. Exit restores the DB "
                  "and deletes the test PDFs, returning everything to the "
                  "pre-debug state."),
            fg=C["text_dim"], bg=C["bg"], wraplength=720, justify="left",
        ).pack(anchor="w", pady=(2, 8))

        self._debug_status_var = tk.StringVar(value="")
        tk.Label(wrap, textvariable=self._debug_status_var,
                 fg=C["text"], bg=C["bg"], font=("Arial", 10)
                 ).pack(anchor="w", pady=(0, 6))

        debug_btns = tk.Frame(wrap, bg=C["bg"])
        debug_btns.pack(anchor="w")
        self._enter_debug_btn = self._mk_button(
            debug_btns, "🐛  Enter debug mode", self._enter_debug_mode,
        )
        self._enter_debug_btn.pack(side="left")
        self._exit_debug_btn = self._mk_button(
            debug_btns, "Exit debug mode", self._exit_debug_mode,
        )
        self._exit_debug_btn.pack(side="left", padx=(8, 0))

    # =====================================================================
    # Debug mode
    # =====================================================================

    def _open_templates_folder(self):
        templates_dir = self.config.resolve_templates_dir()
        if not templates_dir.exists():
            messagebox.showinfo(
                "Templates folder",
                f"Folder does not exist yet:\n{templates_dir}",
            )
            return
        _open_path(templates_dir)

    def _refresh_debug_ui(self):
        active = self.debug_session.is_active()
        if active:
            self._debug_banner_label.configure(
                text=(f"🐛  DEBUG MODE ACTIVE — started "
                      f"{self.debug_session.started_at or '?'} · "
                      f"{len(self.debug_session.created_pdfs)} test PDF(s). "
                      f"Exit restores the DB and deletes test PDFs."),
            )
            self._debug_banner.pack(fill="x", before=self.notebook)
        else:
            self._debug_banner.pack_forget()
        # Settings-tab status + button enable/disable
        if hasattr(self, "_debug_status_var"):
            if active:
                self._debug_status_var.set(
                    f"Status: ACTIVE since {self.debug_session.started_at} · "
                    f"{len(self.debug_session.created_pdfs)} test PDF(s) so far"
                )
            else:
                self._debug_status_var.set("Status: inactive")
        if hasattr(self, "_enter_debug_btn"):
            self._enter_debug_btn.configure(
                state=("disabled" if active else "normal"),
            )
            self._exit_debug_btn.configure(
                state=("normal" if active else "disabled"),
            )

    def _enter_debug_mode(self):
        if self.debug_session.is_active():
            return
        ok = messagebox.askyesno(
            "Enter debug mode",
            "Snapshot the invoice DB and switch to debug mode?\n\n"
            "While active:\n"
            f"  • Test invoices are filed into Boekhouding/{DEBUG_SUBFOLDER_NAME}/\n"
            "  • The DB still records each invoice as if it were real\n"
            "  • Exiting restores the DB snapshot and deletes the test PDFs\n\n"
            "Continue?",
        )
        if not ok:
            return
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = DATA_DIR / f"invoices.sqlite.debug_{ts}.bak"
            self.registry.backup_db(backup_path)
            self.debug_session.start(backup_path)
        except Exception as e:
            logger.exception("Failed to start debug session")
            messagebox.showerror(
                "Enter debug mode", f"Could not start debug session:\n\n{e}",
            )
            return
        self._refresh_debug_ui()
        messagebox.showinfo(
            "Debug mode",
            "Debug mode is now ACTIVE.\n\n"
            "Generate as many test invoices as you like — they will not "
            "permanently change numbering or your Boekhouding tree.",
        )

    def _exit_debug_mode(self):
        if not self.debug_session.is_active():
            return
        pdf_count = len(self.debug_session.created_pdfs)
        ok = messagebox.askyesno(
            "Exit debug mode",
            f"Exit debug mode and roll back everything?\n\n"
            f"This will:\n"
            f"  • Restore the invoice DB from the snapshot\n"
            f"  • Delete {pdf_count} test PDF(s) from "
            f"Boekhouding/{DEBUG_SUBFOLDER_NAME}/\n\n"
            f"Continue?",
        )
        if not ok:
            return
        report = self._perform_debug_rollback()
        self._refresh_debug_ui()
        self._refresh_dashboard()
        self._refresh_preview()
        messagebox.showinfo("Exit debug mode", report)

    def _perform_debug_rollback(self) -> str:
        """Restore the DB snapshot, delete tracked PDFs, clear the session.

        Returns a human-readable summary suitable for a messagebox.
        """
        backup = self.debug_session.db_backup_path
        pdfs = self.debug_session.created_pdfs
        lines: List[str] = []

        # 1) Restore DB
        if backup and backup.exists():
            try:
                self.registry.restore_db(backup)
                lines.append(f"✅  DB restored from {backup.name}")
            except Exception as e:
                logger.exception("DB restore failed")
                lines.append(f"⚠️  DB restore FAILED: {e}")
        else:
            lines.append("⚠️  DB backup missing — could not restore.")

        # 2) Delete tracked PDFs
        result = cleanup_debug_pdfs(pdfs)
        if result["deleted"]:
            lines.append(f"✅  Deleted {len(result['deleted'])} test PDF(s)")
        if result["missing"]:
            lines.append(f"ℹ️  {len(result['missing'])} PDF(s) already gone")
        if result["failed"]:
            lines.append(
                f"⚠️  {len(result['failed'])} PDF(s) could not be deleted "
                f"(may be open in a viewer):\n  - "
                + "\n  - ".join(result["failed"][:5])
            )

        # 3) Remove DB backup file
        if backup and backup.exists():
            try:
                backup.unlink()
            except OSError as e:
                logger.warning(f"Could not remove DB backup {backup}: {e}")

        # 4) Clear the session marker
        self.debug_session.clear()
        return "\n".join(lines) if lines else "Nothing to do."

    def _check_orphaned_debug_session(self):
        """If the marker file says we were mid-session at shutdown, ask the user."""
        if not self.debug_session.is_active():
            return
        backup = self.debug_session.db_backup_path
        if not backup or not backup.exists():
            # Stale marker pointing at a missing backup — just clear it.
            logger.warning("Stale debug marker with missing backup; clearing.")
            self.debug_session.clear()
            self._refresh_debug_ui()
            return
        started = self.debug_session.started_at or "(unknown time)"
        pdf_count = len(self.debug_session.created_pdfs)
        choice = messagebox.askyesnocancel(
            "Debug session was interrupted",
            f"A debug session from {started} was still active when the "
            f"app last closed.\n\n"
            f"  Snapshot: {backup.name}\n"
            f"  Tracked test PDFs: {pdf_count}\n\n"
            f"YES   — roll back now (restore DB + delete test PDFs)\n"
            f"NO    — keep debug mode active and continue testing\n"
            f"CANCEL — leave things as-is for now",
        )
        if choice is True:
            report = self._perform_debug_rollback()
            messagebox.showinfo("Debug rollback", report)
        # Either way, refresh so the banner/state reflects reality.
        self._refresh_debug_ui()
        self._refresh_dashboard()
        self._refresh_preview()

    # =====================================================================
    # Helpers
    # =====================================================================

    def _mk_button(self, parent, text, command, primary=False):
        C = FORM_COLORS
        bg = C["accent_dark"] if primary else C["bg_input"]
        fg = "white" if primary else C["text"]
        btn = tk.Button(
            parent, text=text, command=command,
            bg=bg, fg=fg,
            activebackground=C["bg_hover"], activeforeground=C["text"],
            relief=tk.FLAT, font=("Arial", 10),
            cursor="hand2", padx=12, pady=4,
        )
        btn.bind("<Enter>", lambda e: e.widget.configure(
            bg=(C["accent_hover"] if primary else C["bg_hover"])))
        btn.bind("<Leave>", lambda e: e.widget.configure(bg=bg))
        return btn


# ============================================================================
# Line item dialog
# ============================================================================

class LineItemDialog:
    """Modal for entering / editing a single line item."""

    def __init__(
        self,
        parent: tk.Widget,
        existing: Optional[LineItem] = None,
        default_vat_rate: float = 21.0,
    ):
        C = FORM_COLORS
        self.result: Optional[LineItem] = None

        self.win = tk.Toplevel(parent)
        self.win.title("Line item")
        self.win.configure(bg=C["bg"])
        self.win.transient(parent)
        self.win.resizable(False, False)
        self.win.grab_set()

        frame = tk.Frame(self.win, bg=C["bg"], padx=16, pady=16)
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
            ("Description", self.desc, 40),
            ("Quantity", self.qty, 10),
            ("Unit price (excl. VAT, EUR)", self.unit, 14),
            ("VAT rate (%)", self.vat_rate, 8),
        ]):
            tk.Label(frame, text=label, fg=C["text"], bg=C["bg"]
                     ).grid(row=i, column=0, sticky="w", pady=4)
            tk.Entry(frame, textvariable=var, width=width,
                     bg=C["bg_input"], fg=C["text"],
                     insertbackground=C["text"], relief=tk.FLAT
                     ).grid(row=i, column=1, sticky="we", pady=4, padx=(8, 0))

        btns = tk.Frame(frame, bg=C["bg"])
        btns.grid(row=99, column=0, columnspan=2, pady=(12, 0), sticky="e")
        tk.Button(btns, text="Cancel", command=self._cancel,
                  bg=C["bg_input"], fg=C["text"], relief=tk.FLAT,
                  padx=10, pady=4).pack(side="right", padx=(8, 0))
        tk.Button(btns, text="OK", command=self._ok,
                  bg=C["accent_dark"], fg="white", relief=tk.FLAT,
                  padx=10, pady=4).pack(side="right")
        self.win.bind("<Return>", lambda _e: self._ok())
        self.win.bind("<Escape>", lambda _e: self._cancel())

        # Centre on parent
        self.win.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        self.win.geometry(f"+{px - w // 2}+{py - h // 2}")

        parent.wait_window(self.win)

    def _ok(self):
        desc = self.desc.get().strip()
        if not desc:
            messagebox.showerror("Line item", "Description is required.",
                                 parent=self.win)
            return
        try:
            qty = float(self.qty.get().replace(",", "."))
            unit_cents = to_cents(self.unit.get())
            vat_rate = float(self.vat_rate.get().replace(",", "."))
        except ValueError as e:
            messagebox.showerror("Line item", f"Invalid number: {e}",
                                 parent=self.win)
            return
        self.result = LineItem(
            description=desc, quantity=qty,
            unit_price_cents=unit_cents, vat_rate=vat_rate,
        )
        self.win.destroy()

    def _cancel(self):
        self.win.destroy()


# ============================================================================
# Cross-platform "open with default app"
# ============================================================================

def _open_path(p):
    p = str(p)
    try:
        if sys.platform == "win32":
            os.startfile(p)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", p])
        else:
            # WSL: try Windows Explorer first for native paths
            if p.startswith(("/mnt/", "\\\\wsl")):
                try:
                    subprocess.Popen(["wslview", p])
                    return
                except FileNotFoundError:
                    pass
            subprocess.Popen(["xdg-open", p])
    except Exception as e:
        logger.warning(f"Could not open {p}: {e}")


# ============================================================================
# Entry point
# ============================================================================

def main():
    setup_shared_logging("global_invoice")
    root = tk.Tk()
    apply_category_icon(root)
    GlobalInvoiceGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
