"""Outgoing — every outgoing invoice ever, in one tree.

Combines two data sources:
  - the InvoiceRegistry (current canonical store)
  - legacy PDFs discovered under Boekhouding/ that aren't yet in the
    registry (only shown when "Show legacy" is enabled)

Each company is rendered as a category header; un-imported legacy PDFs
appear as italic, dim rows under their own "Legacy (not in registry)"
subgroup so the old naming convention is clearly separated from current
invoices. Selecting one or more legacy rows surfaces an "Import →
registry" button in the contextual action bar.
"""

from __future__ import annotations

import tempfile
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Dict, List, Optional, Tuple

from invoice_manager.core.filer import file_pdf, quarter_dir_for, quarter_for
from invoice_manager.core.models import format_money
from invoice_manager.core.wc_bridge import WCBridgeError, WooCommerceBridge
from invoice_manager.core.wc_sync import sync_woocommerce_invoices
from shared_logging import get_logger

from invoice_manager.sections.base import Section
from invoice_manager.theme import PALETTE, FONTS
from invoice_manager.widgets.buttons import primary_button, secondary_button
from invoice_manager.widgets.chip import ChipGroup
from invoice_manager.widgets.inputs import make_entry
from invoice_manager.widgets.tree import make_treeview

logger = get_logger("invoice_manager.outgoing")


class OutgoingSection(Section):
    title = "Outgoing"
    sidebar_key = "outgoing"
    sidebar_icon = "📤"

    QUARTERS = ["q1", "q2", "q3", "q4", "year"]
    LEGACY_IID_PREFIX = "L:"

    def __init__(self, parent, state):
        super().__init__(parent, state)
        self._quarter = state.quarter
        self._invoices: List[Dict] = []
        self._search = tk.StringVar()
        self._status_filter = tk.StringVar(value="All")
        self._show_legacy = tk.BooleanVar(value=False)
        self._legacy_path_to_obj: Dict[str, Any] = {}

        self.state.on_year_change(lambda _y: self.reload())
        self.state.on_quarter_change(self._on_state_quarter_change)
        self.state.on_company_change(
            lambda _c: self._render_tree() if self.frame is not None else None
        )
        self.state.on_legacy_scan(self._on_legacy_scan_done)

    # ----- build -------------------------------------------------------

    def build(self, root: tk.Frame) -> None:
        C = PALETTE
        root.configure(bg=C["bg"])
        wrap = tk.Frame(root, bg=C["bg"], padx=20, pady=14)
        wrap.pack(fill="both", expand=True)

        # Filter row 1 — quarter chips + search
        row1 = tk.Frame(wrap, bg=C["bg"])
        row1.pack(fill="x")
        tk.Label(row1, text="Quarter", fg=C["text_dim"], bg=C["bg"],
                 font=FONTS["small"]).pack(side="left", padx=(0, 8))
        self._q_chips = ChipGroup(row1, on_change=self._set_quarter)
        for q, label in [("q1", "Q1"), ("q2", "Q2"),
                         ("q3", "Q3"), ("q4", "Q4"), ("year", "Year")]:
            self._q_chips.add(q, label, selected=(q == self._quarter))
        self._q_chips.pack(side="left")

        tk.Label(row1, text="Search", fg=C["label_fg"], bg=C["bg"],
                 font=FONTS["label"]).pack(side="left", padx=(24, 8))
        make_entry(row1, self._search, width=26).pack(side="left")

        # Filter row 2 — status + show-legacy + rescan + folder hint
        row2 = tk.Frame(wrap, bg=C["bg"])
        row2.pack(fill="x", pady=(8, 0))
        tk.Label(row2, text="Status", fg=C["label_fg"], bg=C["bg"],
                 font=FONTS["label"]).pack(side="left", padx=(0, 8))
        ttk.Combobox(
            row2, textvariable=self._status_filter,
            values=["All", "Filed", "Needs DL", "Missing PDF", "Voided"],
            width=14, state="readonly", style="InvApp.TCombobox",
        ).pack(side="left")
        self._status_filter.trace_add("write", lambda *_: self._render_tree())

        tk.Frame(row2, bg=C["bg"], width=24).pack(side="left")
        tk.Checkbutton(
            row2, text="Show legacy", variable=self._show_legacy,
            command=self._on_legacy_toggle,
            fg=C["label_fg"], bg=C["bg"],
            activeforeground=C["label_fg"], activebackground=C["bg"],
            selectcolor=C["bg_input"], font=FONTS["label"],
            bd=0, highlightthickness=0,
        ).pack(side="left")

        self._legacy_status_var = tk.StringVar(value="")
        tk.Label(row2, textvariable=self._legacy_status_var,
                 fg=C["text_dim"], bg=C["bg"], font=FONTS["small"]
                 ).pack(side="left", padx=(8, 0))
        secondary_button(row2, "Rescan legacy",
                         self.state.rescan_legacy, padx=10, pady=2
                         ).pack(side="left", padx=(8, 0))

        self._folder_var = tk.StringVar(value="")
        folder_lbl = tk.Label(
            row2, textvariable=self._folder_var,
            fg=C["text_dim"], bg=C["bg"], font=FONTS["small"], cursor="hand2",
        )
        folder_lbl.pack(side="right")
        folder_lbl.bind("<Button-1>", self._copy_folder_path)

        # Tree
        tree_wrap = tk.Frame(wrap, bg=C["bg"])
        tree_wrap.pack(fill="both", expand=True, pady=(10, 0))
        cols = ("number", "date", "customer", "total", "status", "filing")
        tree = make_treeview(tree_wrap, cols, height=22, show="tree headings")
        tree.heading("#0", text="")
        tree.heading("number",   text="#",        anchor="center")
        tree.heading("date",     text="Date")
        tree.heading("customer", text="Customer")
        tree.heading("total",    text="Total",    anchor="e")
        tree.heading("status",   text="Status",   anchor="center")
        tree.heading("filing",   text="Filing")
        tree.column("#0",       width=30,  stretch=False)
        tree.column("number",   width=60,  minwidth=50, anchor="center")
        tree.column("date",     width=100, minwidth=80)
        tree.column("customer", width=280, minwidth=140)
        tree.column("total",    width=110, minwidth=80, anchor="e")
        tree.column("status",   width=80,  minwidth=60, anchor="center")
        tree.column("filing",   width=200, minwidth=120)
        tree.bind("<Double-1>", self._on_double_click)
        tree.bind("<<TreeviewSelect>>", lambda _e: self._refresh_action_bar())
        self._tree = tree

        # Action bar
        action_bar = tk.Frame(wrap, bg=C["card_border"], padx=12, pady=8)
        action_bar.pack(fill="x", pady=(10, 0))
        self._action_bar = action_bar
        self._sel_label = tk.Label(
            action_bar, text="No selection", fg=C["text_dim"],
            bg=C["card_border"], font=FONTS["small"],
        )
        self._sel_label.pack(side="left")
        self._action_btns_frame = tk.Frame(action_bar, bg=C["card_border"])
        self._action_btns_frame.pack(side="right")
        self._refresh_action_bar()

        # Reflect scan state in the row 2 hint right away
        self._refresh_legacy_status_label()

    # ----- data + render ----------------------------------------------

    def reload(self) -> None:
        try:
            self._invoices = self.state.registry.list_invoices(
                year=self.state.year, limit=9999,
            )
        except Exception as e:
            logger.exception("Failed to list invoices")
            self._invoices = []
            if self.frame is not None:
                messagebox.showerror("Outgoing", f"Failed to load invoices:\n\n{e}")
        # UI refresh — skip when not mounted (year/company listeners can
        # fire while this section has never been opened yet).
        if self.frame is None:
            return
        self._update_chip_counts()
        self._update_folder_label()
        self._render_tree()

    def on_show(self) -> None:
        self.reload()
        self._refresh_legacy_status_label()

    def _on_legacy_scan_done(self) -> None:
        # Fired from AppState background thread (already marshalled to GUI).
        if self.frame is None:
            return
        self._refresh_legacy_status_label()
        if self._show_legacy.get():
            self._update_chip_counts()
            self._render_tree()

    def _refresh_legacy_status_label(self) -> None:
        if not hasattr(self, "_legacy_status_var"):
            return
        state = self.state.legacy_scan_state()
        if state == "scanning":
            self._legacy_status_var.set("(scanning…)")
        elif state == "failed":
            self._legacy_status_var.set(
                f"(scan failed: {self.state.legacy_scan_error() or 'unknown'})")
        elif state == "done":
            total = len(self.state.legacy_results())
            new = sum(1 for s in self.state.legacy_reg_status().values()
                      if s == "new")
            self._legacy_status_var.set(
                f"({total} PDF(s) found · {new} not yet in registry)")
        else:
            self._legacy_status_var.set("")

    def _on_state_quarter_change(self, q: str) -> None:
        self._quarter = q
        if self.frame is not None:
            self._q_chips.select(q)

    def _set_quarter(self, q: str) -> None:
        self._quarter = q
        self.state.set_quarter(q)
        self._update_folder_label()
        self._render_tree()

    def _update_chip_counts(self) -> None:
        per_q = {q: 0 for q in self.QUARTERS}
        # registry rows
        for inv in self._invoices:
            if inv.get("status") == "draft":
                continue
            try:
                m = int((inv.get("invoice_date") or "")[:7].split("-")[1])
                per_q[f"q{quarter_for(m)}"] += 1
                per_q["year"] += 1
            except (IndexError, ValueError):
                continue
        # un-imported legacy rows, when toggled on
        if self._show_legacy.get() and self.state.legacy_scan_state() == "done":
            reg_status = self.state.legacy_reg_status()
            year = self.state.year
            for r in self.state.legacy_results():
                if reg_status.get(str(r.path)) == "in registry":
                    continue
                if r.year != year:
                    continue
                if r.quarter and 1 <= r.quarter <= 4:
                    per_q[f"q{r.quarter}"] += 1
                per_q["year"] += 1
        self._q_chips.set_counts({k: v if v else None for k, v in per_q.items()})

    def _on_legacy_toggle(self) -> None:
        """Wired to the Show-legacy Checkbutton — refreshes counts + tree
        + the bottom status bar (which counts legacy in its summary)."""
        self._update_chip_counts()
        self._render_tree()
        self._mark_status_dirty()

    def _render_tree(self) -> None:
        tree = self._tree
        for iid in tree.get_children():
            tree.delete(iid)
        self._legacy_path_to_obj.clear()

        search = self._search.get().strip().lower()
        co_filter = self.state.company
        status_filter = self._status_filter.get()

        # ----- registry rows -----
        reg_rows = self._filter_registry(search, co_filter, status_filter)

        # ----- legacy rows (only when toggled + scan ready) -----
        legacy_rows: List[Any] = []
        if self._show_legacy.get() and self.state.legacy_scan_state() == "done":
            legacy_rows = self._filter_legacy(search, co_filter)

        # Group by company key, holding both kinds of rows
        by_co: Dict[str, Dict[str, List]] = {}
        for inv in reg_rows:
            ck = inv.get("company_key", "?")
            by_co.setdefault(ck, {"reg": [], "legacy": []})["reg"].append(inv)
        for r in legacy_rows:
            ck = r.company_key or "?"
            by_co.setdefault(ck, {"reg": [], "legacy": []})["legacy"].append(r)

        for co_key in sorted(by_co):
            reg = by_co[co_key]["reg"]
            leg = by_co[co_key]["legacy"]
            try:
                co = self.state.config.get_company(co_key)
                label = f"{co_key} — {co.display_name}"
            except KeyError:
                label = co_key
            total_cents = sum(r.get("total_cents", 0) for r in reg)
            count_summary = f"{len(reg)}" + (f" + {len(leg)} legacy"
                                              if leg else "")
            summary = f"{count_summary} / {format_money(total_cents)}"
            cat_id = tree.insert(
                "", "end", text="",
                values=(label, "", "", "", "", summary),
                tags=("category",),
            )

            for inv in sorted(reg, key=lambda r: r.get("sequence", 0)):
                self._insert_registry_row(cat_id, inv)

            if leg:
                # Italic, dim separator marking the boundary
                tree.insert(
                    cat_id, "end", text="",
                    values=("─", "", "Legacy (not in registry)", "", "", ""),
                    tags=("legacy_separator",),
                )
                for r in sorted(leg, key=lambda x: (x.invoice_date or "",
                                                     x.sequence or 0)):
                    self._insert_legacy_row(cat_id, r)

            tree.item(cat_id, open=True)

        self._refresh_action_bar()

    def _filter_registry(self, search: str, co_filter: str,
                          status_filter: str) -> List[Dict]:
        rows: List[Dict] = []
        for inv in self._invoices:
            if inv.get("status") == "draft":
                continue
            try:
                m = int((inv.get("invoice_date") or "")[:7].split("-")[1])
                q = quarter_for(m)
            except (IndexError, ValueError):
                continue
            if self._quarter != "year" and f"q{q}" != self._quarter:
                continue
            if co_filter != "All" and inv.get("company_key") != co_filter:
                continue
            if search:
                hay = " ".join(str(inv.get(k, "")) for k in
                               ("sequence", "customer_name",
                                "customer_vat", "source_ref")).lower()
                if search not in hay:
                    continue
            tag = self._filing_tag(inv)
            if status_filter == "Filed" and tag != "filed":      continue
            if status_filter == "Needs DL" and tag != "needs_dl":continue
            if status_filter == "Missing PDF" and tag != "missing": continue
            if status_filter == "Voided" and tag != "voided":    continue
            rows.append(inv)
        return rows

    def _filter_legacy(self, search: str, co_filter: str) -> List[Any]:
        year = self.state.year
        reg_status = self.state.legacy_reg_status()
        out: List[Any] = []
        for r in self.state.legacy_results():
            # Only un-imported ones — already-imported legacy files are
            # already represented as registry rows above.
            if reg_status.get(str(r.path)) == "in registry":
                continue
            if r.year != year:
                continue
            if self._quarter != "year" and r.quarter != int(self._quarter[1]):
                continue
            if co_filter != "All" and (r.company_key or "?") != co_filter:
                continue
            if search:
                hay = " ".join(str(x) for x in (
                    r.sequence or "", r.description or "",
                    r.company_key or "", r.invoice_date or "",
                    r.path.name,
                )).lower()
                if search not in hay:
                    continue
            out.append(r)
        return out

    def _insert_registry_row(self, parent_id: str, inv: Dict) -> None:
        tag = self._filing_tag(inv)
        filing_text = {
            "filed":    "● Filed",
            "needs_dl": f"◐ Needs DL  (#{inv.get('source_ref', '?')})",
            "missing":  "○ Missing PDF",
            "voided":   "—",
        }.get(tag, "")
        self._tree.insert(
            parent_id, "end", iid=str(inv["id"]), text="",
            values=(
                f"{inv.get('sequence', 0):03d}",
                inv.get("invoice_date", "—"),
                inv.get("customer_name", ""),
                format_money(inv.get("total_cents", 0),
                             inv.get("currency", "EUR")),
                inv.get("status", ""),
                filing_text,
            ),
            tags=(tag,),
        )

    def _insert_legacy_row(self, parent_id: str, r: Any) -> None:
        iid = f"{self.LEGACY_IID_PREFIX}{r.path}"
        self._legacy_path_to_obj[str(r.path)] = r
        seq_label = f"{r.sequence:03d}" if r.sequence is not None else "—"
        desc = r.description or r.path.name
        if r.notes:
            desc = f"⚠ {desc}"
        from invoice_manager.core.legacy_scanner import PATTERN_UNRECOGNISED
        importable = r.can_import and r.pattern != PATTERN_UNRECOGNISED
        filing_text = "legacy" + ("" if importable else " · cannot auto-import")
        self._tree.insert(
            parent_id, "end", iid=iid, text="",
            values=(
                seq_label,
                r.invoice_date or "—",
                desc,
                "—",
                "legacy",
                filing_text,
            ),
            tags=("legacy",),
        )

    def _filing_tag(self, inv: Dict) -> str:
        if inv.get("status") == "voided":
            return "voided"
        # Canonical wins (see _resolve_pdf rationale): a stale registry
        # pdf_path pointing at an old base shouldn't keep showing "Filed"
        # if the new canonical location is empty, and shouldn't be
        # preferred over a live canonical file either.
        found = self._find_filed_pdf(inv)
        if found is not None:
            if inv.get("pdf_path") != str(found):
                self._adopt_pdf_path(inv, found)
            return "filed"
        path = inv.get("pdf_path")
        if path and Path(path).exists():
            return "filed"
        if inv.get("source") == "woocommerce":
            return "needs_dl"
        return "missing"

    def _find_filed_pdf(self, inv: Dict) -> Optional[Path]:
        """Probe the canonical quarter folder for a PDF that matches this
        invoice's sequence, regardless of customer-name spelling.

        Pattern: ``{prefix}_*Factuur{seq:03d}*.pdf`` inside
        ``{boekhouding}/{year}/Q{n}/Uitgaand``. Returns the first match
        or None — typical folder has well under 100 files so a glob is
        cheap.
        """
        invoice_date = inv.get("invoice_date") or ""
        sequence = inv.get("sequence", 0)
        if not invoice_date or not sequence:
            return None
        try:
            co = self.state.config.get_company(inv.get("company_key", ""))
        except KeyError:
            return None
        try:
            boek = self.state.config.resolve_boekhouding_base()
            folder = quarter_dir_for(boek, invoice_date)
        except Exception:
            return None
        if not folder.exists():
            return None
        try:
            for match in folder.glob(f"{co.output_prefix}_*Factuur{int(sequence):03d}*.pdf"):
                return match
        except OSError:
            return None
        return None

    def _adopt_pdf_path(self, inv: Dict, path: Path) -> None:
        """Write the discovered path back to the registry so subsequent
        renders don't have to re-glob, and update the in-memory copy so
        the current render reflects it too.

        Uses set_pdf_path (works on any row) rather than finalize_invoice
        (only flips drafts to issued) — the rows we adopt here have
        usually been "issued" since the moment the WC monitor reserved
        them, only their pdf_path was empty.
        """
        try:
            self.state.registry.set_pdf_path(inv["id"], str(path))
            inv["pdf_path"] = str(path)
            logger.info(
                f"Adopted existing PDF for #{inv.get('sequence', 0):03d}: {path}"
            )
        except Exception:
            logger.exception("Could not adopt discovered PDF path")

    def _update_folder_label(self) -> None:
        boek = self.state.config.resolve_boekhouding_base()
        if self._quarter == "year":
            folder = boek / str(self.state.year)
        else:
            q = int(self._quarter[1])
            folder = boek / str(self.state.year) / f"Q{q}" / "Uitgaand"
        self._folder_var.set(str(folder))

    def _copy_folder_path(self, _e=None):
        text = self._folder_var.get()
        if not text:
            return
        self.frame.clipboard_clear()
        self.frame.clipboard_append(text)

    # ----- action bar -------------------------------------------------

    def _refresh_action_bar(self) -> None:
        for child in self._action_btns_frame.winfo_children():
            child.destroy()

        reg_ids = self._selected_registry_ids()
        legacy_paths = self._selected_legacy_paths()
        n_reg = len(reg_ids)
        n_leg = len(legacy_paths)

        if n_reg + n_leg == 0:
            quarter_inv = [
                i for i in self._invoices
                if self._is_in_current_quarter(i)
                and (self.state.company == "All" or
                     i.get("company_key") == self.state.company)
            ]
            self._sel_label.configure(
                text=f"{self._quarter_label()}: {len(quarter_inv)} invoice(s)")
        else:
            parts = []
            if n_reg: parts.append(f"{n_reg} current")
            if n_leg: parts.append(f"{n_leg} legacy")
            self._sel_label.configure(text=f"Selected: " + " + ".join(parts))

        # Registry-row actions
        if n_reg:
            first_inv = self._get_invoice(reg_ids[0])
            if first_inv:
                secondary_button(self._action_btns_frame, "Open PDF",
                                 lambda: self._open_pdf(first_inv)
                                 ).pack(side="left", padx=4)
                secondary_button(self._action_btns_frame, "Open folder",
                                 lambda: self._open_folder(first_inv)
                                 ).pack(side="left", padx=4)
                secondary_button(self._action_btns_frame, "Void…",
                                 lambda: self._void(first_inv)
                                 ).pack(side="left", padx=4)
                if self._is_deletable(first_inv):
                    secondary_button(self._action_btns_frame, "Delete…",
                                     lambda: self._delete_invoice(first_inv)
                                     ).pack(side="left", padx=4)

        # Legacy-row actions
        if n_leg:
            first_path = legacy_paths[0]
            first_obj = self._legacy_path_to_obj.get(first_path)
            if first_obj is not None:
                secondary_button(self._action_btns_frame, "Open legacy PDF",
                                 lambda p=first_obj.path:
                                     self.state.resolve_pdf_open(p)
                                 ).pack(side="left", padx=4)
                secondary_button(self._action_btns_frame, "Open folder",
                                 lambda p=first_obj.path:
                                     self.state.resolve_pdf_open(p.parent)
                                 ).pack(side="left", padx=4)
            primary_button(self._action_btns_frame,
                           f"⬇  Import {n_leg} → registry",
                           self._import_selected_legacy
                           ).pack(side="left", padx=4)

        # Quarter-level "File N WC invoices" (registry only)
        if self._quarter != "year":
            q = int(self._quarter[1])
            needs_dl = [
                i for i in self._invoices
                if self._is_in_quarter(i, q)
                and self._filing_tag(i) == "needs_dl"
            ]
            if needs_dl:
                primary_button(
                    self._action_btns_frame,
                    f"⬇  File Q{q} ({len(needs_dl)})",
                    lambda: self._file_quarter(q, needs_dl),
                ).pack(side="left", padx=4)

        secondary_button(self._action_btns_frame, "🔄  Sync WC",
                         self._sync_wc).pack(side="left", padx=4)
        secondary_button(self._action_btns_frame, "Health check",
                         self._health_check).pack(side="left", padx=4)

    def _quarter_label(self) -> str:
        if self._quarter == "year":
            return f"Year {self.state.year}"
        return f"Q{self._quarter[1]} {self.state.year}"

    def _selected_registry_ids(self) -> List[int]:
        out = []
        for iid in self._tree.selection():
            if iid.startswith(self.LEGACY_IID_PREFIX):
                continue
            try:
                out.append(int(iid))
            except (TypeError, ValueError):
                continue
        return out

    def _selected_legacy_paths(self) -> List[str]:
        return [iid[len(self.LEGACY_IID_PREFIX):]
                for iid in self._tree.selection()
                if iid.startswith(self.LEGACY_IID_PREFIX)]

    def _get_invoice(self, inv_id: int) -> Optional[Dict]:
        try:
            return self.state.registry.get_by_id(inv_id)
        except Exception:
            return None

    def _is_in_quarter(self, inv: Dict, q: int) -> bool:
        if inv.get("status") == "draft":
            return False
        try:
            m = int((inv.get("invoice_date") or "")[:7].split("-")[1])
        except (IndexError, ValueError):
            return False
        return quarter_for(m) == q

    def _is_in_current_quarter(self, inv: Dict) -> bool:
        if self._quarter == "year":
            return inv.get("status") != "draft"
        return self._is_in_quarter(inv, int(self._quarter[1]))

    # ----- row actions: registry --------------------------------------

    def _resolve_pdf(self, inv: Dict) -> Optional[Path]:
        """Return the PDF path for an invoice.

        Canonical (config-driven) location wins over whatever the
        registry remembers. That way a stale `pdf_path` pointing at an
        old `boekhouding_base` (e.g. D:\...) doesn't keep dragging the
        user back there after they migrate the tree to the new base
        (e.g. I:\...). The registered path is used only as a fallback
        when no file is found at the canonical location.
        """
        canonical = self._find_filed_pdf(inv)
        if canonical is not None:
            if inv.get("pdf_path") != str(canonical):
                self._adopt_pdf_path(inv, canonical)
            return canonical
        path = inv.get("pdf_path")
        if path and Path(path).exists():
            return Path(path)
        return None

    def _open_pdf(self, inv: Dict) -> None:
        pdf = self._resolve_pdf(inv)
        if pdf is None:
            messagebox.showinfo("Open PDF", "This invoice has no filed PDF.")
            return
        self.state.resolve_pdf_open(pdf)

    def _open_folder(self, inv: Dict) -> None:
        pdf = self._resolve_pdf(inv)
        if pdf is None:
            # Even with no PDF we can still open the quarter folder where
            # it *would* live — useful for dropping a hand-renamed file.
            try:
                boek = self.state.config.resolve_boekhouding_base()
                folder = quarter_dir_for(boek, inv.get("invoice_date") or "")
                if folder.exists():
                    self.state.resolve_pdf_open(folder)
                    return
            except Exception:
                pass
            messagebox.showinfo("Open folder", "This invoice has no filed PDF.")
            return
        self.state.resolve_pdf_open(pdf.parent)

    def _is_deletable(self, inv: Dict) -> bool:
        """True if `inv` is the most-recently reserved number — the only
        row that can be deleted without leaving a gap in the sequence
        (see `Registry.delete_invoice`). Applies regardless of status:
        drafts and "oops, test invoice" issued rows alike."""
        try:
            preview = self.state.registry.get_next_preview(inv["year"])
        except Exception:
            return False
        return inv.get("sequence") == preview - 1

    def _delete_invoice(self, inv: Dict) -> None:
        if not self._is_deletable(inv):
            messagebox.showinfo(
                "Delete",
                "This invoice can no longer be deleted — it's not the most "
                "recently reserved number anymore.\n\nUse Void instead.",
            )
            return
        msg = (
            f"Permanently delete invoice #{inv['sequence']:03d} (year {inv['year']})?\n\n"
            "This removes the row entirely (and its PDF, if one was filed) "
            "and frees up the number so the next invoice you create will "
            "reuse it."
        )
        if inv.get("status") != "draft":
            msg += (
                "\n\n⚠ This invoice was already issued. Belgian law normally "
                "requires keeping issued numbers (that's what Void is for) — "
                "only delete it if it was a mistake/test that was never "
                "actually sent to a customer."
            )
        if not messagebox.askyesno("Delete invoice", msg, parent=self.frame):
            return
        try:
            deleted = self.state.registry.delete_invoice(inv["id"])
        except ValueError as e:
            messagebox.showerror("Delete", str(e))
            return

        pdf_path = deleted.get("pdf_path")
        if pdf_path:
            try:
                p = Path(pdf_path)
                if p.exists():
                    p.unlink()
            except Exception:
                logger.exception(f"Could not remove PDF for deleted invoice: {pdf_path}")
        self.reload()

    def _void(self, inv: Dict) -> None:
        if inv.get("status") == "voided":
            messagebox.showinfo("Void", "Already voided.")
            return
        reason = simpledialog.askstring(
            "Void invoice",
            f"Void invoice {inv['sequence']:03d} (year {inv['year']})?\n"
            "Belgian law requires keeping the number — it will be marked voided.\n\nReason:",
            parent=self.frame,
        )
        if not reason:
            return
        self.state.registry.void_invoice(inv["id"], reason)
        self.reload()

    def _on_double_click(self, event):
        tree = event.widget
        item = tree.identify_row(event.y)
        if not item:
            return
        if "category" in tree.item(item, "tags"):
            return
        if "legacy_separator" in tree.item(item, "tags"):
            return
        if item.startswith(self.LEGACY_IID_PREFIX):
            path = item[len(self.LEGACY_IID_PREFIX):]
            obj = self._legacy_path_to_obj.get(path)
            if obj:
                self.state.resolve_pdf_open(obj.path)
            return
        try:
            inv_id = int(item)
        except (ValueError, TypeError):
            return
        inv = self._get_invoice(inv_id)
        if inv:
            self._open_pdf(inv)

    # ----- row actions: legacy import ---------------------------------

    def _import_selected_legacy(self) -> None:
        paths = self._selected_legacy_paths()
        items = [self._legacy_path_to_obj[p] for p in paths
                 if p in self._legacy_path_to_obj]
        if not items:
            return
        importable = [r for r in items if r.can_import]
        skipped = [r for r in items if not r.can_import]
        if not importable:
            messagebox.showinfo(
                "Import",
                "None of the selected legacy invoices can be auto-imported.\n\n"
                "Unrecognised files need a proper filename first.",
            )
            return
        reg_status = self.state.legacy_reg_status()
        already = [r for r in importable
                   if reg_status.get(str(r.path)) == "in registry"]
        to_import = [r for r in importable
                     if reg_status.get(str(r.path)) != "in registry"]
        if not to_import:
            messagebox.showinfo("Import",
                                "All selected are already in the registry.")
            return

        msg = f"Import {len(to_import)} invoice(s) as registry stubs?"
        if skipped:
            msg += f"\n\n{len(skipped)} bare/unrecognised file(s) will be skipped."
        if already:
            msg += f"\n\n{len(already)} already-imported file(s) will be skipped."
        if not messagebox.askyesno("Import legacy invoices", msg):
            return

        from invoice_manager.core.registry import RegistryConflictError
        successes, conflicts, errors = [], [], []
        for r in to_import:
            draft = {
                "company_key": r.company_key, "invoice_date": r.invoice_date,
                "customer_name": r.import_customer_name, "line_items": [],
                "source": "legacy_scan", "source_ref": str(r.path),
                "notes": r.notes or "",
            }
            try:
                self.state.registry.import_existing_invoice(
                    r.year, r.sequence, draft, pdf_path=str(r.path),
                )
                successes.append(r)
                self.state.mark_legacy_imported(str(r.path))
            except RegistryConflictError as e:
                conflicts.append((r, str(e)))
            except Exception as e:
                errors.append((r, str(e)))

        self.reload()  # re-pulls registry + re-renders
        lines = [f"Imported: {len(successes)}"]
        if conflicts:
            lines.append(f"\nConflicts ({len(conflicts)}):")
            for r, msg in conflicts:
                lines.append(f"  {r.path.name}: {msg}")
        if errors:
            lines.append(f"\nErrors ({len(errors)}):")
            for r, msg in errors:
                lines.append(f"  {r.path.name}: {msg}")
        if skipped:
            lines.append(f"\nSkipped (no metadata): {len(skipped)}")
        if conflicts or errors:
            messagebox.showwarning("Import complete", "\n".join(lines))
        else:
            messagebox.showinfo("Import complete", "\n".join(lines))

    # ----- bulk actions: WC quarter filing & sync ---------------------

    def _file_quarter(self, q: int, needs_dl: List[Dict]) -> None:
        year = self.state.year
        creds = self.state.config.get_wc_credentials_for_alles3d()
        if not creds:
            messagebox.showerror(f"File Q{q}",
                                 "WooCommerce credentials not configured.")
            return
        if not creds.get("monitor_secret_key"):
            messagebox.showerror(
                f"File Q{q}",
                "monitor_secret_key not set — cannot download invoice PDFs.",
            )
            return
        if not messagebox.askyesno(
            f"File Q{q} {year}",
            f"Download and file {len(needs_dl)} invoice PDF(s) from WooCommerce?",
        ):
            return
        try:
            bridge = WooCommerceBridge(creds)
        except WCBridgeError as e:
            messagebox.showerror(f"File Q{q}", str(e))
            return
        try:
            self.frame.configure(cursor="watch")
        except tk.TclError:
            pass
        threading.Thread(
            target=self._file_quarter_worker,
            args=(bridge, needs_dl, q, year), daemon=True,
        ).start()

    def _file_quarter_worker(self, bridge, rows, q, year):
        boek = self.state.config.resolve_boekhouding_base()
        filed, errors = [], []
        for inv in rows:
            order_id_str = inv.get("source_ref", "")
            try:
                order_id = int(order_id_str)
            except (ValueError, TypeError):
                errors.append((inv, f"Non-numeric source_ref: {order_id_str!r}"))
                continue
            try:
                co = self.state.config.get_company(inv.get("company_key", "3D"))
                prefix = co.output_prefix
            except KeyError:
                prefix = str(inv.get("company_key", "3D"))
            with tempfile.TemporaryDirectory(prefix="fq_") as td:
                tmp_pdf = Path(td) / f"invoice_{order_id}.pdf"
                if not bridge.download_invoice_pdf(order_id, tmp_pdf):
                    errors.append((inv, "Download failed"))
                    continue
                try:
                    final_pdf = file_pdf(
                        tmp_pdf, boek, prefix,
                        inv.get("invoice_date", ""), inv.get("sequence", 0),
                        inv.get("customer_name", "Unknown"), move=False,
                    )
                    self.state.registry.finalize_invoice(inv["id"], str(final_pdf))
                    filed.append((inv, final_pdf))
                except Exception as e:
                    errors.append((inv, str(e)))
        self.frame.after(0, self._file_quarter_done, filed, errors, q, year)

    def _file_quarter_done(self, filed, errors, q, year):
        try:
            self.frame.configure(cursor="")
        except tk.TclError:
            pass
        self.reload()
        lines = [f"Q{q} {year}:  {len(filed)} filed"]
        if errors:
            lines.append(f"\nErrors ({len(errors)}):")
            for inv, msg in errors[:10]:
                lines.append(f"  #{inv.get('sequence', '?'):03d} "
                             f"{inv.get('customer_name', '')}: {msg}")
            messagebox.showwarning(f"File Q{q} complete", "\n".join(lines))
        else:
            messagebox.showinfo(f"File Q{q} complete", "\n".join(lines))

    def _sync_wc(self) -> None:
        creds = self.state.config.get_wc_credentials_for_alles3d()
        if not creds:
            messagebox.showerror("Sync from WooCommerce",
                                 "No WC credentials configured.")
            return
        if not messagebox.askyesno(
            "Sync from WooCommerce",
            "Fetch every WC order and import any with a WCPDF invoice "
            "number into the registry?\n\nIdempotent — already-imported skip.",
        ):
            return
        try:
            bridge = WooCommerceBridge(creds)
        except WCBridgeError as e:
            messagebox.showerror("Sync from WooCommerce", str(e))
            return
        try:
            default_vat_rate = self.state.config.get_company("3D").default_vat_rate
        except KeyError:
            default_vat_rate = 21.0
        try:
            self.frame.configure(cursor="watch")
        except tk.TclError:
            pass
        threading.Thread(target=self._sync_worker,
                         args=(bridge, default_vat_rate), daemon=True).start()

    def _sync_worker(self, bridge, default_vat_rate):
        try:
            report = sync_woocommerce_invoices(
                self.state.registry, bridge, company_key="3D",
                default_vat_rate=default_vat_rate,
                progress=lambda msg: logger.info(msg),
            )
            self.frame.after(0, self._sync_done, report, None)
        except Exception as e:
            logger.exception("WC sync failed")
            self.frame.after(0, self._sync_done, None, str(e))

    def _sync_done(self, report, error):
        try:
            self.frame.configure(cursor="")
        except tk.TclError:
            pass
        if error:
            messagebox.showerror("Sync from WooCommerce",
                                 f"Sync failed:\n\n{error}")
            return
        self.reload()
        title = "Sync from WooCommerce — done"
        if report.conflicts or report.errors:
            messagebox.showwarning(title, report.as_text())
        else:
            messagebox.showinfo(title, report.as_text())

    def _health_check(self) -> None:
        warnings = self.state.registry.health_check()
        if not warnings:
            messagebox.showinfo("Health check", "✓  All years have gapless numbering.")
        else:
            messagebox.showwarning("Health check — warnings", "\n\n".join(warnings))

    # ----- lifecycle ---------------------------------------------------

    def summary(self) -> str:
        rows = [i for i in self._invoices if self._is_in_current_quarter(i)
                and (self.state.company == "All" or
                     i.get("company_key") == self.state.company)]
        filed = sum(1 for i in rows if self._filing_tag(i) == "filed")
        dl = sum(1 for i in rows if self._filing_tag(i) == "needs_dl")
        missing = sum(1 for i in rows if self._filing_tag(i) == "missing")
        total = sum(i.get("total_cents", 0) for i in rows
                    if i.get("status") != "voided")
        parts = [f"{len(rows)} invoice(s)"]
        if filed:   parts.append(f"{filed} filed")
        if dl:      parts.append(f"{dl} need downloading")
        if missing: parts.append(f"{missing} missing PDF")
        parts.append(format_money(total) + " gross")
        if self._show_legacy.get() and self.state.legacy_scan_state() == "done":
            leg_visible = len(self._filter_legacy("", self.state.company))
            if leg_visible:
                parts.append(f"+{leg_visible} legacy")
        return f"{self._quarter_label()} · " + "  ·  ".join(parts)
