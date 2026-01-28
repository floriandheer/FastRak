#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bookkeeping Folder Structure Creator
Author: Florian Dheer
Version: 1.0.0
Description: Creates organized folder structure for quarterly bookkeeping
Location: P:\_Script\floriandheer\PipelineScript_Bookkeeping_FolderStructure.py
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import datetime

# Setup logging using shared utility
from shared_logging import get_logger, setup_logging as setup_shared_logging
from rak_settings import get_rak_settings

# Get logger reference (configured in main())
logger = get_logger("bookkeeping_folders")

# ====================================
# CONSTANTS AND CONFIGURATION
# ====================================

# Base bookkeeping directory
BOOKKEEPING_BASE_DIR = get_rak_settings().get_work_drive() + "\\_LIBRARY\\Boekhouding"

# Folder names
INCOMING_FOLDER = "Binnenkomend"
OUTGOING_FOLDER = "Uitgaand"

# Quarters
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

# Quarter date ranges
QUARTER_MONTHS = {
    "Q1": [1, 2, 3],    # January, February, March
    "Q2": [4, 5, 6],    # April, May, June
    "Q3": [7, 8, 9],    # July, August, September
    "Q4": [10, 11, 12]  # October, November, December
}

# ====================================
# UTILITY FUNCTIONS
# ====================================

def get_current_quarter():
    """Get the current quarter based on today's date."""
    current_month = datetime.datetime.now().month
    for quarter, months in QUARTER_MONTHS.items():
        if current_month in months:
            return quarter
    return "Q1"  # Fallback

def get_next_quarter():
    """Get the next quarter after the current one."""
    current_quarter = get_current_quarter()
    current_index = QUARTERS.index(current_quarter)
    next_index = (current_index + 1) % 4
    return QUARTERS[next_index]

def create_quarter_folders(base_dir, year, quarter):
    """Create the folder structure for a specific quarter."""
    try:
        # Create year directory
        year_dir = os.path.join(base_dir, str(year))
        os.makedirs(year_dir, exist_ok=True)
        
        # Create quarter directory
        quarter_dir = os.path.join(year_dir, quarter)
        os.makedirs(quarter_dir, exist_ok=True)
        
        # Create Binnenkomend and Uitgaand folders
        incoming_dir = os.path.join(quarter_dir, INCOMING_FOLDER)
        outgoing_dir = os.path.join(quarter_dir, OUTGOING_FOLDER)
        
        os.makedirs(incoming_dir, exist_ok=True)
        os.makedirs(outgoing_dir, exist_ok=True)
        
        return True, quarter_dir
        
    except Exception as e:
        return False, str(e)

def get_existing_quarters(base_dir, year):
    """Get list of existing quarters for a specific year."""
    year_dir = os.path.join(base_dir, str(year))
    existing_quarters = []
    
    if os.path.exists(year_dir):
        for item in os.listdir(year_dir):
            item_path = os.path.join(year_dir, item)
            if os.path.isdir(item_path) and item in QUARTERS:
                existing_quarters.append(item)
    
    return sorted(existing_quarters)

# ====================================
# GUI APPLICATION
# ====================================

class BookkeepingFolderGUI:
    """GUI for creating bookkeeping folder structures."""
    
    def __init__(self, root):
        """Initialize the bookkeeping folder creator GUI."""
        self.root = root
        self.root.title("Bookkeeping Folder Structure Creator")
        self.root.geometry("600x500")
        self.root.minsize(1000, 800)
        
        # Variables
        self.year_var = tk.StringVar(value=str(datetime.datetime.now().year))
        self.quarter_var = tk.StringVar(value=get_current_quarter())
        self.base_dir_var = tk.StringVar(value=BOOKKEEPING_BASE_DIR)
        
        # Create GUI
        self.create_header()
        self.create_directory_section()
        self.create_year_section()
        self.create_quarter_section()
        self.create_action_buttons()
        self.create_existing_folders_section()
        self.create_status_section()
        
        # Update existing folders display
        self.update_existing_folders()
        
        # Bind year change to update existing folders
        self.year_var.trace('w', lambda *args: self.update_existing_folders())
    
    def create_header(self):
        """Create header section."""
        # Create header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=80)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        header_frame.pack_propagate(False)
        
        # Add title to header
        title_label = tk.Label(header_frame, text="Bookkeeping Folder Structure Creator", 
                              font=("Arial", 16, "bold"), fg="white", bg="#2c3e50")
        title_label.place(relx=0.5, rely=0.3, anchor=tk.CENTER)
        
        # Add subtitle to header
        desc_label = tk.Label(header_frame, text="Create organized quarterly folders for bookkeeping records", 
                             font=("Arial", 10, "italic"), fg="white", bg="#2c3e50")
        desc_label.place(relx=0.5, rely=0.7, anchor=tk.CENTER)
    
    def create_directory_section(self):
        """Create base directory selection section."""
        dir_frame = ttk.LabelFrame(self.root, text="Base Directory", padding="10")
        dir_frame.pack(fill=tk.X, padx=10, pady=5)

        dir_entry_frame = ttk.Frame(dir_frame)
        dir_entry_frame.pack(fill=tk.X)
        dir_entry_frame.columnconfigure(0, weight=1)
        
        ttk.Entry(
            dir_entry_frame,
            textvariable=self.base_dir_var,
            width=50,
            state="readonly"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(
            dir_entry_frame,
            text="Browse",
            command=self.browse_directory
        ).pack(side=tk.RIGHT, padx=(5, 0))
    
    def create_year_section(self):
        """Create year selection section."""
        year_frame = ttk.LabelFrame(self.root, text="Year", padding="10")
        year_frame.pack(fill=tk.X, padx=10, pady=5)
        
        year_inner_frame = ttk.Frame(year_frame)
        year_inner_frame.pack()
        
        ttk.Label(year_inner_frame, text="Select Year:").pack(side=tk.LEFT, padx=(0, 10))
        
        year_spinbox = ttk.Spinbox(
            year_inner_frame,
            from_=2020,
            to=2030,
            textvariable=self.year_var,
            width=10,
            state="readonly"
        )
        year_spinbox.pack(side=tk.LEFT)
        
        # Current year info
        current_year = datetime.datetime.now().year
        info_label = ttk.Label(
            year_inner_frame,
            text=f"(Current year: {current_year})",
            font=("Arial", 9, "italic")
        )
        info_label.pack(side=tk.LEFT, padx=(10, 0))
    
    def create_quarter_section(self):
        """Create quarter selection section."""
        quarter_frame = ttk.LabelFrame(self.root, text="Quarter Selection", padding="10")
        quarter_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Current quarter info
        current_quarter = get_current_quarter()
        next_quarter = get_next_quarter()
        
        info_frame = ttk.Frame(quarter_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(
            info_frame,
            text=f"Current Quarter: {current_quarter} | Next Quarter: {next_quarter}",
            font=("Arial", 10, "bold")
        ).pack()
        
        # Quarter selection
        selection_frame = ttk.Frame(quarter_frame)
        selection_frame.pack()
        
        ttk.Label(selection_frame, text="Select Quarter:").pack(side=tk.LEFT, padx=(0, 10))
        
        quarter_combo = ttk.Combobox(
            selection_frame,
            textvariable=self.quarter_var,
            values=QUARTERS,
            width=10,
            state="readonly"
        )
        quarter_combo.pack(side=tk.LEFT)
    
    def create_action_buttons(self):
        """Create action buttons section."""
        action_frame = ttk.LabelFrame(self.root, text="Actions", padding="10")
        action_frame.pack(fill=tk.X, padx=10, pady=5)
        
        button_frame = ttk.Frame(action_frame)
        button_frame.pack()
        
        # Create current quarter button
        current_quarter = get_current_quarter()
        ttk.Button(
            button_frame,
            text=f"Create Current Quarter ({current_quarter})",
            command=self.create_current_quarter,
            width=25
        ).pack(side=tk.LEFT, padx=5)
        
        # Create next quarter button
        next_quarter = get_next_quarter()
        ttk.Button(
            button_frame,
            text=f"Create Next Quarter ({next_quarter})",
            command=self.create_next_quarter,
            width=25
        ).pack(side=tk.LEFT, padx=5)
        
        # Create selected quarter button
        ttk.Button(
            button_frame,
            text="Create Selected Quarter",
            command=self.create_selected_quarter,
            width=20
        ).pack(side=tk.LEFT, padx=5)
    
    def create_existing_folders_section(self):
        """Create section showing existing folders."""
        existing_frame = ttk.LabelFrame(self.root, text="Existing Quarters", padding="10")
        existing_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create treeview for existing folders
        self.existing_tree = ttk.Treeview(existing_frame, height=6)
        self.existing_tree.pack(fill=tk.BOTH, expand=True)
        
        # Configure columns
        self.existing_tree["columns"] = ("Quarter", "Path", "Status")
        self.existing_tree.column("#0", width=0, stretch=False)
        self.existing_tree.column("Quarter", width=80, anchor="center")
        self.existing_tree.column("Path", width=300, anchor="w")
        self.existing_tree.column("Status", width=100, anchor="center")
        
        self.existing_tree.heading("Quarter", text="Quarter")
        self.existing_tree.heading("Path", text="Full Path")
        self.existing_tree.heading("Status", text="Status")
    
    def create_status_section(self):
        """Create status section."""
        status_frame = ttk.LabelFrame(self.root, text="Status", padding="10")
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_text = tk.Text(status_frame, height=4, wrap=tk.WORD, state=tk.DISABLED)
        self.status_text.pack(fill=tk.X)
        
        # Configure tags for different message types
        self.status_text.tag_configure("success", foreground="green")
        self.status_text.tag_configure("error", foreground="red")
        self.status_text.tag_configure("info", foreground="blue")
    
    def browse_directory(self):
        """Browse for base directory."""
        from tkinter import filedialog
        directory = filedialog.askdirectory(
            title="Select Bookkeeping Base Directory",
            initialdir=self.base_dir_var.get()
        )
        if directory:
            self.base_dir_var.set(directory)
            self.update_existing_folders()
    
    def update_existing_folders(self):
        """Update the display of existing folders."""
        # Clear existing items
        for item in self.existing_tree.get_children():
            self.existing_tree.delete(item)
        
        year = self.year_var.get()
        base_dir = self.base_dir_var.get()
        
        if not year or not base_dir:
            return
        
        try:
            existing_quarters = get_existing_quarters(base_dir, year)
            year_dir = os.path.join(base_dir, year)
            
            for quarter in QUARTERS:
                quarter_path = os.path.join(year_dir, quarter)
                if quarter in existing_quarters:
                    # Check if subfolders exist
                    incoming_path = os.path.join(quarter_path, INCOMING_FOLDER)
                    outgoing_path = os.path.join(quarter_path, OUTGOING_FOLDER)
                    
                    if os.path.exists(incoming_path) and os.path.exists(outgoing_path):
                        status = "Complete"
                    else:
                        status = "Incomplete"
                    
                    self.existing_tree.insert("", "end", values=(quarter, quarter_path, status))
                else:
                    self.existing_tree.insert("", "end", values=(quarter, quarter_path, "Not Created"))
        
        except Exception as e:
            self.update_status(f"Error updating folder list: {e}", "error")
    
    def update_status(self, message, msg_type="info"):
        """Update status text."""
        self.status_text.config(state=tk.NORMAL)
        
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n", msg_type)
        
        # Scroll to end
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        
        # Force update
        self.root.update_idletasks()
    
    def create_current_quarter(self):
        """Create folders for the current quarter."""
        current_quarter = get_current_quarter()
        self.quarter_var.set(current_quarter)
        self.create_quarter_folders_action(current_quarter, "current")
    
    def create_next_quarter(self):
        """Create folders for the next quarter."""
        next_quarter = get_next_quarter()
        self.quarter_var.set(next_quarter)
        self.create_quarter_folders_action(next_quarter, "next")
    
    def create_selected_quarter(self):
        """Create folders for the selected quarter."""
        quarter = self.quarter_var.get()
        self.create_quarter_folders_action(quarter, "selected")
    
    def create_quarter_folders_action(self, quarter, quarter_type):
        """Perform the actual folder creation."""
        year = self.year_var.get()
        base_dir = self.base_dir_var.get()
        
        if not year or not quarter or not base_dir:
            messagebox.showerror("Error", "Please ensure all fields are filled")
            return
        
        # Check if base directory exists
        if not os.path.exists(base_dir):
            create_base = messagebox.askyesno(
                "Directory Not Found",
                f"The base directory '{base_dir}' does not exist.\n\nWould you like to create it?"
            )
            if not create_base:
                return
            
            try:
                os.makedirs(base_dir, exist_ok=True)
                self.update_status(f"Created base directory: {base_dir}", "success")
            except Exception as e:
                self.update_status(f"Failed to create base directory: {e}", "error")
                return
        
        # Check if quarter already exists
        quarter_path = os.path.join(base_dir, year, quarter)
        if os.path.exists(quarter_path):
            overwrite = messagebox.askyesno(
                "Quarter Exists",
                f"The quarter folder '{quarter}' for year {year} already exists.\n\nDo you want to ensure all subfolders are created?"
            )
            if not overwrite:
                return
        
        # Create the folders
        self.update_status(f"Creating {quarter_type} quarter folder structure...", "info")
        
        success, result = create_quarter_folders(base_dir, year, quarter)
        
        if success:
            self.update_status(f"Successfully created folder structure for {quarter} {year}", "success")
            self.update_status(f"Created: {result}", "info")
            self.update_status(f"Subfolders: {INCOMING_FOLDER}, {OUTGOING_FOLDER}", "info")
            
            # Update existing folders display
            self.update_existing_folders()
            
            # Ask if user wants to open the folder
            open_folder = messagebox.askyesno(
                "Success",
                f"Quarter {quarter} folder structure created successfully!\n\nWould you like to open the folder?"
            )
            
            if open_folder:
                try:
                    os.startfile(result)  # Windows
                except:
                    try:
                        os.system(f'explorer "{result}"')  # Alternative Windows method
                    except:
                        self.update_status("Could not open folder automatically", "error")
        else:
            self.update_status(f"Failed to create folder structure: {result}", "error")
            messagebox.showerror("Error", f"Failed to create folder structure:\n{result}")

# ====================================
# MAIN APPLICATION ENTRY POINT
# ====================================

def main():
    """Main application entry point."""
    # Setup logging when the app actually runs (not at import time)
    setup_shared_logging("bookkeeping_folders")

    # Create Tkinter root
    root = tk.Tk()
    
    # Setup styles
    style = ttk.Style()
    style.configure("TButton", padding=5)
    style.configure("TLabel", padding=2)
    style.configure("TEntry", padding=2)
    
    # Create main application
    app = BookkeepingFolderGUI(root)
    
    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    main()