"""InvoiceManager — top-level window composing shell + sections.

  ┌──────────────────────────────────────────────────────────────┐
  │  DebugBanner (only when active)                              │
  ├──────────────────────────────────────────────────────────────┤
  │  TopBar — title + year/company filters + reload              │
  ├──────────┬───────────────────────────────────────────────────┤
  │ Sidebar  │  Active section frame                              │
  │  nav     │                                                    │
  ├──────────┴───────────────────────────────────────────────────┤
  │  StatusBar — section-specific summary                         │
  └──────────────────────────────────────────────────────────────┘

The WC OrderMonitor and the legacy invoice scanner are kicked off in
background threads as soon as AppState is constructed — the user never
has to click Start. The sidebar Orders entry gets a red badge whenever
there are orders in `processing` status that need shipping.
"""

from __future__ import annotations

import tkinter as tk
from typing import Dict, List, Optional

from shared_window_icon import apply_category_icon

from invoice_manager.shell.debug_banner import DebugBanner
from invoice_manager.shell.sidebar import Sidebar
from invoice_manager.shell.statusbar import StatusBar
from invoice_manager.shell.topbar import TopBar
from invoice_manager.state import AppState
from invoice_manager.theme import PALETTE, install_styles
from invoice_manager.sections.base import Section
from invoice_manager.sections.companies import CompaniesSection
from invoice_manager.sections.compose import ComposeSection
from invoice_manager.sections.dashboard import DashboardSection
from invoice_manager.sections.incoming import IncomingSection
from invoice_manager.sections.orders import OrdersSection
from invoice_manager.sections.outgoing import OutgoingSection
from invoice_manager.sections.settings import SettingsSection


class InvoiceManager:
    """Wires the shell + every section together. Owns the AppState.

    Can run as a standalone window OR be embedded inside another
    Tk app's frame (fastrak_hub mounts it inside the Business panel).
    """

    def __init__(self, parent, *, embedded: bool = False):
        """
        Args:
            parent: Tk root (standalone) or a Frame (embedded).
            embedded: If True, skip window-level configuration
                (title, geometry, icon, ttk theme) so the app renders
                inside the caller's parent frame without taking over
                window state.
        """
        self.embedded = embedded
        if embedded:
            # parent is a Frame inside the host app — derive the real
            # root for after()-marshalling but draw everything into
            # `container`, a Frame we own.
            self.root = parent.winfo_toplevel()
            self.container = tk.Frame(parent, bg=PALETTE["bg"])
            self.container.pack(fill="both", expand=True)
        else:
            self.root = parent
            self.root.title("Invoice Manager")
            self.root.geometry("1280x820")
            self.root.minsize(1100, 700)
            self.root.configure(bg=PALETTE["bg"])
            apply_category_icon(self.root, "Business")
            self.container = self.root

        # Only switch the global ttk theme when standalone — the host
        # picks its own. Named ``InvApp.*`` styles get registered
        # either way and don't conflict with the host's widgets.
        install_styles(self.root, set_theme=not embedded)

        self.state = AppState()
        self.state.on_year_change(self._broadcast_year)
        self.state.on_company_change(self._broadcast_company)

        # ----- chrome -----
        self.debug_banner = DebugBanner(self.container, self.state,
                                        self._on_debug_toggle)
        self.topbar = TopBar(self.container, self.state, self._reload_active)
        self.topbar.pack(side="top", fill="x")

        body = tk.Frame(self.container, bg=PALETTE["bg"])
        body.pack(side="top", fill="both", expand=True)

        self.sidebar = Sidebar(body, on_select=self.navigate)
        self.sidebar.pack(side="left", fill="y")

        self.content = tk.Frame(body, bg=PALETTE["bg"])
        self.content.pack(side="left", fill="both", expand=True)

        self.statusbar = StatusBar(self.container)
        self.statusbar.pack(side="bottom", fill="x")

        # ----- sections -----
        self.sections: Dict[str, Section] = {}
        self._mount_sections()
        for sec in self.sections.values():
            sec.set_status_dirty_callback(self._refresh_status)
        self._mount_sidebar()
        self._refresh_debug_banner()

        # ----- background workers — start AFTER sections subscribe -----
        # Orders section + AppState observers are already registered, so
        # the monitor's first callback will land on a live listener.
        self.state.on_wc_orders(self._on_orders_for_badge)
        # When the legacy scan finishes it usually expands the set of
        # years the user can pick from — refresh the top-bar dropdown.
        self.state.on_legacy_scan(self.topbar.refresh_years)
        self.state.start_wc_monitor(self.root)
        self.state.start_legacy_scan(self.root)

        self.navigate("dashboard")

    # ----- section setup ----------------------------------------------

    def _mount_sections(self) -> None:
        self.sections["dashboard"] = DashboardSection(
            self.content, self.state, nav_to=self.navigate,
        )
        self.sections["compose"]   = ComposeSection(self.content, self.state)
        self.sections["outgoing"]  = OutgoingSection(self.content, self.state)
        self.sections["incoming"]  = IncomingSection(self.content, self.state)
        self.sections["orders"]    = OrdersSection(self.content, self.state)
        self.sections["companies"] = CompaniesSection(self.content, self.state)
        self.sections["settings"]  = SettingsSection(
            self.content, self.state, on_debug_toggle=self._refresh_debug_banner,
        )

    def _mount_sidebar(self) -> None:
        # Primary nav — Legacy import is merged into Outgoing via a toggle.
        for key in ("dashboard", "compose", "outgoing", "incoming", "orders"):
            sec = self.sections[key]
            self.sidebar.add(sec.sidebar_key, sec.title, sec.sidebar_icon)
        self.sidebar.add_separator()
        for key in ("companies", "settings"):
            sec = self.sections[key]
            self.sidebar.add(sec.sidebar_key, sec.title, sec.sidebar_icon)

    # ----- nav ---------------------------------------------------------

    _active: Optional[str] = None

    def navigate(self, key: str) -> None:
        if key not in self.sections:
            return
        if self._active == key:
            return
        if self._active and self._active in self.sections:
            self.sections[self._active].unmount()
        self._active = key
        sec = self.sections[key]
        sec.mount()
        self.sidebar.set_active(key)
        self.topbar.set_title(sec.title)
        self._refresh_status()

    def _reload_active(self) -> None:
        if self._active:
            self.sections[self._active].reload()
            self._refresh_status()

    def _refresh_status(self) -> None:
        if self._active:
            self.statusbar.set(self.sections[self._active].summary())

    # ----- broadcasts -------------------------------------------------

    def _broadcast_year(self, year: int) -> None:
        for sec in self.sections.values():
            try:
                sec.on_year_change(year)
            except Exception:
                pass
        self.topbar.refresh_years()
        self._refresh_status()

    def _broadcast_company(self, company: str) -> None:
        for sec in self.sections.values():
            try:
                sec.on_company_change(company)
            except Exception:
                pass
        self._refresh_status()

    # ----- sidebar badge ----------------------------------------------

    def _on_orders_for_badge(self, orders: List[dict]) -> None:
        """Count of orders in 'processing' status — these are the ones
        that need shipping action. Renders as a red pill next to the
        Orders nav item; hidden when zero.
        """
        n = sum(1 for o in orders if o.get("status") == "processing")
        self.sidebar.set_badge("orders", n if n else None)

    # ----- debug banner -----------------------------------------------

    def _refresh_debug_banner(self) -> None:
        active = self.state.debug_session.is_active()
        self.debug_banner.refresh()
        self.debug_banner.pack_forget()
        if active:
            self.debug_banner.pack(side="top", fill="x", before=self.topbar)

    def _on_debug_toggle(self) -> None:
        self._refresh_debug_banner()


def main():
    root = tk.Tk()
    InvoiceManager(root)
    root.mainloop()


if __name__ == "__main__":
    main()
