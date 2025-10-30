# WooCommerce Order Monitor & Auto-Organizer

## 🎯 What It Does

**Automatically creates organized folders for every WooCommerce order with invoices, labels, and order details!**

```
New Order → Auto Folder → Invoice + Label + Details
```

## ✨ Features

- 📁 **Auto-creates folders** for each order
- 📄 **Generates professional PDF invoices**
- 🏷️ **Downloads shipping labels** (bpost, etc.)
- 📝 **Saves complete order details**
- 🎨 **Customizable folder naming** (with customer names!)
- ⚡ **Real-time monitoring** with GUI
- 🔍 **Smart filtering** (status, shipping method, payment)

## 🚀 Quick Start (3 Minutes!)

### 1. Install Dependencies

```bash
cd modules
pip install -r requirements.txt
```

### 2. Configure

```bash
cp woocommerce_order_monitor_config.json.example woocommerce_order_monitor_config.json
```

Edit the config:
```json
{
    "woocommerce": {
        "url": "https://yourstore.com",
        "consumer_key": "ck_...",  // From WooCommerce → Settings → Advanced → REST API
        "consumer_secret": "cs_..."
    },
    "monitoring": {
        "base_directory": "I:/Physical/Orders"  // Where to save folders
    }
}
```

### 3. Run

```bash
python PipelineScript_Physical_WooCommerceOrderMonitor.py
```

Click **"▶ Start Monitoring"** in the GUI!

## 📁 Result

```
I:/Physical/Orders/
├── Order_1001_John_Doe/
│   ├── Invoice_1001.pdf              ✅ Professional invoice
│   ├── Shipping_Label_1001.pdf       ✅ Ready to print
│   └── Order_Details_1001.txt        ✅ Complete info
├── Order_1002_Jane_Smith/
│   ├── Invoice_1002.pdf
│   └── Order_Details_1002.txt
└── Order_1003_Bob_Wilson/
    ├── Invoice_1003.pdf
    ├── Shipping_Label_1003.pdf
    └── Order_Details_1003.txt
```

## ⚙️ Configuration Options

### Monitor All Orders
```json
"monitoring": {
    "monitor_all_orders": true,
    "download_invoices": true,
    "download_labels": true
}
```

### Monitor Only bpost Orders
```json
"filters": {
    "shipping_methods": ["bpost"]
}
```

### Monitor Specific Statuses
```json
"filters": {
    "order_statuses": ["processing", "completed"]
}
```

### Custom Folder Naming

**Option 1:** `Order_1001/`
```json
"folder_structure": {
    "naming_format": "Order_{order_number}"
}
```

**Option 2:** `Order_1001_John_Doe/`
```json
"folder_structure": {
    "naming_format": "Order_{order_number}_{customer_name}"
}
```

**Option 3:** `20250128_Order_1001_John_Doe/`
```json
"folder_structure": {
    "naming_format": "Order_{order_number}_{customer_name}",
    "include_date": true
}
```

## 🔧 Features in Detail

### 📄 PDF Invoices

Auto-generated with:
- ✅ Order header (number, date, status)
- ✅ Customer billing info
- ✅ Shipping address
- ✅ Product list with prices
- ✅ Shipping costs
- ✅ Tax breakdown
- ✅ Total amount
- ✅ Payment method

### 🏷️ Shipping Labels

Automatically downloads:
- ✅ bpost labels (via WordPress plugin)
- ✅ Other carrier labels from order metadata
- ⚠️ Only if label already exists in WooCommerce

### 📝 Order Details File

Complete order information:
- Customer contact details
- Billing & shipping addresses
- Product details with SKUs
- Shipping & payment info
- Customer notes

## 🎮 GUI Controls

- **▶ Start Monitoring** - Begin watching for new orders
- **⏹ Stop Monitoring** - Pause monitoring
- **🔄 Check Now** - Check immediately
- **⚙ Advanced Settings** - Configure API, filters, etc.

## 📊 Activity Log

Real-time updates with color coding:
- 🟢 **Green** - Success (order processed)
- 🟡 **Orange** - Warning (label not available yet)
- 🔴 **Red** - Error (connection issue, etc.)
- ⚫ **Black** - Info (checking orders, etc.)

## 🛠️ Troubleshooting

### No orders appearing?

1. Check WooCommerce API credentials
2. Verify order status matches filter
3. Ensure orders are within time window (48 hours)

**Test connection:**
```bash
curl -u "ck_xxx:cs_xxx" https://yourstore.com/wp-json/wc/v3/orders
```

### Invoices not generating?

Check:
```bash
pip install reportlab
```

### Labels not downloading?

**Labels require:**
- Label already created in WooCommerce
- For bpost: WordPress helper installed (see PLUGIN_UPDATE_GUIDE.md)

## 📚 Complete Documentation

- **`ORDER_MONITOR_SETUP.md`** - Complete setup guide
- **`PLUGIN_UPDATE_GUIDE.md`** - bpost WordPress integration
- **`woocommerce_order_monitor_config.json.example`** - Full configuration template

## 🎯 Use Cases

### 1. Print-on-Demand
Monitor all orders, generate invoices instantly, process manually

### 2. bpost Automation
Monitor bpost orders only, auto-download labels, pack & ship!

### 3. Wholesale/B2B
Organize by date + customer name, bank transfer filter

### 4. Multi-Channel
Different filters for different order types

## 🔄 Workflow Examples

### Basic Workflow
```
1. Customer places order
2. Monitor detects order (every 5 min)
3. Creates folder with customer name
4. Generates invoice PDF
5. Downloads shipping label (if available)
6. Saves order details
7. Ready to process!
```

### bpost Workflow
```
1. Customer orders with bpost shipping
2. You create label in WooCommerce
3. Monitor detects label in database
4. Downloads everything automatically
5. Print label and invoice
6. Pack and ship!
```

## ⚙️ Advanced Setup

### Run as Background Service

**Windows:**
- Use Task Scheduler
- Run at startup or specific times

**Linux:**
- Create systemd service
- Auto-start on boot

See ORDER_MONITOR_SETUP.md for details.

### Monitor Multiple Stores

1. Copy script for each store
2. Create separate config files
3. Run multiple instances

## 🔒 Security

- ✅ Read-only API access
- ✅ HTTPS recommended
- ✅ Credentials never logged
- ✅ Local file storage only

## 📈 Statistics

Track:
- Total orders processed
- Documents generated
- Labels downloaded
- Processing success rate

## 🆘 Support

1. **Check log file:** `woocommerce_order_monitor.log`
2. **Review setup guide:** `ORDER_MONITOR_SETUP.md`
3. **Test API manually** (curl command above)
4. **Verify configuration** (valid JSON syntax)

## 📦 What's Included

```
modules/
├── PipelineScript_Physical_WooCommerceOrderMonitor.py  ← Main script
├── woocommerce_order_monitor_config.json.example      ← Config template
├── requirements.txt                                    ← Dependencies
├── processed_orders.json                              ← Tracking (auto-generated)
└── woocommerce_order_monitor.log                      ← Activity log (auto-generated)

_ref/
├── ORDER_MONITOR_SETUP.md                             ← Complete guide
├── PLUGIN_UPDATE_GUIDE.md                             ← bpost integration
└── bpost-shipping-platform/                           ← WordPress files
```

## 🎨 Customization

### Change Invoice Template
Edit `generate_invoice()` method to customize:
- Logo
- Colors
- Layout
- Additional fields

### Change Folder Structure
Edit config:
```json
"folder_structure": {
    "naming_format": "Custom_{order_number}",
    "include_date": true,
    "subfolder_documents": true
}
```

### Add Custom Logic
Extend `process_order()` method for:
- Email notifications
- External API calls
- Custom document types
- Integration with other tools

## 🚦 Status Indicators

**GUI Status:**
- 🟢 **Running** - Actively monitoring
- ⚫ **Stopped** - Not monitoring

**Order Processing:**
- ✓ Invoice created
- ✓ Label downloaded
- ⚠ No label available (not an error!)
- ✗ Processing error

## 💡 Pro Tips

1. **Start small** - Monitor "processing" status only at first
2. **Test with old orders** - Set check_orders_since_hours high
3. **Use filters** - Avoid processing same orders multiple times
4. **Check logs** - First place to look when troubleshooting
5. **Backup processed_orders.json** - Prevents re-processing

## 🎯 Next Steps

1. ✅ Install dependencies
2. ✅ Configure WooCommerce API
3. ✅ Create config file
4. ✅ Run monitor
5. ✅ Test with sample order
6. ✅ Customize folder naming
7. ✅ Set up filters
8. ✅ Configure as service (optional)

## 📝 Version History

- **v2.0** - General order monitor with invoices
- **v1.0** - bpost label monitor only

---

**Questions? Check `ORDER_MONITOR_SETUP.md` for detailed documentation!**

**Ready to organize your orders? Run the script! 🚀**
