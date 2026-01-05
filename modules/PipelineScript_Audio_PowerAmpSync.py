#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PipelineScript_Audio_PowerAmpSync.py
Description: Sync MusicBee/iTunes playlists and music to PowerAmp (Android)
Author: Florian Dheer
Version: 2.0.0

Features:
- Reads playlists from iTunes XML (exported from MusicBee or iTunes)
- Selective playlist sync with treeview selection
- Converts lossless audio (FLAC, WAV, AIFF) to MP3 for phone storage
- Configurable MP3 quality (320k CBR, 256k, V0 VBR, V2 VBR)
- Skip existing files option for fast incremental syncs
- Exports playlists to M3U8 format (UTF-8 for Unicode support)
- Configurable source/destination path mapping
- Same UI patterns as TraktorSyncPlaylists for consistency
"""

import os
import sys
import json
import re
import shutil
import threading
import datetime
import subprocess
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, asdict, field
from pathlib import Path
import xml.etree.ElementTree as ET
import urllib.parse

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

APP_NAME = "MusicBee to PowerAmp Sync"
APP_VERSION = "2.0.0"

# Configuration paths
APP_DATA_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "PipelineManager")
CONFIG_FILE = os.path.join(APP_DATA_DIR, "poweramp_sync_config.json")

# Header color (matching pipeline style)
HEADER_COLOR = "#2c3e50"

# Valid audio extensions
VALID_EXTENSIONS = {'.mp3', '.flac', '.wav', '.aiff', '.m4a', '.ogg', '.opus', '.wma', '.aac'}


# ============================================================================
# LOGGING SETUP
# ============================================================================

from shared_logging import get_logger, setup_logging as setup_shared_logging

logger = get_logger("poweramp_sync")


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class SyncSettings:
    """Sync configuration settings."""
    itunes_xml_path: str = ""
    destination_path: str = ""  # Playlist destination
    music_destination_path: str = ""  # Music files destination
    source_music_prefix: str = "M:\\"
    android_music_prefix: str = "/storage/emulated/0/Music/"
    use_relative_paths: bool = False
    selected_playlists: List[str] = field(default_factory=list)
    # Sync mode: "music_and_playlists" or "playlists_only"
    sync_mode: str = "music_and_playlists"
    # MP3 conversion settings
    convert_to_mp3: bool = True
    skip_existing: bool = True
    mp3_bitrate: str = "320k"  # Options: "320k", "256k", "192k", "V0", "V2"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SyncSettings':
        valid_fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid_fields)


# Lossless formats that should be converted to MP3
LOSSLESS_EXTENSIONS = {'.flac', '.wav', '.aiff', '.aif', '.alac', '.ape', '.wv'}


# ============================================================================
# CONFIGURATION MANAGER
# ============================================================================

class ConfigManager:
    """Manages persistent configuration settings."""

    def __init__(self, config_path: str = CONFIG_FILE):
        self.config_path = config_path
        self.settings = self._load_settings()

    def _load_settings(self) -> SyncSettings:
        """Load settings from file or create defaults."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Loaded settings from {self.config_path}")
                    return SyncSettings.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load settings: {e}, using defaults")

        return SyncSettings()

    def save_settings(self) -> bool:
        """Save current settings to file."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings.to_dict(), f, indent=2)
            logger.info(f"Settings saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def update_settings(self, **kwargs) -> None:
        """Update specific settings."""
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save_settings()


# ============================================================================
# GUI APPLICATION
# ============================================================================

class PowerAmpSyncApp:
    """Main application GUI."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("700x850")
        self.root.minsize(650, 750)

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # Initialize managers
        self.config_manager = ConfigManager()

        # State
        self.all_playlists: List[str] = []
        self.playlist_data: Dict[str, Dict] = {}
        self.itunes_root = None
        self.tracks_dict = {}  # Track ID -> track info
        self.syncing = False
        self.bitrate_radios = []

        # Create UI
        self._create_ui()

        # Load settings and initialize default paths
        self._initialize_default_paths()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_ui(self) -> None:
        """Create the complete UI."""
        # Header
        header = tk.Frame(self.root, bg=HEADER_COLOR, height=45)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        tk.Label(header, text="PowerAmp Sync", font=("Segoe UI", 13, "bold"),
                 fg="white", bg=HEADER_COLOR).place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Main content
        main = ttk.Frame(self.root, padding=15)
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)  # Playlists section grows

        # === SECTION 1: SOURCE ===
        src_frame = ttk.LabelFrame(main, text="Source", padding=10)
        src_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        src_frame.columnconfigure(0, weight=1)

        src_row = ttk.Frame(src_frame)
        src_row.pack(fill=tk.X)
        src_row.columnconfigure(0, weight=1)

        self.itunes_xml_var = tk.StringVar()
        ttk.Entry(src_row, textvariable=self.itunes_xml_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(src_row, text="Browse...", command=self._browse_itunes_xml, width=10).grid(row=0, column=1, padx=(0, 5))
        self.load_btn = ttk.Button(src_row, text="Load Library", command=self._load_playlists, width=12)
        self.load_btn.grid(row=0, column=2)

        # === SECTION 2: DESTINATION ===
        dest_frame = ttk.LabelFrame(main, text="Destination", padding=10)
        dest_frame.grid(row=1, column=0, sticky="ew", pady=8)
        dest_frame.columnconfigure(1, weight=1)

        # Mode selection
        mode_row = ttk.Frame(dest_frame)
        mode_row.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        ttk.Label(mode_row, text="Mode:").pack(side=tk.LEFT, padx=(0, 15))
        self.sync_mode_var = tk.StringVar(value="music_and_playlists")
        ttk.Radiobutton(mode_row, text="Music + Playlists", variable=self.sync_mode_var,
                        value="music_and_playlists", command=self._on_sync_mode_changed).pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(mode_row, text="Playlists Only", variable=self.sync_mode_var,
                        value="playlists_only", command=self._on_sync_mode_changed).pack(side=tk.LEFT)

        # Music folder
        ttk.Label(dest_frame, text="Music folder:").grid(row=1, column=0, sticky="w", pady=3)
        self.music_dest_var = tk.StringVar()
        self.music_dest_entry = ttk.Entry(dest_frame, textvariable=self.music_dest_var)
        self.music_dest_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=3)
        self.music_dest_browse_btn = ttk.Button(dest_frame, text="Browse...", command=self._browse_music_destination, width=10)
        self.music_dest_browse_btn.grid(row=1, column=2, pady=3)

        # Playlist folder
        ttk.Label(dest_frame, text="Playlist folder:").grid(row=2, column=0, sticky="w", pady=3)
        self.dest_var = tk.StringVar()
        ttk.Entry(dest_frame, textvariable=self.dest_var).grid(row=2, column=1, sticky="ew", padx=10, pady=3)
        ttk.Button(dest_frame, text="Browse...", command=self._browse_destination, width=10).grid(row=2, column=2, pady=3)

        # Separator
        ttk.Separator(dest_frame, orient="horizontal").grid(row=3, column=0, columnspan=3, sticky="ew", pady=10)

        # Path mapping
        ttk.Label(dest_frame, text="Path mapping:").grid(row=4, column=0, sticky="w", pady=3)
        map_row = ttk.Frame(dest_frame)
        map_row.grid(row=4, column=1, columnspan=2, sticky="ew", pady=3)

        self.source_prefix_var = tk.StringVar()
        ttk.Entry(map_row, textvariable=self.source_prefix_var, width=12).pack(side=tk.LEFT)
        ttk.Label(map_row, text="  →  ").pack(side=tk.LEFT)
        self.android_prefix_var = tk.StringVar()
        ttk.Entry(map_row, textvariable=self.android_prefix_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.relative_paths_var = tk.BooleanVar()
        ttk.Checkbutton(dest_frame, text="Use relative paths only", variable=self.relative_paths_var).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(5, 0))

        # === SECTION 3: CONVERSION ===
        self.conv_frame = ttk.LabelFrame(main, text="Conversion", padding=10)
        self.conv_frame.grid(row=2, column=0, sticky="ew", pady=8)

        # Convert checkbox + Quality dropdown on same row
        conv_row1 = ttk.Frame(self.conv_frame)
        conv_row1.pack(fill=tk.X, pady=(0, 5))

        self.convert_mp3_var = tk.BooleanVar(value=True)
        self.convert_mp3_checkbox = ttk.Checkbutton(conv_row1, text="Convert FLAC/WAV to MP3",
                                                     variable=self.convert_mp3_var, command=self._on_convert_mp3_changed)
        self.convert_mp3_checkbox.pack(side=tk.LEFT)

        ttk.Label(conv_row1, text="Quality:").pack(side=tk.LEFT, padx=(30, 8))
        self.bitrate_var = tk.StringVar(value="320k")
        self.quality_combo = ttk.Combobox(conv_row1, textvariable=self.bitrate_var, state="readonly", width=18,
                                          values=["320 kbps (Best)", "256 kbps", "V0 (~245 kbps VBR)", "V2 (~190 kbps VBR)"])
        self.quality_combo.pack(side=tk.LEFT)
        self.quality_combo.current(0)
        self.quality_combo.bind("<<ComboboxSelected>>", self._on_quality_changed)

        # Skip existing + FFmpeg check
        conv_row2 = ttk.Frame(self.conv_frame)
        conv_row2.pack(fill=tk.X)

        self.skip_existing_var = tk.BooleanVar(value=True)
        self.skip_existing_checkbox = ttk.Checkbutton(conv_row2, text="Skip existing files", variable=self.skip_existing_var)
        self.skip_existing_checkbox.pack(side=tk.LEFT)

        self.ffmpeg_status_var = tk.StringVar(value="")
        ttk.Label(conv_row2, textvariable=self.ffmpeg_status_var).pack(side=tk.RIGHT)
        self.ffmpeg_btn = ttk.Button(conv_row2, text="Check FFmpeg", command=self._check_ffmpeg_ui, width=14)
        self.ffmpeg_btn.pack(side=tk.RIGHT, padx=(30, 8))

        # === SECTION 4: PLAYLISTS ===
        pl_frame = ttk.LabelFrame(main, text="Playlists", padding=10)
        pl_frame.grid(row=3, column=0, sticky="nsew", pady=8)
        pl_frame.columnconfigure(0, weight=1)
        pl_frame.rowconfigure(1, weight=1)

        # Filter row
        filter_row = ttk.Frame(pl_frame)
        filter_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(filter_row, text="Filter:").pack(side=tk.LEFT, padx=(0, 8))
        self.filter_var = tk.StringVar()
        self.filter_var.trace('w', self._filter_playlists)
        ttk.Entry(filter_row, textvariable=self.filter_var, width=25).pack(side=tk.LEFT)

        self.selection_summary = tk.StringVar(value="No playlists loaded")
        ttk.Label(filter_row, textvariable=self.selection_summary).pack(side=tk.RIGHT)

        self.selection_mode = tk.StringVar(value="include")
        ttk.Radiobutton(filter_row, text="Exclude selected", variable=self.selection_mode,
                        value="exclude", command=self._update_selection_summary).pack(side=tk.RIGHT, padx=(0, 15))
        ttk.Radiobutton(filter_row, text="Include selected", variable=self.selection_mode,
                        value="include", command=self._update_selection_summary).pack(side=tk.RIGHT, padx=(0, 5))

        # Treeview
        tree_container = ttk.Frame(pl_frame)
        tree_container.grid(row=1, column=0, sticky="nsew")
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)

        self.playlist_tree = ttk.Treeview(tree_container, columns=("tracks", "type"), show="tree headings", height=8)
        self.playlist_tree.grid(row=0, column=0, sticky="nsew")

        self.playlist_tree.heading("#0", text="Playlist Name")
        self.playlist_tree.heading("tracks", text="Tracks")
        self.playlist_tree.heading("type", text="Type")
        self.playlist_tree.column("#0", width=350)
        self.playlist_tree.column("tracks", width=70, anchor="center")
        self.playlist_tree.column("type", width=80, anchor="center")

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.playlist_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.playlist_tree.config(yscrollcommand=scrollbar.set)
        self.playlist_tree.bind('<<TreeviewSelect>>', lambda e: self._update_selection_summary())

        # Selection buttons
        sel_btn_row = ttk.Frame(pl_frame)
        sel_btn_row.grid(row=2, column=0, sticky="w", pady=(8, 0))

        ttk.Button(sel_btn_row, text="Select All", command=self._select_all_playlists, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(sel_btn_row, text="Select None", command=self._clear_all_playlists, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(sel_btn_row, text="Auto Select", command=self._auto_select_playlists, width=10).pack(side=tk.LEFT, padx=5)

        # === SECTION 5: ACTIONS ===
        action_frame = ttk.Frame(main)
        action_frame.grid(row=4, column=0, sticky="ew", pady=15)

        # Main sync button - dark, prominent
        self.sync_btn = tk.Button(
            action_frame, text="SYNC TO DEVICE", command=self._start_sync,
            font=("Segoe UI", 11, "bold"), width=18, height=2,
            bg="#2c3e50", fg="white", activebackground="#34495e", activeforeground="white",
            cursor="hand2", relief="flat"
        )
        self.sync_btn.pack(side=tk.LEFT)

        # Cancel button - visible but not too prominent
        self.cancel_btn = tk.Button(
            action_frame, text="Cancel", command=self._cancel_sync,
            font=("Segoe UI", 10), width=12, height=2,
            bg="#95a5a6", fg="white", activebackground="#7f8c8d", activeforeground="white",
            cursor="hand2", relief="flat", state=tk.DISABLED
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=(15, 0))

        # Right side buttons
        ttk.Button(action_frame, text="Save Settings", command=self._save_settings, width=12).pack(side=tk.RIGHT)
        ttk.Button(action_frame, text="Preview", command=self._preview_selection, width=10).pack(side=tk.RIGHT, padx=(0, 10))

        # === SECTION 6: LOG ===
        log_frame = ttk.LabelFrame(main, text="Log", padding=5)
        log_frame.grid(row=5, column=0, sticky="nsew", pady=(8, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        # Notebook with tabs
        self.results_notebook = ttk.Notebook(log_frame)
        self.results_notebook.grid(row=0, column=0, sticky="nsew")

        # Library tab
        lib_tab = ttk.Frame(self.results_notebook)
        self.results_notebook.add(lib_tab, text="Library Info")
        lib_tab.columnconfigure(0, weight=1)
        lib_tab.rowconfigure(0, weight=1)

        self.analysis_text = tk.Text(lib_tab, wrap=tk.WORD, height=6, font=("Consolas", 9), bg="#fafafa")
        self.analysis_text.grid(row=0, column=0, sticky="nsew")
        lib_scroll = ttk.Scrollbar(lib_tab, orient="vertical", command=self.analysis_text.yview)
        lib_scroll.grid(row=0, column=1, sticky="ns")
        self.analysis_text.config(yscrollcommand=lib_scroll.set)

        # Sync log tab
        sync_tab = ttk.Frame(self.results_notebook)
        self.results_notebook.add(sync_tab, text="Sync Log")
        sync_tab.columnconfigure(0, weight=1)
        sync_tab.rowconfigure(0, weight=1)

        self.sync_text = tk.Text(sync_tab, wrap=tk.WORD, height=6, font=("Consolas", 9), bg="#fafafa")
        self.sync_text.grid(row=0, column=0, sticky="nsew")
        sync_scroll = ttk.Scrollbar(sync_tab, orient="vertical", command=self.sync_text.yview)
        sync_scroll.grid(row=0, column=1, sticky="ns")
        self.sync_text.config(yscrollcommand=sync_scroll.set)

        # === STATUS BAR ===
        status_frame = tk.Frame(self.root, bg="#ecf0f1", height=25)
        status_frame.grid(row=2, column=0, sticky="ew")
        status_frame.grid_propagate(False)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(status_frame, textvariable=self.status_var, bg="#ecf0f1", fg="#7f8c8d",
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=10, pady=3)

    def _on_quality_changed(self, event=None) -> None:
        """Handle quality combobox selection."""
        selection = self.quality_combo.get()
        # Map display text to internal value
        mapping = {
            "320 kbps (Best)": "320k",
            "256 kbps": "256k",
            "V0 (~245 kbps VBR)": "V0",
            "V2 (~190 kbps VBR)": "V2"
        }
        self.bitrate_var.set(mapping.get(selection, "320k"))

    def _initialize_default_paths(self) -> None:
        """Initialize default paths from config or common locations."""
        settings = self.config_manager.settings

        # Try to find iTunes/MusicBee XML
        if settings.itunes_xml_path and os.path.exists(settings.itunes_xml_path):
            self.itunes_xml_var.set(settings.itunes_xml_path)
        else:
            possible_paths = [
                os.path.join(os.environ.get('USERPROFILE', ''), 'Music', 'iTunes', 'iTunes Music Library.xml'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Music', 'iTunes', 'iTunes Library.xml'),
                "M:\\iTunes Music Library.xml",
                "~/Music/iTunes/iTunes Music Library.xml",
            ]
            for path in possible_paths:
                expanded = os.path.expanduser(path)
                if os.path.exists(expanded):
                    self.itunes_xml_var.set(expanded)
                    break

        # Load other settings
        self.dest_var.set(settings.destination_path)
        self.music_dest_var.set(settings.music_destination_path)
        self.source_prefix_var.set(settings.source_music_prefix)
        self.android_prefix_var.set(settings.android_music_prefix)
        self.relative_paths_var.set(settings.use_relative_paths)

        # Load sync mode and MP3 conversion settings
        self.sync_mode_var.set(settings.sync_mode)
        self.convert_mp3_var.set(settings.convert_to_mp3)
        self.skip_existing_var.set(settings.skip_existing)

        # Set quality combobox based on saved bitrate
        bitrate_to_combo = {
            "320k": "320 kbps (Best)",
            "256k": "256 kbps",
            "V0": "V0 (~245 kbps VBR)",
            "V2": "V2 (~190 kbps VBR)"
        }
        combo_value = bitrate_to_combo.get(settings.mp3_bitrate, "320 kbps (Best)")
        self.quality_combo.set(combo_value)
        self.bitrate_var.set(settings.mp3_bitrate)

        # Update UI state based on sync mode
        self._on_sync_mode_changed()

    def _browse_itunes_xml(self) -> None:
        """Browse for iTunes XML file."""
        filename = filedialog.askopenfilename(
            title="Select iTunes/MusicBee XML Library",
            filetypes=[("XML Files", "*.xml"), ("All Files", "*.*")]
        )
        if filename:
            self.itunes_xml_var.set(filename)
            self._load_playlists()

    def _browse_destination(self) -> None:
        """Browse for destination folder."""
        directory = filedialog.askdirectory(title="Select PowerAmp Playlists Folder")
        if directory:
            self.dest_var.set(directory)

    def _browse_music_destination(self) -> None:
        """Browse for music destination folder."""
        directory = filedialog.askdirectory(title="Select Music Destination Folder")
        if directory:
            self.music_dest_var.set(directory)

    def _on_sync_mode_changed(self) -> None:
        """Handle sync mode change - enable/disable music sync options."""
        playlists_only = self.sync_mode_var.get() == "playlists_only"

        # Enable/disable music sync widgets
        state = "disabled" if playlists_only else "normal"
        combo_state = "disabled" if playlists_only else "readonly"

        self.music_dest_entry.config(state=state)
        self.music_dest_browse_btn.config(state=state)
        self.convert_mp3_checkbox.config(state=state)
        self.skip_existing_checkbox.config(state=state)
        self.ffmpeg_btn.config(state=state)
        self.quality_combo.config(state=combo_state)

    def _on_convert_mp3_changed(self) -> None:
        """Handle conversion checkbox change - check for FFmpeg."""
        if self.convert_mp3_var.get():
            has_ffmpeg = self._check_ffmpeg()
            if not has_ffmpeg:
                messagebox.showwarning(
                    "FFmpeg Required",
                    "FFmpeg is required for audio conversion but was not found.\n\n"
                    "Install FFmpeg:\n"
                    "- Windows: https://ffmpeg.org/download.html\n"
                    "- Or use: winget install ffmpeg\n\n"
                    "After installing, restart the application."
                )
                self.root.after(100, lambda: self.convert_mp3_var.set(False))

    def _check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available."""
        try:
            process_args = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "creationflags": subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            }
            subprocess.run(["ffmpeg", "-version"], **process_args, timeout=10)
            return True
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return False

    def _check_ffmpeg_ui(self) -> None:
        """Check FFmpeg availability and show result in UI."""
        self.analysis_text.delete(1.0, tk.END)
        self.analysis_text.insert(tk.END, "Checking FFmpeg installation...\n\n")
        self.root.update_idletasks()

        try:
            process_args = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "creationflags": subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            }
            result = subprocess.run(["ffmpeg", "-version"], **process_args, timeout=10)
            output = result.stdout.decode('utf-8', errors='replace')

            # Extract version info
            version_line = output.split('\n')[0] if output else "Unknown version"
            self.analysis_text.insert(tk.END, f"FFmpeg found: {version_line}\n")
            self.ffmpeg_status_var.set("FFmpeg OK")
            logger.info(f"FFmpeg available: {version_line}")

        except FileNotFoundError:
            self.analysis_text.insert(tk.END, "FFmpeg NOT FOUND!\n\n")
            self.analysis_text.insert(tk.END, "Install FFmpeg:\n")
            self.analysis_text.insert(tk.END, "- Windows: https://ffmpeg.org/download.html\n")
            self.analysis_text.insert(tk.END, "- Or use: winget install ffmpeg\n")
            self.analysis_text.insert(tk.END, "- macOS: brew install ffmpeg\n")
            self.analysis_text.insert(tk.END, "- Linux: apt install ffmpeg\n")
            self.ffmpeg_status_var.set("FFmpeg NOT FOUND")
            self.convert_mp3_var.set(False)

        except Exception as e:
            self.analysis_text.insert(tk.END, f"Error checking FFmpeg: {e}\n")
            self.ffmpeg_status_var.set("Error")

    def _save_settings(self) -> None:
        """Save current UI settings to config."""
        selected = [
            self.playlist_tree.item(item, "text")
            for item in self.playlist_tree.selection()
        ]

        self.config_manager.update_settings(
            itunes_xml_path=self.itunes_xml_var.get(),
            destination_path=self.dest_var.get(),
            music_destination_path=self.music_dest_var.get(),
            source_music_prefix=self.source_prefix_var.get(),
            android_music_prefix=self.android_prefix_var.get(),
            use_relative_paths=self.relative_paths_var.get(),
            selected_playlists=selected,
            sync_mode=self.sync_mode_var.get(),
            convert_to_mp3=self.convert_mp3_var.get(),
            skip_existing=self.skip_existing_var.get(),
            mp3_bitrate=self.bitrate_var.get()
        )
        self.status_var.set("Settings saved")
        messagebox.showinfo("Settings Saved", "Configuration saved successfully!")

    def _load_playlists(self) -> None:
        """Load playlists from iTunes XML into the treeview."""
        xml_path = self.itunes_xml_var.get()
        if not xml_path or not os.path.exists(xml_path):
            messagebox.showerror("Error", "Please select a valid iTunes/MusicBee XML file first!")
            return

        self.status_var.set("Loading playlists...")
        self.analysis_text.delete(1.0, tk.END)

        # Clear existing data
        for item in self.playlist_tree.get_children():
            self.playlist_tree.delete(item)
        self.all_playlists = []
        self.playlist_data = {}
        self.tracks_dict = {}

        try:
            # Parse the XML file
            self.analysis_text.insert(tk.END, f"Loading: {xml_path}\n\n")
            self.root.update_idletasks()

            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
                self.itunes_root = ET.fromstring(xml_content)

            library_dict = next((child for child in self.itunes_root if child.tag == 'dict'), None)
            if library_dict is None:
                messagebox.showerror("Error", "Invalid iTunes XML format!")
                return

            # First, build tracks dictionary for track lookups
            self._build_tracks_dict(library_dict)

            # Find playlists
            playlists_element = None
            for i in range(len(library_dict)):
                if library_dict[i].tag == 'key' and library_dict[i].text == 'Playlists':
                    if i + 1 < len(library_dict) and library_dict[i + 1].tag == 'array':
                        playlists_element = library_dict[i + 1]
                    break

            if playlists_element is not None:
                auto_generated = {
                    "Library", "Music", "Liked Songs", "Recently Added",
                    "Top 100 Most Played", "Recently Played", "My Top Rated",
                    "Downloaded", "Audiobooks", "Podcasts", "Movies", "TV Shows"
                }

                for playlist_dict in playlists_element:
                    if playlist_dict.tag == 'dict':
                        playlist_name = None
                        playlist_id = None
                        track_count = 0
                        track_ids = []
                        is_smart = False
                        is_master = False
                        is_folder = False

                        # Extract playlist information
                        for i in range(0, len(playlist_dict), 2):
                            if i + 1 < len(playlist_dict) and playlist_dict[i].tag == 'key':
                                key = playlist_dict[i].text
                                value_element = playlist_dict[i + 1]

                                if key == 'Name':
                                    playlist_name = value_element.text
                                elif key == 'Playlist ID':
                                    playlist_id = value_element.text
                                elif key == 'Playlist Items' and value_element.tag == 'array':
                                    track_count = len(value_element)
                                    # Extract track IDs
                                    for item in value_element:
                                        if item.tag == 'dict':
                                            for j in range(0, len(item), 2):
                                                if j + 1 < len(item) and item[j].tag == 'key' and item[j].text == 'Track ID':
                                                    if item[j + 1].text:
                                                        track_ids.append(item[j + 1].text)
                                elif key == 'Smart Info':
                                    is_smart = True
                                elif key == 'Master':
                                    is_master = True
                                elif key == 'Folder':
                                    is_folder = True

                        if playlist_name and not is_folder:
                            # Determine playlist type
                            if is_master:
                                playlist_type = "Master"
                            elif playlist_name in auto_generated or playlist_name.startswith("Top 25 "):
                                playlist_type = "System"
                            elif is_smart:
                                playlist_type = "Smart"
                            else:
                                playlist_type = "User"

                            self.all_playlists.append(playlist_name)
                            self.playlist_data[playlist_name] = {
                                'id': playlist_id,
                                'track_count': track_count,
                                'track_ids': track_ids,
                                'type': playlist_type,
                                'is_smart': is_smart,
                                'is_master': is_master
                            }

                            # Add to treeview
                            self.playlist_tree.insert(
                                "", "end",
                                text=playlist_name,
                                values=(track_count, playlist_type)
                            )

                self.analysis_text.insert(tk.END, f"Found {len(self.all_playlists)} playlists\n")
                self.analysis_text.insert(tk.END, f"Total tracks in library: {len(self.tracks_dict)}\n\n")

                # Show breakdown by type
                type_counts = {}
                for data in self.playlist_data.values():
                    t = data['type']
                    type_counts[t] = type_counts.get(t, 0) + 1

                self.analysis_text.insert(tk.END, "Playlist types:\n")
                for t, count in sorted(type_counts.items()):
                    self.analysis_text.insert(tk.END, f"  {t}: {count}\n")

                self.status_var.set(f"Loaded {len(self.all_playlists)} playlists")

                # Auto-select playlists
                self._auto_select_playlists()
                self._filter_playlists()

            else:
                messagebox.showerror("Error", "No playlists found in XML!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load playlists: {str(e)}")
            self.status_var.set("Error loading playlists")
            logger.error(f"Error loading playlists: {e}")

    def _build_tracks_dict(self, library_dict) -> None:
        """Build a dictionary of track ID -> track info from the iTunes XML."""
        tracks_element = None
        for i in range(len(library_dict)):
            if library_dict[i].tag == 'key' and library_dict[i].text == 'Tracks':
                if i + 1 < len(library_dict) and library_dict[i + 1].tag == 'dict':
                    tracks_element = library_dict[i + 1]
                break

        if tracks_element is None:
            return

        for i in range(0, len(tracks_element), 2):
            if i + 1 >= len(tracks_element):
                break

            if tracks_element[i].tag == 'key' and tracks_element[i + 1].tag == 'dict':
                track_id = tracks_element[i].text
                track_dict = tracks_element[i + 1]

                track_info = {}
                for j in range(0, len(track_dict), 2):
                    if j + 1 >= len(track_dict):
                        break

                    if track_dict[j].tag == 'key':
                        key = track_dict[j].text
                        value_element = track_dict[j + 1]

                        if key == 'Location':
                            # Decode the file:// URL
                            location = value_element.text
                            if location:
                                # Convert file://localhost/M:/... to M:/...
                                if location.startswith('file://localhost/'):
                                    location = urllib.parse.unquote(location[17:])
                                elif location.startswith('file:///'):
                                    location = urllib.parse.unquote(location[8:])
                                elif location.startswith('file://'):
                                    location = urllib.parse.unquote(location[7:])
                                track_info['location'] = location
                        elif key == 'Name':
                            track_info['name'] = value_element.text
                        elif key == 'Artist':
                            track_info['artist'] = value_element.text

                if track_info:
                    self.tracks_dict[track_id] = track_info

    def _filter_playlists(self, *args) -> None:
        """Filter displayed playlists based on search term."""
        filter_text = self.filter_var.get().lower()

        # Store current selections
        selected_playlists = set()
        for item in self.playlist_tree.selection():
            playlist_name = self.playlist_tree.item(item, "text")
            selected_playlists.add(playlist_name)

        # Clear and repopulate treeview
        for item in self.playlist_tree.get_children():
            self.playlist_tree.delete(item)

        for playlist_name in self.all_playlists:
            if not filter_text or filter_text in playlist_name.lower():
                playlist_info = self.playlist_data.get(playlist_name, {})
                track_count = playlist_info.get('track_count', 0)
                playlist_type = playlist_info.get('type', 'User')

                item_id = self.playlist_tree.insert(
                    "", "end",
                    text=playlist_name,
                    values=(track_count, playlist_type)
                )

                # Restore selection
                if playlist_name in selected_playlists:
                    self.playlist_tree.selection_add(item_id)

        self._update_selection_summary()

    def _update_selection_summary(self) -> None:
        """Update the selection summary text."""
        if not self.all_playlists:
            self.selection_summary.set("No playlists loaded")
            return

        selected_items = self.playlist_tree.selection()
        total_playlists = len(self.all_playlists)
        selected_count = len(selected_items)

        # Calculate total tracks
        playlists_to_process = self._get_selected_playlists()
        total_tracks = sum(
            self.playlist_data.get(name, {}).get('track_count', 0)
            for name in playlists_to_process
        )

        if self.selection_mode.get() == "include":
            if selected_count == 0:
                self.selection_summary.set(f"No playlists selected (0/{total_playlists})")
            else:
                self.selection_summary.set(
                    f"Will sync {selected_count}/{total_playlists} playlists ({total_tracks} total tracks)"
                )
        else:  # exclude mode
            processed_count = total_playlists - selected_count
            if selected_count == 0:
                self.selection_summary.set(
                    f"Will sync all {total_playlists} playlists ({total_tracks} total tracks)"
                )
            else:
                self.selection_summary.set(
                    f"Will sync {processed_count}/{total_playlists} playlists (excluding {selected_count})"
                )

        # Update sync button state
        if hasattr(self, 'sync_btn'):
            if self.selection_mode.get() == "include" and selected_count == 0:
                self.sync_btn.config(state=tk.DISABLED)
            else:
                self.sync_btn.config(state=tk.NORMAL)

    def _get_selected_playlists(self) -> List[str]:
        """Get the list of playlists that should be processed."""
        selected_items = self.playlist_tree.selection()
        selected_playlists = [
            self.playlist_tree.item(item, "text")
            for item in selected_items
        ]

        if self.selection_mode.get() == "include":
            return selected_playlists
        else:
            # Exclude mode - return all except selected
            all_visible = [
                self.playlist_tree.item(item, "text")
                for item in self.playlist_tree.get_children()
            ]
            return [p for p in all_visible if p not in selected_playlists]

    def _select_all_playlists(self) -> None:
        """Select all visible playlists."""
        items = self.playlist_tree.get_children()
        self.playlist_tree.selection_set(items)
        self._update_selection_summary()

    def _clear_all_playlists(self) -> None:
        """Clear all playlist selections."""
        self.playlist_tree.selection_remove(self.playlist_tree.selection())
        self._update_selection_summary()

    def _auto_select_playlists(self) -> None:
        """Auto-select playlists (those starting with numbers 1-9)."""
        self._clear_all_playlists()

        for item in self.playlist_tree.get_children():
            playlist_name = self.playlist_tree.item(item, "text")

            # Only select playlists that start with a digit 1-9
            if playlist_name and len(playlist_name) > 0:
                first_char = playlist_name[0]
                if first_char.isdigit() and first_char != '0':
                    self.playlist_tree.selection_add(item)

        self._update_selection_summary()

    def _preview_selection(self) -> None:
        """Show a preview of what will be synced."""
        selected_playlists = self._get_selected_playlists()

        if not selected_playlists:
            messagebox.showwarning("No Selection", "No playlists are selected for sync!")
            return

        # Create preview window
        preview_window = tk.Toplevel(self.root)
        preview_window.title("Sync Preview")
        preview_window.geometry("550x450")
        preview_window.transient(self.root)

        # Create text widget with scrollbar
        text_frame = ttk.Frame(preview_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        preview_text = tk.Text(text_frame, wrap=tk.WORD)
        preview_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=preview_text.yview)
        preview_text.config(yscrollcommand=preview_scroll.set)

        preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Populate preview
        preview_text.insert(tk.END, f"Sync Preview - {len(selected_playlists)} playlists selected\n")
        preview_text.insert(tk.END, "=" * 50 + "\n\n")

        preview_text.insert(tk.END, f"Destination: {self.dest_var.get()}\n")
        preview_text.insert(tk.END, f"Path mapping: {self.source_prefix_var.get()} → {self.android_prefix_var.get()}\n\n")

        total_tracks = 0
        for playlist_name in selected_playlists:
            playlist_info = self.playlist_data.get(playlist_name, {})
            track_count = playlist_info.get('track_count', 0)
            playlist_type = playlist_info.get('type', 'Unknown')

            preview_text.insert(tk.END, f"• {playlist_name}\n")
            preview_text.insert(tk.END, f"  Type: {playlist_type}, Tracks: {track_count}\n")
            preview_text.insert(tk.END, f"  Output: {playlist_name}.m3u\n\n")
            total_tracks += track_count

        preview_text.insert(tk.END, f"\nTotal tracks across all playlists: {total_tracks}\n")
        preview_text.insert(tk.END, "(Note: Duplicate tracks will appear in each playlist)")

        preview_text.config(state=tk.DISABLED)

        # Close button
        ttk.Button(preview_window, text="Close", command=preview_window.destroy).pack(pady=10)

    def _get_relative_path(self, source_path: str) -> str:
        """Get relative path from source prefix for file organization."""
        source_prefix = self.source_prefix_var.get().replace('\\', '/')
        path = source_path.replace('\\', '/')

        if path.lower().startswith(source_prefix.lower()):
            return path[len(source_prefix):].lstrip('/')
        elif len(path) > 2 and path[1] == ':':
            return path[3:].lstrip('/')
        return os.path.basename(path)

    def _get_dest_file_path(self, source_path: str, convert_to_mp3: bool) -> str:
        """Calculate destination path for a source file."""
        music_dest = self.music_dest_var.get().strip()
        relative_path = self._get_relative_path(source_path)

        # Change extension if converting
        if convert_to_mp3:
            file_ext = os.path.splitext(relative_path)[1].lower()
            if file_ext in LOSSLESS_EXTENSIONS:
                relative_path = os.path.splitext(relative_path)[0] + '.mp3'

        return os.path.join(music_dest, relative_path)

    def _find_cover_art(self, source_path: str) -> Optional[str]:
        """Find cover art file in the same folder as the source file."""
        source_dir = os.path.dirname(source_path)

        # Common cover art filenames (in priority order)
        cover_names = [
            'cover.jpg', 'cover.jpeg', 'cover.png',
            'folder.jpg', 'folder.jpeg', 'folder.png',
            'album.jpg', 'album.jpeg', 'album.png',
            'front.jpg', 'front.jpeg', 'front.png',
            'albumart.jpg', 'albumart.jpeg', 'albumart.png',
            'Cover.jpg', 'Cover.jpeg', 'Cover.png',
            'Folder.jpg', 'Folder.jpeg', 'Folder.png',
        ]

        for name in cover_names:
            cover_path = os.path.join(source_dir, name)
            if os.path.exists(cover_path):
                return cover_path

        # Also check for any jpg/png in the folder as fallback
        try:
            for f in os.listdir(source_dir):
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    return os.path.join(source_dir, f)
        except OSError:
            pass

        return None

    def _source_has_embedded_art(self, source_path: str) -> bool:
        """Check if the source file has embedded cover art."""
        try:
            process_args = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "creationflags": subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            }
            # Use ffprobe to check for video/image streams (cover art)
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                 "stream=codec_type", "-of", "csv=p=0", source_path],
                **process_args, timeout=30
            )
            # If there's output, there's a video/image stream (cover art)
            return bool(result.stdout.decode('utf-8', errors='replace').strip())
        except Exception:
            return False

    def _convert_to_mp3(self, source_path: str, dest_path: str) -> bool:
        """Convert an audio file to MP3 using FFmpeg, preserving/embedding cover art."""
        try:
            # Ensure destination directory exists
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

            # Build FFmpeg command based on bitrate setting
            bitrate = self.bitrate_var.get()

            # Check for cover art sources
            has_embedded_art = self._source_has_embedded_art(source_path)
            external_cover = self._find_cover_art(source_path) if not has_embedded_art else None

            # Build the FFmpeg command
            cmd = ["ffmpeg", "-y", "-i", source_path]

            # Add external cover art as input if found
            if external_cover:
                cmd.extend(["-i", external_cover])

            # Audio encoding settings
            if bitrate.startswith("V"):
                # VBR mode (V0, V2, etc.)
                quality = bitrate[1]  # Extract number
                cmd.extend(["-c:a", "libmp3lame", "-q:a", quality])
            else:
                # CBR mode (320k, 256k, etc.)
                cmd.extend(["-c:a", "libmp3lame", "-b:a", bitrate])

            # Handle cover art embedding
            if has_embedded_art:
                # Source has embedded art - copy it to output
                cmd.extend([
                    "-c:v", "copy",           # Copy the image stream
                    "-map", "0:a",            # Map audio from input 0
                    "-map", "0:v?",           # Map video (cover) from input 0 if exists
                    "-id3v2_version", "3",    # Use ID3v2.3 for better compatibility
                    "-metadata:s:v", "title=Album cover",
                    "-metadata:s:v", "comment=Cover (front)",
                ])
            elif external_cover:
                # Use external cover art file
                cmd.extend([
                    "-c:v", "mjpeg" if external_cover.lower().endswith(('.jpg', '.jpeg')) else "png",
                    "-map", "0:a",            # Map audio from input 0
                    "-map", "1:v",            # Map video (cover) from input 1
                    "-id3v2_version", "3",    # Use ID3v2.3 for better compatibility
                    "-metadata:s:v", "title=Album cover",
                    "-metadata:s:v", "comment=Cover (front)",
                ])
            else:
                # No cover art available
                cmd.extend(["-vn"])  # No video/image output

            # Copy metadata from source
            cmd.extend(["-map_metadata", "0", dest_path])

            process_args = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "creationflags": subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            }

            result = subprocess.run(cmd, **process_args, timeout=300)

            if result.returncode == 0 and os.path.exists(dest_path):
                return True
            else:
                logger.error(f"FFmpeg conversion failed for {source_path}: {result.stderr.decode('utf-8', errors='replace')}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"FFmpeg timeout converting {source_path}")
            return False
        except Exception as e:
            logger.error(f"Error converting {source_path}: {e}")
            return False

    def _copy_file(self, source_path: str, dest_path: str) -> bool:
        """Copy a file to destination."""
        try:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(source_path, dest_path)
            return True
        except Exception as e:
            logger.error(f"Error copying {source_path}: {e}")
            return False

    def _translate_path(self, windows_path: str) -> str:
        """Translate a Windows path to an Android-compatible path."""
        path = windows_path.strip()

        # Normalize path separators
        path = path.replace('\\', '/')

        if self.relative_paths_var.get():
            # Return just the filename
            return os.path.basename(path)

        # Replace source prefix with Android prefix
        source_prefix = self.source_prefix_var.get().replace('\\', '/')
        android_prefix = self.android_prefix_var.get()

        # Case-insensitive prefix replacement
        if path.lower().startswith(source_prefix.lower()):
            path = android_prefix + path[len(source_prefix):]
        elif len(path) > 2 and path[1] == ':':
            # Handle drive letter
            path = android_prefix + path[3:]

        # Ensure forward slashes
        path = path.replace('\\', '/')

        return path

    def _write_m3u8_playlist(self, playlist_name: str, track_ids: List[str], output_path: str,
                              path_mapping: Optional[Dict[str, str]] = None) -> Tuple[bool, int]:
        """Write a playlist to M3U/M3U8 format optimized for PowerAmp.

        Args:
            playlist_name: Name of the playlist
            track_ids: List of track IDs
            output_path: Path to write the M3U file
            path_mapping: Optional dict mapping source paths to android paths (for converted files)
        """
        try:
            tracks_written = 0

            # Write with UTF-8 BOM for better compatibility with Android apps
            with open(output_path, 'w', encoding='utf-8-sig') as f:
                # Write M3U header - PowerAmp reads #PLAYLIST: for the display name
                # No blank lines between header directives for better compatibility
                f.write('#EXTM3U\n')
                f.write(f'#PLAYLIST:{playlist_name}\n')

                for track_id in track_ids:
                    track_info = self.tracks_dict.get(track_id, {})
                    location = track_info.get('location', '')

                    if location:
                        # Use path mapping if available, otherwise translate directly
                        if path_mapping and location in path_mapping:
                            android_path = path_mapping[location]
                        else:
                            android_path = self._translate_path(location)

                        # Write EXTINF line with track info if available
                        name = track_info.get('name', os.path.basename(location))
                        artist = track_info.get('artist', '')
                        if artist:
                            f.write(f'#EXTINF:-1,{artist} - {name}\n')
                        else:
                            f.write(f'#EXTINF:-1,{name}\n')

                        f.write(f'{android_path}\n')
                        tracks_written += 1

            return True, tracks_written

        except Exception as e:
            logger.error(f"Error writing playlist {playlist_name}: {e}")
            return False, 0

    def _start_sync(self) -> None:
        """Start the sync process."""
        selected_playlists = self._get_selected_playlists()

        if not selected_playlists:
            messagebox.showwarning("No Selection", "Please select at least one playlist to sync.")
            return

        playlist_dest = self.dest_var.get().strip()
        if not playlist_dest:
            messagebox.showwarning("No Destination", "Please specify a playlist destination folder.")
            return

        music_dest = self.music_dest_var.get().strip()
        convert_to_mp3 = self.convert_mp3_var.get()
        playlists_only = self.sync_mode_var.get() == "playlists_only"
        sync_music = not playlists_only and bool(music_dest)

        # Validate music sync settings
        if not playlists_only and not music_dest:
            messagebox.showwarning("No Music Destination",
                "Please specify a music destination folder, or select 'Playlists Only' mode.")
            return

        if sync_music and convert_to_mp3:
            if not self._check_ffmpeg():
                messagebox.showerror(
                    "FFmpeg Not Found",
                    "FFmpeg is required for audio conversion but was not found.\n\n"
                    "Either install FFmpeg or disable the conversion option."
                )
                return

        # Create destinations if needed
        try:
            os.makedirs(playlist_dest, exist_ok=True)
            if sync_music:
                os.makedirs(music_dest, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"Cannot create destination folder:\n{e}")
            return

        # Build confirmation message
        if playlists_only:
            msg_parts = [f"Export {len(selected_playlists)} playlist(s) (playlists only)"]
        else:
            msg_parts = [f"Sync {len(selected_playlists)} playlist(s)"]
            msg_parts.append(f"\nMusic files to: {music_dest}")
            if convert_to_mp3:
                msg_parts.append(f"\nConvert FLAC/WAV to MP3 ({self.bitrate_var.get()})")
        msg_parts.append(f"\nPlaylists to: {playlist_dest}")
        msg_parts.append("\n\nProceed?")

        if not messagebox.askyesno("Confirm Sync", "".join(msg_parts)):
            return

        # Start sync in thread
        self.syncing = True
        self.sync_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        self.load_btn.config(state=tk.DISABLED)

        self.sync_text.delete(1.0, tk.END)
        self.results_notebook.select(1)  # Switch to Sync Progress tab

        def sync_thread():
            path_mapping = {}  # source path -> android path
            playlist_success = 0
            playlist_error = 0

            self._append_sync_text(f"Starting sync of {len(selected_playlists)} playlist(s)...\n")
            if sync_music:
                self._append_sync_text(f"Music destination: {music_dest}\n")
                if convert_to_mp3:
                    self._append_sync_text(f"Converting lossless audio to MP3 ({self.bitrate_var.get()})\n")
            self._append_sync_text(f"Playlist destination: {playlist_dest}\n")
            self._append_sync_text(f"Path mapping: {self.source_prefix_var.get()} → {self.android_prefix_var.get()}\n")
            self._append_sync_text("=" * 50 + "\n\n")

            # Phase 1: Sync music files if enabled
            if sync_music:
                self._append_sync_text("PHASE 1: Syncing music files...\n")

                # Gather unique tracks from all selected playlists
                unique_tracks = {}  # source_path -> track_info
                for playlist_name in selected_playlists:
                    playlist_info = self.playlist_data.get(playlist_name, {})
                    for track_id in playlist_info.get('track_ids', []):
                        track_info = self.tracks_dict.get(track_id, {})
                        location = track_info.get('location', '')
                        if location and location not in unique_tracks:
                            unique_tracks[location] = track_info

                total_tracks = len(unique_tracks)
                self._append_sync_text(f"Found {total_tracks} unique tracks to sync\n\n")

                copied_count = 0
                converted_count = 0
                skipped_count = 0
                error_count = 0
                skip_existing = self.skip_existing_var.get()

                for i, (source_path, track_info) in enumerate(unique_tracks.items()):
                    if not self.syncing:
                        self._append_sync_text("\nSync cancelled by user.\n")
                        break

                    # Update status
                    self.root.after(0, lambda n=i+1, t=total_tracks:
                                    self.status_var.set(f"Syncing music {n}/{t}"))

                    file_ext = os.path.splitext(source_path)[1].lower()
                    needs_conversion = convert_to_mp3 and file_ext in LOSSLESS_EXTENSIONS
                    dest_path = self._get_dest_file_path(source_path, convert_to_mp3)

                    # Calculate android path for playlist mapping
                    relative_from_music_dest = os.path.relpath(dest_path, music_dest)
                    android_path = self.android_prefix_var.get() + relative_from_music_dest.replace('\\', '/')
                    path_mapping[source_path] = android_path

                    # Check if file exists
                    if skip_existing and os.path.exists(dest_path):
                        skipped_count += 1
                        continue

                    # Check if source file exists
                    if not os.path.exists(source_path):
                        self._append_sync_text(f"✗ Missing: {os.path.basename(source_path)}\n")
                        error_count += 1
                        continue

                    # Copy or convert
                    filename = os.path.basename(source_path)
                    if needs_conversion:
                        self._append_sync_text(f"Converting: {filename}...")
                        if self._convert_to_mp3(source_path, dest_path):
                            self._append_sync_text(" OK\n")
                            converted_count += 1
                        else:
                            self._append_sync_text(" FAILED\n")
                            error_count += 1
                    else:
                        if self._copy_file(source_path, dest_path):
                            copied_count += 1
                        else:
                            self._append_sync_text(f"✗ Failed to copy: {filename}\n")
                            error_count += 1

                # Music sync summary
                self._append_sync_text(f"\nMusic sync complete:\n")
                self._append_sync_text(f"  Converted: {converted_count}\n")
                self._append_sync_text(f"  Copied: {copied_count}\n")
                self._append_sync_text(f"  Skipped (existing): {skipped_count}\n")
                if error_count > 0:
                    self._append_sync_text(f"  Errors: {error_count}\n")
                self._append_sync_text("\n" + "=" * 50 + "\n\n")

                if not self.syncing:
                    self.root.after(0, self._sync_complete)
                    return

            # Phase 2: Write playlists
            phase_num = "2" if sync_music else "1"
            self._append_sync_text(f"PHASE {phase_num}: Writing playlists...\n\n")

            for i, playlist_name in enumerate(selected_playlists):
                if not self.syncing:
                    self._append_sync_text("\nSync cancelled by user.\n")
                    break

                self.root.after(0, lambda n=i+1, t=len(selected_playlists), p=playlist_name:
                                self.status_var.set(f"Writing playlist {n}/{t}: {p}"))

                playlist_info = self.playlist_data.get(playlist_name, {})
                track_ids = playlist_info.get('track_ids', [])

                # Create output path
                output_filename = f"{playlist_name}.m3u"
                output_filename = re.sub(r'[<>:"/\\|?*]', '_', output_filename)
                output_path = os.path.join(playlist_dest, output_filename)

                # Use path mapping if music was synced, otherwise None
                mapping = path_mapping if sync_music else None
                success, tracks_written = self._write_m3u8_playlist(playlist_name, track_ids, output_path, mapping)

                if success:
                    playlist_success += 1
                    self._append_sync_text(f"✓ {playlist_name} ({tracks_written} tracks)\n")
                else:
                    playlist_error += 1
                    self._append_sync_text(f"✗ {playlist_name} - Failed to write\n")

            # Final summary
            self._append_sync_text("\n" + "=" * 50 + "\n")
            self._append_sync_text(f"Sync complete!\n")
            self._append_sync_text(f"  Playlists written: {playlist_success}\n")
            if playlist_error > 0:
                self._append_sync_text(f"  Playlist errors: {playlist_error}\n")

            self.root.after(0, self._sync_complete)

        threading.Thread(target=sync_thread, daemon=True).start()

    def _append_sync_text(self, text: str) -> None:
        """Append text to sync output (thread-safe)."""
        self.root.after(0, lambda: self._do_append_sync_text(text))

    def _do_append_sync_text(self, text: str) -> None:
        """Actually append text to sync output."""
        self.sync_text.insert(tk.END, text)
        self.sync_text.see(tk.END)
        self.root.update_idletasks()

    def _sync_complete(self) -> None:
        """Handle sync completion."""
        self.syncing = False
        self.sync_btn.config(state=tk.NORMAL)
        self.cancel_btn.config(state=tk.DISABLED)
        self.load_btn.config(state=tk.NORMAL)
        self.status_var.set("Sync complete")

        messagebox.showinfo("Sync Complete", "Playlists have been synced to PowerAmp format!")

    def _cancel_sync(self) -> None:
        """Cancel the current sync operation."""
        self.syncing = False
        self.status_var.set("Cancelling...")

    def _on_closing(self) -> None:
        """Handle window close event."""
        if self.syncing:
            if not messagebox.askyesno("Quit", "A sync is in progress. Are you sure you want to quit?"):
                return
            self.syncing = False

        self.root.destroy()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main application entry point."""
    setup_shared_logging("poweramp_sync")

    root = tk.Tk()
    app = PowerAmpSyncApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
