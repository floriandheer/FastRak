#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PipelineScript_Traktor_SyncPlaylists.py
Description: UI wrapper for iTunes/Music Playlist Sync functionality with improved playlist selection and FLAC conversion with album art
"""

import os
import sys
import time
import datetime
import argparse
import threading
import shutil
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET
import urllib.parse
import re
import subprocess
import tempfile
import copy

# Setup logging
def setup_logging():
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format)
    return logging.getLogger("PlaylistSyncScript")

logger = setup_logging()
VALID_EXTENSIONS = {'.mp3', '.flac', '.wav', '.aiff', '.m4a', '.ogg', '.opus'}

class PlaylistSyncUI:
    def __init__(self, root):
        self.root = root
        self.root.title("iTunes Playlist Sync Tool")
        self.root.geometry("900x1100")
        self.root.minsize(900, 800)
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header_frame.grid_propagate(False)
        
        title_label = tk.Label(header_frame, text="iTunes Playlist Sync Tool", 
                             font=("Arial", 16, "bold"), fg="white", bg="#2c3e50")
        title_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        self.create_config_panel(main_frame)
        self.create_results_panel(main_frame)
        
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, 
                                 relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=2, column=0, sticky="ew")
        
        self.syncing = False
        self.initialize_default_paths()
        self.all_playlists = []  # Will be populated when analyzing XML
        self.playlist_data = {}  # Store playlist metadata
        self.itunes_root = None  # Store the XML root for reuse
        
    def initialize_default_paths(self):
        possible_itunes_paths = [
            "~/Music/iTunes/iTunes Music Library.xml",
            "~/Music/iTunes/iTunes Library.xml",
            "~/My Music/iTunes/iTunes Music Library.xml",
            os.path.join(os.environ.get('USERPROFILE', ''), 'Music', 'iTunes', 'iTunes Music Library.xml'),
            os.path.join(os.environ.get('USERPROFILE', ''), 'My Music', 'iTunes', 'iTunes Music Library.xml'),
            "M:\\iTunes Music Library.xml"
        ]
        
        for path in possible_itunes_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                self.itunes_xml_var.set(expanded_path)
                break
        
        default_dj_path = os.path.join(os.environ.get('USERPROFILE', ''), 'Music')
        self.dj_library_var.set(os.path.join(default_dj_path, 'DJ Library'))
        self.export_xml_var.set(os.path.join(default_dj_path, 'DJ Library.xml'))

    def create_config_panel(self, parent):
        config_frame = ttk.LabelFrame(parent, text="Configuration")
        config_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        config_frame.columnconfigure(1, weight=1)
        
        current_row = 0
        
        # Target OS Selection
        ttk.Label(config_frame, text="Target OS:").grid(row=current_row, column=0, sticky="w", padx=10, pady=10)
        self.target_os_var = tk.StringVar(value="Windows")
        os_dropdown = ttk.Combobox(config_frame, textvariable=self.target_os_var, 
                                   values=["Windows", "Mac"], state="readonly", width=20)
        os_dropdown.grid(row=current_row, column=1, sticky="w", padx=5, pady=10)
        os_dropdown.bind("<<ComboboxSelected>>", self.on_target_os_changed)
        
        # Info label for cross-platform workflow
        self.os_info_label = ttk.Label(config_frame, text="", foreground="blue", font=("Arial", 9))
        self.os_info_label.grid(row=current_row, column=2, sticky="w", padx=5, pady=10)
        
        current_row += 1
        
        # iTunes XML path
        ttk.Label(config_frame, text="iTunes XML:").grid(row=current_row, column=0, sticky="w", padx=10, pady=10)
        self.itunes_xml_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.itunes_xml_var, width=50).grid(row=current_row, column=1, sticky="ew", padx=5, pady=10)
        ttk.Button(config_frame, text="Browse", command=self.browse_itunes_xml).grid(row=current_row, column=2, padx=5, pady=10)
        
        current_row += 1
        
        # DJ Library path
        ttk.Label(config_frame, text="DJ Library Folder:").grid(row=current_row, column=0, sticky="w", padx=10, pady=10)
        self.dj_library_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.dj_library_var, width=50).grid(row=current_row, column=1, sticky="ew", padx=5, pady=10)
        ttk.Button(config_frame, text="Browse", command=self.browse_dj_library).grid(row=current_row, column=2, padx=5, pady=10)
        
        current_row += 1
        
        # Export XML path
        ttk.Label(config_frame, text="Export XML:").grid(row=current_row, column=0, sticky="w", padx=10, pady=10)
        self.export_xml_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.export_xml_var, width=50).grid(row=current_row, column=1, sticky="ew", padx=5, pady=10)
        ttk.Button(config_frame, text="Browse", command=self.browse_export_xml).grid(row=current_row, column=2, padx=5, pady=10)
        
        current_row += 1
        
        # Mac-specific paths frame (initially hidden)
        self.mac_paths_frame = ttk.LabelFrame(config_frame, text="Mac Destination Paths (for XML references)")
        self.mac_paths_frame.grid(row=current_row, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        self.mac_paths_frame.columnconfigure(1, weight=1)
        self.mac_paths_frame.grid_remove()  # Hidden by default
        
        # Mac DJ Library path
        ttk.Label(self.mac_paths_frame, text="Mac DJ Library:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        self.mac_dj_library_var = tk.StringVar(value="/Users/flori/Music/DJ Library")
        ttk.Entry(self.mac_paths_frame, textvariable=self.mac_dj_library_var, width=50).grid(row=0, column=1, sticky="ew", padx=5, pady=10)
        
        ttk.Label(self.mac_paths_frame, text="Example: /Users/flori/Music/DJ Library", 
                 foreground="gray", font=("Arial", 8)).grid(row=1, column=1, sticky="w", padx=5, pady=0)
        
        current_row += 1
        
        # Options section
        options_frame = ttk.LabelFrame(config_frame, text="Options")
        options_frame.grid(row=current_row, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        
        self.debug_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Show detailed info for missing tracks", variable=self.debug_var).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        self.skip_existing_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Skip copying files that already exist", variable=self.skip_existing_var).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        
        self.convert_flac_var = tk.BooleanVar(value=True)
        # Add a trace to the checkbox to check FFmpeg when enabled
        self.convert_flac_var.trace('w', self.check_ffmpeg_for_flac_conversion)
        ttk.Checkbutton(options_frame, text="Convert audio files to FLAC format with album art", variable=self.convert_flac_var).grid(row=2, column=0, sticky="w", padx=10, pady=5)
        
        self.preserve_album_art_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Embed album art (from file or cover.jpg/png in folder)", variable=self.preserve_album_art_var).grid(row=3, column=0, sticky="w", padx=10, pady=5)
        
        current_row += 1
        
        # IMPROVED Playlist selection section
        playlist_frame = ttk.LabelFrame(config_frame, text="Playlist Selection")
        playlist_frame.grid(row=current_row, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)
        playlist_frame.columnconfigure(0, weight=1)
        playlist_frame.rowconfigure(2, weight=1)
        
        # Selection mode
        mode_frame = ttk.Frame(playlist_frame)
        mode_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        ttk.Label(mode_frame, text="Selection Mode:").grid(row=0, column=0, sticky="w", padx=5)
        self.selection_mode = tk.StringVar(value="include")
        ttk.Radiobutton(mode_frame, text="Include Selected", variable=self.selection_mode, 
                       value="include", command=self.update_selection_mode).grid(row=0, column=1, padx=10)
        ttk.Radiobutton(mode_frame, text="Exclude Selected", variable=self.selection_mode, 
                       value="exclude", command=self.update_selection_mode).grid(row=0, column=2, padx=10)
        
        # Filter and stats
        filter_frame = ttk.Frame(playlist_frame)
        filter_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        filter_frame.columnconfigure(1, weight=1)
        
        ttk.Label(filter_frame, text="Filter:").grid(row=0, column=0, sticky="w", padx=5)
        self.filter_var = tk.StringVar()
        self.filter_var.trace('w', self.filter_playlists)
        ttk.Entry(filter_frame, textvariable=self.filter_var).grid(row=0, column=1, sticky="ew", padx=5)
        
        # Selection summary label
        self.selection_summary = tk.StringVar()
        self.selection_summary.set("No playlists loaded")
        ttk.Label(filter_frame, textvariable=self.selection_summary, font=("Arial", 9), 
                 foreground="blue").grid(row=0, column=2, padx=10, sticky="e")
        
        # Single listbox with checkboxes (simulated with selection)
        list_frame = ttk.Frame(playlist_frame)
        list_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Create Treeview for better playlist display
        self.playlist_tree = ttk.Treeview(list_frame, columns=("tracks", "type"), show="tree headings", height=10)
        self.playlist_tree.grid(row=0, column=0, sticky="nsew")
        
        # Configure columns
        self.playlist_tree.heading("#0", text="Playlist Name")
        self.playlist_tree.heading("tracks", text="Tracks")
        self.playlist_tree.heading("type", text="Type")
        
        self.playlist_tree.column("#0", width=300)
        self.playlist_tree.column("tracks", width=80, anchor="center")
        self.playlist_tree.column("type", width=100, anchor="center")
        
        # Scrollbar for treeview
        tree_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.playlist_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.playlist_tree.config(yscrollcommand=tree_scroll.set)
        
        # Buttons frame
        btn_frame = ttk.Frame(playlist_frame)
        btn_frame.grid(row=3, column=0, sticky="ew", pady=5)
        btn_frame.columnconfigure(2, weight=1)
        
        ttk.Button(btn_frame, text="Select All", command=self.select_all_playlists).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Clear All", command=self.clear_all_playlists).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="Auto Select", command=self.auto_select_playlists).grid(row=0, column=2, padx=5)
        ttk.Button(btn_frame, text="Preview Selection", command=self.preview_selection).grid(row=0, column=3, padx=5)
        
        # Main action buttons
        main_btn_frame = ttk.Frame(config_frame)
        main_btn_frame.grid(row=current_row+1, column=0, columnspan=3, sticky="ew", pady=10)
        main_btn_frame.columnconfigure(1, weight=1)
        
        self.check_ffmpeg_btn = ttk.Button(main_btn_frame, text="Check FFmpeg", command=self.check_ffmpeg_ui, width=15)
        self.check_ffmpeg_btn.grid(row=0, column=0, padx=10)
        
        self.load_playlists_btn = ttk.Button(main_btn_frame, text="Load Playlists", command=self.load_playlists, width=15)
        self.load_playlists_btn.grid(row=0, column=1, padx=10)
        
        self.sync_btn = ttk.Button(main_btn_frame, text="Start Sync", command=self.start_sync, width=15)
        self.sync_btn.grid(row=0, column=2, padx=10)
        
        # Initialize Mac paths visibility
        self.on_target_os_changed()

    def on_target_os_changed(self, event=None):
        """Handle target OS selection change"""
        target_os = self.target_os_var.get()
        
        if target_os == "Mac":
            self.mac_paths_frame.grid()
            self.os_info_label.config(text="Export to USB/local, then copy to Mac")
        else:
            self.mac_paths_frame.grid_remove()
            self.os_info_label.config(text="")

    def update_selection_mode(self):
        """Update the UI when selection mode changes"""
        self.update_selection_summary()
    
    def update_selection_summary(self):
        """Update the selection summary text"""
        if not self.all_playlists:
            self.selection_summary.set("No playlists loaded")
            return
            
        selected_items = self.playlist_tree.selection()
        total_playlists = len(self.all_playlists)
        selected_count = len(selected_items)
        
        if self.selection_mode.get() == "include":
            if selected_count == 0:
                self.selection_summary.set(f"⚠️ No playlists selected (0/{total_playlists})")
            else:
                self.selection_summary.set(f"✓ Will sync {selected_count}/{total_playlists} playlists")
        else:  # exclude mode
            processed_count = total_playlists - selected_count
            if selected_count == 0:
                self.selection_summary.set(f"✓ Will sync all {total_playlists} playlists")
            else:
                self.selection_summary.set(f"✓ Will sync {processed_count}/{total_playlists} playlists (excluding {selected_count})")
        
        # Update button states
        if hasattr(self, 'sync_btn'):
            if self.selection_mode.get() == "include" and selected_count == 0:
                self.sync_btn.config(state=tk.DISABLED)
            else:
                self.sync_btn.config(state=tk.NORMAL)

    def select_all_playlists(self):
        """Select all visible playlists"""
        items = self.playlist_tree.get_children()
        self.playlist_tree.selection_set(items)
        self.update_selection_summary()

    def clear_all_playlists(self):
        """Clear all playlist selections"""
        self.playlist_tree.selection_remove(self.playlist_tree.selection())
        self.update_selection_summary()

    def auto_select_playlists(self):
        """Auto-select playlists (only those starting with numbers 1-9)"""
        self.clear_all_playlists()
        
        for item in self.playlist_tree.get_children():
            playlist_name = self.playlist_tree.item(item, "text")
            
            # Only select playlists that start with a digit 1-9
            # Exclude playlists that don't start with a number or start with 0
            if playlist_name and len(playlist_name) > 0:
                first_char = playlist_name[0]
                if first_char.isdigit() and first_char != '0':
                    self.playlist_tree.selection_add(item)
        
        self.update_selection_summary()

    def preview_selection(self):
        """Show a preview of what will be synced"""
        selected_playlists = self.get_selected_playlists()
        
        if not selected_playlists:
            messagebox.showwarning("No Selection", "No playlists are selected for sync!")
            return
        
        # Create preview window
        preview_window = tk.Toplevel(self.root)
        preview_window.title("Sync Preview")
        preview_window.geometry("500x400")
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
        preview_text.insert(tk.END, "="*50 + "\n\n")
        
        total_tracks = 0
        for playlist_name in selected_playlists:
            playlist_info = self.playlist_data.get(playlist_name, {})
            track_count = playlist_info.get('track_count', 0)
            playlist_type = playlist_info.get('type', 'Unknown')
            
            preview_text.insert(tk.END, f"• {playlist_name}\n")
            preview_text.insert(tk.END, f"  Type: {playlist_type}, Tracks: {track_count}\n\n")
            total_tracks += track_count
        
        preview_text.insert(tk.END, f"Total tracks across all playlists: {total_tracks}\n")
        preview_text.insert(tk.END, "(Note: Duplicate tracks will only be copied once)")
        
        preview_text.config(state=tk.DISABLED)
        
        # Close button
        ttk.Button(preview_window, text="Close", command=preview_window.destroy).pack(pady=10)

    def filter_playlists(self, *args):
        """Filter displayed playlists based on search term"""
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
                
                item_id = self.playlist_tree.insert("", "end", text=playlist_name, 
                                                   values=(track_count, playlist_type))
                
                # Restore selection if it was selected before
                if playlist_name in selected_playlists:
                    self.playlist_tree.selection_add(item_id)
        
        self.update_selection_summary()
        
        # Bind selection event to update summary
        self.playlist_tree.bind('<<TreeviewSelect>>', lambda e: self.update_selection_summary())

    def get_selected_playlists(self):
        """Get the list of playlists that should be processed based on current selection"""
        selected_items = self.playlist_tree.selection()
        selected_playlists = []
        
        for item in selected_items:
            playlist_name = self.playlist_tree.item(item, "text")
            selected_playlists.append(playlist_name)
        
        if self.selection_mode.get() == "include":
            # Only process selected playlists
            return selected_playlists
        else:
            # Process all playlists except selected ones
            all_visible_playlists = []
            for item in self.playlist_tree.get_children():
                playlist_name = self.playlist_tree.item(item, "text")
                all_visible_playlists.append(playlist_name)
            
            return [p for p in all_visible_playlists if p not in selected_playlists]

    def check_ffmpeg_for_flac_conversion(self, *args):
        """Check if FFmpeg is available when FLAC conversion is enabled"""
        if self.convert_flac_var.get():  # If the checkbox was checked
            has_ffmpeg = self.check_ffmpeg()
            if not has_ffmpeg:
                messagebox.showwarning(
                    "FFmpeg Not Found", 
                    "FFmpeg is not installed or not in your PATH. FLAC conversion will not work.\n\n"
                    "To enable FLAC conversion, please install FFmpeg:\n"
                    "- Windows: https://ffmpeg.org/download.html\n"
                    "- macOS: brew install ffmpeg\n"
                    "- Linux: apt-get install ffmpeg or equivalent\n\n"
                    "The FLAC conversion option has been disabled."
                )
                # Disable the checkbox without triggering this function again
                self.root.after(100, lambda: self.convert_flac_var.set(False))

    def create_results_panel(self, parent):
        results_frame = ttk.LabelFrame(parent, text="Sync Progress and Results")
        results_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        self.results_notebook = ttk.Notebook(results_frame)
        self.results_notebook.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        self.analysis_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(self.analysis_frame, text="Library Analysis")
        self.analysis_frame.columnconfigure(0, weight=1)
        self.analysis_frame.rowconfigure(0, weight=1)
        
        self.analysis_text = tk.Text(self.analysis_frame, wrap=tk.WORD)
        self.analysis_text.grid(row=0, column=0, sticky="nsew")
        
        analysis_scrollbar = ttk.Scrollbar(self.analysis_frame, command=self.analysis_text.yview)
        analysis_scrollbar.grid(row=0, column=1, sticky="ns")
        self.analysis_text.config(yscrollcommand=analysis_scrollbar.set)
        
        self.sync_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(self.sync_frame, text="Sync Progress")
        self.sync_frame.columnconfigure(0, weight=1)
        self.sync_frame.rowconfigure(0, weight=1)
        
        self.sync_text = tk.Text(self.sync_frame, wrap=tk.WORD)
        self.sync_text.grid(row=0, column=0, sticky="nsew")
        
        sync_scrollbar = ttk.Scrollbar(self.sync_frame, command=self.sync_text.yview)
        sync_scrollbar.grid(row=0, column=1, sticky="ns")
        self.sync_text.config(yscrollcommand=sync_scrollbar.set)
        
        self.xml_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(self.xml_frame, text="XML Export")
        self.xml_frame.columnconfigure(0, weight=1)
        self.xml_frame.rowconfigure(0, weight=1)
        
        self.xml_text = tk.Text(self.xml_frame, wrap=tk.WORD)
        self.xml_text.grid(row=0, column=0, sticky="nsew")
        
        xml_scrollbar = ttk.Scrollbar(self.xml_frame, command=self.xml_text.yview)
        xml_scrollbar.grid(row=0, column=1, sticky="ns")
        self.xml_text.config(yscrollcommand=xml_scrollbar.set)

    def browse_itunes_xml(self):
        filename = filedialog.askopenfilename(
            title="Select iTunes XML Library",
            filetypes=[("XML Files", "*.xml"), ("All Files", "*.*")]
        )
        if filename:
            self.itunes_xml_var.set(filename)
            self.load_playlists()
    
    def browse_dj_library(self):
        directory = filedialog.askdirectory(title="Select DJ Library Folder")
        if directory:
            self.dj_library_var.set(directory)
            self.export_xml_var.set(os.path.join(directory, 'DJ Library.xml'))
    
    def browse_export_xml(self):
        filename = filedialog.asksaveasfilename(
            title="Select Export XML Location",
            defaultextension=".xml",
            filetypes=[("XML Files", "*.xml"), ("All Files", "*.*")]
        )
        if filename:
            self.export_xml_var.set(filename)

    def load_playlists(self):
        """Load playlists from iTunes XML into the treeview"""
        xml_path = self.itunes_xml_var.get()
        if not xml_path or not os.path.exists(xml_path):
            messagebox.showerror("Error", "Please select a valid iTunes XML file first!")
            return
        
        self.status_var.set("Loading playlists...")
        
        # Clear existing data
        for item in self.playlist_tree.get_children():
            self.playlist_tree.delete(item)
        self.all_playlists = []
        self.playlist_data = {}
        
        try:
            # Parse the XML file and store the root
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
                self.itunes_root = ET.fromstring(xml_content)
                
            library_dict = next((child for child in self.itunes_root if child.tag == 'dict'), None)
            if library_dict is None:
                messagebox.showerror("Error", "Invalid iTunes XML format!")
                return
                
            playlists_element = None
            for i in range(len(library_dict)):
                if library_dict[i].tag == 'key' and library_dict[i].text == 'Playlists':
                    if i + 1 < len(library_dict) and library_dict[i + 1].tag == 'array':
                        playlists_element = library_dict[i + 1]
                    break
                    
            if playlists_element is not None:
                auto_generated = {"Library", "Music", "Liked Songs", "Recently Added", 
                                "Top 100 Most Played", "Recently Played", "My Top Rated"}
                
                for playlist_dict in playlists_element:
                    if playlist_dict.tag == 'dict':
                        playlist_name = None
                        playlist_id = None
                        track_count = 0
                        is_smart = False
                        is_master = False
                        
                        # Extract playlist information
                        for i in range(0, len(playlist_dict), 2):
                            if i+1 < len(playlist_dict) and playlist_dict[i].tag == 'key':
                                key = playlist_dict[i].text
                                value_element = playlist_dict[i+1]
                                
                                if key == 'Name':
                                    playlist_name = value_element.text
                                elif key == 'Playlist ID':
                                    playlist_id = value_element.text
                                elif key == 'Playlist Items' and value_element.tag == 'array':
                                    track_count = len(value_element)
                                elif key == 'Smart Info':
                                    is_smart = True
                                elif key == 'Master':
                                    is_master = True
                        
                        if playlist_name:
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
                                'type': playlist_type,
                                'is_smart': is_smart,
                                'is_master': is_master
                            }
                            
                            # Add to treeview
                            item_id = self.playlist_tree.insert("", "end", text=playlist_name, 
                                                               values=(track_count, playlist_type))
                
                self.status_var.set(f"Loaded {len(self.all_playlists)} playlists")
                self.auto_select_playlists()  # Auto-select user playlists
                self.filter_playlists()  # Apply initial filtering
            else:
                messagebox.showerror("Error", "No playlists found in XML!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load playlists: {str(e)}")
            self.status_var.set("Error loading playlists")

    def get_subprocess_args(self):
        """Get platform-specific arguments for subprocess to hide console windows"""
        process_args = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE
        }
        
        # On Windows, add creationflags to hide the console window
        if sys.platform == "win32":
            process_args["creationflags"] = 0x08000000  # CREATE_NO_WINDOW flag
            
        return process_args

    def check_ffmpeg_ui(self):
        self.status_var.set("Checking for FFmpeg...")
        
        self.analysis_text.delete(1.0, tk.END)
        self.analysis_text.insert(tk.END, "Checking for FFmpeg...\n\n")
        self.root.update_idletasks()
        
        try:
            process_args = self.get_subprocess_args()
            result = subprocess.run(["ffmpeg", "-version"], **process_args)
            version_output = result.stdout.decode()
            version_info = version_output.split('\n')[0] if version_output else "Unknown version"
            
            self.analysis_text.insert(tk.END, f"✓ FFmpeg is installed and available\n\n")
            self.analysis_text.insert(tk.END, f"Version information:\n{version_info}\n\n")
            self.analysis_text.insert(tk.END, "You can enable FLAC conversion with album art embedding in the options.")
            
            self.status_var.set("FFmpeg check complete - Available")
        except FileNotFoundError:
            self.analysis_text.insert(tk.END, "✗ FFmpeg is NOT installed or not in your PATH.\n\n")
            self.analysis_text.insert(tk.END, "Audio conversion to FLAC will be disabled.\n\n")
            self.analysis_text.insert(tk.END, "To enable FLAC conversion, please install FFmpeg:\n")
            self.analysis_text.insert(tk.END, "- Windows: https://ffmpeg.org/download.html\n")
            self.analysis_text.insert(tk.END, "- macOS: brew install ffmpeg\n")
            self.analysis_text.insert(tk.END, "- Linux: apt-get install ffmpeg or equivalent\n")
            
            self.convert_flac_var.set(False)
            self.status_var.set("FFmpeg check complete - Not available")
        except Exception as e:
            self.analysis_text.insert(tk.END, f"Error checking for FFmpeg: {e}\n")
            self.status_var.set("Error checking for FFmpeg")

    def start_sync(self):
        itunes_xml = self.itunes_xml_var.get()
        dj_library = self.dj_library_var.get()
        export_xml = self.export_xml_var.get()
        
        if not itunes_xml or not os.path.exists(itunes_xml):
            messagebox.showerror("Error", "iTunes XML file not found!")
            return
        
        if not dj_library:
            messagebox.showerror("Error", "Please specify a DJ Library folder!")
            return
        
        if not export_xml:
            messagebox.showerror("Error", "Please specify an export XML path!")
            return
        
        # Check playlist selection
        selected_playlists = self.get_selected_playlists()
        if not selected_playlists:
            messagebox.showerror("Error", "No playlists selected for sync!")
            return
        
        # Make sure the export_xml path is a file, not a directory
        if os.path.isdir(export_xml):
            export_xml = os.path.join(export_xml, "DJ Library.xml")
            self.export_xml_var.set(export_xml)
            messagebox.showinfo("XML Path Updated", 
                               f"Export path was a directory. Updated to: {export_xml}")
        
        # Check if we have write permissions for the XML file's directory
        export_dir = os.path.dirname(export_xml)
        if export_dir and not os.access(export_dir, os.W_OK):
            alt_path = os.path.join(os.path.expanduser("~"), "Documents", "DJ Library.xml")
            response = messagebox.askquestion("Permission Issue", 
                                            f"No write permission for {export_dir}. Would you like to save to {alt_path} instead?")
            if response == 'yes':
                self.export_xml_var.set(alt_path)
                export_xml = alt_path
            else:
                messagebox.showinfo("Sync Cancelled", "Please select a writable location for the XML export.")
                return
        
        if not os.path.exists(dj_library):
            try:
                os.makedirs(dj_library)
                self.analysis_text.insert(tk.END, f"Created DJ Library folder: {dj_library}\n")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create DJ Library folder: {e}")
                return
        
        self.sync_btn.config(state=tk.DISABLED)
        self.check_ffmpeg_btn.config(state=tk.DISABLED)
        self.load_playlists_btn.config(state=tk.DISABLED)
        self.syncing = True
        
        self.analysis_text.delete(1.0, tk.END)
        self.sync_text.delete(1.0, tk.END)
        self.xml_text.delete(1.0, tk.END)
        
        thread = threading.Thread(target=self.sync_process, daemon=True)
        thread.start()

    def sync_process(self):
        try:
            itunes_xml = self.itunes_xml_var.get()
            dj_library = self.dj_library_var.get()
            export_xml = self.export_xml_var.get()
            
            debug_missing = self.debug_var.get()
            skip_existing = self.skip_existing_var.get()
            convert_to_flac = self.convert_flac_var.get()
            preserve_album_art = self.preserve_album_art_var.get()
            
            # Check for FFmpeg at the beginning if FLAC conversion is enabled
            if convert_to_flac:
                self.append_to_text_widget(self.analysis_text, "Checking for FFmpeg...\n")
                has_ffmpeg = self.check_ffmpeg()
                if not has_ffmpeg:
                    # Show a warning dialog
                    self.root.after(0, lambda: messagebox.showwarning(
                        "FFmpeg Not Found", 
                        "FLAC conversion is enabled but FFmpeg is not installed.\n"
                        "FLAC conversion will be disabled for this sync."
                    ))
                    
                    self.append_to_text_widget(self.analysis_text, "FLAC conversion disabled due to missing FFmpeg.\n")
                    convert_to_flac = False
                    self.root.after(0, lambda: self.convert_flac_var.set(False))
            
            start_time = time.time()
            
            self.status_var.set("Step 1: Analyzing iTunes Library...")
            self.append_to_text_widget(self.analysis_text, "===== STEP 1: ANALYZING ITUNES LIBRARY =====\n")
            self.results_notebook.select(0)
            
            # Modified to return more detailed information
            selected_playlist_data, tracks_to_copy, tracks_metadata = self.analyze_library(
                itunes_xml, debug_missing)
            
            step1_time = time.time() - start_time
            self.append_to_text_widget(self.analysis_text, f"Step 1 completed in {step1_time:.2f} seconds\n\n")
            
            if tracks_to_copy:
                self.status_var.set("Step 2: Updating DJ Library...")
                self.append_to_text_widget(self.sync_text, "===== STEP 2: UPDATING DJ LIBRARY =====\n")
                self.results_notebook.select(1)
                
                step2_start = time.time()
                synced_tracks, file_mapping = self.update_dj_library(
                    tracks_to_copy, dj_library, skip_existing, convert_to_flac, preserve_album_art)
                
                step2_time = time.time() - step2_start
                self.append_to_text_widget(self.sync_text, f"Step 2 completed in {step2_time:.2f} seconds\n\n")
                
                if synced_tracks:
                    self.status_var.set("Step 3: Creating updated XML...")
                    self.append_to_text_widget(self.xml_text, "===== STEP 3: CREATING UPDATED XML =====\n")
                    self.results_notebook.select(2)
                    
                    step3_start = time.time()
                    self.create_new_xml(
                        itunes_xml, export_xml, selected_playlist_data, tracks_metadata, file_mapping, dj_library)
                    
                    step3_time = time.time() - step3_start
                    self.append_to_text_widget(self.xml_text, f"Step 3 completed in {step3_time:.2f} seconds\n\n")
            
            total_time = time.time() - start_time
            self.append_to_text_widget(self.xml_text, f"\nTotal sync process completed in {total_time:.2f} seconds\n")
            self.status_var.set("Sync complete!")
            
            self.root.after(0, lambda: messagebox.showinfo("Sync Complete", 
                f"Playlist Sync completed in {total_time:.2f} seconds."))
            
        except Exception as e:
            error_msg = f"Error during sync process: {str(e)}"
            logger.error(error_msg)
            self.append_to_text_widget(self.sync_text, f"\n{error_msg}\n")
            self.status_var.set("Error during sync")
            self.root.after(0, lambda: messagebox.showerror("Sync Error", error_msg))
        
        finally:
            self.root.after(0, self.enable_buttons)
            self.syncing = False
    
    def enable_buttons(self):
        self.sync_btn.config(state=tk.NORMAL)
        self.check_ffmpeg_btn.config(state=tk.NORMAL)
        self.load_playlists_btn.config(state=tk.NORMAL)
    
    def append_to_text_widget(self, text_widget, message):
        def update_text():
            text_widget.insert(tk.END, message)
            text_widget.see(tk.END)
            text_widget.update_idletasks()
        self.root.after(0, update_text)
    
    def check_ffmpeg(self):
        try:
            process_args = self.get_subprocess_args()
            subprocess.run(["ffmpeg", "-version"], **process_args)
            return True
        except:
            return False
    
    def safe_int_conversion(self, value):
        """Safely convert a value to an integer, handling decimal points."""
        try:
            # First try direct conversion
            return int(value)
        except ValueError:
            try:
                # If it has a decimal point, convert to float first then int
                return int(float(value))
            except (ValueError, TypeError):
                # If all else fails, return 0 or some default value
                return 0

    def get_track_title(self, track_path):
        """Extract track title from audio file metadata using ffprobe"""
        try:
            process_args = self.get_subprocess_args()
            
            # Use ffprobe to extract metadata
            result = subprocess.run([
                "ffprobe",
                "-v", "quiet",
                "-show_entries", "format_tags=title",
                "-of", "csv=p=0",
                track_path
            ], **process_args)
            
            if result.returncode == 0 and result.stdout:
                title = result.stdout.decode('utf-8').strip()
                if title and title != "N/A":
                    return self.sanitize_filename(title)
            
            # Fallback: try different tag variations
            for tag in ["TITLE", "Title", "title"]:
                result = subprocess.run([
                    "ffprobe",
                    "-v", "quiet",
                    "-show_entries", f"format_tags={tag}",
                    "-of", "csv=p=0",
                    track_path
                ], **process_args)
                
                if result.returncode == 0 and result.stdout:
                    title = result.stdout.decode('utf-8').strip()
                    if title and title != "N/A":
                        return self.sanitize_filename(title)
            
            # If no title found, return None to use original filename
            return None
            
        except Exception as e:
            self.append_to_text_widget(self.sync_text, f"Warning: Could not extract title from {os.path.basename(track_path)}: {e}\n")
            return None

    def sanitize_filename(self, title):
        """Sanitize track title for use as filename"""
        # Remove or replace invalid filename characters
        invalid_chars = '<>:"/\\|?*'
        sanitized = title
        
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '')
        
        # Replace multiple spaces with single space
        sanitized = ' '.join(sanitized.split())
        
        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip('. ')
        
        # Limit length to avoid filesystem issues
        if len(sanitized) > 200:
            sanitized = sanitized[:200].strip()
        
        # If sanitization results in empty string, return None
        if not sanitized:
            return None
            
        return sanitized

    def find_album_art(self, track_path):
        """Find album art for a track - either embedded or external cover files"""
        album_art_path = None
        
        # First check for external cover files in the same directory
        track_dir = os.path.dirname(track_path)
        cover_files = ['cover.jpg', 'cover.jpeg', 'cover.png', 'folder.jpg', 'folder.png', 
                      'albumart.jpg', 'albumart.png', 'Cover.jpg', 'Cover.png']
        
        for cover_file in cover_files:
            potential_cover = os.path.join(track_dir, cover_file)
            if os.path.exists(potential_cover):
                album_art_path = potential_cover
                break
        
        return album_art_path

    def extract_embedded_art(self, source_path, temp_dir):
        """Extract embedded album art from audio file using FFmpeg"""
        try:
            # Create a temporary file for the extracted art
            art_path = os.path.join(temp_dir, "embedded_art.jpg")
            
            process_args = self.get_subprocess_args()
            
            # Try to extract embedded artwork
            result = subprocess.run([
                "ffmpeg",
                "-i", source_path,
                "-an",  # No audio
                "-vcodec", "copy",
                "-y",  # Overwrite output
                art_path
            ], **process_args)
            
            if result.returncode == 0 and os.path.exists(art_path) and os.path.getsize(art_path) > 0:
                return art_path
            else:
                return None
                
        except Exception as e:
            self.append_to_text_widget(self.sync_text, f"Warning: Could not extract embedded art: {e}\n")
            return None
    
    def analyze_library(self, xml_path, debug_missing=True):
        """
        Analyze the iTunes library XML and extract the selected playlists and their tracks.
        This is a complete rewrite of get_playlist_tracks to properly extract all needed data.
        """
        self.append_to_text_widget(self.analysis_text, f"Analyzing iTunes XML: {xml_path}...\n")
        
        try:
            # Check if we already parsed the XML in load_playlists
            if self.itunes_root is None:
                with open(xml_path, 'r', encoding='utf-8') as f:
                    self.itunes_root = ET.fromstring(f.read())
        except Exception as e:
            self.append_to_text_widget(self.analysis_text, f"Error parsing XML: {e}\n")
            return [], [], {}

        # Get the main dictionary element
        library_dict = next((child for child in self.itunes_root if child.tag == 'dict'), None)
        if library_dict is None:
            self.append_to_text_widget(self.analysis_text, "Invalid iTunes XML structure: missing main dict\n")
            return [], [], {}

        # First, extract all tracks from the library
        tracks_metadata = {}
        tracks_to_copy = []
        track_ids_to_paths = {}
        
        # Find the Tracks dictionary
        tracks_element = None
        for i in range(len(library_dict)):
            if library_dict[i].tag == 'key' and library_dict[i].text == 'Tracks':
                if i + 1 < len(library_dict) and library_dict[i + 1].tag == 'dict':
                    tracks_element = library_dict[i + 1]
                break
                
        if tracks_element is None:
            self.append_to_text_widget(self.analysis_text, "No tracks found in iTunes XML\n")
            return [], [], {}
            
        # Process all tracks
        self.append_to_text_widget(self.analysis_text, "Processing tracks from iTunes library...\n")
        total_tracks = 0
        valid_tracks = 0
        
        # Extract track data
        for i in range(0, len(tracks_element), 2):
            if i+1 >= len(tracks_element):
                break
                
            if tracks_element[i].tag == 'key' and tracks_element[i+1].tag == 'dict':
                track_id = tracks_element[i].text
                track_dict = tracks_element[i+1]
                
                # Create a dictionary to store this track's metadata
                track_data = {}
                location = None
                file_path = None
                
                # Extract all properties for this track
                for j in range(0, len(track_dict), 2):
                    if j+1 >= len(track_dict):
                        break
                        
                    if track_dict[j].tag == 'key':
                        key = track_dict[j].text
                        value_element = track_dict[j+1]
                        
                        # Store the value based on its type
                        if value_element.tag == 'string':
                            track_data[key] = value_element.text
                        elif value_element.tag == 'integer':
                            # Use safe conversion for integers
                            try:
                                track_data[key] = self.safe_int_conversion(value_element.text)
                            except:
                                track_data[key] = 0
                        elif value_element.tag == 'date':
                            track_data[key] = value_element.text
                        elif value_element.tag == 'true':
                            track_data[key] = True
                        elif value_element.tag == 'false':
                            track_data[key] = False
                        
                        # If this is a location, decode the URL
                        if key == 'Location' and value_element.text:
                            location = value_element.text
                            if location.startswith("file://localhost/"):
                                file_path = urllib.parse.unquote(location.replace("file://localhost/", ""))
                            elif location.startswith("file:///"):
                                file_path = urllib.parse.unquote(location.replace("file:///", ""))
                            else:
                                file_path = urllib.parse.unquote(location)
                                if file_path.startswith("file://"):
                                    file_path = file_path.replace("file://", "")
                            
                            # Convert to Windows path format
                            file_path = file_path.replace("/", "\\")
                
                total_tracks += 1
                
                # Store this track's metadata using its ID
                track_id_num = str(track_data.get('Track ID', ''))  # Make sure it's a string
                if track_id_num:
                    tracks_metadata[track_id_num] = track_data
                    
                    # If this track has a valid location, store it
                    if file_path:
                        track_data['file_path'] = file_path
                        track_data['exists'] = os.path.isfile(file_path)
                        track_data['location'] = location
                        file_ext = os.path.splitext(file_path)[1].lower()
                        track_data['extension'] = file_ext
                        
                        # Check if this is a valid audio file that we want to copy
                        if file_ext in VALID_EXTENSIONS and os.path.isfile(file_path):
                            valid_tracks += 1
                            track_ids_to_paths[track_id_num] = file_path
                
                # Log progress every 500 tracks
                if total_tracks % 500 == 0:
                    self.append_to_text_widget(
                        self.analysis_text, 
                        f"Processed {total_tracks} tracks ({valid_tracks} valid)...\n"
                    )
        
        self.append_to_text_widget(
            self.analysis_text, 
            f"Found {valid_tracks} valid audio tracks out of {total_tracks} total tracks\n"
        )
        
        # Now extract the selected playlists
        selected_playlist_data = []
        selected_playlists = self.get_selected_playlists()
        
        self.append_to_text_widget(
            self.analysis_text, 
            f"Selected playlists to process: {', '.join(selected_playlists)}\n"
        )
        
        # Find the Playlists array
        playlists_element = None
        for i in range(len(library_dict)):
            if library_dict[i].tag == 'key' and library_dict[i].text == 'Playlists':
                if i + 1 < len(library_dict) and library_dict[i + 1].tag == 'array':
                    playlists_element = library_dict[i + 1]
                break
                
        if playlists_element is None:
            self.append_to_text_widget(self.analysis_text, "No playlists found in iTunes XML\n")
            return [], [], {}
        
        # Process playlists
        self.append_to_text_widget(self.analysis_text, "Processing selected playlists...\n")
        missing_tracks = {}
        playlist_count = 0
        
        for playlist_dict in playlists_element:
            if playlist_dict.tag != 'dict':
                continue
                
            # Extract playlist metadata
            playlist_data = {}
            playlist_items = []
            
            for j in range(0, len(playlist_dict), 2):
                if j+1 >= len(playlist_dict):
                    break
                    
                if playlist_dict[j].tag == 'key':
                    key = playlist_dict[j].text
                    value_element = playlist_dict[j+1]
                    
                    if key == 'Name' and value_element.tag == 'string':
                        playlist_data['Name'] = value_element.text
                    elif key == 'Playlist ID' and value_element.tag == 'integer':
                        # Use safe conversion
                        try:
                            playlist_data['ID'] = self.safe_int_conversion(value_element.text)
                        except:
                            playlist_data['ID'] = 0
                    elif key == 'Playlist Items' and value_element.tag == 'array':
                        # Extract all track IDs in this playlist
                        for item_dict in value_element:
                            if item_dict.tag == 'dict':
                                for k in range(0, len(item_dict), 2):
                                    if k+1 >= len(item_dict):
                                        break
                                    if item_dict[k].text == 'Track ID' and item_dict[k+1].tag == 'integer':
                                        # Use safe conversion
                                        try:
                                            track_id = str(self.safe_int_conversion(item_dict[k+1].text))
                                            playlist_items.append(track_id)
                                        except:
                                            # Just skip problematic track IDs
                                            pass
            
            playlist_name = playlist_data.get('Name', 'Unknown')
            playlist_id = playlist_data.get('ID', 'Unknown')
            
            # FIXED: Check if this playlist should be included based on our selection
            if playlist_name in selected_playlists:
                playlist_count += 1
                valid_tracks_in_playlist = 0
                missing_tracks_in_playlist = 0
                
                # Add the valid tracks from this playlist to our list of tracks to copy
                for track_id in playlist_items:
                    if track_id in track_ids_to_paths:
                        # This is a valid track - add it to our copy list
                        tracks_to_copy.append(track_ids_to_paths[track_id])
                        valid_tracks_in_playlist += 1
                    else:
                        # This track is missing or invalid - track for debugging
                        missing_tracks_in_playlist += 1
                        if debug_missing:
                            if track_id not in missing_tracks:
                                if track_id in tracks_metadata:
                                    track_info = tracks_metadata[track_id]
                                    missing_tracks[track_id] = {
                                        'name': track_info.get('Name', 'Unknown'),
                                        'artist': track_info.get('Artist', 'Unknown'),
                                        'playlists': [playlist_name]
                                    }
                                else:
                                    missing_tracks[track_id] = {
                                        'error': "Track ID not found in library",
                                        'playlists': [playlist_name]
                                    }
                            else:
                                missing_tracks[track_id]['playlists'].append(playlist_name)
                
                # Store information about this playlist
                selected_playlist_data.append({
                    'name': playlist_name,
                    'id': playlist_id,
                    'track_ids': playlist_items
                })
                
                self.append_to_text_widget(
                    self.analysis_text,
                    f"✓ Playlist: {playlist_name} (ID: {playlist_id}) with {len(playlist_items)} tracks " + 
                    f"({valid_tracks_in_playlist} valid, {missing_tracks_in_playlist} missing)\n"
                )
            else:
                self.append_to_text_widget(self.analysis_text, f"- Skipping playlist: {playlist_name}\n")
        
        # Remove duplicates from tracks_to_copy
        tracks_to_copy = list(set(tracks_to_copy))
        
        self.append_to_text_widget(
            self.analysis_text, 
            f"\nSelected {playlist_count} playlists with {len(tracks_to_copy)} unique valid tracks\n"
        )
        
        # Report on missing tracks
        if debug_missing and missing_tracks:
            self.append_to_text_widget(self.analysis_text, "\n==== MISSING TRACKS ANALYSIS ====\n")
            self.append_to_text_widget(self.analysis_text, f"Total missing tracks: {len(missing_tracks)}\n")
            
            # Categorize missing tracks
            no_location_count = 0
            file_not_found_count = 0
            unsupported_format_count = 0
            other_error_count = 0
            
            for track_id, info in missing_tracks.items():
                if "error" in info:
                    other_error_count += 1
                elif track_id in tracks_metadata:
                    track_info = tracks_metadata[track_id]
                    if 'Location' not in track_info:
                        no_location_count += 1
                    elif not track_info.get('exists', False):
                        file_not_found_count += 1
                    elif track_info.get('extension') not in VALID_EXTENSIONS:
                        unsupported_format_count += 1
                    else:
                        other_error_count += 1
                else:
                    other_error_count += 1
            
            self.append_to_text_widget(self.analysis_text, f"  - Tracks with no file location: {no_location_count}\n")
            self.append_to_text_widget(self.analysis_text, f"  - Files not found on disk: {file_not_found_count}\n")
            self.append_to_text_widget(self.analysis_text, f"  - Unsupported file formats: {unsupported_format_count}\n")
            self.append_to_text_widget(self.analysis_text, f"  - Other errors: {other_error_count}\n\n")
            
            # If detailed debugging is enabled, show more info
            if self.debug_var.get():
                self.append_to_text_widget(self.analysis_text, "Detailed missing tracks information:\n")
                for track_id, info in missing_tracks.items():
                    track_name = info.get("name", "Unknown")
                    artist = info.get("artist", "Unknown")
                    playlists = ", ".join(info.get("playlists", []))
                    
                    if "error" in info:
                        self.append_to_text_widget(self.analysis_text, 
                            f"Track ID {track_id}: {info['error']} (Playlists: {playlists})\n")
                    elif track_id in tracks_metadata:
                        track_info = tracks_metadata[track_id]
                        if 'Location' not in track_info:
                            self.append_to_text_widget(self.analysis_text, 
                                f"'{track_name}' by {artist} has no file location (Playlists: {playlists})\n")
                        elif not track_info.get('exists', False):
                            self.append_to_text_widget(self.analysis_text, 
                                f"'{track_name}' by {artist} - file not found: {track_info.get('file_path', 'Unknown')} (Playlists: {playlists})\n")
                        elif track_info.get('extension') not in VALID_EXTENSIONS:
                            self.append_to_text_widget(self.analysis_text, 
                                f"'{track_name}' by {artist} - unsupported format: {track_info.get('extension', 'Unknown')} (Playlists: {playlists})\n")
                        else:
                            self.append_to_text_widget(self.analysis_text, 
                                f"'{track_name}' by {artist} - unknown error (Playlists: {playlists})\n")
        
        return selected_playlist_data, tracks_to_copy, tracks_metadata
    
    def update_dj_library(self, tracks, dj_library, skip_existing=True, convert_to_flac=True, preserve_album_art=True):
        """Update the DJ Library by copying tracks and optionally converting to FLAC with album art"""
        self.append_to_text_widget(self.sync_text, f"Updating {dj_library} with {len(tracks)} tracks...\n")
        if not tracks:
            self.append_to_text_widget(self.sync_text, "No tracks to copy!\n")
            return [], {}

        if not os.path.exists(dj_library):
            os.makedirs(dj_library)
            self.append_to_text_widget(self.sync_text, f"Created DJ Library directory: {dj_library}\n")

        copied_count = 0
        converted_count = 0
        skipped_count = 0
        skipped_flac_count = 0
        error_count = 0
        album_art_embedded_count = 0
        synced_tracks = []
        
        # Create a mapping from original file path to DJ library path
        file_mapping = {}
        
        total_tracks = len(tracks)
        track_list = list(tracks)
        
        # Create a temporary directory for album art operations
        temp_dir = tempfile.mkdtemp()
        
        try:
            for i, track_path in enumerate(track_list):
                try:
                    file_ext = os.path.splitext(track_path)[1].lower()
                    original_base_name = os.path.splitext(os.path.basename(track_path))[0]
                    
                    # Extract track title from metadata
                    track_title = self.get_track_title(track_path)
                    base_name = track_title if track_title else original_base_name
                    
                    dest_ext = ".flac" if convert_to_flac and file_ext != '.flac' else file_ext
                    dest_path = os.path.join(dj_library, base_name + dest_ext)
                    
                    # Check if file already exists and we should skip it
                    if os.path.exists(dest_path) and skip_existing:
                        # File exists and we want to skip - use the existing file
                        file_mapping[track_path] = dest_path
                        synced_tracks.append(dest_path)
                        skipped_count += 1
                        
                        if i % 20 == 0 or i+1 == total_tracks:
                            progress_pct = (i + 1) * 100 / total_tracks
                            self.status_var.set(f"Processing track {i+1}/{total_tracks} ({progress_pct:.1f}%)")
                            self.append_to_text_widget(
                                self.sync_text, 
                                f"Progress: {i+1}/{total_tracks} tracks processed ({skipped_count} skipped, {copied_count} copied)\n"
                            )
                        continue  # Skip to next track
                    
                    # Handle filename conflicts by adding a suffix (only when not skipping or file doesn't exist)
                    counter = 1
                    original_dest_path = dest_path
                    while os.path.exists(dest_path) and dest_path != file_mapping.get(track_path):
                        name_without_ext = os.path.splitext(original_dest_path)[0]
                        dest_path = f"{name_without_ext} ({counter}){dest_ext}"
                        counter += 1
                    
                    # Add this mapping regardless of whether we copy the file
                    file_mapping[track_path] = dest_path
                    synced_tracks.append(dest_path)
                    
                    is_flac = file_ext == '.flac'
                    
                    progress_pct = (i + 1) * 100 / total_tracks
                    if track_title:
                        progress_msg = f"Processing track {i+1}/{total_tracks} ({progress_pct:.1f}%): {track_title}\n"
                    else:
                        progress_msg = f"Processing track {i+1}/{total_tracks} ({progress_pct:.1f}%): {os.path.basename(track_path)}\n"
                    self.status_var.set(f"Processing track {i+1}/{total_tracks} ({progress_pct:.1f}%)")
                    
                    if os.path.exists(dest_path):
                        # File exists but skip_existing is False - log and continue
                        self.append_to_text_widget(self.sync_text, f"{progress_msg}File already exists, will overwrite: {os.path.basename(dest_path)}\n")
                    
                    # Copy or convert the file (either it doesn't exist, or we're overwriting)
                    if is_flac or not convert_to_flac:
                        # For FLAC files or when not converting, copy directly but potentially add album art
                        if is_flac and preserve_album_art and convert_to_flac:
                            self.append_to_text_widget(
                                self.sync_text, 
                                f"{progress_msg}Copying FLAC file with album art check: {os.path.basename(track_path)}\n"
                            )
                            success = self.copy_with_album_art(track_path, dest_path, temp_dir)
                            if success:
                                album_art_embedded_count += 1
                        else:
                            self.append_to_text_widget(
                                self.sync_text, 
                                f"{progress_msg}Copying directly: {os.path.basename(track_path)}\n"
                            )
                            shutil.copy2(track_path, dest_path)
                        
                        copied_count += 1
                        if is_flac:
                            skipped_flac_count += 1
                    elif convert_to_flac:
                        self.append_to_text_widget(
                            self.sync_text, 
                            f"{progress_msg}Converting to FLAC: {os.path.basename(track_path)}\n"
                        )
                        success, has_art = self.convert_to_flac(track_path, dest_path, temp_dir, preserve_album_art)
                        if success:
                            converted_count += 1
                            copied_count += 1
                            if has_art:
                                album_art_embedded_count += 1
                            self.append_to_text_widget(
                                self.sync_text,
                                f"✓ Conversion to FLAC complete for: {os.path.basename(track_path)}\n"
                            )
                        else:
                            self.append_to_text_widget(
                                self.sync_text,
                                f"⚠ Conversion failed, falling back to regular copy for {os.path.basename(track_path)}\n"
                            )
                            try:
                                # Fall back to copying the original format
                                dest_path = os.path.join(dj_library, base_name + file_ext)
                                file_mapping[track_path] = dest_path  # Update the mapping
                                shutil.copy2(track_path, dest_path)
                                copied_count += 1
                            except Exception as e:
                                self.append_to_text_widget(self.sync_text, f"✗ Fallback copy also failed: {str(e)}\n")
                                error_count += 1
                except Exception as e:
                    self.append_to_text_widget(self.sync_text, f"✗ Error processing {track_path}: {e}\n")
                    error_count += 1
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
        
        self.append_to_text_widget(self.sync_text, f"\n=== UPDATE SUMMARY ===\n")
        self.append_to_text_widget(self.sync_text, f"Total tracks processed: {total_tracks}\n")
        self.append_to_text_widget(self.sync_text, f"Files copied: {copied_count}\n")
        self.append_to_text_widget(self.sync_text, f"Files converted to FLAC: {converted_count}\n")
        self.append_to_text_widget(self.sync_text, f"Files with album art embedded: {album_art_embedded_count}\n")
        self.append_to_text_widget(self.sync_text, f"Files skipped (already exist): {skipped_count}\n")
        self.append_to_text_widget(self.sync_text, f"FLAC files copied directly: {skipped_flac_count}\n")
        self.append_to_text_widget(self.sync_text, f"Errors encountered: {error_count}\n")
        self.append_to_text_widget(self.sync_text, f"Total files in DJ Library: {len(os.listdir(dj_library))}\n")
        self.append_to_text_widget(self.sync_text, f"=====================\n\n")
        return synced_tracks, file_mapping

    def copy_with_album_art(self, source_path, dest_path, temp_dir):
        """Copy a FLAC file and add external album art if found"""
        try:
            # First, copy the file normally
            shutil.copy2(source_path, dest_path)
            
            # Then try to add external album art
            external_art = self.find_album_art(source_path)
            if external_art:
                self.append_to_text_widget(self.sync_text, f"Found external album art: {os.path.basename(external_art)}\n")
                
                # Use FFmpeg to add the album art
                temp_output = os.path.join(temp_dir, "temp_with_art.flac")
                
                process_args = self.get_subprocess_args()
                
                result = subprocess.run([
                    "ffmpeg",
                    "-i", dest_path,
                    "-i", external_art,
                    "-c", "copy",
                    "-disposition:v:0", "attached_pic",
                    "-y",
                    temp_output
                ], **process_args)
                
                if result.returncode == 0 and os.path.exists(temp_output):
                    # Replace the original with the version that has album art
                    shutil.move(temp_output, dest_path)
                    self.append_to_text_widget(self.sync_text, f"✓ Added album art to FLAC file\n")
                    return True
                else:
                    self.append_to_text_widget(self.sync_text, f"⚠ Failed to add album art, keeping original file\n")
            
            return False
            
        except Exception as e:
            self.append_to_text_widget(self.sync_text, f"Error adding album art: {e}\n")
            return False
    
    def convert_to_wav(self, source_path, wav_path):
        """Convert an audio file to WAV format using FFmpeg (first step for Traktor compatibility)"""
        try:
            file_ext = os.path.splitext(source_path)[1].lower()
            
            if file_ext == '.wav':
                shutil.copy2(source_path, wav_path)
                self.append_to_text_widget(
                    self.sync_text,
                    f"File is already in WAV format, copied directly: {os.path.basename(source_path)}\n"
                )
                return True
                
            self.append_to_text_widget(self.sync_text, f"Converting {file_ext} to WAV (step 1/2)...\n")
            
            # Use platform-specific arguments to hide console window
            process_args = self.get_subprocess_args()
            
            # Convert to WAV without any album art (clean conversion)
            process = subprocess.run([
                "ffmpeg", 
                "-i", source_path, 
                "-c:a", "pcm_s16le",  # Standard WAV encoding
                "-ar", "44100",       # Standard sample rate
                "-y",  # Overwrite output file if it exists
                wav_path
            ], check=True, **process_args)
            
            if os.path.exists(wav_path):
                wav_size = os.path.getsize(wav_path)
                self.append_to_text_widget(self.sync_text, f"WAV file created successfully ({wav_size} bytes)\n")
                return True
            else:
                self.append_to_text_widget(self.sync_text, "WARNING: WAV file was not created!\n")
                return False
                
        except subprocess.CalledProcessError as e:
            self.append_to_text_widget(self.sync_text, f"FFmpeg error during WAV conversion: {e}\n")
            self.append_to_text_widget(self.sync_text, f"Error output: {e.stderr.decode() if e.stderr else 'No error output'}\n")
            return False
        except Exception as e:
            self.append_to_text_widget(self.sync_text, f"Error converting file to WAV {source_path}: {e}\n")
            return False

    def convert_wav_to_flac(self, wav_path, flac_path, original_source_path, temp_dir, preserve_album_art=True):
        """Convert WAV to FLAC format with album art (second step for Traktor compatibility)"""
        try:
            self.append_to_text_widget(self.sync_text, f"Converting WAV to FLAC with album art (step 2/2)...\n")
            
            # Use platform-specific arguments to hide console window
            process_args = self.get_subprocess_args()
            
            has_album_art = False
            
            if preserve_album_art:
                # Find album art from the original source file location
                external_art = self.find_album_art(original_source_path)
                embedded_art = self.extract_embedded_art(original_source_path, temp_dir)
                
                art_to_use = embedded_art or external_art
                
                if art_to_use:
                    self.append_to_text_widget(self.sync_text, f"Embedding album art: {os.path.basename(art_to_use)}\n")
                    
                    # Convert WAV to FLAC with album art
                    process = subprocess.run([
                        "ffmpeg", 
                        "-i", wav_path,
                        "-i", art_to_use,
                        "-c:a", "flac",
                        "-c:v", "copy",
                        "-disposition:v:0", "attached_pic",
                        "-y",  # Overwrite output file if it exists
                        flac_path
                    ], check=True, **process_args)
                    
                    has_album_art = True
                else:
                    # Convert WAV to FLAC without album art
                    self.append_to_text_widget(self.sync_text, f"No album art found, converting WAV to FLAC without art\n")
                    process = subprocess.run([
                        "ffmpeg", 
                        "-i", wav_path, 
                        "-c:a", "flac",
                        "-y",  # Overwrite output file if it exists
                        flac_path
                    ], check=True, **process_args)
            else:
                # Convert WAV to FLAC without trying to preserve album art
                process = subprocess.run([
                    "ffmpeg", 
                    "-i", wav_path, 
                    "-c:a", "flac",
                    "-y",  # Overwrite output file if it exists
                    flac_path
                ], check=True, **process_args)
            
            if os.path.exists(flac_path):
                flac_size = os.path.getsize(flac_path)
                self.append_to_text_widget(self.sync_text, f"FLAC file created successfully ({flac_size} bytes)\n")
                return True, has_album_art
            else:
                self.append_to_text_widget(self.sync_text, "WARNING: FLAC file was not created!\n")
                return False, False
                
        except subprocess.CalledProcessError as e:
            self.append_to_text_widget(self.sync_text, f"FFmpeg error during FLAC conversion: {e}\n")
            self.append_to_text_widget(self.sync_text, f"Error output: {e.stderr.decode() if e.stderr else 'No error output'}\n")
            return False, False
        except Exception as e:
            self.append_to_text_widget(self.sync_text, f"Error converting WAV to FLAC {wav_path}: {e}\n")
            return False, False

    def convert_to_flac(self, source_path, dest_path, temp_dir, preserve_album_art=True):
        """Convert an audio file to FLAC format using two-step process: source → WAV → FLAC with album art"""
        try:
            file_ext = os.path.splitext(source_path)[1].lower()
            
            if file_ext == '.flac':
                # If already FLAC, use copy_with_album_art logic
                has_art = self.copy_with_album_art(source_path, dest_path, temp_dir)
                self.append_to_text_widget(
                    self.sync_text,
                    f"File is already in FLAC format, copied directly: {os.path.basename(source_path)}\n"
                )
                return True, has_art
                
            self.append_to_text_widget(self.sync_text, f"Converting {file_ext} to FLAC via WAV (for Traktor compatibility)...\n")
            
            # Create temporary WAV file
            base_name = os.path.splitext(os.path.basename(source_path))[0]
            temp_wav_path = os.path.join(temp_dir, f"{base_name}_temp.wav")
            
            try:
                # Step 1: Convert source to WAV
                if not self.convert_to_wav(source_path, temp_wav_path):
                    return False, False
                
                # Step 2: Convert WAV to FLAC with album art
                success, has_art = self.convert_wav_to_flac(temp_wav_path, dest_path, source_path, temp_dir, preserve_album_art)
                
                # Clean up temporary WAV file
                if os.path.exists(temp_wav_path):
                    os.remove(temp_wav_path)
                
                return success, has_art
                
            except Exception as e:
                # Clean up temporary WAV file on error
                if os.path.exists(temp_wav_path):
                    try:
                        os.remove(temp_wav_path)
                    except:
                        pass
                raise e
                
        except Exception as e:
            self.append_to_text_widget(self.sync_text, f"Error in two-step conversion for {source_path}: {e}\n")
            return False, False
    
    def update_playlist_items(self, playlist_dict, valid_track_ids):
        """
        Update a playlist's items to only include valid tracks.
        Returns the number of tracks kept in the playlist.
        """
        playlist_items = None
        playlist_items_index = None
        
        # Find the Playlist Items array
        for i in range(0, len(playlist_dict), 2):
            if i+1 >= len(playlist_dict):
                break
            if playlist_dict[i].tag == 'key' and playlist_dict[i].text == 'Playlist Items':
                if playlist_dict[i+1].tag == 'array':
                    playlist_items = playlist_dict[i+1]
                    playlist_items_index = i+1
                break
        
        if playlist_items is None:
            # No items in this playlist
            return 0
        
        # Count the valid tracks we keep
        kept_count = 0
        
        # No need to filter if it's a special playlist like "Library"
        for i in range(len(playlist_dict)):
            if playlist_dict[i].tag == 'key' and playlist_dict[i].text == 'Master':
                # This is a special playlist like Library - keep all items
                return len(playlist_items)
        
        # Create a new array with only valid tracks
        new_items_array = ET.Element('array')
        
        # Process each item
        for item_dict in playlist_items:
            if item_dict.tag != 'dict':
                continue
                
            # Extract the Track ID
            track_id = None
            for i in range(0, len(item_dict), 2):
                if i+1 >= len(item_dict):
                    break
                if item_dict[i].tag == 'key' and item_dict[i].text == 'Track ID':
                    # Get the track ID
                    try:
                        if item_dict[i+1].tag == 'integer':
                            track_id = str(self.safe_int_conversion(item_dict[i+1].text))
                        else:
                            track_id = item_dict[i+1].text
                    except:
                        track_id = str(item_dict[i+1].text)
                    break
            
            if track_id is not None and track_id in valid_track_ids:
                # This track is in our list of valid tracks - keep it
                new_items_array.append(copy.deepcopy(item_dict))
                kept_count += 1
        
        # Replace the items array
        playlist_dict[playlist_items_index] = new_items_array
        
        return kept_count
    
    
    def windows_to_mac_path(self, windows_path):
        """Convert a Windows path to Mac path format"""
        # Get the Mac DJ Library base path
        mac_base = self.mac_dj_library_var.get()
        
        # Extract just the filename from the Windows path
        filename = os.path.basename(windows_path)
        
        # Construct Mac path (using forward slashes)
        mac_path = f"{mac_base}/{filename}"
        
        return mac_path
    
    def create_new_xml(self, original_xml_path, export_xml_path, playlists_data, tracks_metadata, file_mapping, dj_library):
        """
        Create a new iTunes-compatible XML file that only includes the selected playlists
        and points to the correct locations in the DJ Library.
        """
        self.append_to_text_widget(self.xml_text, f"Creating new iTunes XML at {export_xml_path}...\n")
        start_time = time.time()
        
        try:
            # First, load the original XML as text to preserve formatting
            with open(original_xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
                
            # Parse the XML
            tree = ET.fromstring(xml_content)
                    
            # We'll create a deep copy to modify
            new_tree = copy.deepcopy(tree)
            
            # Get the main dict from the new tree
            new_dict = next((child for child in new_tree if child.tag == 'dict'), None)
            if new_dict is None:
                self.append_to_text_widget(self.xml_text, "Invalid iTunes XML format: missing main dict\n")
                return False
                
            # Update application version and date
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            target_os = self.target_os_var.get()
            use_mac_paths = (target_os == "Mac")
            
            for i in range(len(new_dict)):
                if new_dict[i].tag == 'key' and new_dict[i].text == 'Application Version':
                    if i+1 < len(new_dict) and new_dict[i+1].tag == 'string':
                        new_dict[i+1].text = f"DJ Export {current_date}"
                elif new_dict[i].tag == 'key' and new_dict[i].text == 'Music Folder':
                    if i+1 < len(new_dict) and new_dict[i+1].tag == 'string':
                        # Update music folder path to DJ library
                        if use_mac_paths:
                            # Use Mac path
                            mac_folder = self.mac_dj_library_var.get()
                            if not mac_folder.endswith("/"):
                                mac_folder += "/"
                            new_dict[i+1].text = f"file://{mac_folder}"
                        else:
                            # Use Windows path
                            dj_path = dj_library.replace("\\", "/")
                            if not dj_path.startswith("/"):
                                dj_path = "/" + dj_path
                            if not dj_path.endswith("/"):
                                dj_path += "/"
                            new_dict[i+1].text = f"file://localhost{dj_path}"
            
            # Build a set of track IDs that are in our playlists
            track_ids_to_keep = set()
            for playlist in playlists_data:
                # Ensure all track IDs are strings
                track_ids_to_keep.update([str(track_id) for track_id in playlist['track_ids']])
                
            self.append_to_text_widget(self.xml_text, f"Identified {len(track_ids_to_keep)} unique tracks to keep\n")
                
            # Find the Tracks dictionary and modify it
            tracks_element = None
            tracks_element_index = None
            for i in range(len(new_dict)):
                if new_dict[i].tag == 'key' and new_dict[i].text == 'Tracks':
                    if i+1 < len(new_dict) and new_dict[i+1].tag == 'dict':
                        tracks_element = new_dict[i+1]
                        tracks_element_index = i+1
                    break
                    
            if tracks_element is None:
                self.append_to_text_widget(self.xml_text, "No tracks element found in XML\n")
                return False
                
            # Create a new tracks dictionary with only the tracks we want to keep
            new_tracks_dict = ET.Element('dict')
            tracks_processed = 0
            tracks_kept = 0
            
            # Create a reverse mapping from file paths to their new DJ library paths
            original_to_dj_path = {}
            target_os = self.target_os_var.get()
            use_mac_paths = (target_os == "Mac")
            
            if use_mac_paths:
                self.append_to_text_widget(self.xml_text, 
                    "Using Mac paths in XML for cross-platform transfer\n")
            
            for orig_path, dj_path in file_mapping.items():
                # Format the paths as URLs
                if use_mac_paths:
                    # Convert Windows path to Mac path
                    mac_path = self.windows_to_mac_path(dj_path)
                    dj_url = f"file://{mac_path}"
                    dj_url = urllib.parse.quote(dj_url, safe='/:')
                else:
                    # Use Windows path
                    dj_url_path = dj_path.replace("\\", "/")
                    if not dj_url_path.startswith("/"):
                        dj_url_path = "/" + dj_url_path
                    dj_url = f"file://localhost{dj_url_path}"
                    dj_url = urllib.parse.quote(dj_url, safe='/:')
                
                original_to_dj_path[orig_path] = dj_url
                
            # Process all tracks
            for i in range(0, len(tracks_element), 2):
                if i+1 >= len(tracks_element):
                    break
                    
                if tracks_element[i].tag == 'key' and tracks_element[i+1].tag == 'dict':
                    track_id = tracks_element[i].text
                    track_dict = tracks_element[i+1]
                    
                    tracks_processed += 1
                    
                    # Get Track ID from the track dict for proper comparison
                    track_id_from_dict = None
                    for j in range(0, len(track_dict), 2):
                        if j+1 >= len(track_dict):
                            break
                        if track_dict[j].tag == 'key' and track_dict[j].text == 'Track ID':
                            # Safely convert the track ID
                            try:
                                if track_dict[j+1].tag == 'integer':
                                    track_id_from_dict = str(self.safe_int_conversion(track_dict[j+1].text))
                                else:
                                    track_id_from_dict = track_dict[j+1].text
                            except:
                                track_id_from_dict = str(track_dict[j+1].text)
                            break
                    
                    # If we couldn't get the Track ID, use the key as fallback
                    if track_id_from_dict is None:
                        track_id_from_dict = track_id
                    
                    # Check if this track is in our playlists
                    if str(track_id_from_dict) in track_ids_to_keep:
                        track_metadata = tracks_metadata.get(str(track_id_from_dict), {})
                        original_path = track_metadata.get('file_path', '')
                        
                        # Create a copy of this track's dict
                        new_track_dict = copy.deepcopy(track_dict)
                        
                        # If we have location info, update it
                        if original_path and original_path in original_to_dj_path:
                            # Find and update the Location element
                            for j in range(0, len(new_track_dict), 2):
                                if j+1 >= len(new_track_dict):
                                    break
                                if new_track_dict[j].tag == 'key' and new_track_dict[j].text == 'Location':
                                    # Update to the new DJ library path
                                    new_track_dict[j+1].text = original_to_dj_path[original_path]
                                    break
                        
                        # Add this track to our new tracks dictionary
                        new_key = ET.Element('key')
                        new_key.text = track_id
                        new_tracks_dict.append(new_key)
                        new_tracks_dict.append(new_track_dict)
                        tracks_kept += 1
                        
                        # Log progress
                        if tracks_kept % 100 == 0:
                            self.append_to_text_widget(
                                self.xml_text,
                                f"Processed {tracks_processed} tracks, kept {tracks_kept}...\n"
                            )
            
            # Replace the tracks dictionary
            new_dict[tracks_element_index] = new_tracks_dict
            
            self.append_to_text_widget(
                self.xml_text,
                f"Processed {tracks_processed} tracks, kept {tracks_kept} for the selected playlists\n"
            )
            
            # Now update the playlists array
            playlists_element = None
            playlists_element_index = None
            for i in range(len(new_dict)):
                if new_dict[i].tag == 'key' and new_dict[i].text == 'Playlists':
                    if i+1 < len(new_dict) and new_dict[i+1].tag == 'array':
                        playlists_element = new_dict[i+1]
                        playlists_element_index = i+1
                    break
                    
            if playlists_element is None:
                self.append_to_text_widget(self.xml_text, "No playlists element found in XML\n")
                return False
                
            # Create a new playlists array
            new_playlists_array = ET.Element('array')
            playlists_kept = 0
            
            # First, find and keep any system playlists (always needed)
            system_playlists = ["Library", "Music"]
            for playlist_dict in playlists_element:
                if playlist_dict.tag != 'dict':
                    continue
                    
                is_system_playlist = False
                playlist_name = None
                
                for i in range(0, len(playlist_dict), 2):
                    if i+1 >= len(playlist_dict):
                        break
                    if playlist_dict[i].tag == 'key' and playlist_dict[i].text == 'Name':
                        playlist_name = playlist_dict[i+1].text
                        if playlist_name in system_playlists:
                            is_system_playlist = True
                        break
                            
                if is_system_playlist:
                    # Keep this system playlist
                    new_playlist = copy.deepcopy(playlist_dict)
                    
                    # Update the playlist items to only include tracks we're keeping
                    self.update_playlist_items(new_playlist, track_ids_to_keep)
                    
                    new_playlists_array.append(new_playlist)
                    playlists_kept += 1
                    self.append_to_text_widget(self.xml_text, f"Added system playlist: {playlist_name}\n")
            
            # Now add our selected playlists, preserving all their track references
            selected_playlist_names = [p['name'] for p in playlists_data]
            for playlist_dict in playlists_element:
                if playlist_dict.tag != 'dict':
                    continue
                    
                playlist_name = None
                for i in range(0, len(playlist_dict), 2):
                    if i+1 >= len(playlist_dict):
                        break
                    if playlist_dict[i].tag == 'key' and playlist_dict[i].text == 'Name':
                        playlist_name = playlist_dict[i+1].text
                        break
                        
                if playlist_name in selected_playlist_names:
                    # This is one of our selected playlists
                    new_playlist = copy.deepcopy(playlist_dict)
                    
                    # Make sure we're preserving all valid tracks in this playlist
                    # (this ensures tracks appear in all playlists they belong to)
                    track_count = self.update_playlist_items(new_playlist, track_ids_to_keep)
                    
                    new_playlists_array.append(new_playlist)
                    playlists_kept += 1
                    self.append_to_text_widget(self.xml_text, f"Added playlist: {playlist_name} with {track_count} tracks\n")
            
            # Replace the playlists array
            new_dict[playlists_element_index] = new_playlists_array
            
            self.append_to_text_widget(
                self.xml_text,
                f"Kept {playlists_kept} playlists in total\n"
            )
            
            # Convert the XML tree to a string and write to the export file
            xml_str = ET.tostring(new_tree, encoding='utf-8')
            
            # Make it human-readable with proper formatting
            xml_pretty = xml_str.decode()
            
            with open(export_xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_pretty)
                
            total_time = time.time() - start_time
            
            summary_msg = (
                f"XML export complete in {total_time:.2f} seconds\n"
                f"Created XML with {tracks_kept} tracks in {playlists_kept} playlists\n"
            )
            
            if use_mac_paths:
                summary_msg += (
                    f"\n{'='*60}\n"
                    f"CROSS-PLATFORM TRANSFER INSTRUCTIONS:\n"
                    f"{'='*60}\n"
                    f"1. Files exported to: {dj_library}\n"
                    f"2. XML created with Mac paths at: {export_xml_path}\n"
                    f"3. Copy both the folder and XML to your Mac\n"
                    f"4. Place files at: {self.mac_dj_library_var.get()}\n"
                    f"{'='*60}\n"
                )
            
            self.append_to_text_widget(self.xml_text, summary_msg)
            
            return True
            
        except Exception as e:
            self.append_to_text_widget(self.xml_text, f"Error creating XML: {e}\n")
            import traceback
            self.append_to_text_widget(self.xml_text, f"Traceback: {traceback.format_exc()}\n")
            return False

def main():
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="iTunes Playlist Sync Tool")
        parser.add_argument("--itunes-xml", required=True, help="Path to iTunes XML library file")
        parser.add_argument("--dj-library", required=True, help="Path to DJ Library folder")
        parser.add_argument("--export-xml", help="Path for exported XML file")
        parser.add_argument("--skip-existing", action="store_true")
        parser.add_argument("--convert-flac", action="store_true")
        parser.add_argument("--preserve-album-art", action="store_true")
        parser.add_argument("--debug", action="store_true")
        parser.add_argument("--auto-run", action="store_true")
        parser.add_argument("--include-playlists", help="Comma-separated list of playlists to include")
        parser.add_argument("--exclude-playlists", help="Comma-separated list of playlists to exclude")
        
        args = parser.parse_args()
        
        if not args.export_xml:
            args.export_xml = os.path.join(args.dj_library, "DJ Library.xml")
        
        if not os.path.exists(args.itunes_xml):
            print(f"Error: iTunes XML file not found at {args.itunes_xml}")
            return 1
        
        if not os.path.exists(args.dj_library):
            try:
                os.makedirs(args.dj_library)
                print(f"Created DJ Library folder: {args.dj_library}")
            except Exception as e:
                print(f"Error creating DJ Library folder: {e}")
                return 1
        
        if not args.auto_run:
            print(f"This will sync playlists from {args.itunes_xml} to {args.dj_library}")
            if args.convert_flac:
                print("Audio files will be converted to FLAC format with album art embedding")
            response = input("Do you want to continue? (y/n): ").strip().lower()
            if response != 'y':
                print("Sync cancelled by user")
                return 0
        
        # Note: Command-line interface would need updates to work with new selection logic
        # For now, the GUI interface is the primary way to use this tool
        print("Please use the GUI interface for the improved playlist selection features.")
        print("Starting GUI...")
        
        root = tk.Tk()
        app = PlaylistSyncUI(root)
        app.itunes_xml_var.set(args.itunes_xml)
        app.dj_library_var.set(args.dj_library)
        app.export_xml_var.set(args.export_xml)
        root.mainloop()
        return 0
        
    else:
        root = tk.Tk()
        app = PlaylistSyncUI(root)
        root.mainloop()
        return 0

if __name__ == "__main__":
    sys.exit(main())