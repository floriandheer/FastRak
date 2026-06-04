"""Contacts — standalone customer directory.

Single-window CRUD over the same contacts table the embedded Invoice
Manager reads from. Use this to manage contacts without spinning up the
full Invoice Manager (no WooCommerce monitor, no legacy scan).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from invoice_manager.contacts_app import ContactsApp

root = tk.Tk()
ContactsApp(root)
root.mainloop()
