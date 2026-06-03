"""Invoice Manager — unified app for outgoing invoices, incoming
invoices, WooCommerce orders, and bookkeeping folder structure.

Single window with a sidebar navigation: Dashboard, Compose, Outgoing,
Incoming, Orders, Companies, Settings.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from invoice_manager.app import InvoiceManager

root = tk.Tk()
InvoiceManager(root)
root.mainloop()
