"""Modal dialog helpers that survive a -fullscreen parent on Windows.

tkinter's messagebox briefly deactivates the parent toplevel, which on
Windows lets the system taskbar slide back in over a fullscreened app.
These wrappers snapshot the parent's fullscreen flag before showing the
dialog and re-assert it on the way out so the taskbar disappears again.

Use ``ask_yes_no(parent, ...)`` / ``show_info(parent, ...)`` /
``show_error(parent, ...)`` anywhere we would have called
``messagebox.askyesno`` etc. ``parent`` can be any widget; we resolve it
to its toplevel internally.
"""

from __future__ import annotations

import tkinter as tk
from contextlib import contextmanager
from tkinter import messagebox
from typing import Iterator


@contextmanager
def preserve_fullscreen(parent: tk.Misc) -> Iterator[None]:
    """Re-assert -fullscreen on `parent`'s toplevel after the block runs."""
    toplevel = parent.winfo_toplevel()
    was_fs = False
    try:
        was_fs = bool(toplevel.attributes("-fullscreen"))
    except tk.TclError:
        pass
    try:
        yield
    finally:
        if was_fs:
            try:
                toplevel.attributes("-fullscreen", True)
            except tk.TclError:
                pass


def ask_yes_no(parent: tk.Misc, title: str, message: str) -> bool:
    with preserve_fullscreen(parent):
        return messagebox.askyesno(title, message, parent=parent.winfo_toplevel())


def show_info(parent: tk.Misc, title: str, message: str) -> None:
    with preserve_fullscreen(parent):
        messagebox.showinfo(title, message, parent=parent.winfo_toplevel())


def show_error(parent: tk.Misc, title: str, message: str) -> None:
    with preserve_fullscreen(parent):
        messagebox.showerror(title, message, parent=parent.winfo_toplevel())
