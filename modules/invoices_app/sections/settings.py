"""Settings — environment status, file/folder shortcuts, debug-mode controls.

Two cards: Environment (paths + creds + health) and Debug mode (snapshot
+ restore).
"""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox
from typing import Callable, List

from global_invoice.config import DATA_DIR
from global_invoice.debug_mode import (
    DEBUG_SUBFOLDER_NAME, cleanup_debug_pdfs,
)
from shared_logging import get_logger

from invoices_app.sections.base import Section
from invoices_app.theme import PALETTE, FONTS
from invoices_app.widgets.buttons import secondary_button, danger_button, primary_button
from invoices_app.widgets.card import Card

logger = get_logger("invoices_app.settings")


class SettingsSection(Section):
    title = "Settings"
    sidebar_key = "settings"
    sidebar_icon = "⚙"

    def __init__(self, parent, state, *, on_debug_toggle: Callable[[], None]):
        super().__init__(parent, state)
        self._on_debug_toggle = on_debug_toggle

    def build(self, root: tk.Frame) -> None:
        C = PALETTE
        root.configure(bg=C["bg"])
        wrap = tk.Frame(root, bg=C["bg"], padx=20, pady=14)
        wrap.pack(fill="both", expand=True)

        # ----- Environment card -----
        env_card = Card(wrap, title="Environment")
        env_card.pack(fill="x")
        self._build_env(env_card.body)

        # ----- Debug card -----
        dbg_card = Card(wrap, title="Debug mode")
        dbg_card.pack(fill="x", pady=(12, 0))
        self._build_debug(dbg_card.body)

    def _build_env(self, parent: tk.Frame) -> None:
        C = PALETTE
        cfg = self.state.config
        soffice = cfg.resolve_soffice_path()
        boek = cfg.resolve_boekhouding_base()
        db = cfg.resolve_db_path()
        creds = cfg.get_wc_credentials_for_alles3d() or {}
        has_secret = bool(creds.get("monitor_secret_key"))

        for label, value, ok in [
            ("DB path",            str(db), db.exists()),
            ("Boekhouding base",   str(boek), boek.exists()),
            ("soffice binary",     str(soffice or "(not configured)"),
             bool(soffice and soffice.exists())),
            ("WC credentials",     "✓ configured" if creds.get("consumer_key") else "(not set)",
             bool(creds.get("consumer_key"))),
            ("monitor_secret_key", "● set — File Quarter WC download available"
             if has_secret else "○ not set — File Quarter WC download disabled",
             has_secret),
        ]:
            row = tk.Frame(parent, bg=C["card_bg"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, fg=C["text_dim"], bg=C["card_bg"],
                     font=FONTS["small"], width=22, anchor="w").pack(side="left")
            tk.Label(row, text=value,
                     fg=(C["dot_filed"] if ok else C["dot_partial"]),
                     bg=C["card_bg"], font=FONTS["body"], anchor="w"
                     ).pack(side="left")

        sep = tk.Frame(parent, bg=C["card_border"], height=1)
        sep.pack(fill="x", pady=(12, 10))

        btn_row = tk.Frame(parent, bg=C["card_bg"])
        btn_row.pack(fill="x")
        for text, cmd in [
            ("Open config.json",   lambda: self.state.resolve_pdf_open(cfg.source_path)),
            ("Open data folder",   lambda: self.state.resolve_pdf_open(cfg.source_path.parent)),
            ("Open templates",     self._open_templates_folder),
            ("Run health check",   self._health_check),
        ]:
            secondary_button(btn_row, text, cmd).pack(side="left", padx=(0, 6))

    def _open_templates_folder(self):
        templates_dir = self.state.config.resolve_templates_dir()
        if not templates_dir.exists():
            messagebox.showinfo("Templates folder",
                                f"Folder does not exist yet:\n{templates_dir}")
            return
        self.state.resolve_pdf_open(templates_dir)

    def _health_check(self):
        warnings = self.state.registry.health_check()
        if not warnings:
            messagebox.showinfo("Health check", "✓  All years have gapless numbering.")
        else:
            messagebox.showwarning("Health check — warnings", "\n\n".join(warnings))

    def _build_debug(self, parent: tk.Frame) -> None:
        C = PALETTE
        tk.Label(
            parent,
            text=(f"Snapshots the invoice DB and files test invoices into "
                  f"Boekhouding/{DEBUG_SUBFOLDER_NAME}/. Exit restores the DB and "
                  f"deletes the test PDFs."),
            fg=C["text_dim"], bg=C["card_bg"],
            font=FONTS["small"], wraplength=820, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        self._debug_status_var = tk.StringVar(value="")
        tk.Label(parent, textvariable=self._debug_status_var,
                 fg=C["text"], bg=C["card_bg"], font=FONTS["body_bold"]
                 ).pack(anchor="w", pady=(0, 8))

        btns = tk.Frame(parent, bg=C["card_bg"])
        btns.pack(anchor="w")
        self._enter_btn = secondary_button(btns, "🐛  Enter debug mode",
                                           self._enter_debug)
        self._enter_btn.pack(side="left")
        self._exit_btn = danger_button(btns, "Exit debug mode",
                                        self._exit_debug)
        self._exit_btn.pack(side="left", padx=(8, 0))

    def on_show(self) -> None:
        self._refresh_debug_status()

    def _refresh_debug_status(self) -> None:
        active = self.state.debug_session.is_active()
        if active:
            self._debug_status_var.set(
                f"Status: ACTIVE since {self.state.debug_session.started_at} · "
                f"{len(self.state.debug_session.created_pdfs)} test PDF(s)"
            )
            self._enter_btn.configure(state="disabled")
            self._exit_btn.configure(state="normal")
        else:
            self._debug_status_var.set("Status: inactive")
            self._enter_btn.configure(state="normal")
            self._exit_btn.configure(state="disabled")

    def _enter_debug(self):
        if self.state.debug_session.is_active():
            return
        if not messagebox.askyesno(
            "Enter debug mode",
            f"Snapshot the invoice DB and switch to debug mode?\n\n"
            f"While active:\n"
            f"  • Test invoices file into Boekhouding/{DEBUG_SUBFOLDER_NAME}/\n"
            f"  • DB still records each invoice as if it were real\n"
            f"  • Exiting restores the snapshot and deletes test PDFs\n\nContinue?",
        ):
            return
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = DATA_DIR / f"invoices.sqlite.debug_{ts}.bak"
            self.state.registry.backup_db(backup_path)
            self.state.debug_session.start(backup_path)
        except Exception as e:
            logger.exception("Failed to start debug session")
            messagebox.showerror("Enter debug mode", f"Could not start: {e}")
            return
        self._refresh_debug_status()
        self._on_debug_toggle()
        messagebox.showinfo(
            "Debug mode",
            "Debug mode ACTIVE. Test invoices will not affect production numbering.",
        )

    def _exit_debug(self):
        ds = self.state.debug_session
        if not ds.is_active():
            return
        pdf_count = len(ds.created_pdfs)
        if not messagebox.askyesno(
            "Exit debug mode",
            f"Roll back debug mode?\n\n"
            f"  • Restore the invoice DB from snapshot\n"
            f"  • Delete {pdf_count} test PDF(s)\n\nContinue?",
        ):
            return
        report = self._rollback()
        self._refresh_debug_status()
        self._on_debug_toggle()
        messagebox.showinfo("Exit debug mode", report)

    def _rollback(self) -> str:
        ds = self.state.debug_session
        backup = ds.db_backup_path
        pdfs = ds.created_pdfs
        lines: List[str] = []
        if backup and backup.exists():
            try:
                self.state.registry.restore_db(backup)
                lines.append(f"✓ DB restored from {backup.name}")
            except Exception as e:
                logger.exception("DB restore failed")
                lines.append(f"⚠ DB restore FAILED: {e}")
        else:
            lines.append("⚠ DB backup missing — could not restore.")

        result = cleanup_debug_pdfs(pdfs)
        if result["deleted"]:
            lines.append(f"✓ Deleted {len(result['deleted'])} test PDF(s)")
        if result["missing"]:
            lines.append(f"ℹ {len(result['missing'])} PDF(s) already gone")
        if result["failed"]:
            lines.append(f"⚠ {len(result['failed'])} PDF(s) could not be deleted")

        if backup and backup.exists():
            try:
                backup.unlink()
            except OSError:
                pass
        ds.clear()
        return "\n".join(lines)

    def summary(self) -> str:
        return "Settings"
