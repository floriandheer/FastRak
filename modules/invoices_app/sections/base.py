"""Base class every section inherits from.

A Section owns one tk.Frame parented to the app's content area. The app
calls `mount()` when the section becomes visible and `unmount()` when
the user navigates away. Most sections build their UI lazily on first
mount and just hide/show the existing frame afterwards.
"""

from __future__ import annotations

import tkinter as tk
from typing import Optional

from typing import Callable

from invoices_app.state import AppState
from invoices_app.theme import PALETTE


class Section:
    """Abstract section. Subclasses override `title`, `build`, and
    optionally `on_year_change`, `on_company_change`, `summary`, `reload`.
    """

    title: str = ""
    sidebar_key: str = ""
    sidebar_icon: str = ""

    def __init__(self, parent: tk.Widget, state: AppState):
        self.parent = parent
        self.state = state
        self.frame: Optional[tk.Frame] = None
        self._built = False
        # Set by the app shell so a section can ask the status bar to
        # re-read its `summary()` after internal state changes.
        self._status_dirty_cb: Optional[Callable[[], None]] = None

    def set_status_dirty_callback(self, cb: Callable[[], None]) -> None:
        self._status_dirty_cb = cb

    def _mark_status_dirty(self) -> None:
        if self._status_dirty_cb is not None:
            try:
                self._status_dirty_cb()
            except Exception:
                pass

    def mount(self) -> None:
        if not self._built:
            self.frame = tk.Frame(self.parent, bg=PALETTE["bg"])
            self.build(self.frame)
            self._built = True
        assert self.frame is not None
        self.frame.pack(fill="both", expand=True)
        self.on_show()

    def unmount(self) -> None:
        if self.frame is not None:
            self.frame.pack_forget()

    # ----- overridable -------------------------------------------------

    def build(self, root: tk.Frame) -> None:
        """Build the section UI into `root`. Called once."""

    def on_show(self) -> None:
        """Called every time the section becomes visible."""

    def on_year_change(self, year: int) -> None:
        """Override to react to top-bar year filter."""

    def on_company_change(self, company: str) -> None:
        """Override to react to top-bar company filter."""

    def reload(self) -> None:
        """Triggered by the top-bar reload button while this section is active."""

    def summary(self) -> str:
        """Text rendered in the statusbar while this section is active."""
        return ""
