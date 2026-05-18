Global Invoice — local data folder
===================================

Files in this folder
--------------------
- config.json          — your real configuration (gitignored; copy from .example)
- config.json.example  — committed template showing the schema
- invoices.sqlite      — SQLite registry; created automatically on first run
- invoices.sqlite-wal  — WAL journal (created automatically)
- invoices.sqlite-shm  — shared memory file (created automatically)

Setup
-----
1. Copy config.json.example to config.json.
2. Edit the company entries for FD, HV, and 3D with real legal names,
   VAT numbers, addresses, and bank details.
3. For Alles3D ("3D"), set `wc_binding.use_monitor_config` to true to reuse
   the credentials from modules/woocommerce_monitor_data/config.json, OR
   fill in the wc_binding fields directly.
4. Place LibreOffice .ott templates at the paths listed in template_path
   (relative to the repo root). See templates/invoice_templates_ott/README.txt.

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
