"""Incoming invoices tab — quarterly verification and naming checks.

Adapted from PipelineScript_Business_InvoiceChecker.py.
Accepts a parent frame instead of a Tk root so it can be embedded in a notebook.
"""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared_form_keyboard import FORM_COLORS
from shared_logging import get_logger

from invoice_manager.incoming_scanner import (
    BOEKHOUDING_ROOT,
    INVOICE2DATA_AVAILABLE,
    _extract_in_subprocess,
    _generate_filename,
    find_duplicates,
    scan_quarter,
    scan_year,
    validate_filenames,
)

logger = get_logger("invoice_manager.incoming")


class IncomingInvoicesTab:
    """Incoming invoices verification panel — embeds inside a tab frame."""

    def __init__(self, parent: tk.Frame):
        self.root = parent
        self.root.configure(bg=FORM_COLORS["bg"])

        now = datetime.now()
        self.current_year = now.year
        self.current_quarter = (now.month - 1) // 3 + 1
        self.trees = {}
        self.tab_folders = {}

        self._build_ui()
        self._scan()

    # --- UI construction -----------------------------------------------------

    def _build_ui(self):
        C = FORM_COLORS

        # Controls bar
        ctrl = tk.Frame(self.root, bg=C["bg"], pady=10)
        ctrl.pack(fill="x", padx=16)

        tk.Label(ctrl, text="Year:", fg=C["text"], bg=C["bg"],
                 font=("Arial", 10)).pack(side="left")
        self.year_var = tk.StringVar(value=str(self.current_year))
        year_cb = ttk.Combobox(ctrl, textvariable=self.year_var, width=6,
                               values=[str(y) for y in range(2023, self.current_year + 1)],
                               state="readonly")
        year_cb.pack(side="left", padx=(4, 16))
        year_cb.bind("<<ComboboxSelected>>", lambda e: self._scan())

        reload_btn = tk.Button(
            ctrl, text="↻  Reload", command=self._scan,
            bg=C["bg_input"], fg=C["text"], activebackground=C["bg_hover"],
            activeforeground=C["text"], relief=tk.FLAT, font=("Arial", 10),
            cursor="hand2", padx=12, pady=2,
        )
        reload_btn.pack(side="left", padx=(0, 8))
        reload_btn.bind("<Enter>", lambda e: e.widget.configure(bg=C["bg_hover"]))
        reload_btn.bind("<Leave>", lambda e: e.widget.configure(bg=C["bg_input"]))

        self.folder_label = tk.Label(ctrl, text="", fg=C["text_dim"], bg=C["bg"],
                                     font=("Arial", 9), cursor="hand2")
        self.folder_label.pack(side="left", padx=(16, 0))
        self.folder_label.bind("<Button-1>", self._copy_folder_path)
        self.folder_label.bind("<Enter>", lambda e: e.widget.configure(fg=C["accent"]))
        self.folder_label.bind("<Leave>", lambda e: e.widget.configure(fg=C["text_dim"]))

        # Shared treeview style
        style = ttk.Style()
        style.configure("IncomingInvoice.Treeview",
                        background=C["bg_input"], foreground=C["text"],
                        fieldbackground=C["bg_input"], rowheight=26,
                        font=("Arial", 10))
        style.configure("IncomingInvoice.Treeview.Heading",
                        background=C["border"], foreground=C["text"],
                        font=("Arial", 10, "bold"))
        style.map("IncomingInvoice.Treeview",
                  background=[("selected", C["accent_dark"])],
                  foreground=[("selected", "white")])
        style.configure("IncomingInvoice.TNotebook", background=C["bg"])
        style.configure("IncomingInvoice.TNotebook.Tab",
                        background=C["bg_input"], foreground=C["text"],
                        padding=[14, 6])
        style.map("IncomingInvoice.TNotebook.Tab",
                  background=[("selected", C["accent_dark"])],
                  foreground=[("selected", "#ffffff")])

        # Sub-notebook
        self.notebook = ttk.Notebook(self.root, style="IncomingInvoice.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Quarter tabs
        for q in range(1, 5):
            frame = tk.Frame(self.notebook, bg=C["bg"])
            tree = self._create_treeview(frame, ("vendor", "frequency", "status", "found", "files"))
            tree.heading("vendor", text="Vendor", anchor="w")
            tree.heading("frequency", text="Frequency", anchor="w")
            tree.heading("status", text="Status", anchor="w")
            tree.heading("found", text="Found", anchor="center")
            tree.heading("files", text="Files", anchor="w")
            tree.column("#0", width=30, stretch=False)
            tree.column("vendor", width=150, minwidth=100)
            tree.column("frequency", width=90, minwidth=70)
            tree.column("status", width=110, minwidth=80)
            tree.column("found", width=70, minwidth=50, anchor="center")
            tree.column("files", width=350, minwidth=150)
            self.notebook.add(frame, text=f"  Q{q}  ")
            self.trees[f"q{q}"] = tree

        # Year overview tab
        year_frame = tk.Frame(self.notebook, bg=C["bg"])
        year_tree = self._create_treeview(year_frame,
                                          ("vendor", "status", "found", "q1", "q2", "q3", "q4"))
        year_tree.heading("vendor", text="Vendor", anchor="w")
        year_tree.heading("status", text="Status", anchor="w")
        year_tree.heading("found", text="Total", anchor="center")
        year_tree.heading("q1", text="Q1", anchor="w")
        year_tree.heading("q2", text="Q2", anchor="w")
        year_tree.heading("q3", text="Q3", anchor="w")
        year_tree.heading("q4", text="Q4", anchor="w")
        year_tree.column("#0", width=30, stretch=False)
        year_tree.column("vendor", width=140, minwidth=100)
        year_tree.column("status", width=110, minwidth=80)
        year_tree.column("found", width=60, minwidth=40, anchor="center")
        year_tree.column("q1", width=140, minwidth=80)
        year_tree.column("q2", width=140, minwidth=80)
        year_tree.column("q3", width=140, minwidth=80)
        year_tree.column("q4", width=140, minwidth=80)
        self.notebook.add(year_frame, text="  Year Overview  ")
        self.trees["year"] = year_tree

        # Duplicates tab
        dup_frame = tk.Frame(self.notebook, bg=C["bg"])
        dup_tree = self._create_treeview(dup_frame, ("filename", "quarters", "details"))
        dup_tree.heading("filename", text="Filename", anchor="w")
        dup_tree.heading("quarters", text="Quarters", anchor="w")
        dup_tree.heading("details", text="Details", anchor="w")
        dup_tree.column("#0", width=30, stretch=False)
        dup_tree.column("filename", width=300, minwidth=200)
        dup_tree.column("quarters", width=150, minwidth=100)
        dup_tree.column("details", width=350, minwidth=200)
        self.notebook.add(dup_frame, text="  Duplicates  ")
        self.trees["dup"] = dup_tree

        # Naming validation tab
        naming_frame = tk.Frame(self.notebook, bg=C["bg"])

        rename_bar = tk.Frame(naming_frame, bg=C["bg"])
        rename_bar.pack(fill="x", padx=4, pady=(4, 0))
        self._rename_pending = []
        self._rename_mode = False

        self.rename_btn = tk.Button(
            rename_bar, text="Rename",
            command=self._on_rename_click,
            bg=C["bg_input"], fg=C["text"], activebackground=C["bg_hover"],
            activeforeground=C["text"], relief=tk.FLAT, font=("Arial", 10),
            cursor="hand2", padx=12, pady=4,
        )
        self.rename_btn.pack(side="left")
        self.rename_btn.bind("<Enter>", self._rename_btn_enter)
        self.rename_btn.bind("<Leave>", self._rename_btn_leave)

        self.cancel_btn = tk.Button(
            rename_bar, text="Cancel",
            command=self._cancel_rename,
            bg=C["bg_input"], fg=C["text"], activebackground=C["bg_hover"],
            activeforeground=C["text"], relief=tk.FLAT, font=("Arial", 10),
            cursor="hand2", padx=12, pady=4,
        )
        self.cancel_btn.bind("<Enter>", lambda e: e.widget.configure(bg=C["bg_hover"]))
        self.cancel_btn.bind("<Leave>", lambda e: e.widget.configure(bg=C["bg_input"]))

        self.rename_count_label = tk.Label(
            rename_bar, text="", fg=C["text_dim"], bg=C["bg"], font=("Arial", 9))
        self.rename_count_label.pack(side="left", padx=(12, 0))

        naming_tree = self._create_treeview(naming_frame, ("quarter", "filename", "issues"))
        naming_tree.heading("quarter", text="Quarter", anchor="w")
        naming_tree.heading("filename", text="Filename", anchor="w")
        naming_tree.heading("issues", text="Issues", anchor="w")
        naming_tree.column("#0", width=30, stretch=False)
        naming_tree.column("quarter", width=80, minwidth=60)
        naming_tree.column("filename", width=320, minwidth=200)
        naming_tree.column("issues", width=400, minwidth=250)
        self.notebook.add(naming_frame, text="  Naming  ")
        self.trees["naming"] = naming_tree

        # Apply tags to all trees
        for tree in self.trees.values():
            tree.tag_configure("ok", background="#1a2e1a", foreground=C["text"])
            tree.tag_configure("partial", background="#2e2a1a", foreground=C["text"])
            tree.tag_configure("missing", background="#2e1a1a", foreground=C["text"])
            tree.tag_configure("optional_missing",
                               background=C["bg_input"], foreground=C["text_dim"])
            tree.tag_configure("not_this_quarter",
                               background=C["bg_input"], foreground=C["text_dim"])
            tree.tag_configure("category", foreground=C["accent"],
                               font=("Arial", 10, "bold"))
            tree.tag_configure("duplicate", background="#2e1a1a", foreground=C["text"])
            tree.tag_configure("no_duplicates", foreground=C["text_dim"])
            tree.tag_configure("warning", background="#2e2a1a", foreground=C["text"])
            tree.tag_configure("error", background="#2e1a1a", foreground=C["text"])
            tree.tag_configure("no_match", background="#2e1a2e", foreground=C["text"])
            tree.tag_configure("no_issues", foreground=C["text_dim"])

        # Summary bar
        self.summary_var = tk.StringVar()
        summary = tk.Label(self.root, textvariable=self.summary_var,
                           fg=C["text"], bg=C["border"],
                           font=("Arial", 10), anchor="w", padx=12, pady=6)
        summary.pack(fill="x", side="bottom")

    def _create_treeview(self, parent, columns):
        C = FORM_COLORS
        tree_frame = tk.Frame(parent, bg=C["bg"])
        tree_frame.pack(fill="both", expand=True, padx=4, pady=4)

        tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings",
                            style="IncomingInvoice.Treeview")
        tree.heading("#0", text="", anchor="w")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        tree.bind("<Double-1>", self._on_row_double_click)
        return tree

    # --- Scanning ------------------------------------------------------------

    def _scan(self):
        year = int(self.year_var.get())
        self._scan_quarters(year)
        self._scan_year_overview(year)
        self._scan_duplicates(year)
        self._scan_naming(year)
        self._update_folder_label()
        self._update_summary()

    def _scan_quarters(self, year: int):
        for q in range(1, 5):
            tree = self.trees[f"q{q}"]
            for item in tree.get_children():
                tree.delete(item)

            folder = BOEKHOUDING_ROOT / str(year) / f"Q{q}" / "Binnenkomend"
            self.tab_folders[f"q{q}"] = folder

            results = scan_quarter(year, q)

            for category, vendors in results.items():
                cat_id = tree.insert("", "end", text="",
                                     values=(category, "", "", "", ""),
                                     tags=("category",))

                for vendor, info in vendors.items():
                    status = info["status"]
                    matches = info["matches"]
                    expected = info["expected_count"]

                    if status == "ok":
                        status_text = "✓  OK"
                        found_text = f"{len(matches)}/{expected}"
                    elif status == "partial":
                        status_text = "△  Incomplete"
                        found_text = f"{len(matches)}/{expected}"
                    elif status == "optional_missing":
                        status_text = "○  Optional"
                        found_text = f"0/{expected}"
                    else:
                        status_text = "✗  MISSING"
                        found_text = f"0/{expected}"

                    freq_labels = {"monthly": "Monthly", "quarterly": "Quarterly"}
                    freq_text = freq_labels.get(info["config"]["frequency"], "")
                    files_text = ", ".join(matches) if matches else ""

                    tree.insert(cat_id, "end", text="",
                                values=(vendor, freq_text, status_text,
                                        found_text, files_text),
                                tags=(status,))

                tree.item(cat_id, open=True)

    def _scan_year_overview(self, year: int):
        tree = self.trees["year"]
        for item in tree.get_children():
            tree.delete(item)

        self.tab_folders["year"] = BOEKHOUDING_ROOT / str(year)
        results = scan_year(year)

        for category, vendors in results.items():
            cat_id = tree.insert("", "end", text="",
                                 values=(category, "", "", "", "", "", ""),
                                 tags=("category",))

            for vendor, info in vendors.items():
                status = info["status"]
                total = info["total_found"]
                expected = info["expected_count"]
                matches_per_q = info["matches"]

                if status == "ok":
                    status_text = "✓  OK"
                elif status == "partial":
                    status_text = "△  Incomplete"
                elif status == "optional_missing":
                    status_text = "○  Optional"
                else:
                    status_text = "✗  MISSING"

                found_text = f"{total}/{expected}"
                q_texts = [
                    ", ".join(matches_per_q.get(q, [])) for q in range(1, 5)
                ]

                tree.insert(cat_id, "end", text="",
                            values=(vendor, status_text, found_text,
                                    q_texts[0], q_texts[1], q_texts[2], q_texts[3]),
                            tags=(status,))

            tree.item(cat_id, open=True)

    def _scan_duplicates(self, year: int):
        tree = self.trees["dup"]
        for item in tree.get_children():
            tree.delete(item)

        duplicates = find_duplicates(year)

        if not duplicates:
            tree.insert("", "end", text="",
                        values=("No duplicates found", "", ""),
                        tags=("no_duplicates",))
            return

        for filename, locations in duplicates:
            quarters = sorted(set(q for q, _ in locations))
            q_text = ", ".join(f"Q{q}" for q in quarters)
            details = " | ".join(f"Q{q}: {fn}" for q, fn in sorted(locations))
            tree.insert("", "end", text="",
                        values=(filename, q_text, details),
                        tags=("duplicate",))

    def _scan_naming(self, year: int):
        tree = self.trees["naming"]
        for item in tree.get_children():
            tree.delete(item)

        self.tab_folders["naming"] = BOEKHOUDING_ROOT / str(year)
        issues_list = validate_filenames(year)

        if not issues_list:
            tree.insert("", "end", text="",
                        values=("", "No naming issues found", ""),
                        tags=("no_issues",))
            self.rename_count_label.config(text="")
            return

        warning_only = {"Date is"}
        no_match_count = 0
        for q, fname, issues, issue_type in issues_list:
            issues_text = " | ".join(issues)
            if issue_type == "no_match":
                tag = "no_match"
                no_match_count += 1
            elif all(any(i.startswith(w) for w in warning_only) for i in issues):
                tag = "warning"
            else:
                tag = "error"
            tree.insert("", "end", text="",
                        values=(f"Q{q}", fname, issues_text),
                        tags=(tag,))

        if no_match_count > 0:
            pdf_count = sum(
                1 for _, fname, _, itype in issues_list
                if itype == "no_match" and fname.lower().endswith(".pdf")
            )
            label = f"{no_match_count} unmatched"
            if pdf_count < no_match_count:
                label += f" ({pdf_count} PDF renameable)"
            self.rename_count_label.config(text=label)
        else:
            self.rename_count_label.config(text="")

    # --- Tab / folder label --------------------------------------------------

    def _on_tab_changed(self, event=None):
        self._update_folder_label()
        self._update_summary()

    def _get_active_tab_key(self):
        idx = self.notebook.index(self.notebook.select())
        if idx < 4:
            return f"q{idx + 1}"
        elif idx == 4:
            return "year"
        elif idx == 5:
            return "dup"
        else:
            return "naming"

    def _update_folder_label(self):
        key = self._get_active_tab_key()
        folder = self.tab_folders.get(key)
        self.folder_label.config(text=str(folder) if folder else "")

    def _update_summary(self):
        year = int(self.year_var.get())
        key = self._get_active_tab_key()

        if key.startswith("q"):
            q = int(key[1])
            tree = self.trees[key]
            total = found = missing = 0
            for cat_id in tree.get_children():
                for child in tree.get_children(cat_id):
                    tags = tree.item(child, "tags")
                    if "ok" in tags:
                        total += 1
                        found += 1
                    elif "partial" in tags or "missing" in tags:
                        total += 1
                        missing += 1
            if missing > 0:
                self.summary_var.set(
                    f"Q{q} {year}:  {found} of {total} invoices found  |  "
                    f"{missing} missing or incomplete"
                )
            else:
                self.summary_var.set(f"Q{q} {year}:  All {found} expected invoices found!")

        elif key == "year":
            results = scan_year(year)
            total = found = 0
            for cat in results.values():
                for info in cat.values():
                    if info["config"].get("optional"):
                        continue
                    total += 1
                    if info["status"] == "ok":
                        found += 1
            self.summary_var.set(f"Year {year}:  {found} of {total} yearly invoices found")

        elif key == "dup":
            duplicates = find_duplicates(year)
            if duplicates:
                self.summary_var.set(
                    f"Duplicates {year}:  {len(duplicates)} file(s) found in multiple quarters!"
                )
            else:
                self.summary_var.set(f"Duplicates {year}:  No duplicates found")

        elif key == "naming":
            issues_list = validate_filenames(year)
            if issues_list:
                no_match = sum(1 for *_, itype in issues_list if itype == "no_match")
                has_errors = sum(1 for *_, itype in issues_list if itype == "has_errors")
                warnings = sum(
                    1 for _, _, issues, itype in issues_list
                    if itype == "has_errors" and all(i.startswith("Date is") for i in issues)
                )
                real_errors = has_errors - warnings
                parts = []
                if no_match:
                    parts.append(f"{no_match} unnamed")
                if real_errors:
                    parts.append(f"{real_errors} error(s)")
                if warnings:
                    parts.append(f"{warnings} warning(s)")
                self.summary_var.set(f"Naming {year}:  {', '.join(parts)}")
            else:
                self.summary_var.set(f"Naming {year}:  All filenames are correct!")

    # --- Rename --------------------------------------------------------------

    def _extract_rename_info(self, pdf_path, timeout=15):
        import multiprocessing as mp

        result_queue = mp.Queue()
        proc = mp.Process(
            target=_extract_in_subprocess,
            args=(str(pdf_path), result_queue),
            daemon=True,
        )
        proc.start()
        proc.join(timeout=timeout)

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=2)
            if proc.is_alive():
                proc.kill()
            logger.warning(f"Extraction timed out for {pdf_path.name} after {timeout}s")
            return None, f"Timed out ({timeout}s)"

        try:
            return result_queue.get_nowait()
        except Exception:
            logger.error(f"Extraction failed for {pdf_path.name} (no result)")
            return None, "Error: no result"

    def _rename_btn_enter(self, event):
        if self._rename_mode:
            event.widget.configure(bg="#2a5a2a")
        else:
            event.widget.configure(bg=FORM_COLORS["bg_hover"])

    def _rename_btn_leave(self, event):
        if self._rename_mode:
            event.widget.configure(bg="#1a4a1a")
        else:
            event.widget.configure(bg=FORM_COLORS["bg_input"])

    def _set_rename_mode(self, active):
        C = FORM_COLORS
        self._rename_mode = active
        if active:
            self.rename_btn.configure(text="Confirm", bg="#1a4a1a", fg="#90ee90")
            self.cancel_btn.pack(side="left", padx=(8, 0))
        else:
            self.rename_btn.configure(text="Rename", bg=C["bg_input"], fg=C["text"])
            self.cancel_btn.pack_forget()
            self._rename_pending = []

    def _cancel_rename(self):
        self._set_rename_mode(False)
        self._scan_naming(int(self.year_var.get()))
        self._update_summary()

    def _on_rename_click(self):
        if self._rename_mode:
            self._confirm_rename()
        else:
            self._preview_rename()

    def _preview_rename(self):
        year = int(self.year_var.get())
        issues_list = validate_filenames(year)

        to_rename = [
            (q, fname) for q, fname, _, itype in issues_list
            if itype == "no_match"
        ]

        if not to_rename:
            self.summary_var.set("No files to rename.")
            return

        if not INVOICE2DATA_AVAILABLE:
            self.summary_var.set(
                "invoice2data is not installed. "
                "Install with: pip install invoice2data pdfplumber"
            )
            return

        self.rename_btn.configure(state="disabled", text="Scanning...")
        self.summary_var.set(f"Scanning {len(to_rename)} file(s)...")
        self.root.update_idletasks()

        def _do_extract():
            results = []
            total = len(to_rename)
            try:
                for i, (q, fname) in enumerate(to_rename, 1):
                    try:
                        folder = BOEKHOUDING_ROOT / str(year) / f"Q{q}" / "Binnenkomend"
                        old_path = folder / fname

                        if fname.lower().endswith(".pdf"):
                            new_name, info = self._extract_rename_info(old_path)
                        else:
                            new_name = None
                            info = "Not a PDF"

                        if new_name is None and fname.lower().endswith(".pdf"):
                            ext = Path(fname).suffix
                            new_name = f"FAC_00-00-00_Onbekend{ext}"
                            info = "Unknown (fallback)"

                        logger.info(f"Scanned {i}/{total}: {fname} -> {new_name or '(skip)'}")
                        results.append((q, old_path, fname, new_name, info))
                    except Exception as e:
                        logger.error(f"Scan failed for {fname}: {e}", exc_info=True)
                        folder = BOEKHOUDING_ROOT / str(year) / f"Q{q}" / "Binnenkomend"
                        results.append((q, folder / fname, fname, None, f"Error: {e}"))
            except Exception as e:
                logger.error(f"Scan thread crashed: {e}", exc_info=True)
            finally:
                self.root.after(0, lambda: self._show_preview_results(year, results))

        threading.Thread(target=_do_extract, daemon=True).start()

    def _show_preview_results(self, year, results):
        tree = self.trees["naming"]
        for item in tree.get_children():
            tree.delete(item)

        self._rename_pending = []
        skipped = 0

        for q, old_path, fname, new_name, info in results:
            if new_name:
                self._rename_pending.append((q, old_path, new_name))
                tree.insert("", "end", text="",
                            values=(f"Q{q}", fname, f"New name: {new_name}"),
                            tags=("ok",))
            else:
                skipped += 1
                tree.insert("", "end", text="",
                            values=(f"Q{q}", fname, info),
                            tags=("no_match",))

        self.rename_btn.configure(state="normal")
        count = len(self._rename_pending)
        if count > 0:
            self._set_rename_mode(True)
            msg = f"Naming {year}:  {count} file(s) to rename"
            if skipped:
                msg += f", {skipped} skipped"
            self.summary_var.set(msg)
        else:
            self.summary_var.set("No files could be automatically recognised.")

    def _confirm_rename(self):
        pending = list(self._rename_pending)
        self.rename_btn.configure(state="disabled", text="Renaming...")
        self.root.update_idletasks()

        renamed_log = []
        errors = []
        for q, old_path, new_name in pending:
            try:
                if not old_path.exists():
                    raise FileNotFoundError(f"Source file not found: {old_path}")
                new_path = old_path.parent / new_name
                if new_path.exists():
                    stem = new_path.stem
                    ext = new_path.suffix
                    counter = 2
                    while new_path.exists():
                        new_path = old_path.parent / f"{stem}_{counter:02d}{ext}"
                        counter += 1
                old_path.rename(new_path)
                renamed_log.append(f"{old_path.name} -> {new_path.name}")
            except Exception as e:
                errors.append(f"{old_path.name}: {e}")

        for entry in renamed_log:
            logger.info(f"Renamed: {entry}")
        for entry in errors:
            logger.error(f"Rename failed: {entry}")

        self._finish_rename(len(renamed_log), errors)

    def _finish_rename(self, renamed, errors):
        self._set_rename_mode(False)
        msg = f"{renamed} file(s) renamed."
        if errors:
            msg += f" {len(errors)} error(s)."
        self.summary_var.set(msg)
        self._scan()

    # --- Clipboard -----------------------------------------------------------

    def _copy_folder_path(self, event=None):
        path = self.folder_label.cget("text")
        if not path:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(path)
        prev = self.summary_var.get()
        self.summary_var.set(f"Copied: {path}")
        self.root.after(2000, lambda: self.summary_var.set(prev))

    def _on_row_double_click(self, event):
        tree = event.widget
        item = tree.identify_row(event.y)
        if not item:
            return
        values = tree.item(item, "values")
        tags = tree.item(item, "tags")

        if "category" in tags or "no_duplicates" in tags or "no_issues" in tags or not values:
            return

        key = self._get_active_tab_key()

        if key.startswith("q"):
            files_text = values[4] if len(values) > 4 else ""
            if not files_text:
                return
            folder = self.tab_folders.get(key)
            filenames = [f.strip() for f in files_text.split(",")]
            full_paths = [str(folder / fn) for fn in filenames]

        elif key == "year":
            year = int(self.year_var.get())
            full_paths = []
            for qi, col_idx in enumerate(range(3, 7), start=1):
                q_files = values[col_idx] if len(values) > col_idx else ""
                if q_files:
                    folder = BOEKHOUDING_ROOT / str(year) / f"Q{qi}" / "Binnenkomend"
                    for fn in q_files.split(","):
                        full_paths.append(str(folder / fn.strip()))
            if not full_paths:
                return

        elif key == "dup":
            filename = values[0] if values else ""
            if not filename:
                return
            year = int(self.year_var.get())
            quarters_text = values[1] if len(values) > 1 else ""
            q_nums = [int(s.strip().replace("Q", ""))
                      for s in quarters_text.split(",") if s.strip()]
            full_paths = []
            for q in q_nums:
                folder = BOEKHOUDING_ROOT / str(year) / f"Q{q}" / "Binnenkomend"
                full_paths.append(str(folder / filename))

        elif key == "naming":
            q_text = values[0] if values else ""
            filename = values[1] if len(values) > 1 else ""
            if not q_text or not filename:
                return
            q = int(q_text.replace("Q", ""))
            year = int(self.year_var.get())
            folder = BOEKHOUDING_ROOT / str(year) / f"Q{q}" / "Binnenkomend"
            full_paths = [str(folder / filename)]
        else:
            return

        clip_text = "\n".join(full_paths)
        self.root.clipboard_clear()
        self.root.clipboard_append(clip_text)

        prev = self.summary_var.get()
        if len(full_paths) == 1:
            self.summary_var.set(f"Copied: {full_paths[0]}")
        else:
            self.summary_var.set(f"{len(full_paths)} paths copied to clipboard")
        self.root.after(2000, lambda: self.summary_var.set(prev))
