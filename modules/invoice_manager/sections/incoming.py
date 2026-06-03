"""Incoming — supplier invoices: vendor coverage, duplicates, naming issues.

Shares the same header pattern as Outgoing (quarter chips + search) so
both browsers feel like one product. A `View` dropdown switches the
tree between three modes:

  - Vendors    — expected-vs-found per vendor (quarterly/yearly)
  - Duplicates — files appearing in more than one quarter
  - Naming     — files whose names don't match the convention

The Naming view exposes a Rename action that uses invoice2data to
extract supplier/date metadata and propose a canonical filename.
"""

from __future__ import annotations

import multiprocessing as mp
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional, Tuple

from shared_logging import get_logger

from invoice_manager.incoming_scanner import (
    BOEKHOUDING_ROOT,
    INVOICE2DATA_AVAILABLE,
    _extract_in_subprocess,
    find_duplicates,
    scan_quarter,
    scan_year,
    validate_filenames,
)
from invoice_manager.sections.base import Section
from invoice_manager.theme import PALETTE, FONTS
from invoice_manager.widgets.buttons import primary_button, secondary_button
from invoice_manager.widgets.chip import ChipGroup
from invoice_manager.widgets.inputs import make_entry
from invoice_manager.widgets.tree import make_treeview

logger = get_logger("invoice_manager.incoming")

VIEW_VENDORS = "Vendors"
VIEW_DUPLICATES = "Duplicates"
VIEW_NAMING = "Naming"


class IncomingSection(Section):
    title = "Incoming"
    sidebar_key = "incoming"
    sidebar_icon = "📥"

    QUARTERS = ["q1", "q2", "q3", "q4", "year"]

    # Per-view column specs: (column_id, header, width, anchor)
    COL_SPECS: Dict[str, List[Tuple[str, str, int, str]]] = {
        VIEW_VENDORS: [
            ("vendor",    "Vendor",    180, "w"),
            ("frequency", "Frequency", 100, "w"),
            ("status",    "Status",    130, "w"),
            ("found",     "Found",     80,  "center"),
            ("files",     "Files",     400, "w"),
        ],
        VIEW_DUPLICATES: [
            ("filename", "Filename", 320, "w"),
            ("quarters", "Quarters", 130, "w"),
            ("details",  "Details",  500, "w"),
        ],
        VIEW_NAMING: [
            ("quarter",  "Quarter",  80,  "center"),
            ("filename", "Filename", 360, "w"),
            ("issues",   "Issues",   500, "w"),
        ],
    }

    def __init__(self, parent, state):
        super().__init__(parent, state)
        self._quarter = "q1"
        self._view = VIEW_VENDORS
        self._search = tk.StringVar()
        self._rename_pending: List[Tuple[int, Path, str]] = []
        self._rename_mode = False

        # Cached scan results (per current year, refreshed on reload)
        self._quarter_results: Dict[int, Dict[str, Dict]] = {}
        self._year_results: Dict[str, Dict] = {}
        self._duplicates: List[Tuple[str, List[Tuple[int, str]]]] = []
        self._naming_issues: List[Tuple[int, str, List[str], str]] = []

        self.state.on_year_change(lambda _y: self.reload())

    # ----- build -------------------------------------------------------

    def build(self, root: tk.Frame) -> None:
        C = PALETTE
        root.configure(bg=C["bg"])
        wrap = tk.Frame(root, bg=C["bg"], padx=20, pady=14)
        wrap.pack(fill="both", expand=True)

        # Row 1 — Quarter chips + Search (mirrors Outgoing exactly)
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
        self._search.trace_add("write", lambda *_: self._render_tree())

        # Row 2 — View dropdown + folder hint
        row2 = tk.Frame(wrap, bg=C["bg"])
        row2.pack(fill="x", pady=(8, 0))
        tk.Label(row2, text="View", fg=C["label_fg"], bg=C["bg"],
                 font=FONTS["label"]).pack(side="left", padx=(0, 8))
        self._view_var = tk.StringVar(value=self._view)
        ttk.Combobox(
            row2, textvariable=self._view_var,
            values=[VIEW_VENDORS, VIEW_DUPLICATES, VIEW_NAMING],
            width=14, state="readonly", style="InvApp.TCombobox",
        ).pack(side="left")
        self._view_var.trace_add("write", lambda *_: self._on_view_change())

        self._folder_var = tk.StringVar(value="")
        folder_lbl = tk.Label(
            row2, textvariable=self._folder_var,
            fg=C["text_dim"], bg=C["bg"], font=FONTS["small"], cursor="hand2",
        )
        folder_lbl.pack(side="right")
        folder_lbl.bind("<Button-1>", self._copy_folder_path)

        # Tree — built with Vendors column set; rebuilt on view change
        self._tree_wrap = tk.Frame(wrap, bg=C["bg"])
        self._tree_wrap.pack(fill="both", expand=True, pady=(10, 0))
        self._tree: Optional[ttk.Treeview] = None
        self._build_tree()

        # Action bar — adapts to view + selection + rename mode
        self._action_bar = tk.Frame(wrap, bg=C["card_border"], padx=12, pady=8)
        self._action_bar.pack(fill="x", pady=(10, 0))
        self._sel_label = tk.Label(
            self._action_bar, text="", fg=C["text_dim"],
            bg=C["card_border"], font=FONTS["small"],
        )
        self._sel_label.pack(side="left")
        self._action_btns = tk.Frame(self._action_bar, bg=C["card_border"])
        self._action_btns.pack(side="right")

        # Status tags shared across views
        # (color, optional row bg) — Treeview tag_configure supports both
        for tag, fg in [
            ("ok",       PALETTE["dot_filed"]),
            ("partial",  PALETTE["dot_partial"]),
            ("missing",  PALETTE["dot_missing"]),
            ("optional_missing", PALETTE["text_dim"]),
            ("not_this_quarter", PALETTE["text_dim"]),
            ("duplicate", PALETTE["dot_partial"]),
            ("warning",  PALETTE["dot_partial"]),
            ("error",    PALETTE["dot_missing"]),
            ("no_match", PALETTE["dot_partial"]),
            ("empty",    PALETTE["text_dim"]),
        ]:
            # Default tag config; refreshed on tree rebuild too.
            pass

    def _build_tree(self) -> None:
        """(Re)build the Treeview with columns for the current view."""
        # Wipe existing tree if present.
        for child in self._tree_wrap.winfo_children():
            child.destroy()

        cols = [c[0] for c in self.COL_SPECS[self._view]]
        tree = make_treeview(self._tree_wrap, cols, height=22,
                             show="tree headings")
        tree.heading("#0", text="")
        tree.column("#0", width=24, stretch=False)
        for col_id, header, width, anchor in self.COL_SPECS[self._view]:
            tree.heading(col_id, text=header, anchor=anchor)
            tree.column(col_id, width=width, anchor=anchor,
                        stretch=(col_id in ("files", "details", "issues")))

        # Per-view row tag colours
        for tag, fg in [
            ("ok",                PALETTE["dot_filed"]),
            ("partial",           PALETTE["dot_partial"]),
            ("missing",           PALETTE["dot_missing"]),
            ("optional_missing",  PALETTE["text_dim"]),
            ("not_this_quarter",  PALETTE["text_dim"]),
            ("duplicate",         PALETTE["dot_partial"]),
            ("warning",           PALETTE["dot_partial"]),
            ("error",             PALETTE["dot_missing"]),
            ("no_match",          PALETTE["dot_partial"]),
            ("empty",             PALETTE["text_dim"]),
        ]:
            tree.tag_configure(tag, foreground=fg)
        tree.tag_configure("category", foreground=PALETTE["accent"],
                            font=FONTS["body_bold"])

        tree.bind("<Double-1>", self._on_double_click)
        tree.bind("<<TreeviewSelect>>", lambda _e: self._refresh_action_bar())
        self._tree = tree

    # ----- data load --------------------------------------------------

    def reload(self) -> None:
        """Re-scan filesystem for the current year — runs the relevant
        scan functions and caches results; UI updated only if mounted.
        """
        year = self.state.year
        try:
            # We only re-run the parts we'll show. Vendors view scans
            # quarters lazily as the user picks chips; here we scan the
            # current quarter eagerly for snappiness.
            if self._quarter == "year":
                self._year_results = scan_year(year)
            else:
                q = int(self._quarter[1])
                self._quarter_results[q] = scan_quarter(year, q)
            self._duplicates = find_duplicates(year)
            self._naming_issues = validate_filenames(year)
        except Exception as e:
            logger.exception("Incoming scan failed")
            if self.frame is not None:
                messagebox.showerror("Incoming",
                                      f"Failed to scan invoices:\n\n{e}")
            return
        if self.frame is None:
            return
        self._update_chip_counts()
        self._update_folder_label()
        self._render_tree()

    def on_show(self) -> None:
        self.reload()

    # ----- chip / view handlers ---------------------------------------

    def _set_quarter(self, q: str) -> None:
        self._quarter = q
        year = self.state.year
        # Lazy-scan quarter the first time it's selected
        if q != "year":
            qi = int(q[1])
            if qi not in self._quarter_results:
                try:
                    self._quarter_results[qi] = scan_quarter(year, qi)
                except Exception as e:
                    logger.exception("scan_quarter failed")
                    self._quarter_results[qi] = {}
        elif not self._year_results:
            try:
                self._year_results = scan_year(year)
            except Exception:
                logger.exception("scan_year failed")
                self._year_results = {}
        self._update_folder_label()
        self._render_tree()

    def _on_view_change(self) -> None:
        new_view = self._view_var.get()
        if new_view == self._view:
            return
        if self._rename_mode:
            # Switching away from Naming should cancel rename mode
            self._set_rename_mode(False)
        self._view = new_view
        self._build_tree()
        self._render_tree()
        self._update_folder_label()

    # ----- chip counts ------------------------------------------------

    def _update_chip_counts(self) -> None:
        """Counts depend on which view is active.

        - Vendors:    number of expected vendors per quarter
        - Duplicates: dup files per quarter (each dup counts in each quarter it appears in)
        - Naming:     issues per quarter
        """
        per_q = {k: 0 for k in self.QUARTERS}

        if self._view == VIEW_VENDORS:
            year = self.state.year
            for q in (1, 2, 3, 4):
                if q in self._quarter_results:
                    rows = self._quarter_results[q]
                else:
                    # We haven't scanned this quarter yet — leave count blank
                    continue
                count = sum(len(vendors) for vendors in rows.values())
                per_q[f"q{q}"] += count
                per_q["year"] += count
            # Year tally uses scan_year when available
            if self._year_results:
                per_q["year"] = sum(
                    len(vendors) for vendors in self._year_results.values()
                )

        elif self._view == VIEW_DUPLICATES:
            for _filename, locations in self._duplicates:
                qs = {q for q, _ in locations}
                for q in qs:
                    per_q[f"q{q}"] += 1
                per_q["year"] += 1

        elif self._view == VIEW_NAMING:
            for q, *_ in self._naming_issues:
                per_q[f"q{q}"] += 1
                per_q["year"] += 1

        self._q_chips.set_counts({k: v if v else None for k, v in per_q.items()})

    # ----- folder hint ------------------------------------------------

    def _update_folder_label(self) -> None:
        year = self.state.year
        if self._view == VIEW_VENDORS and self._quarter != "year":
            q = int(self._quarter[1])
            folder = BOEKHOUDING_ROOT / str(year) / f"Q{q}" / "Binnenkomend"
        else:
            folder = BOEKHOUDING_ROOT / str(year)
        self._folder_var.set(str(folder))

    def _copy_folder_path(self, _e=None) -> None:
        text = self._folder_var.get()
        if not text:
            return
        self.frame.clipboard_clear()
        self.frame.clipboard_append(text)

    # ----- tree rendering --------------------------------------------

    def _render_tree(self) -> None:
        if self._tree is None:
            return
        tree = self._tree
        for iid in tree.get_children():
            tree.delete(iid)

        if self._view == VIEW_VENDORS:
            self._render_vendors()
        elif self._view == VIEW_DUPLICATES:
            self._render_duplicates()
        elif self._view == VIEW_NAMING:
            self._render_naming()
        self._refresh_action_bar()
        self._mark_status_dirty()

    def _matches_search(self, *parts: str) -> bool:
        needle = self._search.get().strip().lower()
        if not needle:
            return True
        return needle in " ".join(str(p) for p in parts).lower()

    def _render_vendors(self) -> None:
        tree = self._tree
        year = self.state.year
        if self._quarter == "year":
            results = self._year_results
            for category, vendors in results.items():
                if not vendors:
                    continue
                cat_id = tree.insert(
                    "", "end", text="",
                    values=(category, "", "", "", ""), tags=("category",),
                )
                visible = 0
                for vendor, info in vendors.items():
                    if not self._matches_search(vendor, category):
                        continue
                    status = info["status"]
                    total = info["total_found"]
                    expected = info["expected_count"]
                    status_text = {
                        "ok":       "✓  OK",
                        "partial":  "△  Incomplete",
                        "optional_missing": "○  Optional",
                    }.get(status, "✗  MISSING")
                    files_text = ", ".join(
                        f"Q{qi}: {', '.join(info['matches'].get(qi, []))}"
                        for qi in range(1, 5) if info['matches'].get(qi)
                    )
                    tree.insert(
                        cat_id, "end", text="",
                        values=(vendor, info["config"].get("frequency", ""),
                                status_text, f"{total}/{expected}", files_text),
                        tags=(status,),
                    )
                    visible += 1
                if visible == 0:
                    tree.delete(cat_id)
                else:
                    tree.item(cat_id, open=True)
        else:
            q = int(self._quarter[1])
            results = self._quarter_results.get(q, {})
            for category, vendors in results.items():
                if not vendors:
                    continue
                cat_id = tree.insert(
                    "", "end", text="",
                    values=(category, "", "", "", ""), tags=("category",),
                )
                visible = 0
                for vendor, info in vendors.items():
                    if not self._matches_search(vendor, category):
                        continue
                    status = info["status"]
                    matches = info["matches"]
                    expected = info["expected_count"]
                    status_text = {
                        "ok":       "✓  OK",
                        "partial":  "△  Incomplete",
                        "optional_missing": "○  Optional",
                    }.get(status, "✗  MISSING")
                    found_text = f"{len(matches)}/{expected}"
                    freq = {"monthly": "Monthly",
                            "quarterly": "Quarterly"}.get(
                        info["config"].get("frequency", ""), "")
                    tree.insert(
                        cat_id, "end", text="",
                        values=(vendor, freq, status_text, found_text,
                                ", ".join(matches)),
                        tags=(status,),
                    )
                    visible += 1
                if visible == 0:
                    tree.delete(cat_id)
                else:
                    tree.item(cat_id, open=True)

    def _render_duplicates(self) -> None:
        tree = self._tree
        # Quarter chip filters: when not "year", only show dups that
        # appear in the selected quarter.
        wanted_q = None if self._quarter == "year" else int(self._quarter[1])
        rows = 0
        for filename, locations in self._duplicates:
            qs = sorted({q for q, _ in locations})
            if wanted_q is not None and wanted_q not in qs:
                continue
            if not self._matches_search(filename, *(fn for _, fn in locations)):
                continue
            q_text = ", ".join(f"Q{q}" for q in qs)
            details = " | ".join(f"Q{q}: {fn}" for q, fn in sorted(locations))
            tree.insert("", "end", text="",
                        values=(filename, q_text, details),
                        tags=("duplicate",))
            rows += 1
        if rows == 0:
            tree.insert("", "end", text="",
                        values=("No duplicates in this scope", "", ""),
                        tags=("empty",))

    def _render_naming(self) -> None:
        tree = self._tree
        wanted_q = None if self._quarter == "year" else int(self._quarter[1])
        warning_only_prefix = "Date is"
        rows = 0
        for q, fname, issues, issue_type in self._naming_issues:
            if wanted_q is not None and q != wanted_q:
                continue
            if not self._matches_search(fname, *issues):
                continue
            issues_text = " | ".join(issues)
            if issue_type == "no_match":
                tag = "no_match"
            elif all(i.startswith(warning_only_prefix) for i in issues):
                tag = "warning"
            else:
                tag = "error"
            tree.insert("", "end", text="",
                        values=(f"Q{q}", fname, issues_text),
                        tags=(tag,))
            rows += 1
        if rows == 0:
            tree.insert("", "end", text="",
                        values=("", "No naming issues in this scope", ""),
                        tags=("empty",))

    # ----- action bar -------------------------------------------------

    def _refresh_action_bar(self) -> None:
        for child in self._action_btns.winfo_children():
            child.destroy()

        sel_items = self._tree.selection() if self._tree else []
        n = len(sel_items)
        self._sel_label.configure(
            text=(f"Selected: {n} row(s)" if n else "Double-click a row to open files")
        )

        # Always-available actions
        if n:
            secondary_button(
                self._action_btns, "Open file(s)",
                self._open_selected_files,
            ).pack(side="left", padx=3)
            secondary_button(
                self._action_btns, "Open folder",
                self._open_selected_folders,
            ).pack(side="left", padx=3)
            secondary_button(
                self._action_btns, "Copy path(s)",
                self._copy_selected_paths,
            ).pack(side="left", padx=3)
        else:
            # No row selected — still let the user open the active
            # quarter folder (the one shown in the folder-hint label).
            secondary_button(
                self._action_btns, "Open folder",
                self._open_quarter_folder,
            ).pack(side="left", padx=3)

        # Naming-mode actions
        if self._view == VIEW_NAMING:
            rename_count = sum(
                1 for *_, itype in self._naming_issues if itype == "no_match"
            )
            if self._rename_mode:
                primary_button(self._action_btns, "✓  Confirm rename",
                               self._confirm_rename).pack(side="left", padx=3)
                secondary_button(self._action_btns, "Cancel",
                                 self._cancel_rename).pack(side="left", padx=3)
            elif rename_count:
                primary_button(self._action_btns,
                               f"✎  Rename {rename_count} unnamed file(s)",
                               self._preview_rename).pack(side="left", padx=3)

        # Manual rescan, useful after dropping new files in Binnenkomend/
        secondary_button(self._action_btns, "↻  Rescan",
                         self.reload).pack(side="left", padx=3)

    # ----- file actions -----------------------------------------------

    def _selected_paths(self) -> List[Path]:
        tree = self._tree
        if tree is None:
            return []
        year = self.state.year
        out: List[Path] = []
        for iid in tree.selection():
            tags = tree.item(iid, "tags")
            values = tree.item(iid, "values")
            if "category" in tags or "empty" in tags or not values:
                continue
            if self._view == VIEW_VENDORS:
                # Vendors: files cell is csv of filenames for the current quarter
                if self._quarter == "year":
                    # Year view files cell is "Q1: a, b | Q2: c"
                    files_cell = values[4]
                    for chunk in files_cell.split("|"):
                        chunk = chunk.strip()
                        if not chunk or ":" not in chunk:
                            continue
                        qstr, fnames = chunk.split(":", 1)
                        try:
                            qi = int(qstr.strip().lstrip("Q"))
                        except ValueError:
                            continue
                        folder = BOEKHOUDING_ROOT / str(year) / f"Q{qi}" / "Binnenkomend"
                        for fn in fnames.split(","):
                            fn = fn.strip()
                            if fn:
                                out.append(folder / fn)
                else:
                    q = int(self._quarter[1])
                    folder = BOEKHOUDING_ROOT / str(year) / f"Q{q}" / "Binnenkomend"
                    files_cell = values[4]
                    for fn in files_cell.split(","):
                        fn = fn.strip()
                        if fn:
                            out.append(folder / fn)
            elif self._view == VIEW_DUPLICATES:
                filename = values[0]
                q_text = values[1]
                for qstr in q_text.split(","):
                    qstr = qstr.strip().lstrip("Q")
                    try:
                        qi = int(qstr)
                    except ValueError:
                        continue
                    folder = BOEKHOUDING_ROOT / str(year) / f"Q{qi}" / "Binnenkomend"
                    out.append(folder / filename)
            elif self._view == VIEW_NAMING:
                q_text = values[0]
                filename = values[1]
                try:
                    qi = int(q_text.lstrip("Q"))
                except ValueError:
                    continue
                folder = BOEKHOUDING_ROOT / str(year) / f"Q{qi}" / "Binnenkomend"
                out.append(folder / filename)
        return out

    def _open_selected_files(self) -> None:
        for path in self._selected_paths():
            self.state.resolve_pdf_open(path)

    def _open_selected_folders(self) -> None:
        """Open the parent folder of each selected row, deduped. Capped at
        3 to avoid spawning a wall of file-explorer windows when the user
        selects rows spanning many quarters in Year view.
        """
        seen: List[Path] = []
        for path in self._selected_paths():
            if path.parent not in seen:
                seen.append(path.parent)
            if len(seen) >= 3:
                break
        if not seen:
            self._open_quarter_folder()
            return
        for parent in seen:
            self.state.resolve_pdf_open(parent)

    def _open_quarter_folder(self) -> None:
        """Open whatever the folder-hint label currently points at — the
        Binnenkomend folder for the active year/quarter, or the year
        folder for the Year chip."""
        text = self._folder_var.get()
        if text:
            self.state.resolve_pdf_open(text)

    def _copy_selected_paths(self) -> None:
        paths = self._selected_paths()
        if not paths:
            return
        self.frame.clipboard_clear()
        self.frame.clipboard_append("\n".join(str(p) for p in paths))

    def _on_double_click(self, _e) -> None:
        self._open_selected_files()

    # ----- rename workflow --------------------------------------------

    def _preview_rename(self) -> None:
        if not INVOICE2DATA_AVAILABLE:
            messagebox.showerror(
                "Rename", "invoice2data is not installed.\n\n"
                "Install with: pip install invoice2data pdfplumber",
            )
            return
        year = self.state.year
        to_rename = [
            (q, fname) for q, fname, _, itype in self._naming_issues
            if itype == "no_match"
        ]
        if not to_rename:
            return
        # Disable the action bar while extracting; long-running.
        self._sel_label.configure(text=f"Scanning {len(to_rename)} file(s)…")
        threading.Thread(
            target=self._extract_thread, args=(year, to_rename), daemon=True,
        ).start()

    def _extract_thread(self, year: int,
                         to_rename: List[Tuple[int, str]]) -> None:
        results: List[Tuple[int, Path, str, Optional[str], str]] = []
        for q, fname in to_rename:
            folder = BOEKHOUDING_ROOT / str(year) / f"Q{q}" / "Binnenkomend"
            old_path = folder / fname
            try:
                if fname.lower().endswith(".pdf"):
                    new_name, info = self._extract_in_subprocess(old_path)
                else:
                    new_name, info = None, "Not a PDF"
                if new_name is None and fname.lower().endswith(".pdf"):
                    new_name = f"FAC_00-00-00_Onbekend{Path(fname).suffix}"
                    info = "Unknown (fallback)"
            except Exception as e:
                logger.exception("Extract failed")
                new_name, info = None, f"Error: {e}"
            results.append((q, old_path, fname, new_name, info))
        if self.frame is not None:
            self.frame.after(0, self._show_preview, results)

    def _extract_in_subprocess(self, pdf_path: Path, timeout: int = 15
                                ) -> Tuple[Optional[str], str]:
        q = mp.Queue()
        proc = mp.Process(target=_extract_in_subprocess,
                          args=(str(pdf_path), q), daemon=True)
        proc.start()
        proc.join(timeout=timeout)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=2)
            if proc.is_alive():
                proc.kill()
            return None, f"Timed out ({timeout}s)"
        try:
            return q.get_nowait()
        except Exception:
            return None, "Error: no result"

    def _show_preview(self, results: List[Tuple[int, Path, str,
                                                  Optional[str], str]]) -> None:
        tree = self._tree
        if tree is None:
            return
        for iid in tree.get_children():
            tree.delete(iid)

        self._rename_pending = []
        skipped = 0
        for q, old_path, fname, new_name, info in results:
            if new_name:
                self._rename_pending.append((q, old_path, new_name))
                tree.insert("", "end", text="",
                            values=(f"Q{q}", fname, f"→ {new_name}"),
                            tags=("ok",))
            else:
                skipped += 1
                tree.insert("", "end", text="",
                            values=(f"Q{q}", fname, info),
                            tags=("no_match",))
        if self._rename_pending:
            self._set_rename_mode(True)
            self._sel_label.configure(
                text=f"{len(self._rename_pending)} ready · {skipped} skipped — review then Confirm")
        else:
            self._sel_label.configure(
                text=f"No files could be auto-recognised ({skipped} skipped)")

    def _set_rename_mode(self, on: bool) -> None:
        self._rename_mode = on
        if not on:
            self._rename_pending = []
        self._refresh_action_bar()

    def _cancel_rename(self) -> None:
        self._set_rename_mode(False)
        self.reload()

    def _confirm_rename(self) -> None:
        pending = list(self._rename_pending)
        renamed, errors = 0, []
        for _q, old_path, new_name in pending:
            try:
                if not old_path.exists():
                    raise FileNotFoundError(old_path)
                new_path = old_path.parent / new_name
                if new_path.exists():
                    stem, ext = new_path.stem, new_path.suffix
                    counter = 2
                    while new_path.exists():
                        new_path = old_path.parent / f"{stem}_{counter:02d}{ext}"
                        counter += 1
                old_path.rename(new_path)
                renamed += 1
                logger.info(f"Renamed: {old_path.name} → {new_path.name}")
            except Exception as e:
                errors.append(f"{old_path.name}: {e}")
                logger.error(f"Rename failed: {old_path.name}: {e}")
        self._set_rename_mode(False)
        msg = f"{renamed} file(s) renamed."
        if errors:
            msg += f" {len(errors)} error(s):\n  " + "\n  ".join(errors[:10])
            messagebox.showwarning("Rename", msg)
        else:
            messagebox.showinfo("Rename", msg)
        self.reload()

    # ----- summary -----------------------------------------------------

    def summary(self) -> str:
        year = self.state.year
        scope = (f"Q{self._quarter[1]} {year}"
                 if self._quarter != "year" else f"Year {year}")
        if self._view == VIEW_VENDORS:
            rows = self._tree_row_count_excluding_categories()
            return f"{scope} · {rows} vendor(s) shown"
        if self._view == VIEW_DUPLICATES:
            n = sum(
                1 for _fn, locs in self._duplicates
                if self._quarter == "year"
                or int(self._quarter[1]) in {q for q, _ in locs}
            )
            return f"{scope} · {n} duplicate(s)"
        if self._view == VIEW_NAMING:
            n_issues = sum(
                1 for q, *_ in self._naming_issues
                if self._quarter == "year" or q == int(self._quarter[1])
            )
            n_no_match = sum(
                1 for q, _f, _i, itype in self._naming_issues
                if itype == "no_match"
                and (self._quarter == "year" or q == int(self._quarter[1]))
            )
            return f"{scope} · {n_issues} issue(s) · {n_no_match} unnamed"
        return scope

    def _tree_row_count_excluding_categories(self) -> int:
        if self._tree is None:
            return 0
        count = 0
        for cat_id in self._tree.get_children():
            count += len(self._tree.get_children(cat_id))
        return count
