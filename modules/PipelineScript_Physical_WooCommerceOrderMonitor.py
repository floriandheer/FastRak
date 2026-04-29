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
from shared_window_icon import apply_category_icon
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
from shared_project_db import ProjectDatabase

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
            response = self.session.get(f"{self.api_url}/orders", params={'per_page': 1})
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

    def download_invoice_pdf(self, order_id: int, save_path: Path) -> bool:
        """Download invoice PDF via custom WordPress AJAX endpoint (pipeline_get_invoice)."""
        try:
            wc_config = self.config.config['woocommerce']
            secret_key = wc_config.get('monitor_secret_key', '')
            if not secret_key:
                logger.warning("monitor_secret_key not configured — cannot download invoice PDF")
                return False

            endpoint = f"{self.base_url}/wp-admin/admin-ajax.php"
            params = {
                'action': 'pipeline_get_invoice',
                'order_id': order_id,
                'secret': secret_key
            }
            logger.debug(f"Requesting invoice from {endpoint} for order {order_id}")
            response = requests.get(endpoint, params=params, timeout=30, allow_redirects=False)
            logger.debug(f"Invoice response: HTTP {response.status_code}, content-type: {response.headers.get('content-type', 'unknown')}, size: {len(response.content)} bytes")

            if response.status_code in (301, 302, 303, 307, 308):
                redirect_url = response.headers.get('Location', 'unknown')
                logger.error(f"Invoice endpoint redirected to {redirect_url} — check server config")
                return False

            if response.status_code != 200:
                logger.error(f"Invoice endpoint returned HTTP {response.status_code} for order {order_id}")
                return False

            content_type = response.headers.get('content-type', '')
            if 'pdf' not in content_type:
                try:
                    data = response.json()
                    error_msg = data.get('data', data.get('message', 'Unknown error'))
                    logger.error(f"Invoice endpoint error for order {order_id}: {error_msg}")
                except ValueError:
                    logger.error(f"Invoice endpoint returned unexpected content-type '{content_type}' for order {order_id}")
                return False

            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"Downloaded invoice PDF for order {order_id}: {save_path}")
            return True
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot reach invoice endpoint — check your store URL")
            return False
        except requests.exceptions.Timeout:
            logger.error(f"Invoice download timed out for order {order_id}")
            return False
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

    def get_all_orders(self) -> List[Dict]:
        """Get all orders matching configured status filters (paginated)."""
        all_orders = []
        page = 1
        try:
            filters = self.config.config['filters']
            while True:
                params = {
                    'per_page': 100,
                    'page': page,
                    'orderby': 'date',
                    'order': 'desc'
                }
                if filters.get('order_statuses'):
                    params['status'] = ','.join(filters['order_statuses'])

                response = self.session.get(f"{self.api_url}/orders", params=params)
                response.raise_for_status()
                orders = response.json()
                if not orders:
                    break
                all_orders.extend(orders)
                page += 1
            return all_orders
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return all_orders

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

    def update_invoice_number(self, order_id: int, new_number: str) -> Optional[Dict]:
        """Update the invoice number on a WooCommerce order (WooCommerce PDF Invoices plugin).

        Updates both _wcpdf_invoice_number (formatted string) and
        _wcpdf_invoice_number_data (structured data the plugin reads when
        generating the PDF).
        """
        try:
            # Build the number_data structure that WCPDF expects
            number_data = {
                "number": int(new_number) if new_number.isdigit() else new_number,
                "formatted_number": str(new_number),
                "prefix": "",
                "suffix": "",
            }

            response = self.session.put(
                f"{self.api_url}/orders/{order_id}",
                json={
                    "meta_data": [
                        {"key": "_wcpdf_invoice_number", "value": str(new_number)},
                        {"key": "_wcpdf_invoice_number_data", "value": number_data},
                    ]
                }
            )
            response.raise_for_status()
            logger.info(f"Updated invoice number for order {order_id} to '{new_number}'")
            return response.json()
        except Exception as e:
            logger.error(f"Failed to update invoice number for order {order_id}: {e}")
            return None

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
        return f"3D_{date_part}_Factuur{int(invoice_number):03d}_{clean_name}.pdf"

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

    def _get_invoice_info_from_meta(self, order: Dict) -> Optional[Dict]:
        """Extract invoice number and date from order metadata (WooCommerce PDF Invoices plugin)."""
        invoice_number = None
        invoice_date = None
        invoice_date_formatted = None
        for meta in order.get('meta_data', []):
            key = meta.get('key', '')
            if key == '_wcpdf_invoice_number':
                invoice_number = meta.get('value')
            elif key == '_wcpdf_invoice_date':
                invoice_date = meta.get('value')
            elif key == '_wcpdf_invoice_date_formatted':
                invoice_date_formatted = meta.get('value')
        if invoice_number:
            # Prefer formatted date if available
            if invoice_date_formatted:
                date_str = invoice_date_formatted
            elif invoice_date:
                # Plugin stores a Unix timestamp — convert to YYYY-MM-DD
                try:
                    dt = datetime.fromtimestamp(int(invoice_date))
                    date_str = dt.strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    # Already a date string
                    date_str = str(invoice_date)[:10]
            else:
                date_str = order.get('date_created', '')[:10]
            return {'invoice_number': str(invoice_number), 'invoice_date': date_str}
        return None

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
        order_number = order.get('number', order_id)

        try:
            # Get invoice info from order metadata (WooCommerce PDF Invoices plugin)
            invoice_info = self._get_invoice_info_from_meta(order)
            if not invoice_info:
                logger.warning(f"No invoice metadata found for order #{order_number} — invoice may not be generated yet")
                return None

            invoice_number = invoice_info['invoice_number']
            invoice_date = invoice_info['invoice_date']
            logger.info(f"Order #{order_number}: invoice #{invoice_number} dated {invoice_date}")

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

            # Create .lnk shortcut in the order/project folder
            outgoing = self._find_outgoing_folder(project_folder)
            if not outgoing:
                # Create an Outgoing folder if one doesn't exist
                outgoing = project_folder / "03_Outgoing"
                outgoing.mkdir(parents=True, exist_ok=True)
            shortcut_name = filename.replace(".pdf", ".lnk")
            self._create_shortcut(outgoing / shortcut_name, invoice_path)

            return invoice_path

        except Exception as e:
            logger.error(f"Failed to file invoice for order #{order_number}: {e}")
            return None

    def refile_invoice(self, order: Dict, project_folder: Path) -> Optional[Path]:
        """
        Re-download and re-file an invoice, removing the old PDF and shortcut first.

        Useful after changing the invoice number or when the invoice content
        has been updated on the server.
        """
        order_id = order['id']
        order_number = order.get('number', order_id)

        try:
            # Remove old invoice PDF and shortcut from Boekhouding / project folder
            self._cleanup_old_invoice(order, project_folder)

            # File the (new) invoice
            return self.file_invoice(order, project_folder)

        except Exception as e:
            logger.error(f"Failed to refile invoice for order #{order_number}: {e}")
            return None

    def _cleanup_old_invoice(self, order: Dict, project_folder: Path):
        """Remove existing invoice PDF in Boekhouding and .lnk shortcut in project folder."""
        order_number = order.get('number', order['id'])
        try:
            # Look for any invoice PDF matching this order in the Boekhouding tree
            invoice_date = order.get('date_created', '')[:10]
            if not invoice_date:
                return
            quarter_dir = self._get_quarter_dir(invoice_date)
            if quarter_dir.exists():
                for f in quarter_dir.iterdir():
                    # Match by order number or old invoice number in filename
                    if f.is_file() and f.suffix == '.pdf' and f.name.startswith('3D_'):
                        # Check if this PDF belongs to the order — the filename
                        # contains the client name which we can match
                        billing = order.get('billing', {})
                        client_name = (billing.get('last_name', '') or
                                       billing.get('first_name', '') or '')
                        clean_name = client_name.replace(" ", "").replace("_", "")
                        if clean_name and clean_name in f.name:
                            logger.info(f"Removing old invoice: {f}")
                            f.unlink()

            # Remove old .lnk shortcuts in outgoing folder
            outgoing = self._find_outgoing_folder(project_folder)
            if outgoing and outgoing.exists():
                for f in outgoing.iterdir():
                    if f.is_file() and f.suffix == '.lnk' and 'Factuur' in f.name:
                        billing = order.get('billing', {})
                        client_name = (billing.get('last_name', '') or
                                       billing.get('first_name', '') or '')
                        clean_name = client_name.replace(" ", "").replace("_", "")
                        if clean_name and clean_name in f.name:
                            logger.info(f"Removing old shortcut: {f}")
                            f.unlink()

        except Exception as e:
            logger.warning(f"Cleanup of old invoice for order #{order_number} failed: {e}")


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
        # The project tracker DB is canonical for projects. Order folders are
        # registered the moment they're created so the tracker doesn't have
        # to re-scan the Order directory afterwards.
        try:
            self.db = ProjectDatabase()
        except Exception as e:
            logger.warning(f"Project DB unavailable; orders will not be registered: {e}")
            self.db = None
        self.running = False
        self.callback = None
        self.order_list_callback = None

    def set_callback(self, callback):
        """Set callback function for status updates"""
        self.callback = callback

    def set_order_list_callback(self, callback):
        """Set callback to push full order list to GUI"""
        self.order_list_callback = callback

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

    def _register_order_in_db(self, order: Dict, order_folder: Path) -> None:
        """Insert the order's folder into the project DB as a Physical/Order
        project. register_project is idempotent on the path, so re-runs (or
        the legacy folder-scan importer) won't create duplicates."""
        if not self.db:
            return
        try:
            order_id = order.get("id")
            order_number = order.get("number", order_id)

            billing = order.get("billing", {}) or {}
            customer_name = (
                f"{billing.get('first_name', '')} {billing.get('last_name', '')}"
            ).strip()
            if not customer_name:
                customer_name = "Guest"

            # Best-effort date — fall back to today if WooCommerce gave us
            # something unparseable.
            date_str = ""
            for key in ("date_paid", "date_completed", "date_created"):
                raw = order.get(key)
                if raw:
                    try:
                        date_str = str(raw)[:10]
                        if len(date_str) == 10:
                            break
                    except Exception:
                        continue
            if not date_str:
                date_str = datetime.now().strftime("%Y-%m-%d")

            shipping = order.get("shipping", {}) or {}
            location_parts = [
                shipping.get("city", ""),
                shipping.get("country", ""),
            ]
            location = ", ".join(p for p in location_parts if p)

            metadata = {
                "is_personal": False,
                "is_sandbox": False,
                "physical_subtype": "Order",
                "location": location,
                "woo_order_id": order_id,
                "woo_order_number": order_number,
                "woo_status": order.get("status", ""),
                "woo_total": order.get("total", ""),
                "woo_currency": order.get("currency", ""),
            }

            self.db.register_project({
                "client_name": customer_name,
                "project_name": f"Order_{order_number}",
                "project_type": "Physical",
                "date_created": date_str,
                "path": str(order_folder),
                "base_directory": str(self.doc_manager.base_dir),
                "status": "active",
                "notes": "",
                "metadata": metadata,
            })
            logger.info(
                f"Registered Physical/Order project for #{order_number} "
                f"({customer_name}) in DB"
            )
        except Exception as e:
            # Don't let DB issues break order processing — folder + invoices
            # still work, and the legacy folder-scan importer can pick the
            # row up later.
            logger.error(f"Failed to register order in project DB: {e}")

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

            # Register in the project DB right away so the tracker sees it
            # without needing a folder rescan.
            self._register_order_in_db(order, order_folder)

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
        """Check for new orders by status filter"""
        try:
            self.log_status("Checking for orders...", "info")

            orders = self.wc_client.get_all_orders()

            # Push full order list to GUI
            if self.order_list_callback:
                self.order_list_callback(orders)

            if not orders:
                self.log_status("No orders found", "info")
                return

            self.log_status(f"Found {len(orders)} order(s)", "info")

            processed_count = 0
            for order in orders:
                if self.process_order(order):
                    processed_count += 1

            if processed_count > 0:
                self.log_status(f"Processed {processed_count} new order(s)", "success")
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
                self._register_order_in_db(order, order_folder)

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
        self.monitor.set_order_list_callback(self.update_order_list)
        self.monitor_thread = None
        self.orders_cache = []  # cached order data for double-click etc.

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
        main_frame.rowconfigure(1, weight=3)  # order table gets most space
        main_frame.rowconfigure(3, weight=1)  # activity log gets less

        # Header
        header_frame = ttk.LabelFrame(main_frame, text="WooCommerce Order Monitor", padding="10")
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Status indicator
        self.status_label = ttk.Label(header_frame, text="Stopped", font=('Arial', 12, 'bold'))
        self.status_label.grid(row=0, column=0, sticky=tk.W)

        # Control buttons
        button_frame = ttk.Frame(header_frame)
        button_frame.grid(row=0, column=1, sticky=tk.E)

        self.start_button = ttk.Button(button_frame, text="Start Monitoring",
                                       command=self.start_monitoring, width=18)
        self.start_button.grid(row=0, column=0, padx=5)

        self.stop_button = ttk.Button(button_frame, text="Stop Monitoring",
                                      command=self.stop_monitoring, state=tk.DISABLED, width=18)
        self.stop_button.grid(row=0, column=1, padx=5)

        self.check_now_button = ttk.Button(button_frame, text="Refresh",
                                          command=self.check_now, width=12)
        self.check_now_button.grid(row=0, column=2, padx=5)

        ttk.Button(button_frame, text="Settings",
                  command=self.open_settings, width=10).grid(row=0, column=3, padx=5)

        # Invoice action buttons (second row)
        invoice_frame = ttk.Frame(header_frame)
        invoice_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))

        ttk.Button(invoice_frame, text="File Quarter Invoices",
                  command=self.file_quarter_invoices, width=22).grid(row=0, column=0, padx=5)

        ttk.Button(invoice_frame, text="Create Project Invoice",
                  command=self.create_project_invoice, width=22).grid(row=0, column=1, padx=5)

        header_frame.columnconfigure(1, weight=1)

        # Orders table
        orders_frame = ttk.LabelFrame(main_frame, text="Orders", padding="10")
        orders_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        orders_frame.columnconfigure(0, weight=1)
        orders_frame.rowconfigure(0, weight=1)

        columns = ("order_num", "invoice_num", "date", "customer", "city", "status", "total", "processed")
        self.order_tree = ttk.Treeview(orders_frame, columns=columns, show="headings", height=12)

        self.order_tree.heading("order_num", text="Order #")
        self.order_tree.heading("invoice_num", text="Invoice #")
        self.order_tree.heading("date", text="Date")
        self.order_tree.heading("customer", text="Customer")
        self.order_tree.heading("city", text="City")
        self.order_tree.heading("status", text="Status")
        self.order_tree.heading("total", text="Total")
        self.order_tree.heading("processed", text="Processed")

        self.order_tree.column("order_num", width=80, anchor="center")
        self.order_tree.column("invoice_num", width=80, anchor="center")
        self.order_tree.column("date", width=100, anchor="center")
        self.order_tree.column("customer", width=180)
        self.order_tree.column("city", width=120)
        self.order_tree.column("status", width=100, anchor="center")
        self.order_tree.column("total", width=80, anchor="e")
        self.order_tree.column("processed", width=80, anchor="center")

        tree_scroll = ttk.Scrollbar(orders_frame, orient="vertical", command=self.order_tree.yview)
        self.order_tree.config(yscrollcommand=tree_scroll.set)
        self.order_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_scroll.grid(row=0, column=1, sticky="ns")

        # Color tags for statuses
        self.order_tree.tag_configure("processing", foreground="#3b82f6")
        self.order_tree.tag_configure("completed", foreground="#22c55e")
        self.order_tree.tag_configure("on-hold", foreground="#f59e0b")
        self.order_tree.tag_configure("cancelled", foreground="#ef4444")
        self.order_tree.tag_configure("refunded", foreground="#a855f7")
        self.order_tree.tag_configure("pending", foreground="#8b949e")

        # Double-click to open folder
        self.order_tree.bind("<Double-1>", self.on_order_double_click)

        # Status change bar below table
        status_bar = ttk.Frame(orders_frame)
        status_bar.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(8, 0))

        ttk.Label(status_bar, text="Change status to:").pack(side=tk.LEFT, padx=(0, 5))
        self.status_change_var = tk.StringVar(value="completed")
        status_combo = ttk.Combobox(status_bar, textvariable=self.status_change_var,
                                    values=["processing", "completed", "on-hold", "cancelled", "refunded", "pending"],
                                    state="readonly", width=14)
        status_combo.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(status_bar, text="Update Status",
                  command=self.change_order_status, width=14).pack(side=tk.LEFT, padx=5)

        # Separator
        ttk.Separator(status_bar, orient="vertical").pack(side=tk.LEFT, fill="y", padx=10, pady=2)

        ttk.Button(status_bar, text="View Invoice",
                  command=self.view_invoice, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Button(status_bar, text="Change Invoice #",
                  command=self.change_invoice_number, width=14).pack(side=tk.LEFT, padx=5)

        ttk.Button(status_bar, text="Refile Invoice",
                  command=self.refile_invoices, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Button(status_bar, text="Create Folder",
                  command=self.create_order_folder, width=12).pack(side=tk.LEFT, padx=5)

        self.order_count_label = ttk.Label(status_bar, text="")
        self.order_count_label.pack(side=tk.RIGHT)

        # Activity log (smaller)
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="10")
        log_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure text tags for colors
        self.log_text.tag_config('info', foreground='black')
        self.log_text.tag_config('success', foreground='green')
        self.log_text.tag_config('warning', foreground='orange')
        self.log_text.tag_config('error', foreground='red')

        # Statistics panel
        stats_frame = ttk.Frame(main_frame)
        stats_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        self.stats_label = ttk.Label(stats_frame, text="Ready to start monitoring")
        self.stats_label.pack(side=tk.LEFT)

    def update_order_list(self, orders: List[Dict]):
        """Update the order table from background thread"""
        self.orders_cache = orders
        self.root.after(0, self._refresh_order_tree, orders)

    def _refresh_order_tree(self, orders: List[Dict]):
        """Refresh the Treeview with order data (must run on main thread)"""
        # Remember selection
        selected_ids = set()
        for item in self.order_tree.selection():
            vals = self.order_tree.item(item, "values")
            if vals:
                selected_ids.add(vals[0])  # order number

        self.order_tree.delete(*self.order_tree.get_children())

        invoice_numbers_seen = []  # (int_value, order_number) for consistency check

        for order in orders:
            order_number = str(order.get('number', order['id']))
            date_str = order.get('date_created', '')[:10]
            billing = order.get('billing', {})
            customer = f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip()
            city = billing.get('city', '')
            status = order.get('status', '')
            currency = order.get('currency_symbol', order.get('currency', ''))
            total = f"{currency}{order.get('total', '0.00')}"
            is_processed = "Yes" if self.monitor.tracker.is_processed(str(order['id'])) else ""

            # Extract invoice number from WooCommerce PDF Invoices metadata
            invoice_num = ""
            for meta in order.get('meta_data', []):
                if meta.get('key') == '_wcpdf_invoice_number':
                    invoice_num = str(meta.get('value', ''))
                    break
            if invoice_num:
                try:
                    invoice_numbers_seen.append((int(invoice_num), order_number))
                except ValueError:
                    pass

            item_id = self.order_tree.insert("", "end", values=(
                order_number, invoice_num, date_str, customer, city, status, total, is_processed
            ), tags=(status,))

            # Restore selection
            if order_number in selected_ids:
                self.order_tree.selection_add(item_id)

        self.order_count_label.config(text=f"{len(orders)} order(s)")

        # Invoice number consistency check — detect gaps in the sequence
        if invoice_numbers_seen:
            invoice_numbers_seen.sort(key=lambda x: x[0])
            nums = [n for n, _ in invoice_numbers_seen]
            expected = set(range(min(nums), max(nums) + 1))
            missing = sorted(expected - set(nums))
            if missing:
                gap_str = ", ".join(str(n) for n in missing)
                self.update_status(
                    f"Invoice gap detected! Missing invoice number(s): {gap_str}",
                    "warning")

    def on_order_double_click(self, event):
        """Open order folder on double-click"""
        selection = self.order_tree.selection()
        if not selection:
            return
        values = self.order_tree.item(selection[0], "values")
        if not values:
            return

        order_id_str = values[0]  # order number

        # Find the order in cache to look up folder
        for order in self.orders_cache:
            if str(order.get('number', order['id'])) == order_id_str:
                # Check tracker for folder path
                tracker_data = self.monitor.tracker.processed_orders.get(str(order['id']))
                if tracker_data and tracker_data.get('folder_path'):
                    folder = Path(tracker_data['folder_path'])
                    if folder.exists():
                        os.startfile(str(folder))
                        return
                # Try to find folder by order number
                found = self.monitor._find_order_folder(order)
                if found and found.exists():
                    os.startfile(str(found))
                    return

        self.update_status("No folder found for this order", "warning")

    def change_order_status(self):
        """Change status of selected order(s)"""
        selection = self.order_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select one or more orders.")
            return

        new_status = self.status_change_var.get()
        order_numbers = []
        for item in selection:
            vals = self.order_tree.item(item, "values")
            if vals:
                order_numbers.append(vals[0])

        if not messagebox.askyesno("Confirm",
                f"Change status of {len(order_numbers)} order(s) to '{new_status}'?"):
            return

        def do_update():
            for order_num in order_numbers:
                for order in self.orders_cache:
                    if str(order.get('number', order['id'])) == order_num:
                        result = self.monitor.wc_client.update_order_status(order['id'], new_status)
                        if result:
                            self.update_status(f"Order #{order_num} -> {new_status}", "success")
                        else:
                            self.update_status(f"Failed to update order #{order_num}", "error")
                        break
            # Refresh the order list
            self.monitor.check_orders()

        threading.Thread(target=do_update, daemon=True).start()

    def _get_selected_order(self) -> Optional[Dict]:
        """Get the first selected order from cache"""
        selection = self.order_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select an order.")
            return None
        values = self.order_tree.item(selection[0], "values")
        if not values:
            return None
        order_num = values[0]
        for order in self.orders_cache:
            if str(order.get('number', order['id'])) == order_num:
                return order
        return None

    def view_invoice(self):
        """Download and open invoice PDF for the selected order"""
        order = self._get_selected_order()
        if not order:
            return

        order_number = order.get('number', order['id'])

        # Check if invoice already exists locally (in tracker)
        tracker_data = self.monitor.tracker.processed_orders.get(str(order['id']))
        if tracker_data and tracker_data.get('documents', {}).get('invoice'):
            invoice_path = Path(tracker_data['documents']['invoice'])
            if invoice_path.exists():
                self.update_status(f"Opening local invoice for order #{order_number}", "info")
                os.startfile(str(invoice_path))
                return

        # Check if monitor_secret_key is configured
        secret = self.config.config['woocommerce'].get('monitor_secret_key', '')
        if not secret:
            self.update_status(
                "Cannot download invoice: monitor_secret_key not configured in Advanced Settings",
                "error")
            return

        # Download to temp and open
        self.update_status(f"Downloading invoice for order #{order_number}...", "info")

        def do_download():
            import tempfile
            temp_path = Path(tempfile.gettempdir()) / f"Invoice_{order_number}.pdf"
            if self.monitor.wc_client.download_invoice_pdf(order['id'], temp_path):
                self.update_status(f"Invoice #{order_number} downloaded and opened", "success")
                os.startfile(str(temp_path))
            else:
                self.update_status(
                    f"Failed to download invoice for order #{order_number} — "
                    "check that the pipeline_get_invoice PHP endpoint is set up on your server",
                    "error")

        threading.Thread(target=do_download, daemon=True).start()

    def change_invoice_number(self):
        """Show dialog to change the invoice number for the selected order."""
        order = self._get_selected_order()
        if not order:
            return

        order_number = order.get('number', order['id'])

        # Get current invoice number from metadata
        current_invoice = ""
        for meta in order.get('meta_data', []):
            if meta.get('key') == '_wcpdf_invoice_number':
                current_invoice = str(meta.get('value', ''))
                break

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Change Invoice # — Order #{order_number}")
        dialog.geometry("380x150")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Order #{order_number}").pack(anchor=tk.W)

        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(row, text="Invoice number:").pack(side=tk.LEFT, padx=(0, 5))
        invoice_var = tk.StringVar(value=current_invoice)
        entry = ttk.Entry(row, textvariable=invoice_var, width=20)
        entry.pack(side=tk.LEFT)
        entry.select_range(0, tk.END)
        entry.focus_set()

        def apply():
            new_number = invoice_var.get().strip()
            if not new_number:
                messagebox.showwarning("Empty", "Please enter an invoice number.", parent=dialog)
                return
            if new_number == current_invoice:
                dialog.destroy()
                return
            dialog.destroy()

            def do_update():
                self.update_status(f"Updating invoice number for order #{order_number} to {new_number}...", "info")
                result = self.monitor.wc_client.update_invoice_number(order['id'], new_number)
                if result:
                    # Update the cached order meta so subsequent actions see the new number
                    for meta in order.get('meta_data', []):
                        if meta.get('key') == '_wcpdf_invoice_number':
                            meta['value'] = new_number
                            break
                    else:
                        order.setdefault('meta_data', []).append(
                            {'key': '_wcpdf_invoice_number', 'value': new_number})
                    self.update_status(
                        f"Invoice number for order #{order_number} changed to {new_number}", "success")
                else:
                    self.update_status(
                        f"Failed to update invoice number for order #{order_number}", "error")

            threading.Thread(target=do_update, daemon=True).start()

        dialog.bind("<Return>", lambda e: apply())

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(btn_frame, text="Apply", command=apply).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)

    def refile_invoices(self):
        """Re-download and re-file invoices for selected order(s)."""
        selection = self.order_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select one or more orders.")
            return

        order_numbers = []
        for item in selection:
            vals = self.order_tree.item(item, "values")
            if vals:
                order_numbers.append(vals[0])

        count = len(order_numbers)
        if not messagebox.askyesno("Confirm",
                f"Re-download and refile invoice{'s' if count > 1 else ''} "
                f"for {count} order{'s' if count > 1 else ''}?\n\n"
                "This will fetch fresh data from WooCommerce,\n"
                "remove the old PDF from Boekhouding, and file the new one."):
            return

        def do_refile():
            success = 0
            failed = 0
            for order_num in order_numbers:
                for cached_order in self.orders_cache:
                    if str(cached_order.get('number', cached_order['id'])) == order_num:
                        order_id = cached_order['id']

                        # Re-fetch order from API to get current metadata
                        self.update_status(f"Fetching order #{order_num} from WooCommerce...", "info")
                        order = self.monitor.wc_client.get_order_details(order_id)
                        if not order:
                            self.update_status(f"Failed to fetch order #{order_num}", "error")
                            failed += 1
                            break

                        # Find or create the order folder
                        project_folder = self.monitor._find_order_folder(order)
                        if not project_folder:
                            project_folder = self.monitor.doc_manager.create_order_folder(order)
                            self.update_status(f"Created folder for order #{order_num}", "info")
                            self.monitor._register_order_in_db(order, project_folder)

                        # Refile
                        filed_path = self.monitor.invoice_filer.refile_invoice(order, project_folder)
                        if filed_path:
                            success += 1
                            self.update_status(
                                f"✓ Refiled invoice for order #{order_num}: {filed_path.name}",
                                "success")
                        else:
                            failed += 1
                            self.update_status(
                                f"✗ Failed to refile invoice for order #{order_num}", "error")
                        break

            self.update_status(
                f"Refile complete: {success} succeeded, {failed} failed", "success" if not failed else "warning")

        threading.Thread(target=do_refile, daemon=True).start()

    def create_order_folder(self):
        """Create folder structure and download documents for selected order(s)"""
        selection = self.order_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select one or more orders.")
            return

        order_numbers = []
        for item in selection:
            vals = self.order_tree.item(item, "values")
            if vals:
                order_numbers.append(vals[0])

        def do_process():
            for order_num in order_numbers:
                for order in self.orders_cache:
                    if str(order.get('number', order['id'])) == order_num:
                        order_id = str(order['id'])
                        if self.monitor.tracker.is_processed(order_id):
                            self.update_status(f"Order #{order_num} already processed", "info")
                        else:
                            self.monitor.process_order(order)
                        break
            # Refresh the table to update Processed column
            if self.orders_cache:
                self.update_order_list(self.orders_cache)

        threading.Thread(target=do_process, daemon=True).start()

    def check_initial_config(self):
        """Check if configuration is complete and auto-refresh"""
        wc_config = self.config.config['woocommerce']
        if not wc_config['consumer_key'] or not wc_config['consumer_secret']:
            if messagebox.askyesno("Configuration Required",
                                   "WooCommerce API credentials not configured.\n\n"
                                   "Would you like to configure them now?"):
                self.open_settings()
        else:
            # Auto-refresh order list on startup
            self.check_now()

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
        """Save current configuration"""
        try:
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
            "4. Set description and permissions to 'Read/Write'\n"
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

        ttk.Label(monitor_frame, text="Poll Interval (seconds):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.poll_interval_var = tk.StringVar(value=str(monitor_config.get('poll_interval', 300)))
        ttk.Entry(monitor_frame, textvariable=self.poll_interval_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(monitor_frame, text="Save Location:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.base_dir_var = tk.StringVar(value=monitor_config.get('base_directory', ''))
        ttk.Entry(monitor_frame, textvariable=self.base_dir_var, width=50).grid(row=1, column=1, sticky=tk.W, pady=5)

        self.download_invoices_var = tk.BooleanVar(value=monitor_config.get('download_invoices', True))
        ttk.Checkbutton(monitor_frame, text="Download/File Invoices",
                       variable=self.download_invoices_var).grid(row=2, column=1, sticky=tk.W, pady=5)

        self.download_labels_var = tk.BooleanVar(value=monitor_config.get('download_labels', True))
        ttk.Checkbutton(monitor_frame, text="Download Shipping Labels",
                       variable=self.download_labels_var).grid(row=3, column=1, sticky=tk.W, pady=5)

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
            self.config.config['monitoring']['poll_interval'] = int(self.poll_interval_var.get())
            self.config.config['monitoring']['base_directory'] = self.base_dir_var.get()
            self.config.config['monitoring']['download_invoices'] = self.download_invoices_var.get()
            self.config.config['monitoring']['download_labels'] = self.download_labels_var.get()

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
    apply_category_icon(root)
    app = OrderMonitorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
