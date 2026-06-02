"""Invoice Manager — top-level window with Outgoing and Incoming tabs."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_form_keyboard import FORM_COLORS

from invoice_manager.outgoing_tab import OutgoingInvoicesTab
from invoice_manager.incoming_tab import IncomingInvoicesTab


class InvoiceManagerGUI:
    """Top-level invoice manager window with two main tabs."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Invoice Manager")
        self.root.geometry("1280x820")
        self.root.minsize(960, 640)
        self.root.configure(bg=FORM_COLORS["bg"])

        self._build_styles()
        self._build_ui()

    def _build_styles(self):
        C = FORM_COLORS
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Manager.TNotebook", background=C["bg"])
        style.configure(
            "Manager.TNotebook.Tab",
            background=C["bg_input"], foreground=C["text"],
            padding=[20, 8], font=("Arial", 11, "bold"),
        )
        style.map(
            "Manager.TNotebook.Tab",
            background=[("selected", C["accent_dark"])],
            foreground=[("selected", "#ffffff")],
        )

    def _build_ui(self):
        C = FORM_COLORS

        # Window header
        header = tk.Frame(self.root, bg=C["accent_dark"], height=52)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Invoice Manager",
            font=("Arial", 16, "bold"), fg="white", bg=C["accent_dark"],
        ).pack(side="left", padx=20, pady=12)

        # Top-level two-tab notebook
        self.notebook = ttk.Notebook(self.root, style="Manager.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=0, pady=0)

        # Outgoing tab
        outgoing_frame = tk.Frame(self.notebook, bg=FORM_COLORS["bg"])
        self.notebook.add(outgoing_frame, text="  📤  Outgoing Invoices  ")
        self.outgoing = OutgoingInvoicesTab(outgoing_frame)

        # Incoming tab
        incoming_frame = tk.Frame(self.notebook, bg=FORM_COLORS["bg"])
        self.notebook.add(incoming_frame, text="  📥  Incoming Invoices  ")
        self.incoming = IncomingInvoicesTab(incoming_frame)
