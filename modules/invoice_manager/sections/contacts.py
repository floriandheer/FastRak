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

from shared_logging import get_logger

from invoice_manager.dialogs import ask_yes_no, show_error, show_info
from invoice_manager.sections.base import Section
from invoice_manager.theme import PALETTE, FONTS
from invoice_manager.widgets.buttons import (
    danger_button, primary_button, secondary_button,
)
from invoice_manager.widgets.card import Card
from invoice_manager.widgets.inputs import form_label, make_entry, make_text

logger = get_logger("invoice_manager.contacts")


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
            tree_wrap, columns=("name", "abbr", "email"),
            show="headings", style="InvApp.Treeview",
            selectmode="browse",
        )
        self._tree.heading("name", text="Name")
        self._tree.heading("abbr", text="Abbreviation")
        self._tree.heading("email", text="Email")
        self._tree.column("name", width=180, anchor="w")
        self._tree.column("abbr", width=120, anchor="w")
        self._tree.column("email", width=180, anchor="w")
        sb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        btns = tk.Frame(parent, bg=C["card_bg"])
        btns.pack(fill="x", pady=(8, 0))
        secondary_button(btns, "+ New", self._on_new).pack(side="left")
        # Reads the project DB for clients that aren't yet a contact —
        # one click opens a picker that pre-fills the form.
        self._import_btn = secondary_button(
            btns, "📥 Import from projects",
            self._open_project_picker,
        )
        self._import_btn.pack(side="left", padx=(8, 0))

    # ----- form pane --------------------------------------------------

    def _build_form(self, card_body: tk.Frame) -> None:
        C = PALETTE
        # Card.body already packs its title label, so we can't grid()
        # directly into it — wrap in an intermediate Frame that we
        # exclusively manage with grid.
        parent = tk.Frame(card_body, bg=C["card_bg"])
        parent.pack(fill="both", expand=True)
        self._f_name = tk.StringVar()
        self._f_abbr = tk.StringVar()
        self._f_vat = tk.StringVar()
        self._f_email = tk.StringVar()
        self._f_notes = tk.StringVar()
        # Project-client link is hidden state — set when the user imports
        # from the project picker (or when loading a previously-linked
        # contact) and persisted on save. The dim "From project: …" label
        # below echoes it so the user knows what folder name we'll keep.
        self._pending_project_link: Optional[str] = None
        self._f_project_label = tk.StringVar(value="")

        parent.columnconfigure(1, weight=1)

        def row(r: int, label: str, widget) -> None:
            form_label(parent, label).grid(
                row=r, column=0, sticky="w", padx=(0, 10), pady=(0, 6),
            )
            widget.grid(row=r, column=1, sticky="we", pady=(0, 6))

        self._name_entry = make_entry(parent, self._f_name, width=32)
        row(0, "Name",  self._name_entry)

        # Abbreviation row + a small hint underneath about its purpose.
        # Kept tightly grouped with the Name field since they often vary
        # together (real name vs. folder-safe short form).
        row(1, "Abbreviation", make_entry(parent, self._f_abbr, width=24))
        tk.Label(
            parent, text="Used for new project folder names.",
            fg=C["text_dim"], bg=C["card_bg"], font=FONTS["small"], anchor="w",
        ).grid(row=2, column=1, sticky="w", pady=(0, 6))

        row(3, "VAT",   make_entry(parent, self._f_vat, width=24))
        row(4, "Email", make_entry(parent, self._f_email, width=32))

        form_label(parent, "Address").grid(
            row=5, column=0, sticky="nw", padx=(0, 10), pady=(2, 6),
        )
        self._f_address = make_text(parent, height=4, width=32)
        self._f_address.grid(row=5, column=1, sticky="we", pady=(0, 6))

        row(6, "Notes", make_entry(parent, self._f_notes, width=32))

        # Dim "From project: <folder name>" line — shows the original
        # one-string client identifier this contact was imported from so
        # the user can verify the project folder mapping stays intact.
        tk.Label(
            parent, textvariable=self._f_project_label,
            fg=C["text_dim"], bg=C["card_bg"], font=FONTS["small"],
            anchor="w",
        ).grid(row=7, column=0, columnspan=2, sticky="we", pady=(4, 0))

        btns = tk.Frame(parent, bg=C["card_bg"])
        btns.grid(row=8, column=0, columnspan=2, sticky="we", pady=(12, 0))
        self._save_btn = primary_button(btns, "Save", self._on_save)
        self._save_btn.pack(side="left")
        self._delete_btn = danger_button(btns, "Delete", self._on_delete)
        self._delete_btn.pack(side="left", padx=(8, 0))

    # ----- list helpers -----------------------------------------------

    def _reload_list(self) -> None:
        self._all_contacts = self.state.registry.list_contacts()
        self._render_list()
        self._refresh_import_button()

    def _refresh_import_button(self) -> None:
        """Update the toolbar button's label with the unlinked-project count."""
        if not hasattr(self, "_import_btn"):
            return
        n = len(self._unlinked_project_clients())
        if n:
            label = f"📥 Import from projects ({n})"
        else:
            label = "📥 Import from projects"
        try:
            self._import_btn.configure(text=label)
        except tk.TclError:
            pass

    def _unlinked_project_clients(self) -> List[Dict]:
        """Project DB clients that don't yet have a linked contact.

        Returns a list of dicts with keys: name (the one-string folder
        name), project_count, is_personal. Sorted by project_count desc
        so the most-used candidates surface first.
        """
        try:
            from shared_project_db import ProjectDatabase
            db = ProjectDatabase()
            all_clients = db.get_all_clients(exclude_personal=True)
        except Exception:
            logger.exception("Could not read project DB for contact import")
            return []
        linked = {
            (c.get("project_client_name") or "").strip()
            for c in self._all_contacts
            if c.get("project_client_name")
        }
        candidates = [
            c for c in all_clients
            if c.get("name", "").strip() and c.get("name") not in linked
        ]
        candidates.sort(key=lambda c: (-int(c.get("project_count") or 0),
                                       c.get("name", "").lower()))
        return candidates

    def _open_project_picker(self) -> None:
        """Modal Toplevel listing unlinked project clients. Multi-select
        is enabled (Shift/Ctrl-click) so a whole batch can be imported in
        one go. Each pick becomes a contact with ``display_name`` set to
        the project's one-string folder name; the user can rename any of
        them later from the main contacts list.
        """
        candidates = self._unlinked_project_clients()
        if not candidates:
            show_info(self.parent, "Import from projects",
                      "Every project client is already a contact.")
            return

        C = PALETTE
        win = tk.Toplevel(self.parent.winfo_toplevel())
        win.title("Import from projects")
        win.configure(bg=C["bg"])
        win.transient(self.parent.winfo_toplevel())
        win.grab_set()
        win.geometry("460x460")

        tk.Label(
            win,
            text=("Pick one or more project clients to promote to "
                  "contacts.\nShift-click or Ctrl-click for multi-select."),
            fg=C["text_dim"], bg=C["bg"], font=FONTS["small"],
            anchor="w", justify="left", padx=14, pady=10,
        ).pack(fill="x")

        tree_wrap = tk.Frame(win, bg=C["bg"], padx=14)
        tree_wrap.pack(fill="both", expand=True)
        tree = ttk.Treeview(
            tree_wrap, columns=("name", "n"), show="headings",
            style="InvApp.Treeview", selectmode="extended",
        )
        tree.heading("name", text="Folder name")
        tree.heading("n", text="Projects")
        tree.column("name", width=260, anchor="w")
        tree.column("n", width=80, anchor="e")
        sb = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for c in candidates:
            tree.insert(
                "", "end", iid=c["name"],
                values=(c["name"], int(c.get("project_count") or 0)),
            )

        # Ctrl+A → select all (handy when the user wants every candidate)
        def select_all(_e=None):
            tree.selection_set(tree.get_children())
            return "break"
        tree.bind("<Control-a>", select_all)
        tree.bind("<Control-A>", select_all)

        def commit(_e=None):
            picked = list(tree.selection())
            if not picked:
                return
            win.destroy()
            self._bulk_import_from_projects(picked)

        tree.bind("<Double-Button-1>", commit)
        tree.bind("<Return>", commit)

        btns = tk.Frame(win, bg=C["bg"], padx=14, pady=10)
        btns.pack(fill="x")
        primary_button(btns, "Add selected as contacts", commit).pack(side="right")
        secondary_button(btns, "Cancel", win.destroy).pack(
            side="right", padx=(0, 8),
        )

    def _bulk_import_from_projects(self, project_client_names: List[str]) -> None:
        """Insert one contact per project client name, using the folder
        name as the display_name. Skips entries that already exist (the
        unique partial index would have rejected them anyway).
        """
        added = 0
        skipped: List[str] = []
        errors: List[str] = []
        for name in project_client_names:
            try:
                # The project folder name is the abbreviation. We leave
                # display_name blank on purpose: the user fills in the
                # real human name from the form, while the abbreviation
                # stays as the on-disk folder identifier.
                self.state.registry.create_contact({
                    "display_name": "",
                    "abbreviation": name,
                    "project_client_name": name,
                })
                added += 1
            except Exception as e:
                # Most likely the unique partial index — someone added
                # this contact from another window between picker open
                # and commit. Treat as "already there" rather than fatal.
                msg = str(e).lower()
                if "unique" in msg or "constraint" in msg:
                    skipped.append(name)
                else:
                    logger.exception(f"Could not import project client {name!r}")
                    errors.append(f"{name}: {e}")

        self._reload_list()
        self._notify_change()
        self._mark_status_dirty()

        parts = [f"Added {added} contact(s)."]
        if skipped:
            parts.append(f"Skipped {len(skipped)} already linked.")
        if errors:
            parts.append("Errors:\n  " + "\n  ".join(errors[:5]))
            if len(errors) > 5:
                parts.append(f"  …and {len(errors) - 5} more (see log)")
        show_info(self.parent, "Import from projects", "\n".join(parts))

    def _render_list(self) -> None:
        needle = (self._filter_var.get() or "").strip().lower()
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        for c in self._all_contacts:
            if needle:
                hay = " ".join(str(c.get(k, "")) for k in
                               ("display_name", "abbreviation", "email", "vat")).lower()
                if needle not in hay:
                    continue
            display = (c.get("display_name") or "").strip() or "(needs name)"
            self._tree.insert(
                "", "end", iid=str(c["id"]),
                values=(display,
                        c.get("abbreviation", "") or "",
                        c.get("email", "") or "—"),
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
            self._name_entry.focus_set()
        except (AttributeError, tk.TclError):
            pass

    # ----- form helpers -----------------------------------------------

    def _clear_form(self, *, disable: bool) -> None:
        self._selected_id = None
        self._pending_project_link = None
        self._f_project_label.set("")
        self._f_name.set("")
        self._f_abbr.set("")
        self._f_vat.set("")
        self._f_email.set("")
        self._f_notes.set("")
        self._f_address.delete("1.0", "end")
        state = "disabled" if disable else "normal"
        self._save_btn.configure(state=state)
        self._delete_btn.configure(state="disabled")

    def _load_form(self, contact: Dict) -> None:
        self._selected_id = int(contact["id"])
        self._f_name.set(contact.get("display_name", ""))
        self._f_abbr.set(contact.get("abbreviation") or "")
        self._f_vat.set(contact.get("vat", ""))
        self._f_email.set(contact.get("email", ""))
        self._f_notes.set(contact.get("notes", ""))
        self._f_address.delete("1.0", "end")
        self._f_address.insert("1.0", contact.get("address", ""))
        self._pending_project_link = contact.get("project_client_name") or None
        self._set_project_label(self._pending_project_link)
        self._save_btn.configure(state="normal")
        self._delete_btn.configure(state="normal")

    def _set_project_label(self, project_client: Optional[str]) -> None:
        if project_client:
            self._f_project_label.set(
                f"From project: {project_client}  "
                f"(project folder name kept as-is)"
            )
        else:
            self._f_project_label.set("")

    def _read_form(self) -> Optional[Dict]:
        name = self._f_name.get().strip()
        abbreviation = self._f_abbr.get().strip() or None
        # At least one of name or abbreviation needs content — otherwise
        # the contact has nothing identifying it. (Imported rows always
        # have an abbreviation, so this only blocks truly empty saves.)
        if not name and not abbreviation:
            show_error(self.parent, "Save contact",
                       "Enter at least a name or an abbreviation.")
            return None
        return {
            "display_name": name,
            "abbreviation": abbreviation,
            "vat": self._f_vat.get().strip(),
            "email": self._f_email.get().strip(),
            "address": self._f_address.get("1.0", "end").strip(),
            "notes": self._f_notes.get().strip(),
            "project_client_name": self._pending_project_link,
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
