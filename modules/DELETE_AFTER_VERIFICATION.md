# Delete after verification

`PipelineScript_Business_InvoicesApp.py` (under `invoices_app/`) replaces
the older invoice scripts. Use this file as a cleanup log.

## Already deleted

- ~~`PipelineScript_Business_InvoiceBrowser.py`~~ — gone
- ~~`PipelineScript_Business_InvoiceCreator.py`~~ — gone
- ~~`PipelineScript_Business_GlobalInvoice.py`~~ — gone
- ~~`invoice_browser/`~~ (whole package) — gone
- ~~`invoice_creator/`~~ (whole package) — gone
- All matching `__pycache__/` entries — gone

The fastrak launcher entries for these scripts were removed from
`pipeline_categories.py` at the same time.

## Verification checklist for the new app

Open `Invoices` from the Business category in fastrak and exercise:

- [ ] **Dashboard** — quarter cards populate, "needs attention" lists known issues, recent activity table fills.
- [ ] **Compose · Manual** — generate a real invoice; PDF lands in Boekhouding; registry sequence advances.
- [ ] **Compose · WC Project** — create a project invoice; WooCommerce order created; PDF filed.
- [ ] **Compose · Expenses tab** — add an expense line, totals update, generated PDF includes it.
- [ ] **Outgoing** — quarter chips swap rows; Sync WC and File Q*N* WC work; Void prompt persists.
- [ ] **Outgoing · Show legacy** — un-imported PDFs render as italic sub-groups; selecting a row reveals `Import → registry`.
- [ ] **Incoming · Vendors view** — quarter chips drive scan; tree shows expected vs found per vendor.
- [ ] **Incoming · Duplicates view** — files appearing in multiple quarters listed.
- [ ] **Incoming · Naming view** — naming issues listed; Rename → Confirm round-trips.
- [ ] **Orders** — order list loads; chips + search filter live; Open folder, View invoice, View label, Change invoice #, Change status all act on the selected order; File quarter invoices dialog runs.
- [ ] **Companies** — card grid renders all companies.
- [ ] **Settings** — environment paths reported correctly; Enter / Exit debug mode round-trip works.

## Still around — but candidates for the next clean-up

These weren't deleted yet because they still launch cleanly. Once
you've confirmed the new app covers everything you need, they can go:

- `PipelineScript_Business_InvoiceManager.py` — legacy launcher, still in the fastrak menu as "Invoice Manager (legacy)".
- `PipelineScript_Business_InvoiceChecker.py` — legacy launcher, still in the fastrak menu as "Invoice Checker (legacy)".
- `invoice_manager/outgoing_tab.py` — dead code in an otherwise-live package. The package's `incoming_scanner.py` is still in use by `invoices_app/sections/incoming.py`, so don't delete the whole `invoice_manager/` folder.
- `invoice_manager/incoming_tab.py` — no longer imported (the new `IncomingSection` uses `incoming_scanner` directly). Safe to delete once you've verified the new Incoming view.

## Special case — `PipelineScript_Physical_WooCommerceOrderMonitor.py`

- Its **GUI** (`OrderMonitorGUI`, `SettingsDialog`, `main()`) is dead
  weight — the new Orders section replaces it.
- Its **backend classes** (`Config`, `OrderMonitor`, `WooCommerceClient`,
  `DocumentManager`, `InvoiceFiler`, `ProcessedOrdersTracker`) are
  imported by `invoices_app/state.py` at runtime. Deleting the file
  without first relocating these will break the Orders section.

**Two options:**

1. **Leave it in place** — perfectly fine; treat it as backend-only.
2. **Relocate the classes** into a clean home (e.g. `invoices_app/wc_monitor/`)
   and update `invoices_app/state.py` to import from there, then delete
   the old file.

## Keep — in active use by the new app

- `invoice_manager/incoming_scanner.py` — still the workhorse for the Incoming section.
- `global_invoice/` — core business-logic library (registry, config, filer, models, wc_bridge, …).
- All `shared_*.py` modules.
