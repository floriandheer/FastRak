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
# Order: Visual, RealTime, Audio, Physical, Photo, Web
CREATIVE_CATEGORIES = {
    "VISUAL": {
        "name": "Visual",
        "description": "Visual effects, graphics and animation tools",
        "icon": "🎬",
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
            "GD": {
                "name": "Graphic Design",
                "icon": "🖼️",
                "scripts": {}
            },
            "FX": {
                "name": "Visual Effects",
                "icon": "🎬",
                "scripts": {}
            },
            "VJ": {
                "name": "Live Video",
                "icon": "💫",
                "scripts": {}
            }
        }
    },
    "REALTIME": {
        "name": "RealTime",
        "description": "Real-time processing and performance tools",
        "icon": "⚡",
        "folder_path": "I:\\RealTime",
        "scripts": {},
        "subcategories": {
            "GODOT": {
                "name": "Godot Engine",
                "icon": "🔵",
                "scripts": {}
            },
            "TD": {
                "name": "TouchDesigner",
                "icon": "🟠",
                "scripts": {}
            }
        }
    },
    "AUDIO": {
        "name": "Audio",
        "description": "Audio processing tools for DJs and producers",
        "icon": "🎵",
        "folder_path": "I:\\Audio",
        "scripts": {
            "backup_musicbee": {
                "name": "Backup Music to OneDrive",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Audio_Backup.py"),
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
                        "name": "Sync Playlists to Traktor",
                        "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Audio_TraktorSync.py"),
                        "description": "Synchronize iTunes playlists to Traktor DJ library with WAV conversion",
                        "icon": "🔄"
                    },
                    "poweramp_sync": {
                        "name": "Sync Playlists to PowerAmp",
                        "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Audio_PowerAmpSync.py"),
                        "description": "Export MusicBee playlists to M3U8 format for PowerAmp on Android",
                        "icon": "📱"
                    }
                }
            },
            "PROD": {
                "name": "Production Tools",
                "icon": "🎛️",
                "scripts": {}
            }
        }
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
    "PHOTO": {
        "name": "Photo",
        "description": "Photography workflow automation",
        "icon": "📷",
        "folder_path": "I:\\Photo",
        "scripts": {
            "new_collection": {
                "name": "New Photo Collection",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Photo_NewCollection.py"),
                "description": "Create a photo collection folder in E:/_photo with date, location, and activity",
                "icon": "📸"
            }
        },
        "subcategories": {}
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
            }
        },
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

# Import shared logging utility
sys.path.insert(0, SCRIPTS_DIR)
from shared_logging import get_logger, setup_logging
from rak_settings import RakSettings, get_rak_settings

# Get logger reference (configured in main())
logger = get_logger("pipeline")

# Import Project Tracker for embedded use (from top-level file)
from floriandheer_project_tracker import ProjectTrackerApp

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


class SettingsDialog:
    """Settings dialog for configuring pipeline paths and preferences."""

    def __init__(self, parent, settings: RakSettings):
        """
        Initialize the settings dialog.

        Args:
            parent: Parent window
            settings: RakSettings instance
        """
        self.parent = parent
        self.settings = settings
        self.result = False  # True if saved

        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Rak Settings")
        self.dialog.geometry("750x750")
        self.dialog.minsize(700, 600)
        self.dialog.configure(bg=COLORS["bg_primary"])

        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # Store original values for cancel
        self._original_work_drive = settings.get_work_drive()
        self._original_archive_base = settings.get_archive_base()

        # Build UI
        self._build_ui()

        # Validate on open
        self._validate_paths()

    def _build_ui(self):
        """Build the settings dialog UI."""
        # Header
        header_frame = tk.Frame(self.dialog, bg=COLORS["bg_secondary"], height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        header_label = tk.Label(
            header_frame,
            text="Rak Settings",
            font=font.Font(family="Segoe UI", size=16, weight="bold"),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_secondary"]
        )
        header_label.pack(side=tk.LEFT, padx=20, pady=15)

        # Notebook for tabs
        style = ttk.Style()
        style.configure("Settings.TNotebook", background=COLORS["bg_primary"])
        style.configure("Settings.TNotebook.Tab",
                       background=COLORS["bg_secondary"],
                       foreground=COLORS["text_primary"],
                       padding=[15, 8],
                       width=20)
        style.map("Settings.TNotebook.Tab",
                 background=[("selected", COLORS["accent_dark"])],
                 foreground=[("selected", "#ffffff")],
                 padding=[("selected", [15, 8])])

        self.notebook = ttk.Notebook(self.dialog, style="Settings.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # === PATHS TAB ===
        paths_tab = tk.Frame(self.notebook, bg=COLORS["bg_primary"])
        self.notebook.add(paths_tab, text="Paths")
        self._build_paths_tab(paths_tab)

        # === SOFTWARE TAB ===
        software_tab = tk.Frame(self.notebook, bg=COLORS["bg_primary"])
        self.notebook.add(software_tab, text="Software Defaults")
        self._build_software_tab(software_tab)

        # === BUTTON ROW ===
        self._build_button_row()

    def _build_paths_tab(self, parent):
        """Build the Paths settings tab."""
        content_frame = tk.Frame(parent, bg=COLORS["bg_primary"])
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # === DRIVE CONFIGURATION SECTION ===
        drive_section = tk.LabelFrame(
            content_frame,
            text=" Drive Configuration ",
            font=font.Font(family="Segoe UI", size=11, weight="bold"),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"],
            padx=15,
            pady=10
        )
        drive_section.pack(fill=tk.X, pady=(0, 15))

        # Active Drive row
        work_frame = tk.Frame(drive_section, bg=COLORS["bg_card"])
        work_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            work_frame,
            text="Active Drive:",
            font=font.Font(family="Segoe UI", size=10),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"],
            width=15,
            anchor="w"
        ).pack(side=tk.LEFT)

        self.work_drive_var = tk.StringVar(value=self.settings.get_work_drive())
        work_entry = tk.Entry(
            work_frame,
            textvariable=self.work_drive_var,
            font=font.Font(family="Segoe UI", size=10),
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            width=30
        )
        work_entry.pack(side=tk.LEFT, padx=(0, 10))
        work_entry.bind('<KeyRelease>', lambda e: self._validate_paths())

        self.work_status_label = tk.Label(
            work_frame,
            text="",
            font=font.Font(family="Segoe UI", size=9),
            bg=COLORS["bg_card"],
            width=25,
            anchor="w"
        )
        self.work_status_label.pack(side=tk.LEFT)

        # Help text for work drive
        tk.Label(
            drive_section,
            text="Mapped via VisualSubst to your active projects directory",
            font=font.Font(family="Segoe UI", size=9, slant="italic"),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"]
        ).pack(anchor="w", padx=(15 * 10, 0), pady=(0, 5))

        # Archive Base row
        archive_frame = tk.Frame(drive_section, bg=COLORS["bg_card"])
        archive_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            archive_frame,
            text="Archive Base:",
            font=font.Font(family="Segoe UI", size=10),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"],
            width=15,
            anchor="w"
        ).pack(side=tk.LEFT)

        self.archive_base_var = tk.StringVar(value=self.settings.get_archive_base())
        archive_entry = tk.Entry(
            archive_frame,
            textvariable=self.archive_base_var,
            font=font.Font(family="Segoe UI", size=10),
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            width=30
        )
        archive_entry.pack(side=tk.LEFT, padx=(0, 10))
        archive_entry.bind('<KeyRelease>', lambda e: self._validate_paths())

        browse_btn = tk.Button(
            archive_frame,
            text="Browse",
            command=self._browse_archive,
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
            font=font.Font(family="Segoe UI", size=9),
            relief=tk.FLAT,
            cursor="hand2",
            padx=10
        )
        browse_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.archive_status_label = tk.Label(
            archive_frame,
            text="",
            font=font.Font(family="Segoe UI", size=9),
            bg=COLORS["bg_card"],
            width=20,
            anchor="w"
        )
        self.archive_status_label.pack(side=tk.LEFT)

        # === CATEGORY PATHS SECTION ===
        paths_section = tk.LabelFrame(
            content_frame,
            text=" Category Paths ",
            font=font.Font(family="Segoe UI", size=11, weight="bold"),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"],
            padx=15,
            pady=10
        )
        paths_section.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Header row
        header_row = tk.Frame(paths_section, bg=COLORS["bg_card"])
        header_row.pack(fill=tk.X, pady=(0, 5))

        tk.Label(
            header_row,
            text="Category",
            font=font.Font(family="Segoe UI", size=9, weight="bold"),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"],
            width=12,
            anchor="w"
        ).pack(side=tk.LEFT)

        tk.Label(
            header_row,
            text="Active Path",
            font=font.Font(family="Segoe UI", size=9, weight="bold"),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"],
            width=25,
            anchor="w"
        ).pack(side=tk.LEFT, padx=(10, 0))

        tk.Label(
            header_row,
            text="Archive Path",
            font=font.Font(family="Segoe UI", size=9, weight="bold"),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"],
            width=30,
            anchor="w"
        ).pack(side=tk.LEFT, padx=(10, 0))

        # Separator
        sep = tk.Frame(paths_section, bg=COLORS["border"], height=1)
        sep.pack(fill=tk.X, pady=5)

        # Category rows
        self.category_labels = {}
        for category in self.settings.get_ordered_categories():
            row = tk.Frame(paths_section, bg=COLORS["bg_card"])
            row.pack(fill=tk.X, pady=2)

            # Category name with color indicator
            cat_color = CATEGORY_COLORS.get(category.upper(), COLORS["text_primary"])
            cat_label = tk.Label(
                row,
                text=f"  {category}",
                font=font.Font(family="Segoe UI", size=10),
                fg=cat_color,
                bg=COLORS["bg_card"],
                width=12,
                anchor="w"
            )
            cat_label.pack(side=tk.LEFT)

            # Work path (read-only, computed from drive + subpath)
            work_path = self.settings.get_work_path(category)
            work_label = tk.Label(
                row,
                text=work_path.replace('\\', '/'),
                font=font.Font(family="Consolas", size=9),
                fg=COLORS["text_primary"],
                bg=COLORS["bg_secondary"],
                width=25,
                anchor="w",
                padx=5
            )
            work_label.pack(side=tk.LEFT, padx=(10, 0))

            # Archive path
            archive_path = self.settings.get_archive_path(category)
            archive_label = tk.Label(
                row,
                text=archive_path.replace('\\', '/'),
                font=font.Font(family="Consolas", size=9),
                fg=COLORS["text_primary"],
                bg=COLORS["bg_secondary"],
                width=30,
                anchor="w",
                padx=5
            )
            archive_label.pack(side=tk.LEFT, padx=(10, 0))

            self.category_labels[category] = {
                "work": work_label,
                "archive": archive_label
            }

            # Show subcategories if any
            cat_config = self.settings.get_category_config(category)
            subcats = cat_config.get("subcategories", [])
            if subcats:
                for subcat in subcats:
                    sub_row = tk.Frame(paths_section, bg=COLORS["bg_card"])
                    sub_row.pack(fill=tk.X, pady=1)

                    tk.Label(
                        sub_row,
                        text=f"    {subcat}",
                        font=font.Font(family="Segoe UI", size=9),
                        fg=COLORS["text_secondary"],
                        bg=COLORS["bg_card"],
                        width=12,
                        anchor="w"
                    ).pack(side=tk.LEFT)

                    tk.Label(
                        sub_row,
                        text="(inherits)",
                        font=font.Font(family="Segoe UI", size=9, slant="italic"),
                        fg=COLORS["text_secondary"],
                        bg=COLORS["bg_card"]
                    ).pack(side=tk.LEFT, padx=(10, 0))

    def _build_software_tab(self, parent):
        """Build the Software Defaults settings tab."""
        # Scrollable frame for software settings
        canvas = tk.Canvas(parent, bg=COLORS["bg_primary"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLORS["bg_primary"])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mousewheel scrolling when mouse is over the canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Store software entry widgets for saving
        self.software_entries = {}

        # Get current software defaults (flat dict)
        software_defaults = self.settings.get_software_defaults()

        # Software grouped by section for display (vertical layout)
        software_sections = [
            ("3D", ["houdini", "blender", "freecad", "alibre", "slicer", "printer"]),
            ("2D", ["affinity"]),
            ("FX", ["fusion", "after_effects"]),
            ("RealTime", ["godot", "resolume", "touchdesigner", "python", "platform", "renderer", "resolution"]),
            ("Audio", ["ableton", "reaper", "traktor"]),
        ]

        for section_label, software_list in software_sections:
            section = tk.LabelFrame(
                scrollable_frame,
                text=f" {section_label} ",
                font=font.Font(family="Segoe UI", size=11, weight="bold"),
                fg=COLORS["text_primary"],
                bg=COLORS["bg_card"],
                padx=15,
                pady=10
            )
            section.pack(fill=tk.X, padx=10, pady=(0, 10))

            for software in software_list:
                # Skip if already has an entry (e.g. touchdesigner appears in both)
                if software in self.software_entries:
                    continue

                current_value = software_defaults.get(software, "")
                label_text = software.replace("_", " ").title()

                row = tk.Frame(section, bg=COLORS["bg_card"])
                row.pack(fill=tk.X, pady=2)

                tk.Label(
                    row,
                    text=f"{label_text}:",
                    font=font.Font(family="Segoe UI", size=10),
                    fg=COLORS["text_secondary"],
                    bg=COLORS["bg_card"],
                    width=18,
                    anchor="w"
                ).pack(side=tk.LEFT)

                var = tk.StringVar(value=current_value)
                entry = tk.Entry(
                    row,
                    textvariable=var,
                    font=font.Font(family="Segoe UI", size=10),
                    bg=COLORS["bg_secondary"],
                    fg=COLORS["text_primary"],
                    insertbackground=COLORS["text_primary"],
                    width=20
                )
                entry.pack(side=tk.LEFT)

                self.software_entries[software] = var

    def _build_button_row(self):
        """Build the button row at the bottom of the dialog."""
        button_frame = tk.Frame(self.dialog, bg=COLORS["bg_primary"])
        button_frame.pack(fill=tk.X, padx=20, pady=15)

        # Reset button (left side)
        reset_btn = tk.Button(
            button_frame,
            text="Reset Defaults",
            command=self._reset_defaults,
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
            font=font.Font(family="Segoe UI", size=10),
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        )
        reset_btn.pack(side=tk.LEFT)

        # Cancel button (right side)
        cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel,
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
            font=font.Font(family="Segoe UI", size=10),
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))

        # Save button (right side)
        save_btn = tk.Button(
            button_frame,
            text="Save",
            command=self._save,
            bg=COLORS["accent_dark"],
            fg="#ffffff",
            font=font.Font(family="Segoe UI", size=10, weight="bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=20,
            pady=8
        )
        save_btn.pack(side=tk.RIGHT)

    def _validate_paths(self):
        """Validate current path entries and update status labels."""
        # Validate work drive
        work_drive = self.work_drive_var.get()
        work_valid, work_msg = self.settings.validate_drive(work_drive)

        if work_valid:
            self.work_status_label.config(text=f"OK {work_msg}", fg=COLORS["success"])
        else:
            self.work_status_label.config(text=f"! {work_msg}", fg=COLORS["warning"])

        # Validate archive base
        archive_base = self.archive_base_var.get()
        archive_valid, archive_msg = self.settings.validate_drive(archive_base)

        if archive_valid:
            self.archive_status_label.config(text=f"OK {archive_msg}", fg=COLORS["success"])
        else:
            self.archive_status_label.config(text=f"! {archive_msg}", fg=COLORS["warning"])

        # Update category path labels
        self._update_category_paths()

    def _update_category_paths(self):
        """Update category path labels based on current drive settings."""
        work_drive = self.work_drive_var.get()
        archive_base = self.archive_base_var.get()

        for category, labels in self.category_labels.items():
            cat_config = self.settings.get_category_config(category)
            work_subpath = cat_config.get("work_subpath", category)
            archive_subpath = cat_config.get("archive_subpath", category)

            work_path = f"{work_drive}\\{work_subpath}".replace('\\', '/')
            archive_path = f"{archive_base}\\{archive_subpath}".replace('\\', '/')

            labels["work"].config(text=work_path)
            labels["archive"].config(text=archive_path)

    def _browse_archive(self):
        """Open folder browser for archive base."""
        current = self.archive_base_var.get()
        initial_dir = current if os.path.isdir(current) else None

        folder = filedialog.askdirectory(
            parent=self.dialog,
            title="Select Archive Base Directory",
            initialdir=initial_dir
        )

        if folder:
            # Normalize to Windows path format
            folder = folder.replace('/', '\\')
            self.archive_base_var.set(folder)
            self._validate_paths()

    def _reset_defaults(self):
        """Reset to default values."""
        if messagebox.askyesno(
            "Reset Defaults",
            "Reset all settings to default values?\n\n"
            "This will reset:\n"
            "- Active Drive: I:\n"
            "- Archive Base: D:\\_work\\Archive\n"
            "- All software version defaults",
            parent=self.dialog
        ):
            # Reset paths
            self.work_drive_var.set("I:")
            self.archive_base_var.set("D:\\_work\\Archive")
            self._validate_paths()

            # Reset software defaults in UI
            if hasattr(self, 'software_entries'):
                defaults = self.settings.DEFAULT_CONFIG.get("software_defaults", {})
                for software, var in self.software_entries.items():
                    var.set(defaults.get(software, ""))

    def _save(self):
        """Save settings and close dialog."""
        work_drive = self.work_drive_var.get()
        archive_base = self.archive_base_var.get()

        # Validate before saving
        work_valid, _ = self.settings.validate_drive(work_drive)
        archive_valid, _ = self.settings.validate_drive(archive_base)

        if not work_valid or not archive_valid:
            if not messagebox.askyesno(
                "Invalid Paths",
                "Some paths could not be validated.\n\n"
                "Save anyway? (You can fix this later)",
                parent=self.dialog
            ):
                return

        # Save path config
        self.settings.set_work_drive(work_drive)
        self.settings.set_archive_base(archive_base)

        # Save software defaults
        if hasattr(self, 'software_entries'):
            versions = {software: var.get() for software, var in self.software_entries.items()}
            self.settings.set_software_defaults(**versions)

        self.result = True
        self.dialog.destroy()
        logger.info("Settings saved")

    def _cancel(self):
        """Cancel and close dialog."""
        self.result = False
        self.dialog.destroy()

    def show(self) -> bool:
        """
        Show the dialog and wait for it to close.

        Returns:
            True if settings were saved, False if cancelled
        """
        self.dialog.wait_window()
        return self.result


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
        """Update the canvas window to match canvas width and minimum height."""
        canvas_width = event.width
        canvas_height = event.height
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)

        # Set minimum height so content fills available space when canvas is taller
        content_height = self.scrollable_frame.winfo_reqheight()
        if canvas_height > content_height:
            self.canvas.itemconfig(self.canvas_window, height=canvas_height)
        else:
            # Reset to natural height when content is taller
            self.canvas.itemconfig(self.canvas_window, height=content_height)
    
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

        # Load path configuration
        self.settings = get_rak_settings()

        # Keyboard navigation state
        self.focused_panel = "categories"  # "categories", "operations", "tools", "tracker"
        self.last_left_panel = "categories"  # Remember last left panel for A key from tracker
        self.panel_before_creation = "categories"  # Remember panel before project creation
        self.category_focus_index = 0      # 0-5 for 2x3 grid
        self.operations_focus_index = 0    # 0-1 for BUSINESS, GLOBAL
        self.tools_focus_index = 0         # Index in current tools+actions list
        self.tool_buttons = []             # References to tool buttons for navigation

        # Layout constants for keyboard navigation
        self.CATEGORY_ORDER = ["VISUAL", "REALTIME", "AUDIO", "PHYSICAL", "PHOTO", "WEB"]
        self.OPERATIONS_ORDER = ["BUSINESS", "GLOBAL"]
        self.SCOPE_ORDER = ["personal", "client", "all"]
        self.STATUS_ORDER = ["active", "archived", "all"]

        # Panel order for WASD navigation (left panel only)
        self.LEFT_PANEL_ORDER = ["categories", "operations", "tools"]

        # Widget references for focus highlighting (set during layout creation)
        self.cat_grid = None
        self.ops_grid = None
        self.action_buttons_frame = None

        # Setup custom styles
        self.setup_styles()

        # Create main layout
        self.create_layout()
    
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

        # Header buttons (right side of header)
        buttons_frame = tk.Frame(inner_header, bg=COLORS["bg_secondary"])
        buttons_frame.grid(row=0, column=2, sticky="e", padx=20)

        # Button style
        btn_font = font.Font(family="Segoe UI", size=10)

        # Refresh button
        refresh_btn = tk.Button(
            buttons_frame,
            text="Refresh",
            command=self.refresh_projects,
            bg=COLORS["bg_hover"],
            fg=COLORS["text_primary"],
            font=btn_font,
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        )
        refresh_btn.pack(side=tk.LEFT, padx=(0, 5), pady=20)
        self._add_header_hint(refresh_btn, "Refresh Projects (F5)")

        # Open Logs button
        logs_btn = tk.Button(
            buttons_frame,
            text="Logs",
            command=self.open_logs_folder,
            bg=COLORS["bg_hover"],
            fg=COLORS["text_primary"],
            font=btn_font,
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        )
        logs_btn.pack(side=tk.LEFT, padx=5, pady=20)
        self._add_header_hint(logs_btn, "Open Logs Folder (Ctrl+L)")

        # Settings button
        settings_btn = tk.Button(
            buttons_frame,
            text="Settings",
            command=self.open_settings,
            bg=COLORS["bg_hover"],
            fg=COLORS["text_primary"],
            font=btn_font,
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        )
        settings_btn.pack(side=tk.LEFT, padx=5, pady=20)
        self._add_header_hint(settings_btn, "Settings (Ctrl+,)")

        # Help button
        help_btn = tk.Button(
            buttons_frame,
            text="Help",
            command=self.open_help,
            bg=COLORS["bg_hover"],
            fg=COLORS["text_primary"],
            font=btn_font,
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        )
        help_btn.pack(side=tk.LEFT, padx=(0, 0), pady=20)
        self._add_header_hint(help_btn, "Keyboard Shortcuts (F1)")

    
    def create_main_notebook(self):
        """Create the main content area (single unified view, no tabs needed)."""
        # Main container with padding
        main_content = tk.Frame(self.main_container, bg=COLORS["bg_primary"])
        main_content.pack(fill=tk.BOTH, expand=True, padx=30, pady=(15, 10))

        # Setup Project Manager with integrated project tracker, tools, and operations
        self.setup_project_manager(main_content)

    def setup_project_manager(self, parent_frame):
        """Setup the unified Project Manager with categories, operations, and tools."""
        # Main container with two columns
        main_container = tk.Frame(parent_frame, bg=COLORS["bg_primary"])
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left panel container (fixed width)
        left_panel_container = tk.Frame(main_container, bg=COLORS["bg_card"], width=280)
        left_panel_container.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15), pady=0)
        left_panel_container.pack_propagate(False)

        # Scrollable left panel (hide scrollbar for cleaner look)
        self.left_scroll = ScrollableFrame(left_panel_container, bg=COLORS["bg_card"])
        self.left_scroll.pack(fill=tk.BOTH, expand=True)
        self.left_scroll.scrollbar.pack_forget()  # Hide scrollbar
        left_panel = self.left_scroll.get_frame()

        # ═══════════════════════════════════════════════════════════
        # CATEGORIES SECTION (includes scope toggles)
        # ═══════════════════════════════════════════════════════════
        self.categories_section = tk.Frame(left_panel, bg=COLORS["bg_card"])
        self.categories_section.pack(fill=tk.X, padx=15, pady=(15, 10))

        # Categories header (clickable to show all)
        cat_header = tk.Label(
            self.categories_section,
            text="CATEGORIES",
            font=font.Font(family="Segoe UI", size=9, weight="bold"),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"],
            cursor="hand2"
        )
        cat_header.pack(anchor="w", pady=(0, 8))
        cat_header.bind("<Button-1>", lambda e: self._clear_category_selection())
        cat_header.bind("<Enter>", lambda e: cat_header.configure(fg=COLORS["accent"]))
        cat_header.bind("<Leave>", lambda e: cat_header.configure(fg=COLORS["text_secondary"]))

        # Scope toggle buttons (inside categories section, matching category grid width)
        scope_frame = tk.Frame(self.categories_section, bg=COLORS["bg_card"])
        scope_frame.pack(fill=tk.X, pady=(0, 10), padx=4)  # Match cat_grid padx

        self.scope_buttons = {}
        self.current_scope = "all"

        scope_options = [
            ("personal", "Personal", "1"),
            ("client", "Work", "2"),
            ("all", "All", "3"),
        ]

        for idx, (value, text, shortcut) in enumerate(scope_options):
            btn = tk.Label(
                scope_frame,
                text=text,
                font=font.Font(family="Segoe UI", size=9),
                fg="white",
                bg=COLORS["bg_secondary"],
                pady=6,
                cursor="hand2"
            )
            # Use grid layout to match category buttons width
            btn.grid(row=0, column=idx, padx=2, sticky="nsew")
            scope_frame.columnconfigure(idx, weight=1)

            def make_scope_click(v):
                def on_click(e):
                    self._set_scope(v)
                return on_click

            def make_scope_enter(v, b, s):
                def on_enter(e):
                    if self.current_scope != v:
                        b.configure(bg="#2d333b")
                    # Show shortcut hint
                    if hasattr(self, 'header_hint_label'):
                        self.header_hint_label.config(text=f"Shortcut: {s}")
                return on_enter

            def make_scope_leave(v, b):
                def on_leave(e):
                    if self.current_scope != v:
                        b.configure(bg=COLORS["bg_secondary"])
                    # Clear shortcut hint
                    if hasattr(self, 'header_hint_label'):
                        self.header_hint_label.config(text="")
                return on_leave

            btn.bind("<Button-1>", make_scope_click(value))
            btn.bind("<Enter>", make_scope_enter(value, btn, shortcut))
            btn.bind("<Leave>", make_scope_leave(value, btn))

            self.scope_buttons[value] = btn

        # Set initial scope button styling
        self._update_scope_button_styles()

        # Category buttons grid (2 columns, 3 rows)
        self.cat_grid = tk.Frame(self.categories_section, bg=COLORS["bg_card"])
        self.cat_grid.pack(fill=tk.X)

        # Store category button references (includes both categories and operations)
        self.category_buttons = {}
        self.selected_category = None

        # Category order and data
        category_order = ["VISUAL", "REALTIME", "AUDIO", "PHYSICAL", "PHOTO", "WEB"]

        for idx, category_key in enumerate(category_order):
            if category_key not in CREATIVE_CATEGORIES:
                continue

            category_data = CREATIVE_CATEGORIES[category_key]
            row = idx // 2
            col = idx % 2

            btn = self._create_category_button(self.cat_grid, category_key, category_data)
            btn.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

        # Configure grid columns to be equal
        self.cat_grid.columnconfigure(0, weight=1)
        self.cat_grid.columnconfigure(1, weight=1)

        # Separator between Categories and Operations
        separator = tk.Frame(left_panel, bg=COLORS["border"], height=1)
        separator.pack(fill=tk.X, padx=15, pady=(10, 10))

        # ═══════════════════════════════════════════════════════════
        # OPERATIONS SECTION
        # ═══════════════════════════════════════════════════════════
        self.operations_section = tk.Frame(left_panel, bg=COLORS["bg_card"])
        self.operations_section.pack(fill=tk.X, padx=15, pady=(0, 10))

        # Operations header
        ops_header = tk.Label(
            self.operations_section,
            text="OPERATIONS",
            font=font.Font(family="Segoe UI", size=9, weight="bold"),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"]
        )
        ops_header.pack(anchor="w", pady=(0, 10))

        # Operations buttons grid (2 columns)
        self.ops_grid = tk.Frame(self.operations_section, bg=COLORS["bg_card"])
        self.ops_grid.pack(fill=tk.X)

        # Operations order and data
        operations_order = ["BUSINESS", "GLOBAL"]

        for idx, ops_key in enumerate(operations_order):
            if ops_key not in BUSINESS_CATEGORIES:
                continue

            ops_data = BUSINESS_CATEGORIES[ops_key]
            row = idx // 2
            col = idx % 2

            btn = self._create_category_button(self.ops_grid, ops_key, ops_data)
            btn.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

        # Configure grid columns to be equal
        self.ops_grid.columnconfigure(0, weight=1)
        self.ops_grid.columnconfigure(1, weight=1)

        # ═══════════════════════════════════════════════════════════
        # SELECTED CATEGORY PANEL (below operations, as separate panel)
        # ═══════════════════════════════════════════════════════════
        # Outer frame with border effect
        self.category_panel_outer = tk.Frame(left_panel, bg=COLORS["border"])

        # Inner panel with padding
        self.category_panel = tk.Frame(self.category_panel_outer, bg=COLORS["bg_secondary"])
        self.category_panel.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Directory & Notes buttons container (at bottom, pack first with side=BOTTOM)
        self.notes_button_container = tk.Frame(self.category_panel, bg=COLORS["bg_secondary"])

        # Create persistent notes button
        self._create_persistent_notes_button()

        # Tools section header
        self.tools_header = tk.Label(
            self.category_panel,
            text="TOOLS",
            font=font.Font(family="Segoe UI", size=9, weight="bold"),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_secondary"]
        )
        self.tools_header.pack(anchor="w", padx=10, pady=(10, 5))

        # Scrollable tools container (takes remaining space)
        self.tools_section = tk.Frame(self.category_panel, bg=COLORS["bg_secondary"])
        self.tools_section.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        # Tools container (no separate scroll - uses left panel scroll)
        self.tools_container = tk.Frame(self.tools_section, bg=COLORS["bg_secondary"])
        self.tools_container.pack(fill=tk.BOTH, expand=True)

        # Rebind mousewheel to left panel after all content is created
        self.left_scroll.rebind_mousewheel()

        # ═══════════════════════════════════════════════════════════
        # RIGHT PANEL: Project Tracker
        # ═══════════════════════════════════════════════════════════
        self.tracker_panel = tk.Frame(main_container, bg=COLORS["bg_primary"])
        self.tracker_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Embed the Project Tracker with status and hint callbacks
        self.project_tracker = ProjectTrackerApp(
            self.tracker_panel,
            embedded=True,
            status_callback=self.update_status,
            hint_callback=self._show_hint,
            creation_start_callback=self._on_creation_start,
            creation_done_callback=self._on_project_creation_done,
            creation_cancel_callback=self._return_to_last_panel
        )

        # Restore state from last session (run once at startup)
        self._restore_session_state()

    def _restore_session_state(self):
        """Restore saved state from last session (category, scope, etc.)."""
        # Sync scope from project tracker's saved settings
        if hasattr(self, 'project_tracker') and hasattr(self.project_tracker, 'filter_scope'):
            saved_scope = self.project_tracker.filter_scope.get()
            self.current_scope = saved_scope
            self._update_scope_button_styles()

        # Restore last selected category from config, or default to None (show all)
        last_category = self.config_manager.config.get("last_selected_category", None)
        if last_category and last_category in PIPELINE_CATEGORIES:
            self._select_category(last_category)
        else:
            # Show all by default (no category selected)
            self._clear_category_selection()

        # Ensure categories panel is focused by default
        self.focused_panel = "categories"
        self.category_focus_index = 0
        self._update_panel_focus()

    def _show_hint(self, text):
        """Show a hint in the status bar header."""
        if hasattr(self, 'header_hint_label'):
            self.header_hint_label.config(text=text)

    def _create_category_button(self, parent, category_key, category_data):
        """Create a square category selection button."""
        color = CATEGORY_COLORS.get(category_key, COLORS["accent"])
        icon = category_data.get("icon", "")
        name = category_data.get("name", category_key)

        # Shortcut mapping for categories
        shortcut_map = {
            "VISUAL": "Shift+V",
            "REALTIME": "Shift+R",
            "AUDIO": "Shift+A",
            "PHYSICAL": "Shift+P",
            "PHOTO": "Shift+H",
            "WEB": "Shift+W",
            "BUSINESS": "Shift+B",
            "GLOBAL": "Shift+G",
        }
        shortcut = shortcut_map.get(category_key, "")

        # Button container (square)
        btn_size = 115
        btn_frame = tk.Frame(
            parent,
            bg=COLORS["bg_secondary"],
            width=btn_size,
            height=btn_size,
            cursor="hand2"
        )
        btn_frame.pack_propagate(False)

        # Content
        content = tk.Frame(btn_frame, bg=COLORS["bg_secondary"])
        content.place(relx=0.5, rely=0.5, anchor="center")

        # Icon
        icon_label = tk.Label(
            content,
            text=icon,
            font=font.Font(family="Segoe UI Emoji", size=24),
            fg=color,
            bg=COLORS["bg_secondary"]
        )
        icon_label.pack()

        # Name
        name_label = tk.Label(
            content,
            text=name,
            font=font.Font(family="Segoe UI", size=10, weight="bold"),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_secondary"]
        )
        name_label.pack(pady=(5, 0))

        # Store references
        self.category_buttons[category_key] = {
            "frame": btn_frame,
            "content": content,
            "icon": icon_label,
            "name": name_label,
            "color": color
        }

        # Hover and click effects
        def on_enter(e):
            if self.selected_category != category_key:
                btn_frame.configure(bg=COLORS["bg_hover"])
                content.configure(bg=COLORS["bg_hover"])
                icon_label.configure(bg=COLORS["bg_hover"], fg=color)
                name_label.configure(bg=COLORS["bg_hover"])
            # Show shortcut hint
            if shortcut and hasattr(self, 'header_hint_label'):
                self.header_hint_label.config(text=f"Shortcut: {shortcut}")

        def on_leave(e):
            if self.selected_category != category_key:
                btn_frame.configure(bg=COLORS["bg_secondary"])
                content.configure(bg=COLORS["bg_secondary"])
                icon_label.configure(bg=COLORS["bg_secondary"], fg=color)
                name_label.configure(bg=COLORS["bg_secondary"])
            # Clear shortcut hint
            if hasattr(self, 'header_hint_label'):
                self.header_hint_label.config(text="")

        def on_click(e):
            self._select_category(category_key)

        for widget in [btn_frame, content, icon_label, name_label]:
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", on_click)

        return btn_frame

    def _select_category(self, category_key):
        """Select a category or operation and show its tools."""
        # Deselect previous
        if self.selected_category and self.selected_category in self.category_buttons:
            prev = self.category_buttons[self.selected_category]
            prev_color = prev["color"]
            prev["frame"].configure(bg=COLORS["bg_secondary"])
            prev["content"].configure(bg=COLORS["bg_secondary"])
            prev["icon"].configure(bg=COLORS["bg_secondary"], fg=prev_color)
            prev["name"].configure(bg=COLORS["bg_secondary"], fg=COLORS["text_primary"])

        # Select new
        self.selected_category = category_key
        if category_key in self.category_buttons:
            curr = self.category_buttons[category_key]
            color = curr["color"]
            curr["frame"].configure(bg=color)
            curr["content"].configure(bg=color)
            curr["icon"].configure(bg=color, fg="#ffffff")
            curr["name"].configure(bg=color, fg="#ffffff")

        # Update tools
        self._update_tools_panel(category_key)

        # Save selected category to config
        self.config_manager.config["last_selected_category"] = category_key
        self.config_manager._save_config()

        # Show/hide project tracker based on category type
        if hasattr(self, 'project_tracker') and self.project_tracker:
            if category_key in CREATIVE_CATEGORIES:
                # Show project tracker and filter by category
                if hasattr(self, 'tracker_panel'):
                    self.tracker_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
                category_name = CREATIVE_CATEGORIES.get(category_key, {}).get("name", category_key)
                # Use the project tracker's category selection method
                if hasattr(self.project_tracker, '_select_category'):
                    self.project_tracker._select_category(category_name)
            else:
                # Hide project tracker for operations (Business/Global)
                if hasattr(self, 'tracker_panel'):
                    self.tracker_panel.pack_forget()

    def _clear_category_selection(self):
        """Clear category selection to show all projects."""
        # Deselect current category button
        if self.selected_category and self.selected_category in self.category_buttons:
            prev = self.category_buttons[self.selected_category]
            prev_color = prev["color"]
            prev["frame"].configure(bg=COLORS["bg_secondary"])
            prev["content"].configure(bg=COLORS["bg_secondary"])
            prev["icon"].configure(bg=COLORS["bg_secondary"], fg=prev_color)
            prev["name"].configure(bg=COLORS["bg_secondary"], fg=COLORS["text_primary"])

        self.selected_category = None

        # Hide the category panel
        if hasattr(self, 'category_panel_outer'):
            self.category_panel_outer.pack_forget()

        # Save to config
        self.config_manager.config["last_selected_category"] = None
        self.config_manager._save_config()

        # Show project tracker and clear filter
        if hasattr(self, 'tracker_panel'):
            self.tracker_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        if hasattr(self, 'project_tracker') and self.project_tracker:
            if hasattr(self.project_tracker, '_clear_category_selection'):
                self.project_tracker._clear_category_selection()

    def _set_scope(self, scope: str):
        """Set the scope filter and update project tracker."""
        self.current_scope = scope
        self._update_scope_button_styles()

        # Update project tracker
        if hasattr(self, 'project_tracker') and self.project_tracker:
            if hasattr(self.project_tracker, 'set_scope'):
                self.project_tracker.set_scope(scope)

        # Update folder path based on new scope (if a category is selected)
        if hasattr(self, '_folder_category') and self._folder_category:
            self._update_notes_button(self._folder_category)

    def _update_scope_button_styles(self):
        """Update scope button visual states based on current selection."""
        if not hasattr(self, 'scope_buttons'):
            return
        for value, btn in self.scope_buttons.items():
            if value == self.current_scope:
                # Selected state - highlighted
                btn.configure(bg=COLORS["accent"], fg="white")
            else:
                # Unselected state
                btn.configure(bg=COLORS["bg_secondary"], fg="white")

    def _update_tools_panel(self, category_key):
        """Update the tools panel to show tools for the selected category or operation."""
        # Reset tool buttons list for keyboard navigation
        self.tool_buttons = []
        self.tools_focus_index = 0

        # Clear current tools from scrollable container
        for widget in self.tools_container.winfo_children():
            widget.destroy()

        if category_key not in PIPELINE_CATEGORIES:
            self.category_panel_outer.pack_forget()
            return

        category_data = PIPELINE_CATEGORIES[category_key]

        # Show the category panel in the left panel (full height)
        self.category_panel_outer.pack(fill=tk.BOTH, expand=True, padx=15, pady=(15, 15))

        # Collect all tools (from category and subcategories)
        all_tools = []

        # Direct category scripts
        scripts = category_data.get("scripts", {})
        for script_key, script_data in scripts.items():
            all_tools.append((script_key, None, script_data))

        # Subcategory scripts
        subcategories = category_data.get("subcategories", {})
        for subcat_key, subcat_data in subcategories.items():
            subcat_scripts = subcat_data.get("scripts", {})
            for script_key, script_data in subcat_scripts.items():
                all_tools.append((script_key, subcat_key, script_data))

        if not all_tools:
            # Show placeholder if no tools
            placeholder = tk.Label(
                self.tools_container,
                text="No tools available\nfor this category",
                font=font.Font(family="Segoe UI", size=10),
                fg=COLORS["text_secondary"],
                bg=COLORS["bg_card"],
                justify="center"
            )
            placeholder.pack(expand=True)
        else:
            # Sort tools by priority (folder structure first, then backup, then others)
            all_tools.sort(key=lambda x: self._get_script_priority(x[0], x[2].get("name", "")))

            # Create tool buttons in scrollable container
            for script_key, subcat_key, script_data in all_tools:
                self._create_tool_button(
                    self.tools_container,
                    category_key,
                    script_key,
                    subcat_key,
                    script_data
                )

        # Update the notes button (hide for GLOBAL since it only has tools)
        if category_key == "GLOBAL":
            self.notes_button_container.pack_forget()
        else:
            # Pack at bottom first, before tools header gets packed
            self.notes_button_container.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=(5, 10))
            self._update_notes_button(category_key)

        # Rebind mousewheel after adding tools
        self.left_scroll.rebind_mousewheel()

    def _create_tool_button(self, parent, category_key, script_key, subcat_key, script_data):
        """Create a professional tool button."""
        color = CATEGORY_COLORS.get(category_key, COLORS["accent"])
        icon = script_data.get("icon", "")
        name = script_data.get("name", script_key)

        # Button frame with left color accent
        btn_frame = tk.Frame(parent, bg=COLORS["bg_secondary"], cursor="hand2")
        btn_frame.pack(fill=tk.X, pady=3)

        # Color accent bar on left
        accent_bar = tk.Frame(btn_frame, bg=color, width=4)
        accent_bar.pack(side=tk.LEFT, fill=tk.Y)

        # Content area
        content = tk.Frame(btn_frame, bg=COLORS["bg_secondary"])
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12, pady=10)

        # Icon
        icon_label = tk.Label(
            content,
            text=icon,
            font=font.Font(family="Segoe UI Emoji", size=14),
            fg=color,
            bg=COLORS["bg_secondary"]
        )
        icon_label.pack(side=tk.LEFT)

        # Name
        name_label = tk.Label(
            content,
            text=name,
            font=font.Font(family="Segoe UI", size=10),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_secondary"],
            anchor="w"
        )
        name_label.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)

        # Arrow indicator
        arrow_label = tk.Label(
            content,
            text=">",
            font=font.Font(family="Segoe UI", size=10),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_secondary"]
        )
        arrow_label.pack(side=tk.RIGHT)

        # Hover effects
        def on_enter(e):
            btn_frame.configure(bg=COLORS["bg_hover"])
            content.configure(bg=COLORS["bg_hover"])
            icon_label.configure(bg=COLORS["bg_hover"])
            name_label.configure(bg=COLORS["bg_hover"])
            arrow_label.configure(bg=COLORS["bg_hover"], fg=color)

        def on_leave(e):
            btn_frame.configure(bg=COLORS["bg_secondary"])
            content.configure(bg=COLORS["bg_secondary"])
            icon_label.configure(bg=COLORS["bg_secondary"])
            name_label.configure(bg=COLORS["bg_secondary"])
            arrow_label.configure(bg=COLORS["bg_secondary"], fg=COLORS["text_secondary"])

        def on_click(e):
            self.run_script(category_key, script_key, subcat_key)

        for widget in [btn_frame, content, icon_label, name_label, arrow_label]:
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", on_click)

        # Store tool button reference for keyboard navigation
        self.tool_buttons.append({
            "frame": btn_frame,
            "content": content,
            "icon_label": icon_label,
            "name_label": name_label,
            "arrow_label": arrow_label,
            "category_key": category_key,
            "script_key": script_key,
            "subcat_key": subcat_key,
            "color": color
        })

    def _create_persistent_notes_button(self):
        """Create persistent Open Directory and Open Notes buttons (called once during setup)."""
        parent = self.notes_button_container

        # Notepad yellow colors (store for hover effects)
        self._notepad_bg = "#FFF9C4"  # Light yellow (notepad color)
        self._notepad_hover = "#E6E0B0"  # Darker yellow for hover (less bright, not more saturated)
        notepad_accent = "#FFD54F"  # Golden accent
        self._notepad_text_color = "#5D4037"  # Brown text for notepad feel

        # Folder button colors (blue theme)
        self._folder_bg = "#E3F2FD"  # Light blue
        self._folder_hover = "#C5D9E8"  # Darker blue for hover (less bright, not more saturated)
        folder_accent = "#2196F3"  # Blue accent
        self._folder_text_color = "#1565C0"  # Dark blue text

        # Store current category for click handler
        self._notes_category = None
        self._folder_path = None
        self._folder_category = None

        # === TOP BUTTON: Open Directory ===
        self._folder_btn_frame = tk.Frame(parent, bg=self._folder_bg, cursor="hand2")
        self._folder_btn_frame.pack(fill=tk.X, pady=(0, 4))

        # Left accent bar (blue)
        folder_accent_bar = tk.Frame(self._folder_btn_frame, bg=folder_accent, width=4)
        folder_accent_bar.pack(side=tk.LEFT, fill=tk.Y)

        # Content area
        self._folder_content = tk.Frame(self._folder_btn_frame, bg=self._folder_bg)
        self._folder_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=8)

        # Folder icon
        self._folder_icon = tk.Label(
            self._folder_content,
            text="📂",
            font=font.Font(family="Segoe UI Emoji", size=12),
            fg=self._folder_text_color,
            bg=self._folder_bg
        )
        self._folder_icon.pack(side=tk.LEFT)

        # Text label
        self._folder_label = tk.Label(
            self._folder_content,
            text="Open Directory",
            font=font.Font(family="Segoe UI", size=9),
            fg=self._folder_text_color,
            bg=self._folder_bg,
            anchor="w"
        )
        self._folder_label.pack(side=tk.LEFT, padx=(6, 0), fill=tk.X, expand=True)

        # Folder button hover effects
        def on_folder_enter(e):
            self._folder_btn_frame.configure(bg=self._folder_hover)
            self._folder_content.configure(bg=self._folder_hover)
            self._folder_icon.configure(bg=self._folder_hover)
            self._folder_label.configure(bg=self._folder_hover)
            # Show shortcut hint in status bar
            if hasattr(self, 'header_hint_label'):
                self.header_hint_label.config(text="Shortcut: G or 0")

        def on_folder_leave(e):
            self._folder_btn_frame.configure(bg=self._folder_bg)
            self._folder_content.configure(bg=self._folder_bg)
            self._folder_icon.configure(bg=self._folder_bg)
            self._folder_label.configure(bg=self._folder_bg)
            # Clear shortcut hint
            if hasattr(self, 'header_hint_label'):
                self.header_hint_label.config(text="")

        def on_folder_click(e):
            if self._folder_category:
                # Check if project tracker is in archive mode
                is_archive_mode = False
                if hasattr(self, 'project_tracker') and self.project_tracker:
                    if hasattr(self.project_tracker, 'filter_status'):
                        is_archive_mode = self.project_tracker.filter_status.get() == "archived"

                if is_archive_mode:
                    # Open archive directory
                    archive_path = self.settings.get_archive_path(self._folder_category)
                    self.open_folder(archive_path)
                elif self._folder_path:
                    # Open active directory
                    self.open_folder(self._folder_path)

        for widget in [self._folder_btn_frame, self._folder_content, self._folder_icon, self._folder_label]:
            widget.bind("<Enter>", on_folder_enter)
            widget.bind("<Leave>", on_folder_leave)
            widget.bind("<Button-1>", on_folder_click)

        # === BOTTOM BUTTON: Open Notes ===
        self._notes_btn_frame = tk.Frame(parent, bg=self._notepad_bg, cursor="hand2")
        self._notes_btn_frame.pack(fill=tk.X, pady=(0, 5))

        # Left accent bar (golden)
        accent_bar = tk.Frame(self._notes_btn_frame, bg=notepad_accent, width=4)
        accent_bar.pack(side=tk.LEFT, fill=tk.Y)

        # Content area
        self._notes_content = tk.Frame(self._notes_btn_frame, bg=self._notepad_bg)
        self._notes_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=8)

        # Notepad icon
        self._notes_icon = tk.Label(
            self._notes_content,
            text="📝",
            font=font.Font(family="Segoe UI Emoji", size=12),
            fg=self._notepad_text_color,
            bg=self._notepad_bg
        )
        self._notes_icon.pack(side=tk.LEFT)

        # Text label (will be updated when category changes)
        self._notes_label = tk.Label(
            self._notes_content,
            text="Open Notes",
            font=font.Font(family="Segoe UI", size=9),
            fg=self._notepad_text_color,
            bg=self._notepad_bg,
            anchor="w"
        )
        self._notes_label.pack(side=tk.LEFT, padx=(6, 0), fill=tk.X, expand=True)

        # Notes button hover effects
        def on_notes_enter(e):
            self._notes_btn_frame.configure(bg=self._notepad_hover)
            self._notes_content.configure(bg=self._notepad_hover)
            self._notes_icon.configure(bg=self._notepad_hover)
            self._notes_label.configure(bg=self._notepad_hover)
            # Show shortcut hint in status bar
            if hasattr(self, 'header_hint_label'):
                self.header_hint_label.config(text="Shortcut: N or .")

        def on_notes_leave(e):
            self._notes_btn_frame.configure(bg=self._notepad_bg)
            self._notes_content.configure(bg=self._notepad_bg)
            self._notes_icon.configure(bg=self._notepad_bg)
            self._notes_label.configure(bg=self._notepad_bg)
            # Clear shortcut hint
            if hasattr(self, 'header_hint_label'):
                self.header_hint_label.config(text="")

        def on_notes_click(e):
            if self._notes_category:
                self.open_note(self._notes_category)

        for widget in [self._notes_btn_frame, self._notes_content, self._notes_icon, self._notes_label]:
            widget.bind("<Enter>", on_notes_enter)
            widget.bind("<Leave>", on_notes_leave)
            widget.bind("<Button-1>", on_notes_click)

    def _update_notes_button(self, category_key):
        """Update the notes and folder buttons for the current category."""
        self._notes_category = category_key
        self._notes_label.configure(text=f"{category_key.title()} Notes")

        # Update folder button based on category's folder_path
        category_data = PIPELINE_CATEGORIES.get(category_key, {})
        folder_path = category_data.get('folder_path')

        if folder_path:
            # Categories that support _Personal subfolder
            categories_with_personal = ["visual", "realtime", "web", "photo"]

            # Adjust path based on current scope
            if hasattr(self, 'current_scope') and self.current_scope == "personal":
                if category_key.lower() in categories_with_personal:
                    folder_path = os.path.join(folder_path, "_Personal")

            self._folder_path = folder_path
            self._folder_category = category_key
            # Show _Personal in label when in personal scope
            if hasattr(self, 'current_scope') and self.current_scope == "personal" and category_key.lower() in categories_with_personal:
                self._folder_label.configure(text=f"{category_key.title()} Personal")
            else:
                self._folder_label.configure(text=f"{category_key.title()} Directory")
            # Re-pack in correct order: folder button first, then notes button
            self._folder_btn_frame.pack(fill=tk.X, pady=(0, 4), before=self._notes_btn_frame)
        else:
            # Hide folder button for categories without folder_path (e.g., Global Tools)
            self._folder_path = None
            self._folder_category = None
            self._folder_btn_frame.pack_forget()

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
            # Special handling for Business category - open current quarter folder
            if folder_path == "I:\\_LIBRARY":
                # Get current year and quarter
                now = datetime.datetime.now()
                current_year = now.year
                current_quarter = (now.month - 1) // 3 + 1

                # Construct the quarterly folder path
                folder_path = f"I:\\_LIBRARY\\Boekhouding\\{current_year}\\Q{current_quarter}"

            if os.path.exists(folder_path):
                os.startfile(folder_path)
                self.update_status(f"Opened folder: {folder_path}", "info")
            else:
                self.update_status(f"Folder not found: {folder_path}", "warning")
        except Exception as e:
            self.update_status(f"Error opening folder: {e}", "error")

    def open_logs_folder(self):
        """Open the centralized logs folder in Windows File Explorer."""
        logs_folder = os.path.join(os.path.expanduser("~"), "AppData", "Local", "PipelineManager", "logs")
        try:
            # Create the folder if it doesn't exist
            os.makedirs(logs_folder, exist_ok=True)
            os.startfile(logs_folder)
            self.update_status(f"Opened logs folder: {logs_folder}", "info")
        except Exception as e:
            self.update_status(f"Error opening logs folder: {e}", "error")

    def _add_tooltip(self, widget, text):
        """Add a tooltip to a widget."""
        tooltip = None

        def show_tooltip(event):
            nonlocal tooltip
            x, y, _, _ = widget.bbox("insert") if hasattr(widget, 'bbox') else (0, 0, 0, 0)
            x += widget.winfo_rootx() + 25
            y += widget.winfo_rooty() + 25

            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{x}+{y}")

            label = tk.Label(
                tooltip,
                text=text,
                bg="#333333",
                fg="white",
                relief=tk.SOLID,
                borderwidth=1,
                font=("Segoe UI", 9),
                padx=8,
                pady=4
            )
            label.pack()

        def hide_tooltip(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None

        widget.bind("<Enter>", show_tooltip)
        widget.bind("<Leave>", hide_tooltip)

    def _add_header_hint(self, widget, text):
        """Add a hint that shows in the status bar header when hovering over a widget."""
        def show_hint(event):
            if hasattr(self, 'header_hint_label'):
                self.header_hint_label.config(text=text)

        def hide_hint(event):
            if hasattr(self, 'header_hint_label'):
                self.header_hint_label.config(text="")

        widget.bind("<Enter>", show_hint)
        widget.bind("<Leave>", hide_hint)

    def open_settings(self):
        """Open the settings dialog."""
        dialog = SettingsDialog(self.root, self.settings)
        if dialog.show():
            self.update_status("Settings saved", "success")
            # Reload path config to reflect changes
            self.settings = get_rak_settings()

    def open_help(self):
        """Open the keyboard shortcuts documentation."""
        shortcuts_path = os.path.join(SCRIPT_FILE_DIR, "SHORTCUTS.md")
        try:
            if os.path.exists(shortcuts_path):
                os.startfile(shortcuts_path)
                self.update_status("Opened keyboard shortcuts documentation", "info")
            else:
                self.update_status(f"Shortcuts file not found: {shortcuts_path}", "error")
        except Exception as e:
            self.update_status(f"Error opening shortcuts: {e}", "error")

    def refresh_projects(self):
        """Delete database and perform fresh import of all projects (F5)."""
        if hasattr(self, 'project_tracker') and self.project_tracker:
            self.project_tracker.refresh_and_import(silent=True)
        else:
            self.update_status("Project Tracker not available", "error")

    def open_note(self, category_key):
        """Open or create a note file for a category."""
        try:
            # Create notes directory if it doesn't exist
            notes_dir = os.path.join(SCRIPT_FILE_DIR, "notes")
            os.makedirs(notes_dir, exist_ok=True)

            # Create note filename based on category key
            note_filename = f"{category_key.lower()}_notes.txt"
            note_path = os.path.join(notes_dir, note_filename)

            # Create the file if it doesn't exist
            if not os.path.exists(note_path):
                with open(note_path, 'w', encoding='utf-8') as f:
                    f.write(f"# Notes for {category_key}\n\n")
                self.update_status(f"Created new note file: {note_filename}", "info")

            # Open the note file with default text editor
            os.startfile(note_path)
            self.update_status(f"Opened notes: {note_filename}", "info")

        except Exception as e:
            self.update_status(f"Error opening note: {e}", "error")
    
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

            # Hover effects for clickable header (will be updated later to include notepad icon)
            def on_header_enter(e):
                # Slightly lighten the header color on hover
                lighter_color = self._lighten_color(header_color)
                header_frame.configure(bg=lighter_color)
                header_container.configure(bg=lighter_color)
                header_content.configure(bg=lighter_color)
                text_container.configure(bg=lighter_color)
                icon_label.configure(bg=lighter_color)
                name_label.configure(bg=lighter_color)
                desc_label.configure(bg=lighter_color)

            def on_header_leave(e):
                # Return to original color
                header_frame.configure(bg=header_color)
                header_container.configure(bg=header_color)
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

        # Container frame to hold both header content and notepad icon
        header_container = tk.Frame(header_frame, bg=header_color)
        header_container.pack(fill=tk.X, padx=15, pady=15)

        # If clickable, bind events to header_container too
        if folder_path:
            header_container.configure(cursor="hand2")
            header_container.bind("<Enter>", lambda e: on_header_enter(e))
            header_container.bind("<Leave>", lambda e: on_header_leave(e))
            header_container.bind("<Button-1>", lambda e: on_header_click(e))

        # Category icon and name/description side by side, aligned to the left
        header_content = tk.Frame(header_container, bg=header_color)
        header_content.pack(side=tk.LEFT, anchor="w")  # Align to left

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

        # Notepad icon on the right side with background box
        notepad_container = tk.Frame(header_container, bg=header_color)
        notepad_container.pack(side=tk.RIGHT, anchor="e", padx=(10, 0))

        # Inner frame for the icon with darkened background
        notepad_bg_color = self._darken_color(header_color, 0.3)  # Darken header color by 30%
        notepad_hover_color = self._lighten_color(header_color, 0.15)  # Lighten slightly on hover

        notepad_frame = tk.Frame(notepad_container,
                                bg=notepad_bg_color,
                                cursor="hand2",
                                relief=tk.FLAT,
                                borderwidth=0)
        notepad_frame.pack(padx=2, pady=2)

        notepad_icon_font = font.Font(family="Segoe UI Emoji", size=18)
        notepad_icon = tk.Label(notepad_frame,
                               text="📝",
                               font=notepad_icon_font,
                               fg="#ffffff",
                               bg=notepad_bg_color,
                               cursor="hand2",
                               padx=6,
                               pady=4)
        notepad_icon.pack()

        # Notepad icon hover effects - change background only, no size change
        def on_notepad_enter(e):
            notepad_frame.configure(bg=notepad_hover_color)
            notepad_icon.configure(bg=notepad_hover_color)

        def on_notepad_leave(e):
            notepad_frame.configure(bg=notepad_bg_color)
            notepad_icon.configure(bg=notepad_bg_color)

        def on_notepad_click(e):
            # Stop event propagation to prevent header click
            self.open_note(category_key)
            return "break"

        notepad_frame.bind("<Enter>", on_notepad_enter)
        notepad_frame.bind("<Leave>", on_notepad_leave)
        notepad_frame.bind("<Button-1>", on_notepad_click)

        notepad_icon.bind("<Enter>", on_notepad_enter)
        notepad_icon.bind("<Leave>", on_notepad_leave)
        notepad_icon.bind("<Button-1>", on_notepad_click)

        # Update header hover effects to include notepad container background
        if folder_path:
            original_on_header_enter = on_header_enter
            original_on_header_leave = on_header_leave

            def on_header_enter(e):
                original_on_header_enter(e)
                lighter_color = self._lighten_color(header_color)
                notepad_container.configure(bg=lighter_color)

            def on_header_leave(e):
                original_on_header_leave(e)
                notepad_container.configure(bg=header_color)

            # Rebind the updated functions
            header_frame.unbind("<Enter>")
            header_frame.unbind("<Leave>")
            header_frame.bind("<Enter>", on_header_enter)
            header_frame.bind("<Leave>", on_header_leave)

            # Also update bindings for child widgets
            header_container.unbind("<Enter>")
            header_container.unbind("<Leave>")
            header_container.bind("<Enter>", lambda e: on_header_enter(e))
            header_container.bind("<Leave>", lambda e: on_header_leave(e))

            header_content.unbind("<Enter>")
            header_content.unbind("<Leave>")
            header_content.bind("<Enter>", lambda e: on_header_enter(e))
            header_content.bind("<Leave>", lambda e: on_header_leave(e))

            icon_label.unbind("<Enter>")
            icon_label.unbind("<Leave>")
            icon_label.bind("<Enter>", lambda e: on_header_enter(e))
            icon_label.bind("<Leave>", lambda e: on_header_leave(e))

            text_container.unbind("<Enter>")
            text_container.unbind("<Leave>")
            text_container.bind("<Enter>", lambda e: on_header_enter(e))
            text_container.bind("<Leave>", lambda e: on_header_leave(e))

            name_label.unbind("<Enter>")
            name_label.unbind("<Leave>")
            name_label.bind("<Enter>", lambda e: on_header_enter(e))
            name_label.bind("<Leave>", lambda e: on_header_leave(e))

            desc_label.unbind("<Enter>")
            desc_label.unbind("<Leave>")
            desc_label.bind("<Enter>", lambda e: on_header_enter(e))
            desc_label.bind("<Leave>", lambda e: on_header_leave(e))

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

    def _darken_color(self, hex_color, factor=0.2):
        """Darken a hex color by a given factor (0.0 to 1.0)."""
        try:
            # Remove the # if present
            hex_color = hex_color.lstrip('#')

            # Convert to RGB
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

            # Darken each component
            rgb_darkened = tuple(max(0, int(c * (1 - factor))) for c in rgb)

            # Convert back to hex
            return '#{:02x}{:02x}{:02x}'.format(*rgb_darkened)
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

        # Collapsible status area - load saved state from config
        self.status_expanded = self.config_manager.config.get("status_log_expanded", True)
        
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

        # Hint label for header buttons (right side of status bar)
        self.header_hint_label = tk.Label(header_frame,
                                         text="",
                                         font=font.Font(family="Segoe UI", size=9),
                                         fg=COLORS["text_secondary"],
                                         bg=COLORS["bg_secondary"])
        self.header_hint_label.pack(side=tk.RIGHT, padx=30, pady=8)
        
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

        # Apply saved collapse state
        if not self.status_expanded:
            self.status_text_container.pack_forget()
            self.toggle_button.config(text="▶ Status Log")

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

        # Save state to config
        self.config_manager.config["status_log_expanded"] = self.status_expanded
        self.config_manager._save_config()
    
    def update_status(self, message, status_type="info"):
        """Update the status text widget."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        self.status_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.status_text.insert(tk.END, f"{message}\n", status_type)
        self.status_text.see(tk.END)
        
        self.root.update_idletasks()
    
    def select_category_by_name(self, category_name):
        """Select a category or operation by name (for backwards compatibility)."""
        # Find the category key by name
        for key, data in PIPELINE_CATEGORIES.items():
            if data.get("name", "").lower() == category_name.lower() or key.lower() == category_name.lower():
                self._select_category(key)
                return
        # If not found, clear selection
        self._clear_category_selection()
    
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
    # KEYBOARD NAVIGATION METHODS
    # ====================================

    def _should_handle_keyboard(self):
        """Check if keyboard shortcuts should be handled (not when typing in text fields)."""
        focused = self.root.focus_get()
        # Don't handle shortcuts when focused on text input widgets
        return not isinstance(focused, (tk.Entry, tk.Text, ttk.Entry))

    def _nav_panel_up(self):
        """Navigate up between panels (W key)."""
        if not self._should_handle_keyboard():
            return
        if self.focused_panel == "tracker":
            # From tracker, W goes to left panel (categories)
            self.focused_panel = "categories"
            self._update_panel_focus()
            self.root.focus_set()
        elif self.focused_panel in self.LEFT_PANEL_ORDER:
            idx = self.LEFT_PANEL_ORDER.index(self.focused_panel)
            if idx > 0:
                self.focused_panel = self.LEFT_PANEL_ORDER[idx - 1]
                self._update_panel_focus()

    def _nav_panel_down(self):
        """Navigate down between panels (S key)."""
        if not self._should_handle_keyboard():
            return
        if self.focused_panel == "tracker":
            # From tracker, S goes to tools (bottom of left panel)
            if self.selected_category:
                self.focused_panel = "tools"
            else:
                # No category selected, go to operations (Business/Global)
                self.focused_panel = "operations"
            self._update_panel_focus()
            self.root.focus_set()
        elif self.focused_panel in self.LEFT_PANEL_ORDER:
            idx = self.LEFT_PANEL_ORDER.index(self.focused_panel)
            if idx < len(self.LEFT_PANEL_ORDER) - 1:
                # Skip tools panel if no category is selected
                next_panel = self.LEFT_PANEL_ORDER[idx + 1]
                if next_panel == "tools" and not self.selected_category:
                    return
                self.focused_panel = next_panel
                self._update_panel_focus()

    def _nav_panel_left(self):
        """Navigate to left panel from tracker (A key)."""
        if not self._should_handle_keyboard():
            return
        if self.focused_panel == "tracker":
            # Return to last selected left panel
            self.focused_panel = self.last_left_panel
            self._update_panel_focus()
            # Remove focus from tracker's grid canvas so arrow keys work on left panel
            self.root.focus_set()

    def _nav_panel_right(self):
        """Navigate to project tracker from left panel (D key)."""
        if not self._should_handle_keyboard():
            return
        if self.focused_panel in self.LEFT_PANEL_ORDER:
            # Remember current left panel before switching to tracker
            self.last_left_panel = self.focused_panel
            self.focused_panel = "tracker"
            self._update_panel_focus()
            # Give focus to tracker's grid canvas for arrow key navigation
            if hasattr(self, 'project_tracker') and hasattr(self.project_tracker, 'grid_canvas'):
                self.project_tracker.grid_canvas.focus_set()

    def _nav_item_up(self):
        """Navigate up within current panel (Up arrow)."""
        if not self._should_handle_keyboard():
            return
        if self.focused_panel == "categories":
            # 2x3 grid: up moves by 2 (one row)
            if self.category_focus_index >= 2:
                self.category_focus_index -= 2
                self._select_focused_category()
        elif self.focused_panel == "operations":
            # 2x1 grid: no up movement (single row)
            pass
        elif self.focused_panel == "tools":
            # Vertical list of tools only (not folder/notes)
            if self.tools_focus_index > 0:
                self.tools_focus_index -= 1
                self._update_item_focus()
        elif self.focused_panel == "tracker":
            if hasattr(self, 'project_tracker'):
                self.project_tracker._on_grid_up(None)

    def _nav_item_down(self):
        """Navigate down within current panel (Down arrow)."""
        if not self._should_handle_keyboard():
            return
        if self.focused_panel == "categories":
            # 2x3 grid: down moves by 2 (one row)
            if self.category_focus_index < len(self.CATEGORY_ORDER) - 2:
                self.category_focus_index += 2
                self._select_focused_category()
        elif self.focused_panel == "operations":
            # 2x1 grid: no down movement (single row)
            pass
        elif self.focused_panel == "tools":
            # Vertical list of tools only (not folder/notes)
            if self.tools_focus_index < len(self.tool_buttons) - 1:
                self.tools_focus_index += 1
                self._update_item_focus()
        elif self.focused_panel == "tracker":
            if hasattr(self, 'project_tracker'):
                self.project_tracker._on_grid_down(None)

    def _nav_item_left(self):
        """Navigate left within current panel (Left arrow)."""
        if not self._should_handle_keyboard():
            return
        if self.focused_panel == "categories":
            # 2x3 grid: left moves by 1
            if self.category_focus_index > 0:
                self.category_focus_index -= 1
                self._select_focused_category()
        elif self.focused_panel == "operations":
            # 2x1 grid: left moves by 1
            if self.operations_focus_index > 0:
                self.operations_focus_index -= 1
                self._select_focused_operation()
        elif self.focused_panel == "tracker":
            if hasattr(self, 'project_tracker'):
                self.project_tracker._on_grid_left(None)

    def _nav_item_right(self):
        """Navigate right within current panel (Right arrow)."""
        if not self._should_handle_keyboard():
            return
        if self.focused_panel == "categories":
            # 2x3 grid: right moves by 1
            if self.category_focus_index < len(self.CATEGORY_ORDER) - 1:
                self.category_focus_index += 1
                self._select_focused_category()
        elif self.focused_panel == "operations":
            # 2x1 grid: right moves by 1
            if self.operations_focus_index < len(self.OPERATIONS_ORDER) - 1:
                self.operations_focus_index += 1
                self._select_focused_operation()
        elif self.focused_panel == "tracker":
            if hasattr(self, 'project_tracker'):
                self.project_tracker._on_grid_right(None)

    def _select_focused_category(self):
        """Select the currently focused category (auto-select on navigation)."""
        if 0 <= self.category_focus_index < len(self.CATEGORY_ORDER):
            category_key = self.CATEGORY_ORDER[self.category_focus_index]
            self._select_category(category_key)

    def _select_focused_operation(self):
        """Select the currently focused operation (auto-select on navigation)."""
        if 0 <= self.operations_focus_index < len(self.OPERATIONS_ORDER):
            ops_key = self.OPERATIONS_ORDER[self.operations_focus_index]
            self._select_category(ops_key)

    def _on_enter_key(self):
        """Handle Enter key to activate focused item."""
        if not self._should_handle_keyboard():
            return
        if self.focused_panel == "categories":
            # Already auto-selected, but Enter can confirm
            pass
        elif self.focused_panel == "operations":
            # Already auto-selected, but Enter can confirm
            pass
        elif self.focused_panel == "tools":
            # Run the focused tool
            if self.tool_buttons and 0 <= self.tools_focus_index < len(self.tool_buttons):
                tool = self.tool_buttons[self.tools_focus_index]
                self.run_script(tool["category_key"], tool["script_key"], tool["subcat_key"])
        elif self.focused_panel == "tracker":
            if hasattr(self, 'project_tracker'):
                self.project_tracker._on_enter_key(None)

    def _quick_select_category(self, category_key):
        """Quick select a category via Shift+Letter."""
        if not self._should_handle_keyboard():
            return
        if category_key in PIPELINE_CATEGORIES:
            self._select_category(category_key)
            # Update focus index
            if category_key in self.CATEGORY_ORDER:
                self.focused_panel = "categories"
                self.category_focus_index = self.CATEGORY_ORDER.index(category_key)
            elif category_key in self.OPERATIONS_ORDER:
                self.focused_panel = "operations"
                self.operations_focus_index = self.OPERATIONS_ORDER.index(category_key)
            self._update_panel_focus()

    def _quick_open_folder(self):
        """Quick open current category's folder (G key)."""
        if not self._should_handle_keyboard():
            return
        if self._folder_category and self._folder_path:
            # Check if project tracker is in archive mode
            is_archive_mode = False
            if hasattr(self, 'project_tracker') and self.project_tracker:
                if hasattr(self.project_tracker, 'filter_status'):
                    is_archive_mode = self.project_tracker.filter_status.get() == "archived"

            if is_archive_mode:
                archive_path = self.settings.get_archive_path(self._folder_category)
                self.open_folder(archive_path)
            else:
                self.open_folder(self._folder_path)

    def _quick_open_notes(self):
        """Quick open current category's notes (N key)."""
        if not self._should_handle_keyboard():
            return
        if self._notes_category:
            self.open_note(self._notes_category)

    def _cycle_scope(self):
        """Cycle through scope options (backtick key)."""
        if not self._should_handle_keyboard():
            return
        current_idx = self.SCOPE_ORDER.index(self.current_scope) if self.current_scope in self.SCOPE_ORDER else 0
        next_idx = (current_idx + 1) % len(self.SCOPE_ORDER)
        self._set_scope(self.SCOPE_ORDER[next_idx])

    def _set_status_filter(self, status):
        """Set project tracker status filter (4/5/6 keys)."""
        if not self._should_handle_keyboard():
            return
        if hasattr(self, 'project_tracker') and self.project_tracker:
            self.project_tracker.filter_status.set(status)
            self.project_tracker._on_filter_changed()

    def _focus_tracker_search(self):
        """Focus the project tracker search field (/ key)."""
        if not self._should_handle_keyboard():
            return
        if hasattr(self, 'project_tracker') and hasattr(self.project_tracker, 'search_entry'):
            self.project_tracker.search_entry.focus_set()

    def _new_project(self):
        """Create new project for current category (Ctrl+N)."""
        if hasattr(self, 'project_tracker') and self.project_tracker:
            # Launch the creation flow (callback will save current panel state)
            self.project_tracker._on_fab_clicked()
            # Switch focus to tracker for arrow key navigation in subtype selection
            if self.project_tracker.view_state != "PROJECT_LIST":
                self.focused_panel = "tracker"
                self._update_panel_focus()

    def _on_escape_key(self):
        """Handle Escape key - close creation panel if open."""
        # Check if project tracker is in creation mode - close that
        # The cancel callback (_return_to_last_panel) handles focus restoration
        if hasattr(self, 'project_tracker') and self.project_tracker:
            if self.project_tracker.view_state != "PROJECT_LIST":
                self.project_tracker._close_creation_panel()

    def _on_creation_start(self):
        """Called when project creation starts (FAB clicked or Ctrl+N)."""
        # Remember current panel before switching to creation mode
        self.panel_before_creation = self.focused_panel
        if self.focused_panel in self.LEFT_PANEL_ORDER:
            self.last_left_panel = self.focused_panel

    def _return_to_last_panel(self):
        """Return focus to the panel we were on before project creation."""
        self.focused_panel = self.panel_before_creation
        self._update_panel_focus()
        # Set appropriate focus based on panel type
        if self.focused_panel == "tracker":
            if hasattr(self, 'project_tracker') and hasattr(self.project_tracker, 'grid_canvas'):
                self.project_tracker.grid_canvas.focus_set()
        else:
            self.root.focus_set()

    def _on_project_creation_done(self, project_data=None):
        """Called after successful project creation. Switch filters, refresh, focus tracker, select project."""
        if not hasattr(self, 'project_tracker') or not self.project_tracker:
            return

        tracker = self.project_tracker

        # 1. Reload DB to pick up the project registered by the creation form
        tracker.db.reload()

        # 2. Switch status filter to "active"
        if tracker.filter_status.get() != "active":
            tracker.filter_status.set("active")
            tracker._update_filter_button_styles()

        # 3. Switch scope to match the new project (personal vs work)
        if project_data:
            is_personal = (
                project_data.get('client_name', '').lower() == 'personal' or
                project_data.get('metadata', {}).get('is_personal', False)
            )
            target_scope = "personal" if is_personal else "client"
            if self.current_scope != target_scope and self.current_scope != "all":
                self._set_scope(target_scope)

        # 4. Set category filter to match the new project
        if project_data:
            project_type = project_data.get('project_type', '')
            category = tracker._get_category_for_type(project_type)
            if category and tracker.selected_category and tracker.selected_category != category:
                tracker.selected_category = category
                for name, btn_info in tracker.category_buttons.items():
                    tracker._update_category_card_style(btn_info, name)

        # 5. Force geometry update so grid canvas has valid dimensions
        self.root.update_idletasks()

        # 6. Refresh project list (populates grid_projects)
        tracker.refresh_project_list()

        # 6. Focus tracker panel
        self.focused_panel = "tracker"
        self._update_panel_focus()
        if hasattr(tracker, 'grid_canvas'):
            tracker.grid_canvas.focus_set()

        # 7. Select the newly created project
        if project_data and project_data.get('path'):
            tracker._select_project_by_path(project_data['path'])

    def _update_panel_focus(self):
        """Update visual focus indicator for panels."""
        # Clear all item focus first
        self._clear_all_item_focus()

        # Update panel focus indicators (subtle left accent bar)
        self._update_panel_indicator()

        # Update item focus for current panel
        self._update_item_focus()

        # Update status bar hint
        self._update_keyboard_hint()

    def _update_panel_indicator(self):
        """Update subtle focus indicator for panels (left accent bar on grids only)."""
        # Create/update focus indicator bars if they don't exist
        if not hasattr(self, '_panel_indicators'):
            self._panel_indicators = {}

        # Only show indicators on the actual grids/sections
        grids = [
            ("cat_grid", self.cat_grid, "categories", COLORS["bg_card"]),
            ("ops_grid", self.ops_grid, "operations", COLORS["bg_card"]),
            ("tools_section", self.tools_section if hasattr(self, 'tools_section') else None, "tools", COLORS["bg_secondary"]),
            ("tracker_panel", self.tracker_panel if hasattr(self, 'tracker_panel') else None, "tracker", COLORS["bg_primary"]),
        ]

        for grid_name, grid_widget, panel_name, bg_color in grids:
            if grid_widget is None:
                continue

            # Check if indicator exists and is still valid
            indicator_valid = (
                grid_name in self._panel_indicators and
                self._panel_indicators[grid_name].winfo_exists()
            )

            # Create indicator if it doesn't exist or was destroyed
            if not indicator_valid:
                indicator = tk.Frame(grid_widget, bg=bg_color, width=3)
                indicator.place(x=0, y=0, relheight=1.0)
                self._panel_indicators[grid_name] = indicator

            # Update indicator color based on focus
            indicator = self._panel_indicators[grid_name]
            try:
                if panel_name == self.focused_panel:
                    indicator.configure(bg=COLORS["accent"])
                else:
                    # Hide by matching background
                    indicator.configure(bg=bg_color)
            except tk.TclError:
                # Widget was destroyed, remove from cache
                del self._panel_indicators[grid_name]

    def _clear_all_item_focus(self):
        """Clear focus highlighting from all items (reset to normal background)."""
        # Clear tool focus - reset to normal background
        for tool in self.tool_buttons:
            tool["frame"].configure(bg=COLORS["bg_secondary"])
            tool["content"].configure(bg=COLORS["bg_secondary"])
            tool["icon_label"].configure(bg=COLORS["bg_secondary"])
            tool["name_label"].configure(bg=COLORS["bg_secondary"])
            tool["arrow_label"].configure(bg=COLORS["bg_secondary"])

    def _update_item_focus(self):
        """Update visual focus indicator for items within panels (darken focused item)."""
        if self.focused_panel == "categories":
            # Categories auto-select, no extra focus needed
            pass

        elif self.focused_panel == "operations":
            # Operations auto-select, no extra focus needed
            pass

        elif self.focused_panel == "tools":
            # Tools only (not folder/notes) - darken focused item background
            for idx, tool in enumerate(self.tool_buttons):
                if idx == self.tools_focus_index:
                    # Darken the focused tool
                    tool["frame"].configure(bg=COLORS["bg_hover"])
                    tool["content"].configure(bg=COLORS["bg_hover"])
                    tool["icon_label"].configure(bg=COLORS["bg_hover"])
                    tool["name_label"].configure(bg=COLORS["bg_hover"])
                    tool["arrow_label"].configure(bg=COLORS["bg_hover"], fg=tool["color"])
                else:
                    # Normal background
                    tool["frame"].configure(bg=COLORS["bg_secondary"])
                    tool["content"].configure(bg=COLORS["bg_secondary"])
                    tool["icon_label"].configure(bg=COLORS["bg_secondary"])
                    tool["name_label"].configure(bg=COLORS["bg_secondary"])
                    tool["arrow_label"].configure(bg=COLORS["bg_secondary"], fg=COLORS["text_secondary"])

    def _update_keyboard_hint(self):
        """Update status bar with keyboard hints based on focused panel."""
        hints = {
            "categories": "Arrows: navigate | Shift+Letter: quick select | S: operations | D: tracker",
            "operations": "Left/Right: navigate | W: categories | S: tools | D: tracker",
            "tools": "Up/Down: navigate | Enter: run | G: folder | N: notes | W/S: panels",
            "tracker": "Arrows: navigate | Enter: open | A: left panel | /: search",
        }
        if hasattr(self, 'header_hint_label'):
            self.header_hint_label.config(text=hints.get(self.focused_panel, ""))

# ====================================
# MAIN APPLICATION ENTRY POINT
# ====================================

def main():
    """Main application entry point."""
    # Setup logging when the app actually runs (not at import time)
    setup_logging("pipeline")

    root = tk.Tk()
    
    # Create main application
    app = ProfessionalPipelineGUI(root)

    # Bind keyboard shortcuts - existing
    root.bind('<Control-comma>', lambda e: app.open_settings())
    root.bind('<Control-l>', lambda e: app.open_logs_folder())
    root.bind('<F5>', lambda e: app.refresh_projects())
    root.bind('<F1>', lambda e: app.open_help())
    root.bind('<F11>', lambda e: root.attributes('-fullscreen', not root.attributes('-fullscreen')))

    # ====================================
    # RAK KEYBOARD NAVIGATION BINDINGS
    # ====================================

    # Number keys - Global filters (scope 1/2/3, status 4/5/6)
    root.bind('1', lambda e: app._set_scope("personal"))
    root.bind('2', lambda e: app._set_scope("client"))
    root.bind('3', lambda e: app._set_scope("all"))
    root.bind('4', lambda e: app._set_status_filter("active"))
    root.bind('5', lambda e: app._set_status_filter("archived"))
    root.bind('6', lambda e: app._set_status_filter("all"))

    # Panel navigation (WASD)
    root.bind('w', lambda e: app._nav_panel_up())
    root.bind('W', lambda e: app._nav_panel_up())
    root.bind('s', lambda e: app._nav_panel_down())
    root.bind('S', lambda e: app._nav_panel_down())
    root.bind('a', lambda e: app._nav_panel_left())
    root.bind('A', lambda e: app._nav_panel_left())
    root.bind('d', lambda e: app._nav_panel_right())
    root.bind('D', lambda e: app._nav_panel_right())

    # In-panel navigation (Arrows)
    root.bind('<Up>', lambda e: app._nav_item_up())
    root.bind('<Down>', lambda e: app._nav_item_down())
    root.bind('<Left>', lambda e: app._nav_item_left())
    root.bind('<Right>', lambda e: app._nav_item_right())
    root.bind('<Return>', lambda e: app._on_enter_key())

    # Quick actions
    root.bind('g', lambda e: app._quick_open_folder())
    root.bind('G', lambda e: app._quick_open_folder())
    root.bind('0', lambda e: app._quick_open_folder())  # Alternative for G
    root.bind('n', lambda e: app._quick_open_notes())
    root.bind('N', lambda e: app._quick_open_notes())
    root.bind('.', lambda e: app._quick_open_notes())   # Alternative for N
    root.bind('`', lambda e: app._cycle_scope())
    root.bind('/', lambda e: app._focus_tracker_search())
    root.bind('<Escape>', lambda e: app._on_escape_key())

    # Category quick select (Shift+Key)
    root.bind('<Shift-V>', lambda e: app._quick_select_category('VISUAL'))
    root.bind('<Shift-R>', lambda e: app._quick_select_category('REALTIME'))
    root.bind('<Shift-A>', lambda e: app._quick_select_category('AUDIO'))
    root.bind('<Shift-P>', lambda e: app._quick_select_category('PHYSICAL'))
    root.bind('<Shift-H>', lambda e: app._quick_select_category('PHOTO'))
    root.bind('<Shift-W>', lambda e: app._quick_select_category('WEB'))
    root.bind('<Shift-B>', lambda e: app._quick_select_category('BUSINESS'))
    root.bind('<Shift-G>', lambda e: app._quick_select_category('GLOBAL'))

    # Search shortcut
    root.bind('<Control-f>', lambda e: app._focus_tracker_search())
    root.bind('<Control-F>', lambda e: app._focus_tracker_search())

    # New project shortcut
    root.bind('<Control-n>', lambda e: app._new_project())
    root.bind('<Control-N>', lambda e: app._new_project())

    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    main()