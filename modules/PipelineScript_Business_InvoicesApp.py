"""Invoices — unified app replacing InvoiceBrowser, InvoiceCreator, and
the GUI of WooCommerceOrderMonitor.

Single window with a sidebar navigation: Dashboard, Compose, Outgoing,
Incoming, Orders, Legacy, Companies, Settings.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from invoices_app.app import InvoicesApp

root = tk.Tk()
InvoicesApp(root)
root.mainloop()
