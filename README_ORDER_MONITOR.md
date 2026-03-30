# WooCommerce Order Monitor & Invoice Manager

Monitors WooCommerce orders, organizes project folders, and files invoices to the bookkeeping system.

## What It Does

```
Webshop Order  ──> Folder created  ──> Invoice filed to Boekhouding  ──> .lnk in project folder
Project Work   ──> Manual invoice via WooCommerce API  ──> Same filing flow
```

**All invoices go through WooCommerce** — one source of truth, one sequential numbering from WCPDF.

## Setup

### 1. WooCommerce REST API

1. WordPress Admin > WooCommerce > Settings > Advanced > REST API
2. Add key with **Read/Write** permissions (write needed for manual orders)
3. Copy the Consumer Key (`ck_...`) and Consumer Secret (`cs_...`)

### 2. WordPress Invoice Endpoint

The monitor downloads invoice PDFs via a custom WordPress endpoint. Add the contents of `woocommerce_monitor_data/pipeline-invoice-endpoint.php` to your theme's `functions.php` or as a micro-plugin:

```
wp-content/mu-plugins/pipeline-invoice-endpoint.php
```

This endpoint:
- Serves invoice PDFs authenticated via `monitor_secret_key`
- Auto-creates WCPDF invoice numbers if they don't exist yet
- Returns invoice metadata (number, date) for the filing system

**Requires:** [WooCommerce PDF Invoices & Packing Slips](https://wordpress.org/plugins/woocommerce-pdf-invoices-packing-slips/) plugin (free version works).

### 3. Monitor Secret Key

The endpoint uses the same secret as the bpost label integration. Set it in WordPress:

```bash
wp option update bpost_monitor_secret_key "your-secret-here"
```

Or add to `wp-config.php`:
```php
define('BPOST_MONITOR_SECRET_KEY', 'your-secret-here');
```

Then configure the same key in the monitor's Advanced Settings > Monitor Secret Key.

### 4. Configure the Monitor

First run creates `woocommerce_monitor_data/config.json`. Key settings:

```json
{
    "woocommerce": {
        "url": "https://yourdomain.com",
        "consumer_key": "ck_...",
        "consumer_secret": "cs_...",
        "monitor_secret_key": "your-secret-here"
    },
    "monitoring": {
        "base_directory": "I:/Physical/Order",
        "download_invoices": true,
        "download_labels": true
    }
}
```

Or configure everything via the GUI: **Advanced Settings** button.

## Features

### Order Monitoring

Polls WooCommerce for new orders and for each one:
1. Creates an order folder in `Physical/Order/`
2. Downloads the invoice PDF via the custom endpoint
3. Files it to `Boekhouding/{year}/Q{n}/Uitgaand/` as `3D_YYMMDD_Factuur{number}_{ClientName}.pdf`
4. Creates a `.lnk` shortcut in the order's `03_Outgoing/` folder
5. Downloads shipping labels (bpost) if available
6. Saves order details as text file

If the invoice endpoint isn't set up yet, falls back to legacy download methods.

### File Quarter Invoices

Catches up on any invoices that weren't filed during monitoring:

1. Click **"File Quarter Invoices"**
2. Select year and quarter
3. Fetches all orders for that period from WooCommerce
4. Files any missing invoices to the bookkeeping folder
5. Skips orders that already have a `.lnk` in their outgoing folder

### Create Project Invoice

For projects that come in outside the webshop (in person, phone, email):

1. Click **"Create Project Invoice"**
2. Fill in customer details and line item (description + amount)
3. Browse to the project folder
4. Creates a WooCommerce order via API (triggers WCPDF numbering)
5. Downloads and files the invoice, creates `.lnk` in project folder

This keeps all invoices in one system with sequential numbering.

## Folder Structure

### Active orders
```
D:\_work\Active\Physical\Order\
    Order_1001_JanJansens\
        00_Incoming\
        02_Production\
        03_Outgoing\
            3D_260315_Factuur012_Jansens.lnk  --> points to Boekhouding
```

### Bookkeeping (single source of truth)
```
D:\_work\Active\_LIBRARY\Boekhouding\2026\
    Q1\
        Binnenkomend\       <-- incoming invoices (purchases)
        Uitgaand\           <-- outgoing invoices (sales)
            3D_260107_Factuur009_Meubeltjes.pdf
            3D_260215_Factuur010_Pansen.pdf
            3D_260315_Factuur012_Jansens.pdf
    Q2\
        ...
```

### Invoice naming convention
```
3D_YYMMDD_Factuur{number}_{ClientLastName}.pdf
     |         |                |
     |         |                └── From WooCommerce billing last name
     |         └── From WCPDF invoice number
     └── From WCPDF invoice date
```

## GUI Controls

| Button | Description |
|--------|-------------|
| **Start Monitoring** | Begin polling for new orders |
| **Stop Monitoring** | Pause monitoring |
| **Check Now** | One-time check for new orders |
| **File Quarter Invoices** | Batch-file invoices for a quarter |
| **Create Project Invoice** | Create WooCommerce order + file invoice for non-webshop work |
| **Advanced Settings** | API credentials, filters, paths |

## Filters

Configure in Advanced Settings > Filters tab:

```json
"filters": {
    "order_statuses": ["processing", "completed"],
    "shipping_methods": [],
    "payment_methods": []
}
```

Empty arrays = accept all. Specify values to restrict (e.g. `["bpost"]` for shipping).

## Troubleshooting

### Invoice endpoint not working

1. Verify the PHP file is loaded: visit `yoursite.com/wp-admin/admin-ajax.php?action=pipeline_get_invoice_info&order_id=1&secret=your-key`
2. Should return JSON with invoice number/date, or an error message
3. Check that WCPDF plugin is active
4. Verify `monitor_secret_key` matches between WordPress and monitor config

### No orders found

1. Check API credentials (test with **Check Now**)
2. Verify `check_orders_since_hours` covers the time range
3. Check order status filter matches actual order statuses

### Shortcut creation fails

Requires `pywin32`:
```bash
pip install pywin32
```

## Files

```
modules/
    PipelineScript_Physical_WooCommerceOrderMonitor.py   <-- Main script
    woocommerce_monitor_data/
        config.json                                       <-- Configuration (auto-created)
        config.json.example                               <-- Config template
        processed_orders.json                             <-- Tracking (auto-created)
        pipeline-invoice-endpoint.php                     <-- WordPress endpoint (copy to WP)
        README.txt
```

## Version History

- **v3.0** - Invoice filing to Boekhouding, quarterly export, project invoicing via WooCommerce API
- **v2.0** - General order monitor with folder creation and document downloads
- **v1.0** - bpost label monitor only
