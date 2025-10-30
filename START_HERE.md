# 🚀 WooCommerce Order Monitor - START HERE!

## What You Got

I've created a **complete order automation system** that automatically organizes ALL your WooCommerce orders with invoices, labels, and order details!

## 📦 What It Does

```
New Order Arrives
       ↓
Auto-Creates Folder: "Order_1001_John_Doe/"
       ↓
   ├─ Invoice_1001.pdf          (Professional PDF invoice)
   ├─ Shipping_Label_1001.pdf   (bpost or other carrier)
   └─ Order_Details_1001.txt    (Complete order info)
       ↓
Ready to Pack & Ship!
```

## 🎯 What It Does

**Monitor ALL your WooCommerce orders and auto-organize everything!**

✅ All shipping methods (bpost, flat rate, etc.)
✅ Auto-generates professional invoices
✅ Downloads labels when available
✅ Customizable folder naming
✅ Smart filtering options

📄 **Script:** `modules/PipelineScript_Physical_WooCommerceOrderMonitor.py`
📘 **Quick Guide:** `README_ORDER_MONITOR.md`
📘 **Full Guide:** `_ref/ORDER_MONITOR_SETUP.md`

## ⚡ Quick Start (3 Minutes)

### Step 1: Install Python Packages

```bash
cd modules
pip install -r requirements.txt
```

This installs:
- `requests` - For WooCommerce API
- `reportlab` - For PDF generation

### Step 2: Get WooCommerce API Credentials

1. Log in to WordPress admin
2. Go to **WooCommerce → Settings → Advanced → REST API**
3. Click **"Add key"**
4. Set:
   - Description: "Order Monitor"
   - Permissions: **Read**
5. Click **"Generate API key"**
6. **Copy** Consumer Key and Consumer Secret

### Step 3: Configure

```bash
cd modules/woocommerce_monitor_data
cp config.json.example config.json
```

Edit `config.json`:

```json
{
    "woocommerce": {
        "url": "https://yourstore.com",           ← Your WooCommerce URL
        "consumer_key": "ck_xxxxx",               ← From Step 2
        "consumer_secret": "cs_xxxxx",            ← From Step 2
        "api_version": "wc/v3"
    },
    "monitoring": {
        "poll_interval": 300,                     ← Check every 5 minutes
        "base_directory": "I:/Physical/Orders"    ← Where to save folders
    }
}
```

### Step 4: Run It!

```bash
python PipelineScript_Physical_WooCommerceOrderMonitor.py
```

**The GUI opens!** Click **"▶ Start Monitoring"**

## ✅ Done!

The monitor will now:
1. Check for new orders every 5 minutes
2. Create organized folders automatically
3. Generate invoices
4. Download shipping labels (when available)
5. Save all order details

## 📁 Files Overview

### Main Script
```
modules/
└── PipelineScript_Physical_WooCommerceOrderMonitor.py     ← Order monitor script
```

### Configuration & Data
```
modules/woocommerce_monitor_data/
├── config.json.example          ← Template
├── config.json                  ← Your config (create from example)
├── processed_orders.json        ← Auto-generated tracking
├── monitor.log                  ← Auto-generated log
└── README.txt                   ← Folder documentation
```

### Documentation
```
README_ORDER_MONITOR.md              ← Quick reference guide
_ref/ORDER_MONITOR_SETUP.md          ← Complete setup guide
_ref/PLUGIN_UPDATE_GUIDE.md          ← bpost WordPress integration (optional)
```

## 🎨 Example Output

After running, you'll get folders like:

```
I:/Physical/Orders/
├── Order_1001_John_Doe/
│   ├── Invoice_1001.pdf
│   ├── Shipping_Label_1001.pdf
│   └── Order_Details_1001.txt
│
├── Order_1002_Jane_Smith/
│   ├── Invoice_1002.pdf
│   └── Order_Details_1002.txt
│
└── Order_1003_Bob_Wilson/
    ├── Invoice_1003.pdf
    ├── Shipping_Label_1003.pdf
    └── Order_Details_1003.txt
```

## ⚙️ Common Configurations

### Monitor Everything
```json
"monitoring": {
    "monitor_all_orders": true,
    "download_invoices": true,
    "download_labels": true
},
"filters": {
    "order_statuses": [],
    "shipping_methods": [],
    "payment_methods": []
}
```

### Monitor Only Processing Orders
```json
"filters": {
    "order_statuses": ["processing"]
}
```

### Monitor Only bpost Orders
```json
"filters": {
    "shipping_methods": ["bpost"]
}
```

### Custom Folder Names

**Simple:** `Order_1001/`
```json
"folder_structure": {
    "naming_format": "Order_{order_number}"
}
```

**With Customer:** `Order_1001_John_Doe/`
```json
"folder_structure": {
    "naming_format": "Order_{order_number}_{customer_name}"
}
```

**With Date:** `20250128_Order_1001_John_Doe/`
```json
"folder_structure": {
    "naming_format": "Order_{order_number}_{customer_name}",
    "include_date": true
}
```

## 🏷️ bpost Label Integration (Optional)

To automatically download bpost labels from WordPress:

### Quick Setup:

1. **Install WordPress helper files:**
   ```
   Upload to: /wp-content/plugins/bpost-shipping-platform/
   - bpost-monitor-helper.php
   - Modified Bpost.php
   ```
   (Files are in `_ref/bpost-shipping-platform/`)

2. **Get secret key from WordPress:**
   ```sql
   SELECT option_value FROM wp_options
   WHERE option_name = 'bpost_monitor_secret_key';
   ```

3. **Add to config:**
   ```json
   "woocommerce": {
       "monitor_secret_key": "your_secret_key_here"
   }
   ```

📘 **Full instructions:** `_ref/PLUGIN_UPDATE_GUIDE.md`

## 🛠️ Troubleshooting

### "Connection Error"
→ Check WooCommerce API credentials
→ Ensure URL is correct (with https://)
→ Verify API key has "Read" permission

### No Orders Appearing
→ Check order status filter (default: processing, completed)
→ Verify orders are within time window (default: 48 hours)
→ Test API manually:
```bash
curl -u "ck_xxx:cs_xxx" https://yourstore.com/wp-json/wc/v3/orders
```

### Invoices Not Generating
→ Install reportlab: `pip install reportlab`
→ Check folder is writable
→ Review log file: `woocommerce_order_monitor.log`

### Labels Not Downloading
→ Labels must be created in WooCommerce first!
→ For bpost: Install WordPress helper (optional)
→ Check order has label URL in metadata

## 📊 Monitoring Dashboard

The GUI shows:
- 🟢/⚫ **Status** (Running/Stopped)
- 📝 **Activity Log** (real-time updates)
- 📈 **Statistics** (processed orders count)
- 🎮 **Controls** (Start, Stop, Check Now)

**Log Colors:**
- 🟢 Green = Success
- 🟡 Orange = Warning
- 🔴 Red = Error
- ⚫ Black = Info

## 🔧 Advanced Features

### Run as Background Service
Set up Windows Task Scheduler or Linux systemd to run automatically.
📘 See: `_ref/ORDER_MONITOR_SETUP.md`

### Monitor Multiple Stores
Create separate configs and run multiple instances.

### Custom Invoice Templates
Edit `generate_invoice()` method to add your logo, colors, etc.

## 📚 Documentation Quick Links

| What You Need | Where to Look |
|--------------|---------------|
| Quick reference | `README_ORDER_MONITOR.md` |
| Complete setup guide | `_ref/ORDER_MONITOR_SETUP.md` |
| bpost integration | `_ref/PLUGIN_UPDATE_GUIDE.md` |
| Configuration options | `woocommerce_order_monitor_config.json.example` |

## 💡 Tips

1. **Start simple** - Use default config first
2. **Test with old orders** - Set `check_orders_since_hours: 720` (30 days)
3. **Check the log** - First place to look when troubleshooting
4. **Customize later** - Get it working, then tweak folder names, etc.
5. **Backup config** - Save your configuration file!

## 🎯 Recommended Workflow

### For New Users:
1. ✅ Install dependencies
2. ✅ Configure API credentials
3. ✅ Run monitor with defaults
4. ✅ Test with one order
5. ✅ Customize if needed

### For Advanced Users:
1. ✅ Configure filters (order status, shipping methods)
2. ✅ Customize folder naming
3. ✅ Set up bpost integration (if using bpost)
4. ✅ Configure as background service
5. ✅ Set up backups

## 🚦 What's Next?

After successful setup:
1. Monitor will check every 5 minutes
2. New orders create folders automatically
3. Check `I:/Physical/Orders/` for results
4. Review `woocommerce_order_monitor.log` for activity
5. Customize configuration as needed

## 🆘 Need Help?

1. **Check log file:** `modules/woocommerce_order_monitor.log`
2. **Read setup guide:** `_ref/ORDER_MONITOR_SETUP.md`
3. **Test API connection** (curl command in Troubleshooting)
4. **Verify configuration** (JSON syntax)

## 🎉 You're All Set!

Your order monitoring system is ready to go!

**To start monitoring:**
```bash
cd modules
python PipelineScript_Physical_WooCommerceOrderMonitor.py
```

Click **"▶ Start Monitoring"** and watch it work! 🚀

---

**Questions? Start with `README_ORDER_MONITOR.md` for quick reference!**

**Happy automating! 🎊**
