"""InvoicesApp — top-level window composing shell + sections.

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

from invoices_app.shell.debug_banner import DebugBanner
from invoices_app.shell.sidebar import Sidebar
from invoices_app.shell.statusbar import StatusBar
from invoices_app.shell.topbar import TopBar
from invoices_app.state import AppState
from invoices_app.theme import PALETTE, install_styles
from invoices_app.sections.base import Section
from invoices_app.sections.companies import CompaniesSection
from invoices_app.sections.compose import ComposeSection
from invoices_app.sections.dashboard import DashboardSection
from invoices_app.sections.incoming import IncomingSection
from invoices_app.sections.orders import OrdersSection
from invoices_app.sections.outgoing import OutgoingSection
from invoices_app.sections.settings import SettingsSection


class InvoicesApp:
    """Wires the shell + every section together. Owns the AppState."""

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Invoices")
        root.geometry("1280x820")
        root.minsize(1100, 700)
        root.configure(bg=PALETTE["bg"])
        apply_category_icon(root, "Business")

        install_styles(root)

        self.state = AppState()
        self.state.on_year_change(self._broadcast_year)
        self.state.on_company_change(self._broadcast_company)

        # ----- chrome -----
        self.debug_banner = DebugBanner(root, self.state, self._on_debug_toggle)
        self.topbar = TopBar(root, self.state, self._reload_active)
        self.topbar.pack(side="top", fill="x")

        body = tk.Frame(root, bg=PALETTE["bg"])
        body.pack(side="top", fill="both", expand=True)

        self.sidebar = Sidebar(body, on_select=self.navigate)
        self.sidebar.pack(side="left", fill="y")

        self.content = tk.Frame(body, bg=PALETTE["bg"])
        self.content.pack(side="left", fill="both", expand=True)

        self.statusbar = StatusBar(root)
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
        self.state.start_wc_monitor(root)
        self.state.start_legacy_scan(root)

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
    InvoicesApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
