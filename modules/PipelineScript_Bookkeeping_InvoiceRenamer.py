#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
Invoice Renaming Script
Author: Florian Dheer
Version: 1.0.3
Description: Automatically rename invoices to standardized format: FAC_YY-MM-DD_CompanyName
             With fallback naming for missing information
             Added functionality to process selected files only
Location: P:\_Script\floriandheer\PipelineScript_Business_InvoiceRenamer.py
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import datetime
import re
import shutil
from pathlib import Path

# Setup logging using shared utility
from shared_logging import get_logger, setup_logging as setup_shared_logging
from rak_settings import get_rak_settings

# Get logger reference (configured in main())
logger = get_logger("invoice_renamer")

# PDF processing imports
try:
    import pdfplumber
    PDF_LIBRARY = "pdfplumber"
except ImportError:
    try:
        import PyPDF2
        PDF_LIBRARY = "PyPDF2"
    except ImportError:
        PDF_LIBRARY = None

# ====================================
# CONSTANTS AND CONFIGURATION
# ====================================

# Supported file extensions
SUPPORTED_EXTENSIONS = ['.pdf', '.PDF']

# Default browsing directory
DEFAULT_BROWSE_DIR = get_rak_settings().get_work_drive() + r"\_LIBRARY\Boekhouding"

# Company name mapping for standardization
COMPANY_MAPPING = {
    # Common variations to standardized names
    'lucien bike': 'Lucien',
    'lucien bike nv': 'Lucien',
    'lucien lebbeke': 'Lucien',
    'google cloud emea limited': 'Google',
    'google cloud': 'Google',
    'google workspace': 'Google',
    'combell nv': 'Combell',
    'combell': 'Combell',
    'ovh bv': 'OVH',
    'ovhcloud': 'OVH',
    'fiscaal bureau pas': 'FiscaalBureauPas',
    'fiscaal bureau pas bv': 'FiscaalBureauPas',
    'orange belgium': 'Orange',
    'orange belgium nv': 'Orange',
    'new house internet services': 'PTGui',
    'new house internet services bv': 'PTGui',
    'kamera express': 'KameraExpress',
    'kamera express rotterdam': 'KameraExpress',
    'kamera express rotterdam b.v.': 'KameraExpress',
    'microsoft': 'Microsoft',
    'microsoft corporation': 'Microsoft',
    'adobe': 'Adobe',
    'adobe systems': 'Adobe',
}

# Date patterns to search for in PDFs
DATE_PATTERNS = [
    # Dutch patterns (common in Belgian invoices)
    r'factuurdatum[:\s]*(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})',
    r'factuurdatum[:\s]*(\d{1,2})\s+(\w+)\s+(\d{4})',  # "18 augustus 2025"
    r'datum[:\s]*(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})',
    r'datum\s+van\s+afgifte[:\s]*(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})',
    
    # English patterns
    r'invoice\s+date[:\s]*(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})',
    r'date[:\s]*(\d{1,2})\s+(\w+)\s+(\d{4})',  # "28 Aug 2025"
    r'date[:\s]*(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})',
    
    # Generic date patterns
    r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})',
    r'(\d{1,2})\s+(\w+)\s+(\d{4})',  # "31 August 2025"
]

# Company name patterns - more specific for Belgian/Dutch invoices
COMPANY_PATTERNS = [
    # Header patterns (common in invoices)
    r'^([A-Z][A-Za-z\s&\.]{5,40}(?:nv|bv|b\.v\.|sa|ltd|limited|inc|corp|gmbh)?)',
    r'(lucien\s+(?:bike|lebbeke))',
    r'(combell(?:\s+nv)?)',
    r'(ovh(?:\s+bv|cloud)?)',
    r'(orange(?:\s+belgium)?(?:\s+nv)?)',
    r'(fiscaal\s+bureau\s+pas(?:\s+bv)?)',
    r'(new\s+house\s+internet\s+services(?:\s+bv)?)',
    r'(kamera\s+express(?:\s+rotterdam)?(?:\s+b\.v\.)?)',
    r'(google(?:\s+cloud)?(?:\s+emea)?(?:\s+limited)?)',
    
    # Context-based patterns
    r'(?:from|bill\s+from|your\s+store|jouw\s+winkel)[:\s]*([^\n\r]{5,50})',
    r'(?:company|bedrijf)[:\s]*([^\n\r]{5,50})',
    r'btw[:\s]*[A-Z]{2}[0-9\s\.]+.*?([A-Za-z][^\n\r]{5,40})',
]

# Month name mappings
MONTH_NAMES = {
    # English months
    'january': 1, 'jan': 1,
    'february': 2, 'feb': 2,
    'march': 3, 'mar': 3,
    'april': 4, 'apr': 4,
    'may': 5,
    'june': 6, 'jun': 6,
    'july': 7, 'jul': 7,
    'august': 8, 'aug': 8,
    'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10,
    'november': 11, 'nov': 11,
    'december': 12, 'dec': 12,
    
    # Dutch months
    'januari': 1,
    'februari': 2,
    'maart': 3,
    'april': 4,
    'mei': 5,
    'juni': 6,
    'juli': 7,
    'augustus': 8,
    'september': 9,
    'oktober': 10,
    'november': 11,
    'december': 12,
}

# Fallback configuration
FALLBACK_COMPANY_NAME = "Unknown"
FALLBACK_START_DATE = datetime.date(2025, 1, 1)  # Starting date for fallbacks

# ====================================
# PDF PROCESSING FUNCTIONS
# ====================================

def extract_pdf_text(pdf_path):
    """Extract text from PDF using available library."""
    text = ""
    
    if PDF_LIBRARY == "pdfplumber":
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            logging.error(f"Error extracting text with pdfplumber: {e}")
            
    elif PDF_LIBRARY == "PyPDF2":
        try:
            import PyPDF2
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            logging.error(f"Error extracting text with PyPDF2: {e}")
    
    return text

def extract_invoice_date(text):
    """Extract invoice date from PDF text."""
    if not text:
        return None
        
    text_lower = text.lower()
    
    for pattern in DATE_PATTERNS:
        matches = re.finditer(pattern, text_lower, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            try:
                groups = match.groups()
                
                if len(groups) == 3:
                    # Handle different date formats
                    
                    # Check for ISO format YYYY-MM-DD
                    if len(groups[0]) == 4 and groups[0].isdigit():
                        year = int(groups[0])
                        month = int(groups[1])
                        day = int(groups[2])
                        if 2020 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31:
                            return datetime.date(year, month, day)
                    
                    # Check if any group is a month name
                    month_num = None
                    day_num = None
                    year_num = None
                    
                    for i, group in enumerate(groups):
                        if group.lower() in MONTH_NAMES:
                            month_num = MONTH_NAMES[group.lower()]
                            # Other groups should be day and year
                            remaining = [groups[j] for j in range(3) if j != i]
                            for val in remaining:
                                if val.isdigit():
                                    if len(val) == 4 and int(val) >= 2020:
                                        year_num = int(val)
                                    elif 1 <= int(val) <= 31:
                                        day_num = int(val)
                            break
                    
                    if month_num and day_num and year_num:
                        if 1 <= day_num <= 31 and year_num >= 2020:
                            return datetime.date(year_num, month_num, day_num)
                    
                    # Handle numeric date patterns
                    if all(g.isdigit() for g in groups):
                        nums = [int(g) for g in groups]
                        
                        # Handle 2-digit years (convert to 20XX)
                        for i, num in enumerate(nums):
                            if 20 <= num <= 30:  # Assume 2020-2030 range for 2-digit years
                                nums[i] = 2000 + num
                        
                        # Try different date interpretations
                        date_interpretations = []
                        
                        # DD/MM/YYYY or DD-MM-YYYY
                        if 1 <= nums[0] <= 31 and 1 <= nums[1] <= 12 and nums[2] >= 2020:
                            date_interpretations.append((nums[2], nums[1], nums[0]))
                        
                        # MM/DD/YYYY
                        if 1 <= nums[1] <= 31 and 1 <= nums[0] <= 12 and nums[2] >= 2020:
                            date_interpretations.append((nums[2], nums[0], nums[1]))
                        
                        # YYYY/MM/DD (already handled above for ISO format, but just in case)
                        if nums[0] >= 2020 and 1 <= nums[1] <= 12 and 1 <= nums[2] <= 31:
                            date_interpretations.append((nums[0], nums[1], nums[2]))
                        
                        # Return the first valid interpretation
                        for year, month, day in date_interpretations:
                            try:
                                return datetime.date(year, month, day)
                            except ValueError:
                                continue
                            
            except (ValueError, IndexError):
                continue
    
    return None

def extract_company_name(text):
    """Extract company name from PDF text."""
    if not text:
        return None
        
    # Split into lines for easier processing
    lines = text.split('\n')
    
    # First, try specific known patterns based on your invoice examples
    text_lower = text.lower()
    
    # Check for your known companies first (case insensitive)
    for variant, standard in COMPANY_MAPPING.items():
        if variant in text_lower:
            return standard
    
    # Look for specific company patterns
    for pattern in COMPANY_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            company = match.group(1).strip()
            company_clean = clean_company_name(company)
            if company_clean and len(company_clean) > 2:
                return company_clean
    
    # Fallback: look for the first line that looks like a company name
    for i, line in enumerate(lines[:15]):  # Check first 15 lines
        line_clean = line.strip()
        if (len(line_clean) > 3 and 
            len(line_clean) < 60 and 
            not re.match(r'^\d+[/\-\.]', line_clean) and  # Not a date
            not re.match(r'^factuur', line_clean, re.IGNORECASE) and  # Not "factuur"
            not re.match(r'^invoice', line_clean, re.IGNORECASE) and  # Not "invoice"
            not re.match(r'^bill', line_clean, re.IGNORECASE) and     # Not "bill"
            not re.match(r'^creditnota', line_clean, re.IGNORECASE) and # Not "creditnota"
            not line_clean.lower().startswith(('your', 'uw', 'jouw', 'florian', 'verbindingsstraat'))):
            
            company_clean = clean_company_name(line_clean)
            if company_clean:
                return company_clean
    
    return None

def clean_company_name(company):
    """Clean and standardize company name."""
    if not company:
        return None
        
    # Remove common prefixes and suffixes
    company = re.sub(r'^(bill\s+to|from|your\s+store|jouw\s+winkel|facturatieadres|verzendadres)[:\s]*', '', company, flags=re.IGNORECASE)
    company = re.sub(r'\s+(limited|ltd|nv|bv|sa|inc|corp|gmbh|b\.v\.)\.?$', '', company, flags=re.IGNORECASE)
    
    # Remove VAT numbers and other codes
    company = re.sub(r'\s+[A-Z]{2}[0-9\s\.]+.*$', '', company)
    company = re.sub(r'\s+btw[:\s]*[A-Z]{2}[0-9\s\.]+.*$', '', company, flags=re.IGNORECASE)
    
    # Remove phone numbers and email addresses
    company = re.sub(r'\s+\+?\d{2,3}[\s\d\-\.]+', '', company)
    company = re.sub(r'\s+[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', company)
    
    # Remove addresses and other unwanted patterns
    company = re.sub(r'\s+\d+[a-zA-Z]*\s+[A-Z][a-z]+.*$', '', company)  # Remove addresses
    company = re.sub(r'\s+\d{4}\s+[A-Z][a-z]+.*$', '', company)  # Remove postal codes
    
    # Remove special characters except spaces, hyphens, and ampersands
    company = re.sub(r'[^\w\s\-&]', '', company)
    company = ' '.join(company.split())  # Normalize whitespace
    
    # Capitalize first letter of each word
    company = company.title()
    
    # Check mapping again after cleaning
    company_lower = company.lower()
    for variant, standard in COMPANY_MAPPING.items():
        if variant in company_lower:
            return standard
    
    return company if len(company) > 2 else None

def generate_new_filename(date_obj, company_name, original_extension):
    """Generate new filename in format FAC_YY-MM-DD_CompanyName."""
    if not date_obj or not company_name:
        return None
    
    # Format date as YY-MM-DD
    date_str = date_obj.strftime("%y-%m-%d")
    
    # Clean company name for filename
    company_clean = re.sub(r'[^\w\-]', '', company_name)
    
    return f"FAC_{date_str}_{company_clean}{original_extension}"

def generate_fallback_filename(fallback_date, company_name, original_extension, existing_names):
    """Generate fallback filename with incrementing dates to avoid duplicates."""
    if not company_name:
        company_name = FALLBACK_COMPANY_NAME
    
    # Clean company name for filename
    company_clean = re.sub(r'[^\w\-]', '', company_name)
    
    # Start with the provided fallback date and increment until unique
    current_date = fallback_date
    max_attempts = 365  # Prevent infinite loop
    attempts = 0
    
    while attempts < max_attempts:
        date_str = current_date.strftime("%y-%m-%d")
        new_filename = f"FAC_{date_str}_{company_clean}{original_extension}"
        
        # Check if this filename is already used
        if new_filename not in existing_names:
            return new_filename, current_date
        
        # Increment date by one day
        current_date = current_date + datetime.timedelta(days=1)
        attempts += 1
    
    # If we still haven't found a unique name, append a number
    base_filename = f"FAC_{fallback_date.strftime('%y-%m-%d')}_{company_clean}"
    counter = 1
    while counter < 1000:
        new_filename = f"{base_filename}_{counter:03d}{original_extension}"
        if new_filename not in existing_names:
            return new_filename, fallback_date
        counter += 1
    
    # Last resort - use timestamp
    timestamp = datetime.datetime.now().strftime("%H%M%S")
    return f"{base_filename}_{timestamp}{original_extension}", fallback_date

# ====================================
# GUI APPLICATION
# ====================================

class InvoiceRenamerGUI:
    """GUI for the Invoice Renamer."""
    
    def __init__(self, root):
        """Initialize the invoice renamer GUI."""
        self.root = root
        self.root.title("Invoice Renaming Tool")
        self.root.geometry("800x700")
        self.root.minsize(600, 500)
        
        # Variables
        self.source_dir_var = tk.StringVar()
        self.target_dir_var = tk.StringVar()
        self.copy_files_var = tk.BooleanVar(value=True)
        self.preview_mode_var = tk.BooleanVar(value=True)
        
        # File processing results
        self.processing_results = []
        
        # Fallback naming tracking
        self.used_filenames = set()
        self.fallback_date_counter = FALLBACK_START_DATE
        
        # Setup logging
        self.setup_logging()
        
        # Create GUI
        self.create_header()
        self.create_directory_section()
        self.create_options_section()
        self.create_preview_section()
        self.create_action_buttons()
        self.create_results_section()
        self.create_status_section()
    
    def setup_logging(self):
        """Setup logging for the application."""
        # Use shared logger (configured in main())
        self.logger = logger
    
    def create_header(self):
        """Create header section."""
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=80)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, 
                              text="Invoice Renaming Tool", 
                              font=("Arial", 16, "bold"), 
                              fg="white", 
                              bg="#2c3e50")
        title_label.place(relx=0.5, rely=0.3, anchor=tk.CENTER)
        
        desc_label = tk.Label(header_frame, 
                             text="Automatically rename invoices to format: FAC_YY-MM-DD_CompanyName", 
                             font=("Arial", 10, "italic"), 
                             fg="white", 
                             bg="#2c3e50")
        desc_label.place(relx=0.5, rely=0.7, anchor=tk.CENTER)
    
    def create_directory_section(self):
        """Create directory selection section."""
        dir_frame = ttk.LabelFrame(self.root, text="Directory Selection", padding="10")
        dir_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Source directory
        source_frame = ttk.Frame(dir_frame)
        source_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(source_frame, text="Source Directory:").pack(anchor=tk.W)
        
        source_entry_frame = ttk.Frame(source_frame)
        source_entry_frame.pack(fill=tk.X, pady=(2, 0))
        
        ttk.Entry(source_entry_frame, 
                 textvariable=self.source_dir_var, 
                 width=60).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(source_entry_frame, 
                  text="Browse", 
                  command=self.browse_source_directory).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Target directory
        target_frame = ttk.Frame(dir_frame)
        target_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(target_frame, text="Target Directory (optional - leave empty to rename in place):").pack(anchor=tk.W)
        
        target_entry_frame = ttk.Frame(target_frame)
        target_entry_frame.pack(fill=tk.X, pady=(2, 0))
        
        ttk.Entry(target_entry_frame, 
                 textvariable=self.target_dir_var, 
                 width=60).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(target_entry_frame, 
                  text="Browse", 
                  command=self.browse_target_directory).pack(side=tk.RIGHT, padx=(5, 0))
    
    def create_options_section(self):
        """Create options section."""
        options_frame = ttk.LabelFrame(self.root, text="Options", padding="10")
        options_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Checkbutton(options_frame, 
                       text="Copy files instead of moving (keep originals)", 
                       variable=self.copy_files_var).pack(anchor=tk.W)
        
        ttk.Checkbutton(options_frame, 
                       text="Preview mode (don't actually rename files)", 
                       variable=self.preview_mode_var).pack(anchor=tk.W, pady=(5, 0))
    
    def create_preview_section(self):
        """Create preview section."""
        preview_frame = ttk.LabelFrame(self.root, text="Preview", padding="10")
        preview_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(preview_frame, 
                  text="Scan Directory", 
                  command=self.scan_directory).pack(side=tk.LEFT)
        
        ttk.Label(preview_frame, 
                 text="(Scan first to see what will be renamed)").pack(side=tk.LEFT, padx=(10, 0))
    
    def create_action_buttons(self):
        """Create action buttons."""
        action_frame = ttk.LabelFrame(self.root, text="Actions", padding="10")
        action_frame.pack(fill=tk.X, padx=10, pady=5)
        
        button_frame = ttk.Frame(action_frame)
        button_frame.pack()
        
        ttk.Button(button_frame, 
                  text="Process All Files", 
                  command=self.process_all_files).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, 
                  text="Process Selected Files", 
                  command=self.process_selected_files).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, 
                  text="Clear Results", 
                  command=self.clear_results).pack(side=tk.LEFT, padx=5)
    
    def create_results_section(self):
        """Create results display section."""
        results_frame = ttk.LabelFrame(self.root, text="Results", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create treeview for results
        columns = ("Original", "Extracted Info", "New Name", "Status")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=10)
        
        # Configure columns
        self.results_tree.heading("Original", text="Original Filename")
        self.results_tree.heading("Extracted Info", text="Date | Company")
        self.results_tree.heading("New Name", text="New Filename")
        self.results_tree.heading("Status", text="Status")
        
        self.results_tree.column("Original", width=200)
        self.results_tree.column("Extracted Info", width=150)
        self.results_tree.column("New Name", width=200)
        self.results_tree.column("Status", width=100)
        
        # Enable multiple selection
        self.results_tree.configure(selectmode="extended")
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_tree.yview)
        h_scrollbar = ttk.Scrollbar(results_frame, orient="horizontal", command=self.results_tree.xview)
        
        self.results_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack widgets
        self.results_tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")
    
    def create_status_section(self):
        """Create status section."""
        status_frame = ttk.LabelFrame(self.root, text="Status", padding="10")
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_text = tk.Text(status_frame, height=4, wrap=tk.WORD, state=tk.DISABLED)
        
        status_scrollbar = ttk.Scrollbar(status_frame, command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=status_scrollbar.set)
        
        self.status_text.pack(side="left", fill="both", expand=True)
        status_scrollbar.pack(side="right", fill="y")
    
    def browse_source_directory(self):
        """Browse for source directory."""
        initial_dir = DEFAULT_BROWSE_DIR if os.path.exists(DEFAULT_BROWSE_DIR) else os.getcwd()
        directory = filedialog.askdirectory(title="Select Source Directory", initialdir=initial_dir)
        if directory:
            self.source_dir_var.set(directory)
    
    def browse_target_directory(self):
        """Browse for target directory."""
        initial_dir = DEFAULT_BROWSE_DIR if os.path.exists(DEFAULT_BROWSE_DIR) else os.getcwd()
        directory = filedialog.askdirectory(title="Select Target Directory", initialdir=initial_dir)
        if directory:
            self.target_dir_var.set(directory)
    
    def update_status(self, message, clear=False):
        """Update status text."""
        self.status_text.config(state=tk.NORMAL)
        if clear:
            self.status_text.delete(1.0, tk.END)
        
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        
        self.root.update_idletasks()
    
    def reset_fallback_tracking(self):
        """Reset fallback tracking for a new batch of files."""
        self.used_filenames.clear()
        self.fallback_date_counter = FALLBACK_START_DATE
    
    def get_selected_files(self):
        """Get selected files from the results tree."""
        selected_items = self.results_tree.selection()
        selected_files = []
        
        for item in selected_items:
            values = self.results_tree.item(item, "values")
            if values:
                original_filename = values[0]
                selected_files.append(original_filename)
        
        return selected_files
    
    def process_selected_files(self):
        """Process only the selected files."""
        source_dir = self.source_dir_var.get()
        
        if not source_dir or not os.path.exists(source_dir):
            messagebox.showerror("Error", "Please select a valid source directory")
            return
        
        if PDF_LIBRARY is None:
            messagebox.showerror("Error", "No PDF processing library available. Please install PyPDF2 or pdfplumber")
            return
        
        # Get selected files
        selected_files = self.get_selected_files()
        
        if not selected_files:
            messagebox.showwarning("No Selection", "Please select one or more files from the results list.")
            return
        
        # Confirm if not in preview mode
        if not self.preview_mode_var.get():
            action = "copy" if self.copy_files_var.get() else "move"
            response = messagebox.askyesno(
                "Confirm Processing", 
                f"This will {action} and rename {len(selected_files)} selected file(s). Continue?"
            )
            if not response:
                return
        
        self.update_status(f"Processing {len(selected_files)} selected files...", clear=True)
        
        source_path = Path(source_dir)
        processed_count = 0
        
        # Reset fallback tracking for selected files processing
        if not self.preview_mode_var.get():
            self.reset_fallback_tracking()
        
        for filename in selected_files:
            pdf_file = source_path / filename
            
            if pdf_file.exists() and pdf_file.is_file() and pdf_file.suffix.lower() == '.pdf':
                preview_only = self.preview_mode_var.get()
                self.process_single_file(pdf_file, preview_only=preview_only)
                processed_count += 1
            else:
                self.update_status(f"Warning: File not found or invalid: {filename}")
        
        if processed_count > 0:
            mode_text = "preview" if self.preview_mode_var.get() else "processing"
            self.update_status(f"Completed {mode_text} of {processed_count} selected files")
        else:
            self.update_status("No valid files were processed")
    
    def scan_directory(self):
        """Scan directory for PDF files and extract information."""
        source_dir = self.source_dir_var.get()
        
        if not source_dir or not os.path.exists(source_dir):
            messagebox.showerror("Error", "Please select a valid source directory")
            return
        
        if PDF_LIBRARY is None:
            messagebox.showerror("Error", "No PDF processing library available. Please install PyPDF2 or pdfplumber:\npip install PyPDF2\nor\npip install pdfplumber")
            return
        
        self.clear_results()
        self.reset_fallback_tracking()
        self.update_status("Scanning directory for PDF files...", clear=True)
        
        # Use set to avoid duplicates and get unique files only
        pdf_files = set()
        source_path = Path(source_dir)
        
        # Only check .pdf extension (case insensitive)
        for pdf_file in source_path.iterdir():
            if pdf_file.is_file() and pdf_file.suffix.lower() == '.pdf':
                pdf_files.add(pdf_file)
        
        if not pdf_files:
            self.update_status("No PDF files found in the selected directory")
            return
        
        self.update_status(f"Found {len(pdf_files)} PDF files. Processing...")
        
        for pdf_file in sorted(pdf_files):  # Sort for consistent order
            self.process_single_file(pdf_file, preview_only=True)
        
        self.update_status("Scanning completed")
    
    def process_single_file(self, pdf_path, preview_only=False):
        """Process a single PDF file."""
        try:
            filename = pdf_path.name
            self.update_status(f"Processing: {filename}")
            
            # Extract text from PDF
            text = extract_pdf_text(str(pdf_path))
            if not text or len(text.strip()) < 10:
                # Generate fallback name even for files with no extractable text
                new_filename, _ = generate_fallback_filename(
                    self.fallback_date_counter, 
                    FALLBACK_COMPANY_NAME, 
                    pdf_path.suffix, 
                    self.used_filenames
                )
                self.used_filenames.add(new_filename)
                self.fallback_date_counter += datetime.timedelta(days=1)
                
                self.add_result(filename, "No text | Fallback used", new_filename, "Fallback")
                return
            
            # Extract date and company
            invoice_date = extract_invoice_date(text)
            company_name = extract_company_name(text)
            
            # Create extracted info string
            date_str = invoice_date.strftime("%d/%m/%Y") if invoice_date else "Not found"
            company_str = company_name if company_name else "Not found"
            
            # Generate filename - use fallback if missing info
            if invoice_date and company_name:
                # Both date and company found - use normal naming
                new_filename = generate_new_filename(invoice_date, company_name, pdf_path.suffix)
                status = "Ready" if preview_only else "Processed"
                extracted_info = f"{date_str} | {company_str}"
                
                # Check for duplicates and handle them
                if new_filename in self.used_filenames:
                    # Generate fallback to avoid duplicate
                    new_filename, _ = generate_fallback_filename(
                        self.fallback_date_counter, 
                        company_name, 
                        pdf_path.suffix, 
                        self.used_filenames
                    )
                    status = "Fallback (duplicate)"
                    extracted_info = f"{date_str} | {company_str} (duplicate)"
                    self.fallback_date_counter += datetime.timedelta(days=1)
                
            else:
                # Missing information - use fallback naming
                fallback_company = company_name if company_name else FALLBACK_COMPANY_NAME
                new_filename, fallback_date_used = generate_fallback_filename(
                    self.fallback_date_counter, 
                    fallback_company, 
                    pdf_path.suffix, 
                    self.used_filenames
                )
                
                missing = []
                if not invoice_date:
                    missing.append("date")
                if not company_name:
                    missing.append("company")
                
                status = f"Fallback ({', '.join(missing)} missing)"
                extracted_info = f"{date_str} | {company_str} (fallback used)"
                self.fallback_date_counter = fallback_date_used + datetime.timedelta(days=1)
            
            # Track used filename
            self.used_filenames.add(new_filename)
            
            self.add_result(filename, extracted_info, new_filename, status)
            
            # If not preview mode, actually rename/copy the file
            if not preview_only and new_filename:
                success = self.rename_or_copy_file(pdf_path, new_filename)
                if success:
                    self.update_result_status(filename, "Success")
                else:
                    self.update_result_status(filename, "Failed")
            
        except Exception as e:
            # Generate fallback name even for processing errors
            try:
                new_filename, _ = generate_fallback_filename(
                    self.fallback_date_counter, 
                    FALLBACK_COMPANY_NAME, 
                    pdf_path.suffix, 
                    self.used_filenames
                )
                self.used_filenames.add(new_filename)
                self.fallback_date_counter += datetime.timedelta(days=1)
                
                self.add_result(filename, f"Error: {str(e)}", new_filename, "Error (fallback)")
            except:
                self.add_result(filename, f"Error: {str(e)}", "Processing failed", "Error")
            
            self.logger.error(f"Error processing {filename}: {e}")
    
    def rename_or_copy_file(self, source_path, new_filename):
        """Rename or copy file to new location."""
        try:
            target_dir = self.target_dir_var.get() or source_path.parent
            target_path = Path(target_dir) / new_filename
            
            # Ensure target directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if target file already exists
            if target_path.exists():
                response = messagebox.askyesno(
                    "File Exists", 
                    f"File '{new_filename}' already exists. Overwrite?"
                )
                if not response:
                    return False
            
            if self.copy_files_var.get():
                shutil.copy2(source_path, target_path)
                self.update_status(f"Copied: {source_path.name} -> {new_filename}")
            else:
                source_path.rename(target_path)
                self.update_status(f"Renamed: {source_path.name} -> {new_filename}")
            
            return True
            
        except Exception as e:
            self.update_status(f"Error renaming {source_path.name}: {e}")
            return False
    
    def add_result(self, original, extracted_info, new_name, status):
        """Add result to the results tree."""
        self.results_tree.insert("", "end", values=(original, extracted_info, new_name, status))
    
    def update_result_status(self, original_name, new_status):
        """Update the status of a specific result."""
        for item in self.results_tree.get_children():
            values = self.results_tree.item(item, "values")
            if values[0] == original_name:
                new_values = values[:-1] + (new_status,)
                self.results_tree.item(item, values=new_values)
                break
    
    def process_all_files(self):
        """Process all files in the source directory."""
        source_dir = self.source_dir_var.get()
        
        if not source_dir or not os.path.exists(source_dir):
            messagebox.showerror("Error", "Please select a valid source directory")
            return
        
        if PDF_LIBRARY is None:
            messagebox.showerror("Error", "No PDF processing library available. Please install PyPDF2 or pdfplumber")
            return
        
        # Confirm if not in preview mode
        if not self.preview_mode_var.get():
            action = "copy" if self.copy_files_var.get() else "move"
            response = messagebox.askyesno(
                "Confirm Processing", 
                f"This will {action} and rename files. Continue?"
            )
            if not response:
                return
        
        self.clear_results()
        self.reset_fallback_tracking()
        self.update_status("Processing all files...", clear=True)
        
        # Use set to avoid duplicates and get unique files only
        pdf_files = set()
        source_path = Path(source_dir)
        
        # Only check .pdf extension (case insensitive)
        for pdf_file in source_path.iterdir():
            if pdf_file.is_file() and pdf_file.suffix.lower() == '.pdf':
                pdf_files.add(pdf_file)
        
        if not pdf_files:
            self.update_status("No PDF files found in the selected directory")
            return
        
        for pdf_file in sorted(pdf_files):  # Sort for consistent order
            preview_only = self.preview_mode_var.get()
            self.process_single_file(pdf_file, preview_only=preview_only)
        
        self.update_status("Processing completed")
    
    def clear_results(self):
        """Clear the results tree."""
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

def main():
    """Main application entry point."""
    # Setup logging when the app actually runs (not at import time)
    setup_shared_logging("invoice_renamer")

    # Check for PDF processing libraries
    if PDF_LIBRARY is None:
        logger.warning("No PDF processing library found!")
        logger.warning("Please install: pip install pdfplumber or pip install PyPDF2")
        logger.warning("The application will start but PDF processing will not work.")

    # Create Tkinter root
    root = tk.Tk()
    
    # Create main application
    app = InvoiceRenamerGUI(root)
    
    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    main()