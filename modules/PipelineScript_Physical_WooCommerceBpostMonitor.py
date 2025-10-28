#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WooCommerce bpost Label Monitor
Author: Florian Dheer
Version: 1.0.0
Description: Automatically monitor WooCommerce orders and download bpost shipping labels
Location: P:\\_Scripts\modules\PipelineScript_Physical_WooCommerceBpostMonitor.py
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
import logging
from typing import Dict, List, Optional
import base64

# ====================================
# CONFIGURATION
# ====================================

class Config:
    """Configuration manager for WooCommerce-bpost integration"""
    
    def __init__(self):
        self.config_file = Path(__file__).parent / "woocommerce_bpost_config.json"
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load configuration from file"""
        # Use absolute paths relative to script directory
        script_dir = Path(__file__).parent

        default_config = {
            "woocommerce": {
                "url": "https://yourdomain.com",
                "consumer_key": "",
                "consumer_secret": "",
                "api_version": "wc/v3"
            },
            "bpost": {
                "api_key": "",
                "account_id": "",
                "use_direct_api": False
            },
            "monitoring": {
                "poll_interval": 300,  # seconds (5 minutes)
                "check_orders_since_hours": 48,  # Check orders from last 48 hours
                "base_directory": "I:/Physical/Orders",
                "processed_orders_file": str(script_dir / "processed_orders.json")
            },
            "logging": {
                "enabled": True,
                "log_file": str(script_dir / "woocommerce_bpost_monitor.log"),
                "log_level": "INFO"
            }
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults
                    self._merge_config(default_config, loaded_config)

                    # Convert relative paths to absolute paths
                    log_file = default_config['logging']['log_file']
                    if not os.path.isabs(log_file):
                        default_config['logging']['log_file'] = str(script_dir / log_file)

                    processed_file = default_config['monitoring']['processed_orders_file']
                    if not os.path.isabs(processed_file):
                        default_config['monitoring']['processed_orders_file'] = str(script_dir / processed_file)

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
            logging.error(f"Failed to save tracker: {e}")
    
    def is_processed(self, order_id: str) -> bool:
        """Check if order has been processed"""
        return str(order_id) in self.processed_orders
    
    def mark_processed(self, order_id: str, label_path: str):
        """Mark order as processed"""
        self.processed_orders[str(order_id)] = {
            "processed_at": datetime.now().isoformat(),
            "label_path": label_path
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
            # Calculate date filter
            from datetime import datetime, timedelta
            after_date = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            params = {
                'after': after_date,
                'per_page': 100,
                'orderby': 'date',
                'order': 'desc'
            }
            
            response = self.session.get(f"{self.api_url}/orders", params=params)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logging.error(f"Failed to get orders: {e}")
            return []
    
    def get_order_details(self, order_id: int) -> Optional[Dict]:
        """Get detailed order information"""
        try:
            response = self.session.get(f"{self.api_url}/orders/{order_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Failed to get order {order_id}: {e}")
            return None
    
    def has_bpost_shipping(self, order: Dict) -> bool:
        """Check if order uses bpost shipping"""
        # Check shipping lines
        for shipping_line in order.get('shipping_lines', []):
            method_id = shipping_line.get('method_id', '').lower()
            method_title = shipping_line.get('method_title', '').lower()
            
            if 'bpost' in method_id or 'bpost' in method_title:
                return True
        
        # Check meta data
        for meta in order.get('meta_data', []):
            key = meta.get('key', '').lower()
            if 'bpost' in key:
                return True
        
        return False
    
    def get_bpost_label_url(self, order: Dict) -> Optional[str]:
        """Extract bpost label URL from order metadata"""
        # Common meta keys used by bpost plugins
        label_meta_keys = [
            '_bpost_label_url',
            '_bpost_shipping_label',
            'bpost_label',
            '_shipping_label_url',
            '_bpost_label_pdf'
        ]
        
        for meta in order.get('meta_data', []):
            key = meta.get('key', '')
            if key in label_meta_keys:
                return meta.get('value')
        
        return None


# ====================================
# BPOST LABEL DOWNLOADER
# ====================================

class BpostLabelDownloader:
    """Handle bpost label downloading"""
    
    def __init__(self, config: Config):
        self.config = config
        self.base_dir = Path(config.config['monitoring']['base_directory'])
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def download_label(self, order_id: str, label_url: str, order_number: str = None) -> Optional[str]:
        """Download bpost label PDF and save to order folder"""
        try:
            # Create order folder
            folder_name = f"Order_{order_number or order_id}"
            order_folder = self.base_dir / folder_name
            order_folder.mkdir(parents=True, exist_ok=True)
            
            # Download label
            response = requests.get(label_url, timeout=30)
            response.raise_for_status()
            
            # Save label PDF
            label_path = order_folder / f"bpost_label_{order_id}.pdf"
            with open(label_path, 'wb') as f:
                f.write(response.content)
            
            logging.info(f"Downloaded label for order {order_id} to {label_path}")
            return str(label_path)
            
        except Exception as e:
            logging.error(f"Failed to download label for order {order_id}: {e}")
            return None
    
    def download_label_from_content(self, order_id: str, pdf_content: bytes, order_number: str = None) -> Optional[str]:
        """Save label PDF from content bytes"""
        try:
            # Create order folder
            folder_name = f"Order_{order_number or order_id}"
            order_folder = self.base_dir / folder_name
            order_folder.mkdir(parents=True, exist_ok=True)
            
            # Save label PDF
            label_path = order_folder / f"bpost_label_{order_id}.pdf"
            with open(label_path, 'wb') as f:
                f.write(pdf_content)
            
            logging.info(f"Saved label for order {order_id} to {label_path}")
            return str(label_path)
            
        except Exception as e:
            logging.error(f"Failed to save label for order {order_id}: {e}")
            return None


# ====================================
# ORDER MONITOR
# ====================================

class OrderMonitor:
    """Main order monitoring logic"""
    
    def __init__(self, config: Config):
        self.config = config
        self.wc_client = WooCommerceClient(config)
        self.downloader = BpostLabelDownloader(config)
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
            logging.error(message)
        elif level == "warning":
            logging.warning(message)
        else:
            logging.info(message)
    
    def process_order(self, order: Dict) -> bool:
        """Process a single order"""
        order_id = str(order['id'])
        order_number = order.get('number', order_id)
        
        # Check if already processed
        if self.tracker.is_processed(order_id):
            return False
        
        # Check if has bpost shipping
        if not self.wc_client.has_bpost_shipping(order):
            self.log_status(f"Order #{order_number} doesn't use bpost shipping", "info")
            return False
        
        self.log_status(f"Processing order #{order_number} with bpost shipping", "info")
        
        # Try to get label URL
        label_url = self.wc_client.get_bpost_label_url(order)
        
        if label_url:
            # Download label
            label_path = self.downloader.download_label(order_id, label_url, order_number)
            
            if label_path:
                self.tracker.mark_processed(order_id, label_path)
                self.log_status(f"✓ Successfully processed order #{order_number}", "success")
                return True
            else:
                self.log_status(f"✗ Failed to download label for order #{order_number}", "error")
                return False
        else:
            self.log_status(f"⚠ No label URL found for order #{order_number}", "warning")
            return False
    
    def check_orders(self):
        """Check for new orders with bpost shipping"""
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
                self.log_status(f"Processed {processed_count} new order(s)", "success")
            else:
                self.log_status("No new orders to process", "info")
                
        except Exception as e:
            self.log_status(f"Error checking orders: {e}", "error")
    
    def start_monitoring(self):
        """Start continuous monitoring"""
        self.running = True
        self.log_status("🚀 Monitoring started", "success")
        
        while self.running:
            self.check_orders()
            
            if self.running:
                interval = self.config.config['monitoring']['poll_interval']
                self.log_status(f"Next check in {interval} seconds...", "info")
                
                # Sleep in small increments to allow quick stopping
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

class BpostMonitorGUI:
    """GUI for bpost label monitoring"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("WooCommerce bpost Label Monitor")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
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
        log_config = self.config.config['logging']
        if log_config['enabled']:
            logging.basicConfig(
                level=getattr(logging, log_config['log_level']),
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_config['log_file']),
                    logging.StreamHandler()
                ]
            )
    
    def create_gui(self):
        """Create the main GUI"""
        # Configure style
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
        header_frame = ttk.LabelFrame(main_frame, text="WooCommerce bpost Label Monitor", padding="10")
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
        
        header_frame.columnconfigure(1, weight=1)
        
        # Configuration section
        config_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="10")
        config_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        config_frame.columnconfigure(1, weight=1)
        
        # WooCommerce URL
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
        
        # Settings button
        ttk.Button(config_frame, text="⚙ Advanced Settings", 
                  command=self.open_settings).grid(row=3, column=1, sticky=tk.E, pady=5)
        
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
        # Save current config
        self.save_current_config()
        
        # Test connection first
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
    
    def save_current_config(self):
        """Save current configuration from GUI"""
        try:
            self.config.config['woocommerce']['url'] = self.url_var.get()
            self.config.config['monitoring']['poll_interval'] = int(self.interval_var.get())
            self.config.config['monitoring']['base_directory'] = self.base_dir_var.get()
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
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_dialog()
    
    def create_dialog(self):
        """Create settings dialog"""
        # Create notebook for tabs
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # WooCommerce tab
        wc_frame = ttk.Frame(notebook, padding="10")
        notebook.add(wc_frame, text="WooCommerce API")
        
        wc_config = self.config.config['woocommerce']
        
        # Consumer Key
        ttk.Label(wc_frame, text="Consumer Key:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.consumer_key_var = tk.StringVar(value=wc_config['consumer_key'])
        ttk.Entry(wc_frame, textvariable=self.consumer_key_var, width=50).grid(row=0, column=1, pady=5)
        
        # Consumer Secret
        ttk.Label(wc_frame, text="Consumer Secret:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.consumer_secret_var = tk.StringVar(value=wc_config['consumer_secret'])
        ttk.Entry(wc_frame, textvariable=self.consumer_secret_var, width=50, show="*").grid(row=1, column=1, pady=5)
        
        # Instructions
        instructions = tk.Text(wc_frame, height=10, wrap=tk.WORD)
        instructions.grid(row=2, column=0, columnspan=2, pady=10, sticky=(tk.W, tk.E))
        instructions.insert(tk.END, 
            "How to get WooCommerce API credentials:\n\n"
            "1. Log in to your WordPress admin\n"
            "2. Go to WooCommerce → Settings → Advanced → REST API\n"
            "3. Click 'Add key'\n"
            "4. Set description (e.g., 'bpost Monitor')\n"
            "5. Set permissions to 'Read'\n"
            "6. Click 'Generate API key'\n"
            "7. Copy Consumer Key and Consumer Secret here\n"
        )
        instructions.config(state=tk.DISABLED)
        
        # Monitoring tab
        monitor_frame = ttk.Frame(notebook, padding="10")
        notebook.add(monitor_frame, text="Monitoring")
        
        monitor_config = self.config.config['monitoring']
        
        ttk.Label(monitor_frame, text="Check orders from last (hours):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.check_hours_var = tk.StringVar(value=str(monitor_config['check_orders_since_hours']))
        ttk.Entry(monitor_frame, textvariable=self.check_hours_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save", command=self.save_settings).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)
    
    def save_settings(self):
        """Save settings"""
        try:
            # Update config
            self.config.config['woocommerce']['consumer_key'] = self.consumer_key_var.get()
            self.config.config['woocommerce']['consumer_secret'] = self.consumer_secret_var.get()
            self.config.config['monitoring']['check_orders_since_hours'] = int(self.check_hours_var.get())
            
            # Save to file
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
    root = tk.Tk()
    app = BpostMonitorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
