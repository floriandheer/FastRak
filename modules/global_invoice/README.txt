Global Invoice — module README
===============================

This folder is the Python package; runtime data lives elsewhere.

Files in this folder
--------------------
- config.py / models.py / registry.py / …  — module source (committed)
- config.json.example                       — config template (committed)
- README.txt                                — this file (committed)

User-private data (NOT in the repo)
-----------------------------------
config.json and invoices.sqlite live in the per-user PipelineManager
AppData folder so they're never committed:

  Windows:  %LOCALAPPDATA%\PipelineManager\global_invoice\
  WSL:      /mnt/c/Users/<you>/AppData/Local/PipelineManager/global_invoice/
  Linux:    ~/.local/share/PipelineManager/global_invoice/

Files there:
  config.json          — your real configuration
  invoices.sqlite      — SQLite registry; created automatically on first run
  invoices.sqlite-wal  — WAL journal (created automatically)
  invoices.sqlite-shm  — shared memory file (created automatically)

Setup
-----
1. Run the tool once. If config.json doesn't exist it will tell you the
   exact destination path; copy config.json.example there and edit it.
2. Fill in real legal names, VAT numbers, addresses, and bank details
   for FD, HV, and 3D.
3. For Alles3D ("3D"), set wc_binding.use_monitor_config to true to reuse
   the credentials from modules/woocommerce_monitor_data/config.json, OR
   fill in the wc_binding fields directly in this config.
4. Place LibreOffice .ott templates at the paths listed in template_path
   (relative to the repo root). See templates/invoice_templates_ott/README.txt.

Migration from older layout
---------------------------
If you used a previous version that kept files inside the repo at
modules/global_invoice_data/, the first run after upgrading will
automatically move config.json and invoices.sqlite into the user data
folder above. The old folder can then be deleted.

Numbering
---------
- One shared sequence across all three companies, resets every calendar year.
- Voided invoices keep their number (Belgian gapless-numbering requirement).
- Test invoices: never delete — void with reason "test" instead.

Database
--------
- SQLite with WAL mode. Safe for concurrent read from the Tk UI and
  write from the WC monitor poll loop.
- Source of truth for all invoice numbers. If config.json is missing,
  the module won't start.
