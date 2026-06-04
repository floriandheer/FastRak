"""Standalone Contacts window.

Top-level Tk app whose only job is to host the ContactsSection. Reuses
AppState (so the same SQLite registry / config is loaded), but skips the
WooCommerce monitor and legacy scan — neither is needed to manage
contacts and both add noticeable startup time. The Invoice Manager keeps
its own AppState; both write to the same DB file, so edits made here are
visible to the next Invoice Manager session and vice versa.
"""

from __future__ import annotations

import tkinter as tk

from shared_window_icon import apply_category_icon

from invoice_manager.sections.contacts import ContactsSection
from invoice_manager.state import AppState
from invoice_manager.theme import PALETTE, install_styles


class ContactsApp:
    """Single-section app — owns its window, AppState, and a mounted
    ContactsSection. Constructed against a Tk root (standalone) or a
    Toplevel (if another module wants to pop it as a child window).
    """

    def __init__(self, parent: tk.Misc):
        self.root = parent
        self.root.title("Contacts")
        self.root.geometry("960x680")
        self.root.minsize(780, 540)
        self.root.configure(bg=PALETTE["bg"])
        apply_category_icon(self.root, "Business")
        install_styles(self.root, set_theme=True)

        self.state = AppState()

        # Single-section host. No topbar / sidebar / statusbar — those
        # only earn their pixels in the multi-section Invoice Manager.
        host = tk.Frame(self.root, bg=PALETTE["bg"])
        host.pack(fill="both", expand=True)

        self.section = ContactsSection(host, self.state)
        self.section.mount()


def main() -> None:
    root = tk.Tk()
    ContactsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
