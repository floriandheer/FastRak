"""Contacts — directory of customers used by the compose form.

Two-pane layout: a left-hand list (with filter box) and a right-hand
edit form. Add/Save/Delete buttons drive the registry's contact CRUD
helpers; selecting a row loads it into the form. The optional WC
customer id links a contact to a WooCommerce customer so future order →
invoice flows can pick the right contact automatically.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional

from invoice_manager.dialogs import ask_yes_no, show_error, show_info
from invoice_manager.sections.base import Section
from invoice_manager.theme import PALETTE, FONTS
from invoice_manager.widgets.buttons import (
    danger_button, primary_button, secondary_button,
)
from invoice_manager.widgets.card import Card
from invoice_manager.widgets.inputs import form_label, make_entry, make_text


class ContactsSection(Section):
    title = "Contacts"
    sidebar_key = "contacts"
    sidebar_icon = "👤"

    # ----- listeners other parts of the app can subscribe to ----------
    _change_listeners: List = []

    @classmethod
    def on_change(cls, cb) -> None:
        """Fire `cb()` whenever any ContactsSection mutates the table."""
        cls._change_listeners.append(cb)

    def _notify_change(self) -> None:
        for cb in list(self._change_listeners):
            try:
                cb()
            except Exception:
                pass

    # ----- lifecycle --------------------------------------------------

    def build(self, root: tk.Frame) -> None:
        C = PALETTE
        root.configure(bg=C["bg"])
        wrap = tk.Frame(root, bg=C["bg"], padx=20, pady=14)
        wrap.pack(fill="both", expand=True)

        # Two-column body: list on the left, form on the right.
        body = tk.Frame(wrap, bg=C["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1, uniform="co")
        body.columnconfigure(1, weight=2, uniform="co")
        body.rowconfigure(0, weight=1)

        list_card = Card(body, title="All contacts")
        list_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._build_list(list_card.body)

        self._form_card = Card(body, title="Edit contact")
        self._form_card.grid(row=0, column=1, sticky="nsew")
        self._build_form(self._form_card.body)

        self._selected_id: Optional[int] = None
        self._all_contacts: List[Dict] = []
        self._reload_list()
        self._clear_form(disable=True)

    # ----- list pane --------------------------------------------------

    def _build_list(self, parent: tk.Frame) -> None:
        C = PALETTE

        filter_row = tk.Frame(parent, bg=C["card_bg"])
        filter_row.pack(fill="x", pady=(0, 8))
        form_label(filter_row, "Filter").pack(side="left", padx=(0, 8))
        self._filter_var = tk.StringVar()
        self._filter_var.trace_add("write", lambda *_: self._render_list())
        make_entry(filter_row, self._filter_var, width=24).pack(
            side="left", fill="x", expand=True,
        )

        tree_wrap = tk.Frame(parent, bg=C["card_bg"])
        tree_wrap.pack(fill="both", expand=True)
        self._tree = ttk.Treeview(
            tree_wrap, columns=("name", "email", "wc"),
            show="headings", style="InvApp.Treeview",
            selectmode="browse",
        )
        self._tree.heading("name", text="Name")
        self._tree.heading("email", text="Email")
        self._tree.heading("wc", text="WC #")
        self._tree.column("name", width=180, anchor="w")
        self._tree.column("email", width=180, anchor="w")
        self._tree.column("wc", width=60, anchor="e")
        sb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        btns = tk.Frame(parent, bg=C["card_bg"])
        btns.pack(fill="x", pady=(8, 0))
        secondary_button(btns, "+ New", self._on_new).pack(side="left")

    # ----- form pane --------------------------------------------------

    def _build_form(self, parent: tk.Frame) -> None:
        C = PALETTE
        self._f_name = tk.StringVar()
        self._f_vat = tk.StringVar()
        self._f_email = tk.StringVar()
        self._f_wc = tk.StringVar()
        self._f_notes = tk.StringVar()

        parent.columnconfigure(1, weight=1)

        def row(r: int, label: str, widget) -> None:
            form_label(parent, label).grid(
                row=r, column=0, sticky="w", padx=(0, 10), pady=(0, 6),
            )
            widget.grid(row=r, column=1, sticky="we", pady=(0, 6))

        row(0, "Name",  make_entry(parent, self._f_name, width=32))
        row(1, "VAT",   make_entry(parent, self._f_vat, width=24))
        row(2, "Email", make_entry(parent, self._f_email, width=32))
        row(3, "WC #",  make_entry(parent, self._f_wc, width=12))

        form_label(parent, "Address").grid(
            row=4, column=0, sticky="nw", padx=(0, 10), pady=(2, 6),
        )
        self._f_address = make_text(parent, height=4, width=32)
        self._f_address.grid(row=4, column=1, sticky="we", pady=(0, 6))

        row(5, "Notes", make_entry(parent, self._f_notes, width=32))

        btns = tk.Frame(parent, bg=C["card_bg"])
        btns.grid(row=6, column=0, columnspan=2, sticky="we", pady=(12, 0))
        self._save_btn = primary_button(btns, "Save", self._on_save)
        self._save_btn.pack(side="left")
        self._delete_btn = danger_button(btns, "Delete", self._on_delete)
        self._delete_btn.pack(side="left", padx=(8, 0))

    # ----- list helpers -----------------------------------------------

    def _reload_list(self) -> None:
        self._all_contacts = self.state.registry.list_contacts()
        self._render_list()

    def _render_list(self) -> None:
        needle = (self._filter_var.get() or "").strip().lower()
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        for c in self._all_contacts:
            if needle:
                hay = " ".join(str(c.get(k, "")) for k in
                               ("display_name", "email", "vat")).lower()
                if needle not in hay:
                    continue
            wc = c.get("wc_customer_id")
            self._tree.insert(
                "", "end", iid=str(c["id"]),
                values=(c.get("display_name", ""),
                        c.get("email", "") or "—",
                        str(wc) if wc else ""),
            )
        # Preserve selection if the row is still visible
        if self._selected_id is not None:
            sid = str(self._selected_id)
            if self._tree.exists(sid):
                self._tree.selection_set(sid)

    def _on_select(self, _e=None) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        cid = int(sel[0])
        contact = self.state.registry.get_contact(cid)
        if contact is None:
            return
        self._load_form(contact)

    def _on_new(self) -> None:
        self._tree.selection_remove(*self._tree.selection())
        self._clear_form(disable=False)
        # Hand focus to the name field so the user can just start typing.
        try:
            self._f_name.set("")
            # Find the Name entry to focus
            for child in self._form_card.body.winfo_children():
                if isinstance(child, tk.Entry):
                    child.focus_set()
                    break
        except Exception:
            pass

    # ----- form helpers -----------------------------------------------

    def _clear_form(self, *, disable: bool) -> None:
        self._selected_id = None
        self._f_name.set("")
        self._f_vat.set("")
        self._f_email.set("")
        self._f_wc.set("")
        self._f_notes.set("")
        self._f_address.delete("1.0", "end")
        state = "disabled" if disable else "normal"
        self._save_btn.configure(state=state)
        self._delete_btn.configure(state="disabled")

    def _load_form(self, contact: Dict) -> None:
        self._selected_id = int(contact["id"])
        self._f_name.set(contact.get("display_name", ""))
        self._f_vat.set(contact.get("vat", ""))
        self._f_email.set(contact.get("email", ""))
        wc = contact.get("wc_customer_id")
        self._f_wc.set("" if wc is None else str(wc))
        self._f_notes.set(contact.get("notes", ""))
        self._f_address.delete("1.0", "end")
        self._f_address.insert("1.0", contact.get("address", ""))
        self._save_btn.configure(state="normal")
        self._delete_btn.configure(state="normal")

    def _read_form(self) -> Optional[Dict]:
        name = self._f_name.get().strip()
        if not name:
            show_error(self.parent, "Save contact",
                       "Name is required.")
            return None
        wc_raw = self._f_wc.get().strip()
        wc_id: Optional[int] = None
        if wc_raw:
            try:
                wc_id = int(wc_raw)
            except ValueError:
                show_error(self.parent, "Save contact",
                           "WC # must be a number (or empty).")
                return None
        return {
            "display_name": name,
            "vat": self._f_vat.get().strip(),
            "email": self._f_email.get().strip(),
            "address": self._f_address.get("1.0", "end").strip(),
            "notes": self._f_notes.get().strip(),
            "wc_customer_id": wc_id,
        }

    def _on_save(self) -> None:
        data = self._read_form()
        if data is None:
            return
        try:
            if self._selected_id is None:
                new_id = self.state.registry.create_contact(data)
                self._selected_id = new_id
            else:
                self.state.registry.update_contact(self._selected_id, data)
        except Exception as e:
            show_error(self.parent, "Save contact", f"Could not save:\n{e}")
            return
        self._reload_list()
        self._notify_change()
        self._mark_status_dirty()

    def _on_delete(self) -> None:
        if self._selected_id is None:
            return
        contact = self.state.registry.get_contact(self._selected_id)
        if contact is None:
            return
        name = contact.get("display_name", "(no name)")
        if not ask_yes_no(self.parent, "Delete contact",
                          f"Delete contact '{name}'?\n\n"
                          "Existing invoices keep their snapshot of the "
                          "customer fields — only the contact entry is removed."):
            return
        try:
            self.state.registry.delete_contact(self._selected_id)
        except Exception as e:
            show_error(self.parent, "Delete contact", f"Could not delete:\n{e}")
            return
        self._clear_form(disable=True)
        self._reload_list()
        self._notify_change()
        self._mark_status_dirty()

    # ----- Section overrides ------------------------------------------

    def on_show(self) -> None:
        self._reload_list()

    def reload(self) -> None:
        self._reload_list()

    def summary(self) -> str:
        return f"Contacts · {len(self._all_contacts)} total"
