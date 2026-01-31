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
from tkinter import ttk, font
import datetime
import threading

# ====================================
# CONSTANTS AND CONFIGURATION
# ====================================

# Base script directory (relative to this file)
SCRIPT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(SCRIPT_FILE_DIR, "modules")

# ====================================
# IMPORTS FROM MODULES
# ====================================

sys.path.insert(0, SCRIPTS_DIR)
from shared_logging import get_logger, setup_logging
from rak_settings import get_rak_settings

from ui_theme import COLORS, CATEGORY_COLORS
from ui_pipeline_categories import (
    APP_NAME, APP_VERSION, LOGO_PATH,
    CREATIVE_CATEGORIES, BUSINESS_CATEGORIES, PIPELINE_CATEGORIES
)
from ui_config_manager import ConfigManager
from ui_settings_dialog import SettingsDialog
from ui_script_runner import ScriptRunner
from ui_keyboard_navigator import KeyboardNavigatorMixin

# Get logger reference (configured in main())
logger = get_logger("pipeline")

# Import Project Tracker for embedded use (from top-level file)
from floriandheer_project_tracker import ProjectTrackerApp

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

class ProfessionalPipelineGUI(KeyboardNavigatorMixin):
    """Professional GUI for the Pipeline Manager."""

    def __init__(self, root):
        """Initialize the Pipeline Manager GUI."""
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")

        # Open maximized or fullscreen depending on setting
        self.root.state('zoomed')  # Windows maximized

        # Set minimum size
        self.root.minsize(1200, 800)

        # Configure root window background
        self.root.configure(bg=COLORS["bg_primary"])

        # Load configuration
        self.config_manager = ConfigManager()

        # Load path configuration
        self.settings = get_rak_settings()

        # Apply fullscreen if configured
        if self.settings.get_start_fullscreen():
            self.root.attributes('-fullscreen', True)

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
            library_path = get_rak_settings().get_work_drive() + "\\_LIBRARY"
            if folder_path == library_path:
                # Get current year and quarter
                now = datetime.datetime.now()
                current_year = now.year
                current_quarter = (now.month - 1) // 3 + 1

                # Construct the quarterly folder path
                folder_path = f"{library_path}\\Boekhouding\\{current_year}\\Q{current_quarter}"

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
    root.bind('1', lambda e: app._set_scope("personal") if app._should_handle_keyboard() else None)
    root.bind('2', lambda e: app._set_scope("client") if app._should_handle_keyboard() else None)
    root.bind('3', lambda e: app._set_scope("all") if app._should_handle_keyboard() else None)
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
