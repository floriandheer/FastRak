"""Form input helpers — Entry, Text, Spinbox, and labels with a
consistent look. Every input has a visible 1px border and a focus
ring in the accent color, so fields remain identifiable against any
card background.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Optional

from invoices_app.theme import PALETTE, FONTS


_INPUT_KWARGS = dict(
    relief=tk.FLAT,
    bd=0,
    highlightthickness=1,
)


def make_entry(parent: tk.Widget, textvariable: tk.Variable,
               width: int = 28, **kwargs: Any) -> tk.Entry:
    C = PALETTE
    entry = tk.Entry(
        parent, textvariable=textvariable, width=width,
        bg=C["bg_input"], fg=C["text"],
        insertbackground=C["text"],
        highlightbackground=C["input_border"],
        highlightcolor=C["input_border_focus"],
        font=FONTS["body"],
        **_INPUT_KWARGS, **kwargs,
    )
    return entry


def make_text(parent: tk.Widget, height: int = 4, width: int = 36,
              **kwargs: Any) -> tk.Text:
    C = PALETTE
    text = tk.Text(
        parent, height=height, width=width, wrap="word",
        bg=C["bg_input"], fg=C["text"],
        insertbackground=C["text"],
        highlightbackground=C["input_border"],
        highlightcolor=C["input_border_focus"],
        font=FONTS["body"],
        padx=6, pady=4,
        **_INPUT_KWARGS, **kwargs,
    )
    return text


def make_spinbox(parent: tk.Widget, textvariable: tk.Variable,
                 from_: float, to: float, width: int = 8,
                 **kwargs: Any) -> tk.Spinbox:
    C = PALETTE
    spin = tk.Spinbox(
        parent, textvariable=textvariable, from_=from_, to=to, width=width,
        bg=C["bg_input"], fg=C["text"],
        insertbackground=C["text"],
        buttonbackground=C["bg_panel"],
        highlightbackground=C["input_border"],
        highlightcolor=C["input_border_focus"],
        font=FONTS["body"],
        **_INPUT_KWARGS, **kwargs,
    )
    return spin


def form_label(parent: tk.Widget, text: str, **kwargs: Any) -> tk.Label:
    """Stronger-contrast label for form fields."""
    C = PALETTE
    bg = kwargs.pop("bg", C["card_bg"])
    return tk.Label(
        parent, text=text, fg=C["label_fg"], bg=bg,
        font=FONTS["label"], anchor="w", **kwargs,
    )
