#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WooCommerce Order Monitor & Auto-Organizer
Author: Florian Dheer
Version: 2.1.0
Description: Automatically monitor WooCommerce orders and organize order folders by downloading invoices, labels, and documents
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import requests
from requests.auth import HTTPBasicAuth
import json
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import base64

# Setup logging using shared utility
from shared_logging import get_logger, setup_logging as setup_shared_logging
from rak_settings import get_rak_settings

# Get logger reference (configured in main())
logger = get_logger("woocommerce_monitor")

# ====================================
# CONFIGURATION
# ====================================

class Config:
    """Configuration manager for WooCommerce order monitoring"""

    def __init__(self):
        # Store all data files in a subfolder to keep modules/ clean
        self.data_dir = Path(__file__).parent / "woocommerce_monitor_data"
        self.data_dir.mkdir(exist_ok=True)
        self.config_file = self.data_dir / "config.json"
        self.config = self.load_config()

    def load_config(self) -> Dict:
        """Load configuration from file"""
        default_config = {
            "woocommerce": {
                "url": "https://yourdomain.com",
                "consumer_key": "",
                "consumer_secret": "",
                "api_version": "wc/v3",
                "monitor_secret_key": ""
            },
            "monitoring": {
                "poll_interval": 300,
                "check_orders_since_hours": 48,
                "base_directory": get_rak_settings().get_work_path("Physical").replace('\\', '/') + "/Order",
                "processed_orders_file": str(self.data_dir / "processed_orders.json"),
                "download_invoices": True,
                "download_labels": True
            },
            "folder_structure": {
                "naming_format": "Order_{order_number}_{customer_name}",  # Options: order_number, customer_name, date
                "include_date": False,
                "subfolder_documents": False  # Create Documents/ subfolder
            },
            "documents": {
                "invoice_filename": "Invoice_{order_number}.pdf",
                "label_filename": "Shipping_Label_{order_number}.pdf",
                "order_details_filename": "Order_Details_{order_number}.txt"
            },
            "filters": {
                "order_statuses": ["processing", "completed"],  # Which order statuses to monitor
                "shipping_methods": [],  # Empty = all methods. Or: ["bpost", "flat_rate"]
                "payment_methods": []  # Empty = all methods
            },
            "logging": {
                "enabled": True,
                "log_file": str(Path.home() / "AppData" / "Local" / "PipelineManager" / "logs" / "woocommerce_monitor.log"),
                "log_level": "INFO"
            }
        }

        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    self._merge_config(default_config, loaded_config)
                    # Reset empty path overrides to defaults so stale values don't persist
                    mon = default_config.get("monitoring", {})
                    if not mon.get("base_directory"):
                        mon["base_directory"] = get_rak_settings().get_work_path("Physical").replace('\\', '/') + "/Order"
                    if not mon.get("processed_orders_file"):
                        mon["processed_orders_file"] = str(self.data_dir / "processed_orders.json")
                    log = default_config.get("logging", {})
                    if not log.get("log_file"):
                        log["log_file"] = str(Path.home() / "AppData" / "Local" / "PipelineManager" / "logs" / "woocommerce_monitor.log")
                    return default_config
            except Exception as e:
                print(f"Error loading config: {e}")
                return default_config
        else:
            self.save_config(default_config)
            return default_config

    def _merge_config(self, default: Dict, loaded: Dict):
        """Recursively merge loaded config into default"""
        for key, value in loaded.items():
            if key in default:
                if isinstance(value, dict) and isinstance(default[key], dict):
                    self._merge_config(default[key], value)
                else:
                    default[key] = value

    def save_config(self, config: Optional[Dict] = None):
        """Save configuration to file"""
        if config:
            self.config = config

        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False


# ====================================
# PROCESSED ORDERS TRACKER
# ====================================

class ProcessedOrdersTracker:
    """Track which orders have already been processed"""

    def __init__(self, config: Config):
        self.config = config
        self.tracker_file = Path(config.config['monitoring']['processed_orders_file'])
        self.processed_orders = self.load_tracker()

    def load_tracker(self) -> Dict:
        """Load processed orders from file"""
        if self.tracker_file.exists():
            try:
                with open(self.tracker_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_tracker(self):
        """Save processed orders to file"""
        try:
            with open(self.tracker_file, 'w') as f:
                json.dump(self.processed_orders, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save tracker: {e}")

    def is_processed(self, order_id: str) -> bool:
        """Check if order has been processed"""
        return str(order_id) in self.processed_orders

    def mark_processed(self, order_id: str, folder_path: str, documents: Dict):
        """Mark order as processed"""
        self.processed_orders[str(order_id)] = {
            "processed_at": datetime.now().isoformat(),
            "folder_path": folder_path,
            "documents": documents
        }
        self.save_tracker()


# ====================================
# WOOCOMMERCE API CLIENT
# ====================================

class WooCommerceClient:
    """WooCommerce REST API client"""

    def __init__(self, config: Config):
        self.config = config
        wc_config = config.config['woocommerce']

        self.base_url = wc_config['url'].rstrip('/')
        self.api_url = f"{self.base_url}/wp-json/{wc_config['api_version']}"
        self.auth = HTTPBasicAuth(
            wc_config['consumer_key'],
            wc_config['consumer_secret']
        )
        self.session = requests.Session()
        self.session.auth = self.auth

    def test_connection(self) -> tuple[bool, str]:
        """Test WooCommerce API connection"""
        try:
            response = self.session.get(f"{self.api_url}/system_status")
            if response.status_code == 200:
                return True, "Connection successful"
            else:
                return False, f"API returned status {response.status_code}"
        except Exception as e:
            return False, str(e)

    def get_recent_orders(self, hours: int = 48) -> List[Dict]:
        """Get recent orders from WooCommerce"""
        try:
            from datetime import datetime, timedelta
            after_date = (datetime.now() - timedelta(hours=hours)).isoformat()

            # Get filter settings
            filters = self.config.config['filters']

            params = {
                'after': after_date,
                'per_page': 100,
                'orderby': 'date',
                'order': 'desc'
            }

            # Add status filter if specified
            if filters.get('order_statuses'):
                params['status'] = ','.join(filters['order_statuses'])

            response = self.session.get(f"{self.api_url}/orders", params=params)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []

    def get_order_details(self, order_id: int) -> Optional[Dict]:
        """Get detailed order information"""
        try:
            response = self.session.get(f"{self.api_url}/orders/{order_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            return None

    def update_order_status(self, order_id: int, status: str) -> Optional[Dict]:
        """Update order status (e.g., 'processing', 'completed', 'on-hold')."""
        try:
            response = self.session.put(
                f"{self.api_url}/orders/{order_id}",
                json={"status": status}
            )
            response.raise_for_status()
            logger.info(f"Order {order_id} status updated to '{status}'")
            return response.json()
        except Exception as e:
            logger.error(f"Failed to update order {order_id} status: {e}")
            return None

    def get_orders_for_period(self, after: str, before: str) -> List[Dict]:
        """Get all orders in a date range. Dates as ISO strings (YYYY-MM-DD)."""
        all_orders = []
        page = 1
        try:
            while True:
                params = {
                    'after': f"{after}T00:00:00",
                    'before': f"{before}T23:59:59",
                    'per_page': 100,
                    'page': page,
                    'orderby': 'date',
                    'order': 'asc'
                }
                response = self.session.get(f"{self.api_url}/orders", params=params)
                response.raise_for_status()
                orders = response.json()
                if not orders:
                    break
                all_orders.extend(orders)
                page += 1
            return all_orders
        except Exception as e:
            logger.error(f"Failed to get orders for period {after} to {before}: {e}")
            return all_orders

    def get_invoice_info(self, order_id: int) -> Optional[Dict]:
        """Get invoice number and date from custom WordPress endpoint."""
        try:
            wc_config = self.config.config['woocommerce']
            secret_key = wc_config.get('monitor_secret_key', '')
            if not secret_key:
                logger.warning("No monitor_secret_key configured for invoice endpoint")
                return None

            endpoint = f"{self.base_url}/wp-admin/admin-ajax.php"
            params = {
                'action': 'pipeline_get_invoice_info',
                'order_id': order_id,
                'secret': secret_key
            }
            response = requests.get(endpoint, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('data'):
                    return data['data']
            return None
        except Exception as e:
            logger.error(f"Failed to get invoice info for order {order_id}: {e}")
            return None

    def download_invoice_pdf(self, order_id: int, save_path: Path) -> bool:
        """Download invoice PDF via custom WordPress endpoint."""
        try:
            wc_config = self.config.config['woocommerce']
            secret_key = wc_config.get('monitor_secret_key', '')
            if not secret_key:
                logger.warning("No monitor_secret_key configured for invoice endpoint")
                return False

            endpoint = f"{self.base_url}/wp-admin/admin-ajax.php"
            params = {
                'action': 'pipeline_get_invoice',
                'order_id': order_id,
                'secret': secret_key
            }
            response = requests.get(endpoint, params=params, timeout=30)

            if response.status_code != 200:
                logger.error(f"Invoice endpoint returned {response.status_code}")
                return False

            content_type = response.headers.get('content-type', '')
            if 'pdf' not in content_type:
                # Might be a JSON error response
                try:
                    data = response.json()
                    logger.error(f"Invoice endpoint error: {data.get('data', 'Unknown error')}")
                except ValueError:
                    logger.error(f"Unexpected response type: {content_type}")
                return False

            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"Downloaded invoice PDF: {save_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to download invoice for order {order_id}: {e}")
            return False

    def create_manual_order(self, customer: Dict, line_items: List[Dict],
                            status: str = "completed") -> Optional[Dict]:
        """
        Create a manual WooCommerce order for project invoicing.

        Args:
            customer: Dict with billing info (first_name, last_name, email, address_1, etc.)
            line_items: List of dicts with name, quantity, total (price as string)
            status: Order status (default 'completed' to trigger invoice generation)
        """
        try:
            order_data = {
                "status": status,
                "billing": customer,
                "line_items": line_items,
                "set_paid": True
            }
            response = self.session.post(f"{self.api_url}/orders", json=order_data)
            response.raise_for_status()
            order = response.json()
            logger.info(f"Created manual order #{order.get('number', order['id'])}")
            return order
        except Exception as e:
            logger.error(f"Failed to create manual order: {e}")
            return None

    def matches_filters(self, order: Dict) -> bool:
        """Check if order matches configured filters"""
        filters = self.config.config['filters']

        # Check shipping method filter
        if filters.get('shipping_methods'):
            shipping_method = order.get('shipping_lines', [])
            if shipping_method:
                method_id = shipping_method[0].get('method_id', '').lower()
                if not any(method.lower() in method_id for method in filters['shipping_methods']):
                    return False

        # Check payment method filter
        if filters.get('payment_methods'):
            payment_method = order.get('payment_method', '').lower()
            if not any(method.lower() in payment_method for method in filters['payment_methods']):
                return False

        return True

    def has_bpost_shipping(self, order: Dict) -> bool:
        """Check if order uses bpost shipping"""
        for shipping_line in order.get('shipping_lines', []):
            method_id = shipping_line.get('method_id', '').lower()
            method_title = shipping_line.get('method_title', '').lower()

            if 'bpost' in method_id or 'bpost' in method_title:
                return True

        for meta in order.get('meta_data', []):
            key = meta.get('key', '').lower()
            if 'bpost' in key:
                return True

        return False

    def get_bpost_label_url(self, order: Dict) -> Optional[str]:
        """Extract bpost label URL from order metadata"""
        label_meta_keys = [
            '_bpost_label_url',
            '_bpost_shipping_label',
            'bpost_label',
            '_shipping_label_url',
            '_bpost_label_pdf',
            'Bpost_trackingurl'
        ]

        for meta in order.get('meta_data', []):
            key = meta.get('key', '')
            if key in label_meta_keys:
                return meta.get('value')

        return None

    def get_bpost_label_from_db(self, order_id: int) -> Optional[str]:
        """Query custom wp_Bpost table for label URL via WordPress AJAX endpoint"""
        try:
            wc_config = self.config.config['woocommerce']
            base_url = wc_config['url'].rstrip('/')
            secret_key = wc_config.get('monitor_secret_key', '')

            if not secret_key:
                logger.debug("No monitor_secret_key configured, skipping database query")
                return None

            endpoint = f"{base_url}/wp-admin/admin-ajax.php"

            params = {
                'action': 'bpost_monitor_get_label',
                'order_id': order_id,
                'secret': secret_key
            }

            response = requests.get(endpoint, params=params, timeout=10)

            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('success') and data.get('data'):
                        label_url = data['data'].get('labelurl')
                        if label_url:
                            logger.info(f"Found label URL in wp_Bpost table for order {order_id}")
                            return label_url
                except Exception as e:
                    logger.debug(f"Error parsing response: {e}")

        except Exception as e:
            logger.debug(f"Could not query wp_Bpost table: {e}")

        return None


# ====================================
# DOCUMENT GENERATOR & DOWNLOADER
# ====================================

class DocumentManager:
    """Handle document generation and downloading"""

    def __init__(self, config: Config, wc_client: WooCommerceClient):
        self.config = config
        self.wc_client = wc_client
        self.base_dir = Path(config.config['monitoring']['base_directory'])
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_order_folder(self, order: Dict) -> Path:
        """Create folder for order based on naming format"""
        order_id = order['id']
        order_number = order.get('number', order_id)

        # Get customer name
        billing = order.get('billing', {})
        customer_name = f"{billing.get('first_name', '')}_{billing.get('last_name', '')}".strip('_')
        if not customer_name:
            customer_name = "Guest"

        # Clean customer name for filesystem
        customer_name = self._sanitize_filename(customer_name)

        # Build folder name based on format
        naming_format = self.config.config['folder_structure']['naming_format']
        folder_name = naming_format.format(
            order_number=order_number,
            order_id=order_id,
            customer_name=customer_name
        )

        # Add date if configured
        if self.config.config['folder_structure'].get('include_date'):
            date_str = datetime.now().strftime('%Y%m%d')
            folder_name = f"{date_str}_{folder_name}"

        # Create folder
        order_folder = self.base_dir / folder_name
        order_folder.mkdir(parents=True, exist_ok=True)

        # Create subfolder for documents if configured
        if self.config.config['folder_structure'].get('subfolder_documents'):
            docs_folder = order_folder / "Documents"
            docs_folder.mkdir(exist_ok=True)

        return order_folder

    def _sanitize_filename(self, name: str) -> str:
        """Remove invalid filesystem characters"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        return name

    def download_invoice(self, order: Dict, order_folder: Path) -> Optional[str]:
        """Download invoice PDF from WooCommerce if available"""
        try:
            # Common meta keys used by WooCommerce invoice plugins
            invoice_meta_keys = [
                '_wcpdf_invoice_pdf',
                'invoice_url',
                '_invoice_pdf_url',
                '_invoice_url',
                'wcpdf_invoice_url',
                '_wcpdf_invoice_link'
            ]

            # Try to get invoice URL from metadata
            invoice_url = None
            for meta in order.get('meta_data', []):
                key = meta.get('key', '')
                if key in invoice_meta_keys:
                    invoice_url = meta.get('value')
                    break

            # If no direct URL in metadata, try to construct it from WooCommerce PDF Invoices plugin
            if not invoice_url:
                # Check if order has an invoice number
                invoice_number = None
                for meta in order.get('meta_data', []):
                    key = meta.get('key', '')
                    if key == '_wcpdf_invoice_number':
                        invoice_number = meta.get('value')
                        break

                # Construct URL if we have invoice number
                if invoice_number:
                    wc_config = self.config.config['woocommerce']
                    base_url = wc_config['url'].rstrip('/')
                    # Try common WooCommerce PDF Invoices plugin endpoint
                    invoice_url = f"{base_url}/?action=generate_wpo_wcpdf&template_type=invoice&order_ids={order['id']}&my-account"

            if not invoice_url:
                logger.debug(f"No invoice URL found for order {order['id']}")
                return None

            # Download invoice
            doc_config = self.config.config['documents']
            filename = doc_config['invoice_filename'].format(
                order_number=order.get('number', order['id']),
                order_id=order['id']
            )

            if self.config.config['folder_structure'].get('subfolder_documents'):
                invoice_path = order_folder / "Documents" / filename
            else:
                invoice_path = order_folder / filename

            # Download the PDF
            response = requests.get(invoice_url, timeout=30)
            response.raise_for_status()

            # Verify it's a PDF
            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' not in content_type and not invoice_url.endswith('.pdf'):
                logger.warning(f"Downloaded file might not be a PDF: {content_type}")

            with open(invoice_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"Downloaded invoice: {invoice_path}")
            return str(invoice_path)

        except Exception as e:
            logger.error(f"Failed to download invoice for order {order['id']}: {e}")
            return None

    def download_shipping_label(self, order: Dict, order_folder: Path) -> Optional[str]:
        """Download shipping label if available"""
        try:
            # Try to get label URL from metadata first
            label_url = self.wc_client.get_bpost_label_url(order)

            # If not in metadata, try database query
            if not label_url and self.wc_client.has_bpost_shipping(order):
                label_url = self.wc_client.get_bpost_label_from_db(order['id'])

            if not label_url:
                return None

            # Download label
            doc_config = self.config.config['documents']
            filename = doc_config['label_filename'].format(
                order_number=order.get('number', order['id']),
                order_id=order['id']
            )

            if self.config.config['folder_structure'].get('subfolder_documents'):
                label_path = order_folder / "Documents" / filename
            else:
                label_path = order_folder / filename

            response = requests.get(label_url, timeout=30)
            response.raise_for_status()

            with open(label_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"Downloaded shipping label: {label_path}")
            return str(label_path)

        except Exception as e:
            logger.error(f"Failed to download label for order {order['id']}: {e}")
            return None

    def create_order_details_file(self, order: Dict, order_folder: Path) -> Optional[str]:
        """Create a text file with order details"""
        try:
            doc_config = self.config.config['documents']
            filename = doc_config['order_details_filename'].format(
                order_number=order.get('number', order['id']),
                order_id=order['id']
            )

            if self.config.config['folder_structure'].get('subfolder_documents'):
                details_path = order_folder / "Documents" / filename
            else:
                details_path = order_folder / filename

            with open(details_path, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write(f"ORDER DETAILS - #{order.get('number', order['id'])}\n")
                f.write("=" * 60 + "\n\n")

                f.write(f"Order ID: {order['id']}\n")
                f.write(f"Order Number: {order.get('number', order['id'])}\n")
                f.write(f"Date: {order['date_created']}\n")
                f.write(f"Status: {order['status'].upper()}\n")
                f.write(f"Currency: {order['currency']}\n")
                f.write(f"Total: {order['currency_symbol']}{order['total']}\n\n")

                # Customer Info
                billing = order.get('billing', {})
                f.write("-" * 60 + "\n")
                f.write("CUSTOMER INFORMATION\n")
                f.write("-" * 60 + "\n")
                f.write(f"Name: {billing.get('first_name', '')} {billing.get('last_name', '')}\n")
                if billing.get('company'):
                    f.write(f"Company: {billing['company']}\n")
                f.write(f"Email: {billing.get('email', '')}\n")
                f.write(f"Phone: {billing.get('phone', '')}\n\n")

                # Billing Address
                f.write("Billing Address:\n")
                f.write(f"  {billing.get('address_1', '')}\n")
                if billing.get('address_2'):
                    f.write(f"  {billing['address_2']}\n")
                f.write(f"  {billing.get('postcode', '')} {billing.get('city', '')}\n")
                f.write(f"  {billing.get('state', '')} {billing.get('country', '')}\n\n")

                # Shipping Address
                shipping = order.get('shipping', {})
                if shipping:
                    f.write("Shipping Address:\n")
                    f.write(f"  {shipping.get('first_name', '')} {shipping.get('last_name', '')}\n")
                    f.write(f"  {shipping.get('address_1', '')}\n")
                    if shipping.get('address_2'):
                        f.write(f"  {shipping['address_2']}\n")
                    f.write(f"  {shipping.get('postcode', '')} {shipping.get('city', '')}\n")
                    f.write(f"  {shipping.get('state', '')} {shipping.get('country', '')}\n\n")

                # Line Items
                f.write("-" * 60 + "\n")
                f.write("ORDER ITEMS\n")
                f.write("-" * 60 + "\n")
                for item in order.get('line_items', []):
                    f.write(f"\n{item.get('name', '')}\n")
                    f.write(f"  SKU: {item.get('sku', 'N/A')}\n")
                    f.write(f"  Quantity: {item.get('quantity', 1)}\n")
                    f.write(f"  Price: {order['currency_symbol']}{item.get('price', 0)}\n")
                    f.write(f"  Total: {order['currency_symbol']}{item.get('total', 0)}\n")

                # Shipping Method
                f.write("\n" + "-" * 60 + "\n")
                f.write("SHIPPING\n")
                f.write("-" * 60 + "\n")
                for ship_line in order.get('shipping_lines', []):
                    f.write(f"Method: {ship_line.get('method_title', 'N/A')}\n")
                    f.write(f"Cost: {order['currency_symbol']}{ship_line.get('total', 0)}\n")

                # Payment
                f.write("\n" + "-" * 60 + "\n")
                f.write("PAYMENT\n")
                f.write("-" * 60 + "\n")
                f.write(f"Method: {order.get('payment_method_title', 'N/A')}\n")
                f.write(f"Transaction ID: {order.get('transaction_id', 'N/A')}\n")

                # Customer Note
                if order.get('customer_note'):
                    f.write("\n" + "-" * 60 + "\n")
                    f.write("CUSTOMER NOTE\n")
                    f.write("-" * 60 + "\n")
                    f.write(order['customer_note'] + "\n")

                f.write("\n" + "=" * 60 + "\n")
                f.write("End of Order Details\n")
                f.write("=" * 60 + "\n")

            logger.info(f"Created order details file: {details_path}")
            return str(details_path)

        except Exception as e:
            logger.error(f"Failed to create order details for order {order['id']}: {e}")
            return None


# ====================================
# INVOICE FILER
# ====================================

class InvoiceFiler:
    """
    Handles filing invoices to the bookkeeping folder and creating
    .lnk shortcuts in order/project folders.

    Bookkeeping structure: {library}/Boekhouding/{year}/Q{quarter}/Uitgaand/
    Invoice naming: 3D_YYMMDD_Factuur{number}_{ClientName}.pdf
    """

    def __init__(self, config: Config, wc_client: WooCommerceClient):
        self.config = config
        self.wc_client = wc_client
        settings = get_rak_settings()
        self.library_base = Path(settings.get_active_base()) / "_LIBRARY" / "Boekhouding"

    def _get_quarter_dir(self, date_str: str) -> Path:
        """Get the Uitgaand folder for the quarter containing the given date."""
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        quarter = (dt.month - 1) // 3 + 1
        return self.library_base / str(dt.year) / f"Q{quarter}" / "Uitgaand"

    def _build_invoice_filename(self, invoice_number: str, invoice_date: str,
                                client_name: str) -> str:
        """Build filename: 3D_YYMMDD_Factuur{number}_{ClientName}.pdf"""
        dt = datetime.strptime(invoice_date[:10], "%Y-%m-%d")
        date_part = dt.strftime("%y%m%d")
        # Clean client name for filesystem
        clean_name = client_name.replace(" ", "").replace("_", "")
        for ch in '<>:"/\\|?*':
            clean_name = clean_name.replace(ch, "")
        return f"3D_{date_part}_Factuur{invoice_number}_{clean_name}.pdf"

    def _find_outgoing_folder(self, project_folder: Path) -> Optional[Path]:
        """Find the outgoing folder (e.g. 03_Outgoing) in a project folder."""
        try:
            for item in project_folder.iterdir():
                if item.is_dir() and "outgoing" in item.name.lower():
                    return item
        except Exception:
            pass
        return None

    def _create_shortcut(self, shortcut_path: Path, target_path: Path):
        """Create a Windows .lnk shortcut."""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(str(shortcut_path))
            shortcut.TargetPath = str(target_path)
            shortcut.WorkingDirectory = str(target_path.parent)
            shortcut.save()
            logger.info(f"Created shortcut: {shortcut_path}")
        except Exception as e:
            logger.error(f"Failed to create shortcut: {e}")

    def file_invoice(self, order: Dict, project_folder: Path) -> Optional[Path]:
        """
        Download invoice, copy to Boekhouding, create .lnk in project folder.

        Args:
            order: WooCommerce order dict
            project_folder: Path to the order/project folder

        Returns:
            Path to the filed invoice in Boekhouding, or None on failure
        """
        order_id = order['id']

        # Get invoice info (number + date) from WordPress
        invoice_info = self.wc_client.get_invoice_info(order_id)
        if not invoice_info:
            logger.warning(f"No invoice info available for order {order_id}")
            return None

        invoice_number = invoice_info['invoice_number']
        invoice_date = invoice_info['invoice_date']

        # Get client name from billing
        billing = order.get('billing', {})
        client_name = f"{billing.get('last_name', '')}".strip()
        if not client_name:
            client_name = f"{billing.get('first_name', '')}".strip()
        if not client_name:
            client_name = "Unknown"

        # Build paths
        quarter_dir = self._get_quarter_dir(invoice_date)
        quarter_dir.mkdir(parents=True, exist_ok=True)

        filename = self._build_invoice_filename(invoice_number, invoice_date, client_name)
        invoice_path = quarter_dir / filename

        # Download invoice PDF directly to Boekhouding
        if not self.wc_client.download_invoice_pdf(order_id, invoice_path):
            return None

        logger.info(f"Filed invoice: {invoice_path}")

        # Create .lnk shortcut in the project's outgoing folder
        outgoing = self._find_outgoing_folder(project_folder)
        if outgoing:
            outgoing.mkdir(parents=True, exist_ok=True)
            shortcut_name = filename.replace(".pdf", ".lnk")
            self._create_shortcut(outgoing / shortcut_name, invoice_path)
        else:
            logger.warning(f"No outgoing folder found in {project_folder}")

        return invoice_path


# ====================================
# ORDER MONITOR
# ====================================

class OrderMonitor:
    """Main order monitoring logic"""

    def __init__(self, config: Config):
        self.config = config
        self.wc_client = WooCommerceClient(config)
        self.doc_manager = DocumentManager(config, self.wc_client)
        self.invoice_filer = InvoiceFiler(config, self.wc_client)
        self.tracker = ProcessedOrdersTracker(config)
        self.running = False
        self.callback = None

    def set_callback(self, callback):
        """Set callback function for status updates"""
        self.callback = callback

    def log_status(self, message: str, level: str = "info"):
        """Log status message"""
        if self.callback:
            self.callback(message, level)

        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)

    def process_order(self, order: Dict) -> bool:
        """Process a single order"""
        order_id = str(order['id'])
        order_number = order.get('number', order_id)

        # Check if already processed
        if self.tracker.is_processed(order_id):
            return False

        # Check if matches filters
        if not self.wc_client.matches_filters(order):
            self.log_status(f"Order #{order_number} doesn't match filters", "info")
            return False

        self.log_status(f"Processing order #{order_number}...", "info")

        try:
            # Create order folder
            order_folder = self.doc_manager.create_order_folder(order)
            self.log_status(f"Created folder: {order_folder.name}", "success")

            documents = {}

            # Generate/download documents based on configuration
            monitor_config = self.config.config['monitoring']

            # Invoice — file to Boekhouding and create .lnk in order folder
            if monitor_config.get('download_invoices', True):
                filed_path = self.invoice_filer.file_invoice(order, order_folder)
                if filed_path:
                    documents['invoice'] = str(filed_path)
                    self.log_status(f"✓ Invoice filed to {filed_path.parent.name}/", "success")
                else:
                    # Fallback: try legacy download directly to order folder
                    invoice_path = self.doc_manager.download_invoice(order, order_folder)
                    if invoice_path:
                        documents['invoice'] = invoice_path
                        self.log_status(f"✓ Invoice downloaded (legacy)", "success")
                    else:
                        self.log_status(f"⚠ No invoice available yet", "warning")

            # Shipping label
            if monitor_config.get('download_labels', True):
                label_path = self.doc_manager.download_shipping_label(order, order_folder)
                if label_path:
                    documents['label'] = label_path
                    self.log_status(f"✓ Shipping label downloaded", "success")
                elif self.wc_client.has_bpost_shipping(order):
                    self.log_status(f"⚠ No shipping label available yet", "warning")

            # Order details
            details_path = self.doc_manager.create_order_details_file(order, order_folder)
            if details_path:
                documents['details'] = details_path
                self.log_status(f"✓ Order details saved", "success")

            # Mark as processed
            self.tracker.mark_processed(order_id, str(order_folder), documents)

            self.log_status(f"✓ Successfully processed order #{order_number}", "success")
            return True

        except Exception as e:
            self.log_status(f"✗ Error processing order #{order_number}: {e}", "error")
            return False

    def check_orders(self):
        """Check for new orders"""
        try:
            self.log_status("Checking for new orders...", "info")

            hours = self.config.config['monitoring']['check_orders_since_hours']
            orders = self.wc_client.get_recent_orders(hours)

            if not orders:
                self.log_status("No recent orders found", "info")
                return

            self.log_status(f"Found {len(orders)} recent orders", "info")

            processed_count = 0
            for order in orders:
                if self.process_order(order):
                    processed_count += 1

            if processed_count > 0:
                self.log_status(f"✓ Processed {processed_count} new order(s)", "success")
            else:
                self.log_status("No new orders to process", "info")

        except Exception as e:
            self.log_status(f"Error checking orders: {e}", "error")

    def file_quarter_invoices(self, year: int, quarter: int):
        """
        Fetch all orders for a quarter and file their invoices to Boekhouding.
        Useful for catching up on invoices that weren't filed during monitoring.
        """
        # Calculate quarter date range
        start_month = (quarter - 1) * 3 + 1
        after = f"{year}-{start_month:02d}-01"
        if quarter == 4:
            before = f"{year}-12-31"
        else:
            end_month = quarter * 3
            # Last day of end_month
            import calendar
            last_day = calendar.monthrange(year, end_month)[1]
            before = f"{year}-{end_month:02d}-{last_day:02d}"

        self.log_status(f"Fetching orders for Q{quarter} {year} ({after} to {before})...", "info")

        orders = self.wc_client.get_orders_for_period(after, before)
        if not orders:
            self.log_status(f"No orders found for Q{quarter} {year}", "info")
            return

        self.log_status(f"Found {len(orders)} orders for Q{quarter} {year}", "info")

        filed_count = 0
        skipped_count = 0
        for order in orders:
            order_number = order.get('number', order['id'])

            # Find existing order folder if it exists
            order_folder = self._find_order_folder(order)

            if not order_folder:
                # Create folder if it doesn't exist
                order_folder = self.doc_manager.create_order_folder(order)
                self.log_status(f"Created folder for order #{order_number}", "info")

            # Check if invoice already filed (look for .lnk in outgoing)
            outgoing = self.invoice_filer._find_outgoing_folder(order_folder)
            if outgoing and any(f.suffix == '.lnk' for f in outgoing.iterdir() if f.is_file()):
                skipped_count += 1
                continue

            filed_path = self.invoice_filer.file_invoice(order, order_folder)
            if filed_path:
                filed_count += 1
                self.log_status(f"✓ Filed invoice for order #{order_number}", "success")
            else:
                self.log_status(f"⚠ Could not file invoice for order #{order_number}", "warning")

        self.log_status(
            f"Quarter done: {filed_count} filed, {skipped_count} already existed", "success"
        )

    def _find_order_folder(self, order: Dict) -> Optional[Path]:
        """Try to find an existing folder for an order in the Order directory."""
        base_dir = Path(self.config.config['monitoring']['base_directory'])
        if not base_dir.exists():
            return None

        order_number = str(order.get('number', order['id']))
        billing = order.get('billing', {})
        customer_name = f"{billing.get('first_name', '')}_{billing.get('last_name', '')}".strip('_')

        try:
            for item in base_dir.iterdir():
                if not item.is_dir():
                    continue
                name = item.name
                # Match by order number in folder name
                if order_number in name:
                    return item
                # Match by customer name
                if customer_name and customer_name in name:
                    return item
        except Exception:
            pass
        return None

    def create_project_invoice(self, customer: Dict, line_items: List[Dict],
                               project_folder: Path) -> Optional[Path]:
        """
        Create a WooCommerce order for a project and file the invoice.

        Args:
            customer: Billing info dict (first_name, last_name, email, address_1, etc.)
            line_items: List of dicts with name, quantity, total
            project_folder: Path to the project folder

        Returns:
            Path to the filed invoice, or None on failure
        """
        self.log_status("Creating WooCommerce order for project invoice...", "info")

        order = self.wc_client.create_manual_order(customer, line_items)
        if not order:
            self.log_status("Failed to create WooCommerce order", "error")
            return None

        order_number = order.get('number', order['id'])
        self.log_status(f"Created order #{order_number}", "success")

        # File the invoice
        filed_path = self.invoice_filer.file_invoice(order, project_folder)
        if filed_path:
            self.log_status(f"✓ Invoice filed: {filed_path.name}", "success")
        else:
            self.log_status(f"⚠ Order created but invoice filing failed", "warning")

        return filed_path

    def start_monitoring(self):
        """Start continuous monitoring"""
        self.running = True
        self.log_status("🚀 Monitoring started", "success")

        while self.running:
            self.check_orders()

            if self.running:
                interval = self.config.config['monitoring']['poll_interval']
                self.log_status(f"Next check in {interval} seconds...", "info")

                for _ in range(interval):
                    if not self.running:
                        break
                    time.sleep(1)

    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
        self.log_status("⏹ Monitoring stopped", "warning")


# ====================================
# GUI APPLICATION
# ====================================

class OrderMonitorGUI:
    """GUI for order monitoring"""

    def __init__(self, root):
        self.root = root
        self.root.title("WooCommerce Order Monitor & Auto-Organizer")
        self.root.geometry("1000x800")
        self.root.minsize(900, 700)

        # Initialize components
        self.config = Config()
        self.monitor = OrderMonitor(self.config)
        self.monitor.set_callback(self.update_status)
        self.monitor_thread = None

        # Setup logging
        self.setup_logging()

        # Create GUI
        self.create_gui()

        # Check configuration
        self.root.after(100, self.check_initial_config)

    def setup_logging(self):
        """Setup logging configuration"""
        # Logging is now handled by shared_logging module in main()
        # This method is kept for backward compatibility but does nothing
        pass

    def create_gui(self):
        """Create the main GUI"""
        style = ttk.Style()
        style.theme_use('clam')

        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)

        # Header
        header_frame = ttk.LabelFrame(main_frame, text="WooCommerce Order Monitor", padding="10")
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Status indicator
        self.status_label = ttk.Label(header_frame, text="⚫ Stopped", font=('Arial', 12, 'bold'))
        self.status_label.grid(row=0, column=0, sticky=tk.W)

        # Control buttons
        button_frame = ttk.Frame(header_frame)
        button_frame.grid(row=0, column=1, sticky=tk.E)

        self.start_button = ttk.Button(button_frame, text="▶ Start Monitoring",
                                       command=self.start_monitoring, width=20)
        self.start_button.grid(row=0, column=0, padx=5)

        self.stop_button = ttk.Button(button_frame, text="⏹ Stop Monitoring",
                                      command=self.stop_monitoring, state=tk.DISABLED, width=20)
        self.stop_button.grid(row=0, column=1, padx=5)

        self.check_now_button = ttk.Button(button_frame, text="🔄 Check Now",
                                          command=self.check_now, width=15)
        self.check_now_button.grid(row=0, column=2, padx=5)

        # Invoice action buttons (second row)
        invoice_frame = ttk.Frame(header_frame)
        invoice_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))

        ttk.Button(invoice_frame, text="📋 File Quarter Invoices",
                  command=self.file_quarter_invoices, width=22).grid(row=0, column=0, padx=5)

        ttk.Button(invoice_frame, text="📄 Create Project Invoice",
                  command=self.create_project_invoice, width=22).grid(row=0, column=1, padx=5)

        header_frame.columnconfigure(1, weight=1)

        # Configuration section
        config_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="10")
        config_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        config_frame.columnconfigure(1, weight=1)

        # Store URL
        ttk.Label(config_frame, text="Store URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.url_var = tk.StringVar(value=self.config.config['woocommerce']['url'])
        url_entry = ttk.Entry(config_frame, textvariable=self.url_var)
        url_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)

        # Poll interval
        ttk.Label(config_frame, text="Check Interval (seconds):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.interval_var = tk.StringVar(value=str(self.config.config['monitoring']['poll_interval']))
        interval_entry = ttk.Entry(config_frame, textvariable=self.interval_var, width=10)
        interval_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        # Base directory
        ttk.Label(config_frame, text="Save Location:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.base_dir_var = tk.StringVar(value=self.config.config['monitoring']['base_directory'])
        base_dir_entry = ttk.Entry(config_frame, textvariable=self.base_dir_var)
        base_dir_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        ttk.Button(config_frame, text="Browse", command=self.browse_directory).grid(row=2, column=2, padx=5)

        # Monitor options
        options_frame = ttk.Frame(config_frame)
        options_frame.grid(row=3, column=1, sticky=tk.W, pady=5)

        self.download_invoices_var = tk.BooleanVar(value=self.config.config['monitoring'].get('download_invoices', True))
        ttk.Checkbutton(options_frame, text="Generate Invoices",
                       variable=self.download_invoices_var).grid(row=0, column=0, padx=5)

        self.download_labels_var = tk.BooleanVar(value=self.config.config['monitoring'].get('download_labels', True))
        ttk.Checkbutton(options_frame, text="Download Labels",
                       variable=self.download_labels_var).grid(row=0, column=1, padx=5)

        # Settings button
        ttk.Button(config_frame, text="⚙ Advanced Settings",
                  command=self.open_settings).grid(row=4, column=1, sticky=tk.E, pady=5)

        # Status log
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="10")
        log_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure text tags for colors
        self.log_text.tag_config('info', foreground='black')
        self.log_text.tag_config('success', foreground='green')
        self.log_text.tag_config('warning', foreground='orange')
        self.log_text.tag_config('error', foreground='red')

        # Statistics panel
        stats_frame = ttk.Frame(main_frame)
        stats_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        self.stats_label = ttk.Label(stats_frame, text="Ready to start monitoring")
        self.stats_label.pack(side=tk.LEFT)

    def browse_directory(self):
        """Browse for save directory"""
        from tkinter import filedialog
        directory = filedialog.askdirectory(initialdir=self.base_dir_var.get())
        if directory:
            self.base_dir_var.set(directory)

    def check_initial_config(self):
        """Check if configuration is complete"""
        wc_config = self.config.config['woocommerce']
        if not wc_config['consumer_key'] or not wc_config['consumer_secret']:
            if messagebox.askyesno("Configuration Required",
                                   "WooCommerce API credentials not configured.\n\n"
                                   "Would you like to configure them now?"):
                self.open_settings()

    def open_settings(self):
        """Open settings dialog"""
        SettingsDialog(self.root, self.config)

    def update_status(self, message: str, level: str = "info"):
        """Update status in GUI"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        self.log_text.insert(tk.END, log_message, level)
        self.log_text.see(tk.END)

        # Update stats
        processed_count = len(self.monitor.tracker.processed_orders)
        self.stats_label.config(text=f"Processed orders: {processed_count}")

    def start_monitoring(self):
        """Start monitoring in background thread"""
        self.save_current_config()

        # Test connection
        self.update_status("Testing WooCommerce connection...", "info")
        success, message = self.monitor.wc_client.test_connection()

        if not success:
            messagebox.showerror("Connection Error",
                               f"Failed to connect to WooCommerce:\n{message}\n\n"
                               "Please check your credentials in Advanced Settings.")
            return

        self.update_status("Connection successful!", "success")

        # Update UI
        self.status_label.config(text="🟢 Running")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.check_now_button.config(state=tk.DISABLED)

        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitor.start_monitoring, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitor.stop_monitoring()

        # Update UI
        self.status_label.config(text="⚫ Stopped")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.check_now_button.config(state=tk.NORMAL)

    def check_now(self):
        """Check for orders immediately"""
        self.save_current_config()
        threading.Thread(target=self.monitor.check_orders, daemon=True).start()

    def file_quarter_invoices(self):
        """Show quarter selection dialog and file invoices."""
        dialog = tk.Toplevel(self.root)
        dialog.title("File Quarter Invoices")
        dialog.geometry("350x180")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Select quarter to file invoices for:").pack(anchor=tk.W, pady=(0, 10))

        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=5)

        now = datetime.now()
        ttk.Label(row, text="Year:").pack(side=tk.LEFT, padx=(0, 5))
        year_var = tk.StringVar(value=str(now.year))
        year_spin = ttk.Spinbox(row, from_=2020, to=2030, textvariable=year_var, width=6)
        year_spin.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(row, text="Quarter:").pack(side=tk.LEFT, padx=(0, 5))
        current_quarter = (now.month - 1) // 3 + 1
        quarter_var = tk.StringVar(value=str(current_quarter))
        quarter_spin = ttk.Spinbox(row, from_=1, to=4, textvariable=quarter_var, width=4)
        quarter_spin.pack(side=tk.LEFT)

        def run():
            dialog.destroy()
            self.save_current_config()
            year = int(year_var.get())
            quarter = int(quarter_var.get())
            threading.Thread(
                target=self.monitor.file_quarter_invoices,
                args=(year, quarter), daemon=True
            ).start()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(btn_frame, text="File Invoices", command=run).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)

    def create_project_invoice(self):
        """Show dialog to create a manual WooCommerce order and file the invoice."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Project Invoice")
        dialog.geometry("500x480")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        # Customer info
        ttk.Label(frame, text="Customer", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))

        fields = {}
        customer_fields = [
            ("First Name:", "first_name"),
            ("Last Name:", "last_name"),
            ("Email:", "email"),
            ("Address:", "address_1"),
            ("Postcode:", "postcode"),
            ("City:", "city"),
            ("Country:", "country"),
        ]
        for i, (label, key) in enumerate(customer_fields, start=1):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=2)
            var = tk.StringVar(value="BE" if key == "country" else "")
            ttk.Entry(frame, textvariable=var).grid(row=i, column=1, sticky=tk.EW, padx=5, pady=2)
            fields[key] = var

        # Line item
        row_offset = len(customer_fields) + 1
        ttk.Label(frame, text="Invoice Item", font=('Arial', 10, 'bold')).grid(
            row=row_offset, column=0, columnspan=2, sticky=tk.W, pady=(10, 5))

        ttk.Label(frame, text="Description:").grid(row=row_offset+1, column=0, sticky=tk.W, pady=2)
        desc_var = tk.StringVar()
        ttk.Entry(frame, textvariable=desc_var).grid(row=row_offset+1, column=1, sticky=tk.EW, padx=5, pady=2)

        ttk.Label(frame, text="Amount (EUR):").grid(row=row_offset+2, column=0, sticky=tk.W, pady=2)
        amount_var = tk.StringVar()
        ttk.Entry(frame, textvariable=amount_var).grid(row=row_offset+2, column=1, sticky=tk.W, padx=5, pady=2)

        # Project folder
        ttk.Label(frame, text="Project Folder:").grid(row=row_offset+3, column=0, sticky=tk.W, pady=(10, 2))
        folder_var = tk.StringVar()
        folder_frame = ttk.Frame(frame)
        folder_frame.grid(row=row_offset+3, column=1, sticky=tk.EW, padx=5, pady=(10, 2))
        ttk.Entry(folder_frame, textvariable=folder_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        def browse():
            from tkinter import filedialog
            d = filedialog.askdirectory()
            if d:
                folder_var.set(d)
        ttk.Button(folder_frame, text="...", command=browse, width=3).pack(side=tk.LEFT, padx=(5, 0))

        def create():
            customer = {k: v.get() for k, v in fields.items()}
            line_items = [{
                "name": desc_var.get(),
                "quantity": 1,
                "total": amount_var.get()
            }]
            project_path = Path(folder_var.get())

            if not desc_var.get() or not amount_var.get():
                messagebox.showwarning("Missing Info", "Please fill in description and amount.")
                return
            if not project_path.exists():
                messagebox.showwarning("Invalid Path", "Project folder does not exist.")
                return

            dialog.destroy()
            threading.Thread(
                target=self.monitor.create_project_invoice,
                args=(customer, line_items, project_path), daemon=True
            ).start()

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row_offset+4, column=0, columnspan=2, sticky=tk.EW, pady=(15, 0))
        ttk.Button(btn_frame, text="Create Invoice", command=create).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)

    def save_current_config(self):
        """Save current configuration from GUI"""
        try:
            self.config.config['woocommerce']['url'] = self.url_var.get()
            self.config.config['monitoring']['poll_interval'] = int(self.interval_var.get())
            self.config.config['monitoring']['base_directory'] = self.base_dir_var.get()
            self.config.config['monitoring']['download_invoices'] = self.download_invoices_var.get()
            self.config.config['monitoring']['download_labels'] = self.download_labels_var.get()
            self.config.save_config()
        except Exception as e:
            self.update_status(f"Error saving config: {e}", "error")


# ====================================
# SETTINGS DIALOG
# ====================================

class SettingsDialog:
    """Advanced settings dialog"""

    def __init__(self, parent, config: Config):
        self.config = config
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Advanced Settings")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_dialog()

    def create_dialog(self):
        """Create settings dialog"""
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # WooCommerce tab
        wc_frame = ttk.Frame(notebook, padding="10")
        notebook.add(wc_frame, text="WooCommerce API")

        wc_config = self.config.config['woocommerce']

        ttk.Label(wc_frame, text="Consumer Key:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.consumer_key_var = tk.StringVar(value=wc_config['consumer_key'])
        ttk.Entry(wc_frame, textvariable=self.consumer_key_var, width=60).grid(row=0, column=1, pady=5)

        ttk.Label(wc_frame, text="Consumer Secret:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.consumer_secret_var = tk.StringVar(value=wc_config['consumer_secret'])
        ttk.Entry(wc_frame, textvariable=self.consumer_secret_var, width=60, show="*").grid(row=1, column=1, pady=5)

        ttk.Label(wc_frame, text="Monitor Secret Key:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.monitor_secret_var = tk.StringVar(value=wc_config.get('monitor_secret_key', ''))
        ttk.Entry(wc_frame, textvariable=self.monitor_secret_var, width=60, show="*").grid(row=2, column=1, pady=5)

        instructions = tk.Text(wc_frame, height=12, wrap=tk.WORD)
        instructions.grid(row=3, column=0, columnspan=2, pady=10, sticky=(tk.W, tk.E))
        instructions.insert(tk.END,
            "WooCommerce API Setup:\n\n"
            "1. Log in to WordPress admin\n"
            "2. Go to WooCommerce → Settings → Advanced → REST API\n"
            "3. Click 'Add key'\n"
            "4. Set description and permissions to 'Read'\n"
            "5. Copy Consumer Key and Secret here\n\n"
            "Monitor Secret Key (optional):\n"
            "Only needed for bpost label database queries.\n"
            "Get from WordPress: wp option get bpost_monitor_secret_key"
        )
        instructions.config(state=tk.DISABLED)

        # Monitoring tab
        monitor_frame = ttk.Frame(notebook, padding="10")
        notebook.add(monitor_frame, text="Monitoring")

        monitor_config = self.config.config['monitoring']

        ttk.Label(monitor_frame, text="Check orders from last (hours):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.check_hours_var = tk.StringVar(value=str(monitor_config['check_orders_since_hours']))
        ttk.Entry(monitor_frame, textvariable=self.check_hours_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=5)

        # Filters tab
        filter_frame = ttk.Frame(notebook, padding="10")
        notebook.add(filter_frame, text="Filters")

        filters = self.config.config['filters']

        ttk.Label(filter_frame, text="Order Statuses (comma-separated):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.statuses_var = tk.StringVar(value=','.join(filters.get('order_statuses', [])))
        ttk.Entry(filter_frame, textvariable=self.statuses_var, width=40).grid(row=0, column=1, pady=5)

        ttk.Label(filter_frame, text="Example: processing,completed,on-hold").grid(row=1, column=1, sticky=tk.W)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Save", command=self.save_settings).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def save_settings(self):
        """Save settings"""
        try:
            self.config.config['woocommerce']['consumer_key'] = self.consumer_key_var.get()
            self.config.config['woocommerce']['consumer_secret'] = self.consumer_secret_var.get()
            self.config.config['woocommerce']['monitor_secret_key'] = self.monitor_secret_var.get()
            self.config.config['monitoring']['check_orders_since_hours'] = int(self.check_hours_var.get())

            statuses = [s.strip() for s in self.statuses_var.get().split(',') if s.strip()]
            self.config.config['filters']['order_statuses'] = statuses

            if self.config.save_config():
                messagebox.showinfo("Success", "Settings saved successfully!")
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to save settings")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid settings: {e}")


# ====================================
# MAIN
# ====================================

def main():
    """Main entry point"""
    # Setup logging when the app actually runs (not at import time)
    setup_shared_logging("woocommerce_monitor")

    root = tk.Tk()
    app = OrderMonitorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
