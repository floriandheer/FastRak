"""Invoice Manager — unified outgoing and incoming invoice management.

Two-tab window:
  📤 Outgoing Invoices  — create invoices, manage registry (from GlobalInvoice)
  📥 Incoming Invoices  — quarterly verification and naming checks (from InvoiceChecker)

The old PipelineScript_Business_GlobalInvoice.py and
PipelineScript_Business_InvoiceChecker.py still exist and work independently.
"""

import os
import sys

import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared_logging import setup_logging as setup_shared_logging
from shared_window_icon import apply_category_icon

from invoice_manager.gui import InvoiceManagerGUI


def main():
    setup_shared_logging("invoice_manager")
    root = tk.Tk()
    apply_category_icon(root)
    InvoiceManagerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
