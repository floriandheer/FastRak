#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pipeline Management System - Professional UI
Author: Florian Dheer
Version: 0.5.0
Description: Main launcher for various pipeline scripts with professional UI
Location: P:\\_Scripts\floriandheer_pipeline.py
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font
import subprocess
import datetime
import logging
import threading
import json

# ====================================
# CONSTANTS AND CONFIGURATION
# ====================================

# Application constants
APP_NAME = "Pipeline Manager"
APP_VERSION = "0.5.0"
APP_ICON = None  # Add path to icon file if available

# Base script directory (relative to this file)
SCRIPT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(SCRIPT_FILE_DIR, "modules")

# Logo path
LOGO_PATH = os.path.join(SCRIPT_FILE_DIR, "assets", "Logo_FlorianDheer_LogoWhite.png")

# Professional color scheme
COLORS = {
    "bg_primary": "#0d1117",      # GitHub dark background
    "bg_secondary": "#161b22",    # Slightly lighter
    "bg_card": "#1c2128",         # Card background
    "bg_hover": "#262c36",        # Hover state
    "text_primary": "#f0f6fc",    # Main text
    "text_secondary": "#8b949e",  # Secondary text
    "accent": "#58a6ff",          # Bright blue accent
    "accent_hover": "#79c0ff",    # Hover accent
    "accent_dark": "#1f6feb",     # Darker accent
    "success": "#3fb950",
    "warning": "#d29922",
    "error": "#f85149",
    "border": "#30363d",
    "tab_active_bg": "#1f6feb",   # Active tab background
    "tab_active_fg": "#ffffff"    # Active tab text
}

# Category colors
CATEGORY_COLORS = {
    "AUDIO": "#9333ea",      # Purple
    "PHOTO": "#10b981",      # Emerald
    "VISUAL": "#f97316",     # Orange
    "WEB": "#eab308",        # Yellow
    "PHYSICAL": "#ec4899",   # Pink
    "REALTIME": "#06b6d4",   # Cyan
    "BUSINESS": "#22c55e",   # Green
    "GLOBAL": "#6b7280"      # Gray
}

# Pipeline categories organized by main sections
CREATIVE_CATEGORIES = {
    "AUDIO": {
        "name": "Audio",
        "description": "Audio processing tools for DJs and producers",
        "icon": "🎵",
        "folder_path": "I:\\Audio",
        "scripts": {
            "backup_musicbee": {
                "name": "Backup MusicBee to OneDrive",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Audio_MusicBeeBackup.py"),
                "description": "Backup MusicBee library to OneDrive, only transferring changed or new files",
                "icon": "💾"
            }
        },
        "subcategories": {
            "DJ": {
                "name": "DJ Tools",
                "icon": "🎧",
                "scripts": {
                    "sync_playlists": {
                        "name": "Sync iTunes Playlists to DJ Library",
                        "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Audio_TraktorSyncPlaylists.py"),
                        "description": "Synchronize iTunes playlists to Traktor DJ library with WAV conversion",
                        "icon": "🔄"
                    }
                }
            },
            "PROD": {
                "name": "Production Tools",
                "icon": "🎛️",
                "scripts": {
                    "folder_structure": {
                        "name": "New Audio Production Project",
                        "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Audio_FolderStructure.py"),
                        "description": "Create folder structure for audio production projects",
                        "icon": "📁"
                    }
                }
            }
        }
    },
    "PHOTO": {
        "name": "Photo",
        "description": "Photography workflow automation",
        "icon": "📷",
        "folder_path": "I:\\Photo",
        "scripts": {
            "folder_structure": {
                "name": "New Photo Project",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Photo_FolderStructure.py"),
                "description": "Create folder structure for photography projects",
                "icon": "📁"
            },
            "new_collection": {
                "name": "New Photo Collection",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Photo_NewCollection.py"),
                "description": "Create a photo collection folder in E:/_photo with date, location, and activity",
                "icon": "📸"
            }
        },
        "subcategories": {}
    },
    "VISUAL": {
        "name": "Visual",
        "description": "Visual effects and animation tools",
        "icon": "🎨",
        "folder_path": "I:\\Visual",
        "scripts": {
            "add_txt_to_metadata": {
                "name": "Add Text to Image Metadata",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Visual_AddTxtToMetadata.py"),
                "description": "Add text from matching .txt files to JPEG image metadata",
                "icon": "🏷"
            }
        },
        "subcategories": {
            "CG": {
                "name": "Computer Graphics",
                "icon": "🎬",
                "scripts": {
                    "folder_structure": {
                        "name": "New VFX Project",
                        "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Visual_FolderStructure_VFX.py"),
                        "description": "Create folder structure for VFX/3D projects",
                        "icon": "📁"
                    }
                }
            },
            "GD": {
                "name": "Graphic Design",
                "icon": "🖼️",
                "scripts": {
                    "folder_structure": {
                        "name": "New Graphic Design Project",
                        "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Visual_FolderStructure_GD.py"),
                        "description": "Create folder structure for graphic design projects",
                        "icon": "📁"
                    }
                }
            },
            "VJ": {
                "name": "VJ Tools",
                "icon": "💫",
                "scripts": {}
            }
        }
    },
    "WEB": {
        "name": "Web",
        "description": "Web development and publishing tools",
        "icon": "🌐",
        "folder_path": "I:\\Web",
        "scripts": {
            "backup_laragon": {
                "name": "Backup Laragon",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Web_BackupLaragon.py"),
                "description": "Create a timestamped backup of Laragon installation",
                "icon": "💾"
            },
            "folder_structure": {
                "name": "New Webdev Project",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Web_FolderStructure.py"),
                "description": "Create folder structure for web projects",
                "icon": "📁"
            }
        },
        "subcategories": {}
    },
    "PHYSICAL": {
        "name": "Physical",
        "description": "Physical workflow automation",
        "icon": "🔧",
        "folder_path": "I:\\Physical",
        "scripts": {},
        "subcategories": {
            "3DPRINTING": {
                "name": "3D Printing",
                "icon": "🖨️",
                "scripts": {
                    "folder_structure": {
                        "name": "New 3D Printing Project",
                        "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Physical_FolderStructure.py"),
                        "description": "Create folder structure for 3D printing projects",
                        "icon": "📁"
                    },
                    "woocommerce_monitor": {
                        "name": "WooCommerce Order Monitor",
                        "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Physical_WooCommerceOrderMonitor.py"),
                        "description": "Automatically monitor WooCommerce orders and organize folders with invoices, labels, and details",
                        "icon": "📦"
                    }
                }
            }
        }
    },
    "REALTIME": {
        "name": "Real Time",
        "description": "Real-time processing and performance tools",
        "icon": "⚡",
        "folder_path": "I:\\Real Time",
        "scripts": {},
        "subcategories": {}
    }
}

BUSINESS_CATEGORIES = {
    "BUSINESS": {
        "name": "Business",
        "description": "Business and financial management tools",
        "icon": "💼",
        "folder_path": "I:\\_LIBRARY",
        "scripts": {
            "bookkeeping_structure": {
                "name": "Create Bookkeeping Folder Structure",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Bookkeeping_FolderStructure.py"),
                "description": "Create folder structure for bookkeeping and financial records",
                "icon": "📋"
            },
            "invoice_renamer": {
                "name": "Invoice Renamer",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Bookkeeping_InvoiceRenamer.py"),
                "description": "Automatically rename invoices to standardized format: FAC_YY-MM-DD_CompanyName",
                "icon": "📄"
            }
        },
        "subcategories": {}
    },
    "GLOBAL": {
        "name": "Global Tools",
        "description": "General-purpose utilities",
        "icon": "🛠️",
        # No folder_path for Global Tools as requested
        "scripts": {
            "global_cleanup": {
                "name": "Global Cleanup",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Global_Cleanup.py"),
                "description": "Clean up temporary files and folders",
                "icon": "🧹"
            }
        },
        "subcategories": {}
    }
}

# Combine all categories
PIPELINE_CATEGORIES = {**CREATIVE_CATEGORIES, **BUSINESS_CATEGORIES}

# Default configuration path
DEFAULT_CONFIG_PATH = os.path.join(os.path.expanduser("~"), "AppData", "Local", "PipelineManager", "config.json")

# ====================================
# LOGGING AND CONFIG (Simplified)
# ====================================

def setup_logging():
    """Configure and set up logging for the application."""
    log_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "PipelineManager", "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"pipeline_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger("PipelineManager")

logger = setup_logging()

class ConfigManager:
    """Manages configuration settings for the pipeline manager."""
    
    def __init__(self, config_path=DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from file or create default if not exists."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                return self._create_default_config()
        else:
            return self._create_default_config()
    
    def _create_default_config(self):
        """Create default configuration."""
        config = {
            "version": APP_VERSION,
            "last_main_tab": "creative",
            "last_category": "AUDIO",
            "scripts": {}
        }
        
        self._save_config(config)
        return config
    
    def _save_config(self, config=None):
        """Save configuration to file."""
        if config is None:
            config = self.config
            
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False
    
    def get_script_config(self, category_key, script_key):
        """Get configuration for a specific script."""
        script_id = f"{category_key}_{script_key}"
        if script_id not in self.config.get("scripts", {}):
            self.config.setdefault("scripts", {})[script_id] = {
                "args": [],
                "env_vars": {},
                "last_run": None
            }
            self._save_config()
        return self.config["scripts"][script_id]
    
    def update_script_config(self, category_key, script_key, new_config):
        """Update configuration for a specific script."""
        script_id = f"{category_key}_{script_key}"
        self.config.setdefault("scripts", {})[script_id] = new_config
        return self._save_config()

class ScriptRunner:
    """Handles running external scripts."""
    
    @staticmethod
    def run_script(script_path, args=None, env_vars=None, callback=None):
        """Run a Python script as a subprocess."""
        if not os.path.exists(script_path):
            error_msg = f"Script not found: {script_path}"
            logger.error(error_msg)
            if callback:
                callback(error_msg, "error")
            return False
        
        cmd = [sys.executable, script_path] + (args or [])
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)
        
        logger.info(f"Running script: {' '.join(cmd)}")
        if callback:
            callback(f"Running: {os.path.basename(script_path)}", "info")
        
        try:
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            def monitor_output():
                for line in iter(process.stdout.readline, ''):
                    if line.strip():
                        logger.info(line.strip())
                        if callback:
                            callback(line.strip(), "info")
                
                # Filter out Python warnings from stderr
                warning_indicators = ['Warning:', 'SyntaxWarning', 'DeprecationWarning', 'FutureWarning', 'UserWarning']
                warning_context_lines = 0  # Track lines after a warning (usually code context)
                
                for line in iter(process.stderr.readline, ''):
                    if line.strip():
                        stripped_line = line.strip()
                        
                        # Check if this line contains a Python warning
                        is_warning_line = any(indicator in stripped_line for indicator in warning_indicators)
                        
                        if is_warning_line:
                            # This is a warning - skip it and the next 2 lines (usually file path + code)
                            warning_context_lines = 2
                            continue
                        
                        if warning_context_lines > 0:
                            # Skip context lines after a warning
                            warning_context_lines -= 1
                            continue
                        
                        # This is a real error - show it
                        logger.error(stripped_line)
                        if callback:
                            callback(stripped_line, "error")
                
                exit_code = process.wait()
                
                if exit_code == 0:
                    success_msg = f"✓ Completed: {os.path.basename(script_path)}"
                    logger.info(success_msg)
                    if callback:
                        callback(success_msg, "success")
                else:
                    error_msg = f"✗ Failed (exit code {exit_code}): {os.path.basename(script_path)}"
                    logger.error(error_msg)
                    if callback:
                        callback(error_msg, "error")
            
            threading.Thread(target=monitor_output, daemon=True).start()
            return True
            
        except Exception as e:
            error_msg = f"Error running script: {e}"
            logger.error(error_msg)
            if callback:
                callback(error_msg, "error")
            return False

# ====================================
# CUSTOM WIDGETS
# ====================================


class ScrollableFrame(tk.Frame):
    """A scrollable frame widget with smooth mouse wheel scrolling."""
    
    def __init__(self, parent, bg=None):
        super().__init__(parent, bg=bg)
        
        # Create canvas and scrollbar
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=bg)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Bind canvas resize to frame width
        self.canvas.bind('<Configure>', self._configure_canvas_window)
        
        # Bind mouse wheel directly to canvas (simpler approach)
        self._bind_mouse_wheel()
        
        # Pack widgets
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
    
    def _configure_canvas_window(self, event):
        """Update the canvas window to match canvas width."""
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)
    
    def _bind_mouse_wheel(self):
        """Bind mouse wheel events directly to canvas."""
        # Windows and MacOS - bind directly to canvas
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        # Linux
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)
        
        # Also bind to all children recursively
        self._bind_to_mousewheel(self.scrollable_frame)
    
    def _bind_to_mousewheel(self, widget):
        """Recursively bind mousewheel to widget and all its children."""
        # Bind to the widget
        widget.bind("<MouseWheel>", self._on_mouse_wheel, add="+")
        widget.bind("<Button-4>", self._on_mouse_wheel, add="+")
        widget.bind("<Button-5>", self._on_mouse_wheel, add="+")
        
        # Bind to all children
        for child in widget.winfo_children():
            self._bind_to_mousewheel(child)
    
    def rebind_mousewheel(self):
        """Rebind mousewheel to all widgets after content has been added."""
        # Rebind to the scrollable frame and all its children
        self._bind_to_mousewheel(self.scrollable_frame)
    
    def _on_mouse_wheel(self, event):
        """Handle mouse wheel scrolling."""
        # Check if there's actually content to scroll
        try:
            bbox = self.canvas.bbox("all")
            if bbox is None:
                return "break"
            
            # Get the current view
            view_height = self.canvas.winfo_height()
            content_height = bbox[3] - bbox[1]
            
            # Only scroll if content is larger than view
            if content_height <= view_height:
                return "break"
            
            # Determine scroll direction and amount
            if event.num == 4 or event.delta > 0:
                # Scroll up
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5 or event.delta < 0:
                # Scroll down
                self.canvas.yview_scroll(1, "units")
            
            return "break"  # Prevent event from propagating
        except:
            return "break"
    
    def get_frame(self):
        """Get the scrollable frame."""
        return self.scrollable_frame

# ====================================
# PROFESSIONAL GUI IMPLEMENTATION
# ====================================

class ProfessionalPipelineGUI:
    """Professional GUI for the Pipeline Manager."""
    
    def __init__(self, root):
        """Initialize the Pipeline Manager GUI."""
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        
        # Open in fullscreen
        self.root.state('zoomed')  # Windows
        # For Linux/Mac, use: self.root.attributes('-zoomed', True)
        
        # Set minimum size
        self.root.minsize(1200, 800)
        
        # Configure root window background
        self.root.configure(bg=COLORS["bg_primary"])
        
        # Load configuration
        self.config_manager = ConfigManager()
        
        # Setup custom styles
        self.setup_styles()
        
        # Create main layout
        self.create_layout()
        
        # Initialize with last used tab
        self.current_categories = CREATIVE_CATEGORIES
        self.select_main_tab(self.config_manager.config.get("last_main_tab", "creative"))
    
    def setup_styles(self):
        """Setup custom ttk styles for professional look."""
        style = ttk.Style()
        
        # Force a specific theme to avoid system overrides
        try:
            style.theme_use('clam')  # or 'alt', 'default', 'classic'
        except:
            pass  # If theme doesn't exist, continue with default
    
        
        # Configure notebook style with better contrast
        style.configure("Main.TNotebook", 
                       background=COLORS["bg_primary"],
                       borderwidth=0,
                       tabmargins=[2, 5, 2, 0])
        
        # Base tab styling (for unselected tabs - smaller)
        style.configure("Main.TNotebook.Tab", 
                       background=COLORS["bg_secondary"],
                       foreground=COLORS["text_secondary"],
                       padding=[15, 8],  # Smaller padding for unselected tabs
                       borderwidth=0,
                       focuscolor="none",
                       font=('Segoe UI', 10, 'normal'))
        
        # Dynamic styling with different padding for selected vs unselected
        style.map("Main.TNotebook.Tab",
                 background=[('selected', COLORS["tab_active_bg"]), 
                            ('!selected', COLORS["bg_secondary"]),
                            ('active', COLORS["bg_hover"])],
                 foreground=[('selected', COLORS["tab_active_fg"]), 
                            ('!selected', COLORS["text_secondary"])],
                 padding=[('selected', [22, 12]),  # Bigger padding when selected
                         ('!selected', [15, 8])],  # Smaller padding when not selected
                 expand=[("selected", [1, 1, 1, 0])])
        
        # Fix the selected tab text visibility with better styling
        style.map("Main.TNotebook.Tab",
                 background=[('selected', COLORS["tab_active_bg"]), 
                            ('!selected', COLORS["bg_secondary"]),
                            ('active', COLORS["bg_hover"])],  # Added hover state
                 foreground=[('selected', COLORS["tab_active_fg"]), 
                            ('!selected', COLORS["text_secondary"])],
                 expand=[("selected", [1, 1, 1, 0])])
        
        # Configure scrollbar style
        style.configure("Vertical.TScrollbar",
                       background=COLORS["bg_secondary"],
                       bordercolor=COLORS["bg_secondary"],
                       arrowcolor=COLORS["text_secondary"],
                       troughcolor=COLORS["bg_primary"])
        
        style.map("Vertical.TScrollbar",
                 background=[("active", COLORS["bg_hover"])])

    def create_layout(self):
        """Create the main layout."""
        # Main container
        self.main_container = tk.Frame(self.root, bg=COLORS["bg_primary"])
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Create header
        self.create_header()
        
        # Create main notebook
        self.create_main_notebook()
        
        # Create status bar
        self.create_status_bar()

    def load_logo(self, path, size=(80, 50)):
        """Load an image file and resize it for the logo."""
        try:
            from PIL import Image, ImageTk
            image = Image.open(path)
            
            # Calculate dimensions to maintain aspect ratio
            orig_width, orig_height = image.size
            aspect_ratio = orig_width / orig_height
            
            if aspect_ratio > 1:  # Width is greater than height
                new_width = size[0]
                new_height = int(size[0] / aspect_ratio)
            else:  # Height is greater than or equal to width
                new_height = size[1]
                new_width = int(size[1] * aspect_ratio)
                
            # Make sure we don't exceed our target box
            new_width = min(new_width, size[0])
            new_height = min(new_height, size[1])
            
            # Resize the image while maintaining aspect ratio
            image = image.resize((new_width, new_height), Image.LANCZOS)
            return ImageTk.PhotoImage(image)
            
        except ImportError:
            print("WARNING: PIL/Pillow library not installed. Unable to load logo image.")
            print("Please install the required library using: pip install pillow")
            return None
        except Exception as e:
            print(f"Error loading logo image: {str(e)}")
            return None
    
    def create_header(self):
        """Create professional header with logo."""
        header_frame = tk.Frame(self.main_container, bg=COLORS["bg_secondary"], height=90)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        # Inner container for content alignment
        inner_header = tk.Frame(header_frame, bg=COLORS["bg_secondary"])
        inner_header.pack(expand=True, fill=tk.BOTH)
        
        # Configure grid for proper layout
        inner_header.grid_columnconfigure(1, weight=1)
        
        # Logo section (left side)
        logo_frame = tk.Frame(inner_header, bg=COLORS["bg_secondary"], width=100)
        logo_frame.grid(row=0, column=0, padx=20, sticky="w")
        logo_frame.grid_propagate(False)
        
        # Try to load the logo
        try:
            self.logo_image = self.load_logo(LOGO_PATH, size=(80, 50))
            if self.logo_image:
                logo_label = tk.Label(logo_frame, 
                                    image=self.logo_image, 
                                    bg=COLORS["bg_secondary"])
                logo_label.pack(pady=20)
            else:
                # Fallback to text logo
                logo_label = tk.Label(logo_frame,
                                    text="FD",
                                    font=font.Font(family="Segoe UI", size=20, weight="bold"),
                                    fg=COLORS["accent"],
                                    bg=COLORS["bg_secondary"])
                logo_label.pack(pady=20)
        except Exception as e:
            # Fallback to text logo
            logo_label = tk.Label(logo_frame,
                                text="FD",
                                font=font.Font(family="Segoe UI", size=20, weight="bold"),
                                fg=COLORS["accent"],
                                bg=COLORS["bg_secondary"])
            logo_label.pack(pady=20)
        
        # Title section (center-left)
        title_container = tk.Frame(inner_header, bg=COLORS["bg_secondary"])
        title_container.grid(row=0, column=1, sticky="w", padx=20)
        
        # Main title
        title_font = font.Font(family="Segoe UI", size=26, weight="bold")
        title_label = tk.Label(title_container,
                              text="PIPELINE MANAGER",
                              font=title_font,
                              fg=COLORS["text_primary"],
                              bg=COLORS["bg_secondary"])
        title_label.pack(anchor="w", pady=(20, 0))
        
    
    def create_main_notebook(self):
        """Create the main notebook with Creative and Business tabs."""
        # Notebook container with padding
        notebook_container = tk.Frame(self.main_container, bg=COLORS["bg_primary"])
        notebook_container.pack(fill=tk.BOTH, expand=True, padx=30, pady=(15, 10))
        
        # Try using theme to fix tab colors
        style = ttk.Style()
        
        
        style.configure("Main.TNotebook.Tab",
                       background=COLORS["bg_secondary"],
                       foreground=COLORS["text_secondary"],
                       padding=[30, 15],
                       borderwidth=2,
                       relief="flat")
        
        # Force selected tab to be dark blue with white text
        style.map("Main.TNotebook.Tab",
                 background=[('selected', '#1f6feb'), ('!selected', COLORS["bg_secondary"])],
                 foreground=[('selected', '#ffffff'), ('!selected', COLORS["text_secondary"])],
                 relief=[('selected', 'flat'), ('!selected', 'flat')],
                 borderwidth=[('selected', 0), ('!selected', 0)])
        
        self.main_notebook = ttk.Notebook(notebook_container, style="Main.TNotebook")
        self.main_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Creative Activities Tab
        self.creative_frame = tk.Frame(self.main_notebook, bg=COLORS["bg_primary"])
        self.main_notebook.add(self.creative_frame, text="Creative Activities")
        
        # Business & Utilities Tab
        self.business_frame = tk.Frame(self.main_notebook, bg=COLORS["bg_primary"])
        self.main_notebook.add(self.business_frame, text="Business & Utilities")
        
        # Setup content for each tab
        self.setup_grid_layout(self.creative_frame, CREATIVE_CATEGORIES)
        self.setup_grid_layout(self.business_frame, BUSINESS_CATEGORIES)
        
        # Bind tab change event
        self.main_notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
    
    def setup_grid_layout(self, parent_frame, categories):
        """Setup grid layout for categories."""
        # Create scrollable frame
        scroll_frame = ScrollableFrame(parent_frame, bg=COLORS["bg_primary"])
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Get the actual frame to add content to
        content_frame = scroll_frame.get_frame()
        
        # Create grid of category cards
        columns = 3  # Number of columns in grid
        for i, (category_key, category_data) in enumerate(categories.items()):
            row = i // columns
            col = i % columns
            
            # Create category card
            card = self.create_category_card(content_frame, category_key, category_data)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            # Configure grid weights for proper expansion
            content_frame.grid_columnconfigure(col, weight=1)
        
        # IMPORTANT: Rebind mousewheel after all widgets are added
        scroll_frame.rebind_mousewheel()
    
    def open_folder(self, folder_path):
        """Open a folder in Windows File Explorer."""
        try:
            if os.path.exists(folder_path):
                os.startfile(folder_path)
                self.update_status(f"Opened folder: {folder_path}", "info")
            else:
                self.update_status(f"Folder not found: {folder_path}", "warning")
        except Exception as e:
            self.update_status(f"Error opening folder: {e}", "error")
    
    def create_category_card(self, parent, category_key, category_data):
        """Create a professional category card."""
        # Main card frame with border
        card_frame = tk.Frame(parent, bg=COLORS["bg_card"], relief=tk.FLAT, bd=0)
        card_frame.configure(highlightbackground=COLORS["border"], highlightthickness=1)
        
        # Card header with category color
        header_color = CATEGORY_COLORS.get(category_key, COLORS["accent"])
        header_frame = tk.Frame(card_frame, bg=header_color)
        header_frame.pack(fill=tk.X)
        
        # Make header clickable if folder_path exists (excluding Global Tools)
        folder_path = category_data.get('folder_path')
        if folder_path:
            header_frame.configure(cursor="hand2")
            
            # Hover effects for clickable header
            def on_header_enter(e):
                # Slightly lighten the header color on hover
                lighter_color = self._lighten_color(header_color)
                header_frame.configure(bg=lighter_color)
                header_content.configure(bg=lighter_color)
                text_container.configure(bg=lighter_color)
                icon_label.configure(bg=lighter_color)
                name_label.configure(bg=lighter_color)
                desc_label.configure(bg=lighter_color)
            
            def on_header_leave(e):
                # Return to original color
                header_frame.configure(bg=header_color)
                header_content.configure(bg=header_color)
                text_container.configure(bg=header_color)
                icon_label.configure(bg=header_color)
                name_label.configure(bg=header_color)
                desc_label.configure(bg=header_color)
            
            def on_header_click(e):
                self.open_folder(folder_path)
            
            header_frame.bind("<Enter>", on_header_enter)
            header_frame.bind("<Leave>", on_header_leave)
            header_frame.bind("<Button-1>", on_header_click)
        
        # Category icon and name/description side by side, aligned to the left
        header_content = tk.Frame(header_frame, bg=header_color)
        header_content.pack(anchor="w", padx=15, pady=15)  # Align to left
        
        # If clickable, bind events to header_content too
        if folder_path:
            header_content.configure(cursor="hand2")
            header_content.bind("<Enter>", lambda e: on_header_enter(e))
            header_content.bind("<Leave>", lambda e: on_header_leave(e))
            header_content.bind("<Button-1>", lambda e: on_header_click(e))
        
        # Icon on the left
        icon_font = font.Font(family="Segoe UI Emoji", size=20)
        icon_label = tk.Label(header_content,
                             text=category_data.get('icon', ''),
                             font=icon_font,
                             fg="#ffffff",
                             bg=header_color)
        icon_label.pack(side=tk.LEFT, anchor="n")  # Anchor to top
        
        # If clickable, bind events to icon too
        if folder_path:
            icon_label.configure(cursor="hand2")
            icon_label.bind("<Enter>", lambda e: on_header_enter(e))
            icon_label.bind("<Leave>", lambda e: on_header_leave(e))
            icon_label.bind("<Button-1>", lambda e: on_header_click(e))
        
        # Text container for name and description next to icon
        text_container = tk.Frame(header_content, bg=header_color)
        text_container.pack(side=tk.LEFT, padx=(5, 0), fill=tk.X, expand=True)
        
        # If clickable, bind events to text container too
        if folder_path:
            text_container.configure(cursor="hand2")
            text_container.bind("<Enter>", lambda e: on_header_enter(e))
            text_container.bind("<Leave>", lambda e: on_header_leave(e))
            text_container.bind("<Button-1>", lambda e: on_header_click(e))
        
        # Name on top in the text container
        name_font = font.Font(family="Segoe UI", size=13, weight="bold")
        name_label = tk.Label(text_container,
                             text=category_data['name'],
                             font=name_font,
                             fg="#ffffff",
                             bg=header_color,
                             anchor="w")
        name_label.pack(anchor="w", fill=tk.X)
        
        # If clickable, bind events to name label too
        if folder_path:
            name_label.configure(cursor="hand2")
            name_label.bind("<Enter>", lambda e: on_header_enter(e))
            name_label.bind("<Leave>", lambda e: on_header_leave(e))
            name_label.bind("<Button-1>", lambda e: on_header_click(e))
        
        # Description underneath the name in the same text container
        desc_font = font.Font(family="Segoe UI", size=9)
        desc_label = tk.Label(text_container,
                             text=category_data["description"],
                             font=desc_font,
                             fg="#ffffff",
                             bg=header_color,
                             justify=tk.LEFT,
                             anchor="w",
                             wraplength=280)
        desc_label.pack(anchor="w", fill=tk.X, pady=(2, 0))
        
        # If clickable, bind events to description label too
        if folder_path:
            desc_label.configure(cursor="hand2")
            desc_label.bind("<Enter>", lambda e: on_header_enter(e))
            desc_label.bind("<Leave>", lambda e: on_header_leave(e))
            desc_label.bind("<Button-1>", lambda e: on_header_click(e))
        
        # Card body with scrollable content
        body_frame = tk.Frame(card_frame, bg=COLORS["bg_card"])
        body_frame.pack(fill=tk.BOTH, expand=True)
        
        # Collect and organize all scripts
        all_scripts = []
        
        # Direct scripts from category
        scripts = category_data.get("scripts", {})
        for script_key, script_data in scripts.items():
            all_scripts.append({
                'key': script_key,
                'data': script_data,
                'category_key': category_key,
                'subcat_key': None,
                'priority': self._get_script_priority(script_key, script_data['name'])
            })
        
        # Scripts from subcategories
        subcategories = category_data.get("subcategories", {})
        for subcat_key, subcat_data in subcategories.items():
            subcat_scripts = subcat_data.get("scripts", {})
            for script_key, script_data in subcat_scripts.items():
                all_scripts.append({
                    'key': script_key,
                    'data': script_data,
                    'category_key': category_key,
                    'subcat_key': subcat_key,
                    'subcat_name': subcat_data.get('name', ''),
                    'subcat_icon': subcat_data.get('icon', ''),
                    'priority': self._get_script_priority(script_key, script_data['name'])
                })
        
        # Sort by priority (folder structure first, then backup, then others)
        all_scripts.sort(key=lambda x: x['priority'])
        
        # Group scripts by type for display
        folder_scripts = [s for s in all_scripts if s['priority'] == 1]
        backup_scripts = [s for s in all_scripts if s['priority'] == 2]
        other_scripts = [s for s in all_scripts if s['priority'] == 3]
        
        # Add folder structure scripts
        if folder_scripts:
            for script in folder_scripts:
                self.create_full_width_script_button(body_frame, script)
        
        # Add backup scripts
        if backup_scripts:
            for script in backup_scripts:
                self.create_full_width_script_button(body_frame, script)
        
        # Add other scripts (subcategory headers removed for cleaner UI)
        for script in other_scripts:
            self.create_full_width_script_button(body_frame, script)
        
        # If no scripts available
        if not all_scripts:
            no_scripts_font = font.Font(family="Segoe UI", size=9, slant="italic")
            no_scripts_label = tk.Label(body_frame,
                                       text="No scripts available yet",
                                       font=no_scripts_font,
                                       fg=COLORS["text_secondary"],
                                       bg=COLORS["bg_card"])
            no_scripts_label.pack(pady=20)
        
        return card_frame
    
    def _lighten_color(self, hex_color, factor=0.2):
        """Lighten a hex color by a given factor (0.0 to 1.0)."""
        try:
            # Remove the # if present
            hex_color = hex_color.lstrip('#')
            
            # Convert to RGB
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            
            # Lighten each component
            rgb_lightened = tuple(min(255, int(c + (255 - c) * factor)) for c in rgb)
            
            # Convert back to hex
            return '#{:02x}{:02x}{:02x}'.format(*rgb_lightened)
        except:
            # Return original color if conversion fails
            return hex_color
    
    def _get_script_priority(self, script_key, script_name):
        """Get priority for script ordering (1=highest priority)."""
        # Check both script key and name for folder structure
        if 'folder_structure' in script_key.lower() or 'folder structure' in script_name.lower():
            return 1
        # Check for backup scripts
        elif 'backup' in script_key.lower() or 'backup' in script_name.lower():
            return 2
        else:
            return 3
    
    def add_subcategory_header(self, parent, icon, name):
        """Add a subcategory header."""
        # Section title
        title_frame = tk.Frame(parent, bg=COLORS["bg_card"])
        title_frame.pack(fill=tk.X, padx=15, pady=(10, 2))
        
        title_font = font.Font(family="Segoe UI", size=10, weight="bold")
        title_label = tk.Label(title_frame,
                              text=f"{icon} {name}",
                              font=title_font,
                              fg=COLORS["accent"],
                              bg=COLORS["bg_card"])
        title_label.pack(anchor=tk.W)
    
    def create_full_width_script_button(self, parent, script):
        """Create a full-width script button with name and description."""
        script_data = script['data']
        
        # Button frame that spans full width
        button_frame = tk.Frame(parent, bg=COLORS["bg_secondary"], cursor="hand2")
        button_frame.pack(fill=tk.X, pady=2, padx=15)
        
        # Inner content frame for proper text alignment
        content_frame = tk.Frame(button_frame, bg=COLORS["bg_secondary"])
        content_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)
        
        # Add hover effect
        def on_enter(e):
            button_frame.configure(bg=COLORS["bg_hover"])
            content_frame.configure(bg=COLORS["bg_hover"])
            name_label.configure(bg=COLORS["bg_hover"])
            desc_label.configure(bg=COLORS["bg_hover"])
        
        def on_leave(e):
            button_frame.configure(bg=COLORS["bg_secondary"])
            content_frame.configure(bg=COLORS["bg_secondary"])
            name_label.configure(bg=COLORS["bg_secondary"])
            desc_label.configure(bg=COLORS["bg_secondary"])
        
        button_frame.bind("<Enter>", on_enter)
        button_frame.bind("<Leave>", on_leave)
        
        # Script name (left aligned, bold)
        name_font = font.Font(family="Segoe UI", size=10, weight="bold")
        name_label = tk.Label(content_frame,
                            text=f"{script_data.get('icon', '▶')} {script_data['name']}",
                            font=name_font,
                            fg=COLORS["text_primary"],
                            bg=COLORS["bg_secondary"],
                            cursor="hand2",
                            anchor="w",
                            justify=tk.LEFT)
        name_label.pack(anchor="w", fill=tk.X)
        
        # Script description (left aligned, smaller, secondary color)
        desc_font = font.Font(family="Segoe UI", size=8)
        desc_label = tk.Label(content_frame,
                            text=script_data.get('description', ''),
                            font=desc_font,
                            fg=COLORS["text_secondary"],
                            bg=COLORS["bg_secondary"],
                            cursor="hand2",
                            anchor="w",
                            justify=tk.LEFT,
                            wraplength=280)
        desc_label.pack(anchor="w", fill=tk.X, pady=(2, 0))
        
        # Make the entire frame clickable
        def run_script_wrapper(e=None):
            self.run_script(script['category_key'], script['key'], script.get('subcat_key'))
        
        button_frame.bind("<Button-1>", run_script_wrapper)
        content_frame.bind("<Button-1>", run_script_wrapper)
        name_label.bind("<Button-1>", run_script_wrapper)
        desc_label.bind("<Button-1>", run_script_wrapper)
        
        # Bind hover events to all elements
        content_frame.bind("<Enter>", on_enter)
        content_frame.bind("<Leave>", on_leave)
        name_label.bind("<Enter>", on_enter)
        name_label.bind("<Leave>", on_leave)
        desc_label.bind("<Enter>", on_enter)
        desc_label.bind("<Leave>", on_leave)
    
    def create_status_bar(self):
        """Create professional status bar."""
        status_container = tk.Frame(self.main_container, bg=COLORS["bg_secondary"])
        status_container.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Collapsible status area
        self.status_expanded = True
        
        # Status header bar
        header_bar = tk.Frame(status_container, bg=COLORS["border"], height=1)
        header_bar.pack(fill=tk.X)
        
        header_frame = tk.Frame(status_container, bg=COLORS["bg_secondary"], height=35)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        # Toggle button
        self.toggle_button = tk.Label(header_frame,
                                     text="▼ Status Log",
                                     font=font.Font(family="Segoe UI", size=10),
                                     fg=COLORS["text_primary"],
                                     bg=COLORS["bg_secondary"],
                                     cursor="hand2")
        self.toggle_button.pack(side=tk.LEFT, padx=30, pady=8)
        self.toggle_button.bind("<Button-1>", self.toggle_status)
        
        # Status text container
        self.status_text_container = tk.Frame(status_container, bg=COLORS["bg_primary"], height=150)
        self.status_text_container.pack(fill=tk.X, padx=30, pady=(0, 10))
        self.status_text_container.pack_propagate(False)
        
        # Status text area
        self.status_text = tk.Text(self.status_text_container, 
                                  bg=COLORS["bg_primary"],
                                  fg=COLORS["text_primary"],
                                  font=font.Font(family="Consolas", size=9),
                                  relief=tk.FLAT,
                                  wrap=tk.WORD,
                                  height=8,
                                  padx=10,
                                  pady=10)
        self.status_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.status_text_container, command=self.status_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.status_text.config(yscrollcommand=scrollbar.set)
        
        # Configure tags
        self.status_text.tag_configure("error", foreground=COLORS["error"])
        self.status_text.tag_configure("warning", foreground=COLORS["warning"])
        self.status_text.tag_configure("success", foreground=COLORS["success"])
        self.status_text.tag_configure("info", foreground=COLORS["text_primary"])
        self.status_text.tag_configure("timestamp", foreground=COLORS["text_secondary"])
        
        # Initial message
        self.update_status("Pipeline Manager ready", "info")
    
    def toggle_status(self, event=None):
        """Toggle status area visibility."""
        if self.status_expanded:
            self.status_text_container.pack_forget()
            self.toggle_button.config(text="▶ Status Log")
            self.status_expanded = False
        else:
            self.status_text_container.pack(fill=tk.X, padx=30, pady=(0, 10))
            self.toggle_button.config(text="▼ Status Log")
            self.status_expanded = True
    
    def update_status(self, message, status_type="info"):
        """Update the status text widget."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        self.status_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.status_text.insert(tk.END, f"{message}\n", status_type)
        self.status_text.see(tk.END)
        
        self.root.update_idletasks()
    
    def on_tab_changed(self, event):
        """Handle main tab change event."""
        selected_index = self.main_notebook.index(self.main_notebook.select())
        if selected_index == 0:
            self.current_categories = CREATIVE_CATEGORIES
            self.config_manager.config["last_main_tab"] = "creative"
        else:
            self.current_categories = BUSINESS_CATEGORIES
            self.config_manager.config["last_main_tab"] = "business"
        self.config_manager._save_config()
    
    def select_main_tab(self, tab_name):
        """Select a main tab by name."""
        if tab_name == "creative":
            self.main_notebook.select(0)
            self.current_categories = CREATIVE_CATEGORIES
        else:
            self.main_notebook.select(1)
            self.current_categories = BUSINESS_CATEGORIES
    
    def run_script(self, category_key, script_key, subcat_key=None):
        """Run a script."""
        # Get script data
        category = PIPELINE_CATEGORIES.get(category_key, {})
        
        if subcat_key:
            script_data = category.get("subcategories", {}).get(subcat_key, {}).get("scripts", {}).get(script_key)
            config_key = f"{subcat_key}_{script_key}"
        else:
            script_data = category.get("scripts", {}).get(script_key)
            config_key = script_key
        
        if not script_data or "path" not in script_data:
            self.update_status(f"Script not found: {script_key}", "error")
            return
        
        script_path = script_data["path"]
        
        # Get script configuration
        script_config = self.config_manager.get_script_config(category_key, config_key)
        
        # Update last run timestamp
        script_config["last_run"] = datetime.datetime.now().isoformat()
        self.config_manager.update_script_config(category_key, config_key, script_config)
        
        # Run the script
        self.update_status(f"Starting: {script_data['name']}", "info")
        
        # Run script in a separate thread
        threading.Thread(
            target=lambda: ScriptRunner.run_script(
                script_path,
                args=script_config.get("args", []),
                env_vars=script_config.get("env_vars", {}),
                callback=self.update_status
            ),
            daemon=True
        ).start()

# ====================================
# MAIN APPLICATION ENTRY POINT
# ====================================

def main():
    """Main application entry point."""
    root = tk.Tk()
    
    # Create main application
    app = ProfessionalPipelineGUI(root)
    
    # Add menu bar
    menu_bar = tk.Menu(root, bg=COLORS["bg_secondary"], fg=COLORS["text_primary"], 
                      activebackground=COLORS["accent"], activeforeground="#ffffff")
    root.config(menu=menu_bar)
    
    # File menu
    file_menu = tk.Menu(menu_bar, tearoff=0, bg=COLORS["bg_secondary"], 
                       fg=COLORS["text_primary"],
                       activebackground=COLORS["accent"], activeforeground="#ffffff")
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=root.quit, accelerator="Alt+F4")
    menu_bar.add_cascade(label="File", menu=file_menu)
    
    # View menu
    view_menu = tk.Menu(menu_bar, tearoff=0, bg=COLORS["bg_secondary"], 
                       fg=COLORS["text_primary"],
                       activebackground=COLORS["accent"], activeforeground="#ffffff")
    view_menu.add_command(label="Toggle Fullscreen", 
                         command=lambda: root.attributes('-fullscreen', not root.attributes('-fullscreen')),
                         accelerator="F11")
    menu_bar.add_cascade(label="View", menu=view_menu)
    
    # Bind F11 to toggle fullscreen
    root.bind('<F11>', lambda e: root.attributes('-fullscreen', not root.attributes('-fullscreen')))
    root.bind('<Escape>', lambda e: root.attributes('-fullscreen', False))
    
    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    main()