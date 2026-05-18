LibreOffice invoice templates (.ott)
====================================

Drop one .ott file per company that uses LibreOffice rendering:
  - florian_dheer.ott   for company key "FD"
  - hyphen_v.ott        for company key "HV"

Alles3D ("3D") doesn't need a template here — its PDFs are rendered by
the WooCommerce PDF-Invoices plugin (the global system just assigns the
number and pushes it back into WC).

Placeholders the renderer will substitute
-----------------------------------------
Scalar placeholders (anywhere in body text, headers, footers, tables):
  {{invoice_number}}        e.g. "005"
  {{invoice_date}}          e.g. "2026-05-18"
  {{company_legal_name}}    from config.json
  {{company_vat}}
  {{company_address}}       multi-line, newline-joined
  {{company_email}}
  {{company_iban}}
  {{company_bic}}
  {{customer_name}}
  {{customer_vat}}          may be empty for B2C
  {{customer_address}}      multi-line
  {{subtotal}}              formatted "€ 1.234,56"
  {{vat}}                   formatted "€ 1.234,56"
  {{total}}                 formatted "€ 1.234,56"
  {{currency}}              e.g. "EUR"

Line items: build a table row that contains the literal marker
  {{line_item_row}}
somewhere in the row (in a comment cell, or in a hidden span). That row
is cloned once per line item, with these per-row placeholders:
  {{desc}}
  {{qty}}
  {{unit_price}}            formatted "€ 1.234,56"
  {{vat_rate}}              e.g. "21%"
  {{line_total}}            formatted "€ 1.234,56"

The marker text itself is stripped from the cloned rows after substitution.

Tips
----
- Don't apply character formatting across a placeholder (LibreOffice will
  split the run and the substitution will fail). Type {{x}} as one
  continuous span of plain text, then format afterwards.
- Currency formatting follows European convention (dot thousands, comma
  decimal). Edit global_invoice/template_engine.py if you need otherwise.
