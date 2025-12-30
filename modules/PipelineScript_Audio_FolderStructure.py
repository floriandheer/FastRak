import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import shutil
import re
from pathlib import Path

# Add modules to path
MODULES_DIR = Path(__file__).parent
sys.path.insert(0, str(MODULES_DIR))

from shared_path_config import get_path_config

class FolderStructureCreator:
    def __init__(self, root):
        self.root = root
        self.root.title("Production Folder Structure")
        self.root.geometry("750x700")
        self.root.minsize(700, 550)

        # Initialize path config
        self.path_config = get_path_config()

        # Configure main window
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        
        # Create header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header_frame.grid_propagate(False)
        
        # Add title to header
        title_label = tk.Label(header_frame, text="Production Folder Structure", 
                              font=("Arial", 16, "bold"), fg="white", bg="#2c3e50")
        title_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Create main frame with preview only
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)  # Give more weight to preview
        main_frame.rowconfigure(0, weight=1)
        
        # Create form panel (left side)
        form_frame = ttk.LabelFrame(main_frame, text="Project Settings")
        form_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        form_frame.columnconfigure(1, weight=1)

        # Base directory (from path config)
        ttk.Label(form_frame, text="Base Directory:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        default_base = self.path_config.get_work_path("Audio").replace('\\', '/')
        self.base_dir_var = tk.StringVar(value=default_base)
        base_dir_entry = ttk.Entry(form_frame, textvariable=self.base_dir_var, width=40)
        base_dir_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=10)
        ttk.Button(form_frame, text="Browse", command=self.browse_base_dir).grid(row=0, column=2, padx=5, pady=10)
        
        # Name Client (formerly Client Name)
        ttk.Label(form_frame, text="Name Client:").grid(row=1, column=0, sticky="w", padx=10, pady=(10, 2))
        self.client_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.client_name_var, width=40).grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=(10, 2))
        
        # Personal checkbox (just as a standalone checkbox, no field)
        ttk.Label(form_frame, text="Personal:").grid(row=2, column=0, sticky="w", padx=10, pady=(0, 10))
        self.personal_var = tk.BooleanVar(value=False)
        personal_check = ttk.Checkbutton(form_frame, text="", variable=self.personal_var, 
                                      command=self.toggle_personal)
        personal_check.grid(row=2, column=1, sticky="w", padx=5, pady=(0, 10))
        
        # Name Project (formerly Project Name)
        ttk.Label(form_frame, text="Name Project:").grid(row=3, column=0, sticky="w", padx=10, pady=10)
        self.project_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.project_name_var, width=40).grid(row=3, column=1, columnspan=2, sticky="ew", padx=5, pady=10)
        
        # Project date
        ttk.Label(form_frame, text="Date:").grid(row=4, column=0, sticky="w", padx=10, pady=10)
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        date_entry = ttk.Entry(form_frame, textvariable=self.date_var, width=40)
        date_entry.grid(row=4, column=1, columnspan=2, sticky="ew", padx=5, pady=10)
        
        # Software version specifications
        spec_frame = ttk.LabelFrame(form_frame, text="3D Printing Specs")
        spec_frame.grid(row=5, column=0, columnspan=3, sticky="ew", padx=5, pady=10)
        spec_frame.columnconfigure(1, weight=1)
        
        # Houdini version
        ttk.Label(spec_frame, text="Houdini:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.houdini_var = tk.StringVar(value="19.5")
        ttk.Entry(spec_frame, textvariable=self.houdini_var, width=15).grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        # Blender version
        ttk.Label(spec_frame, text="Blender:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.blender_var = tk.StringVar(value="3.6")
        ttk.Entry(spec_frame, textvariable=self.blender_var, width=15).grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        # Replace Fusion text field with Slicer dropdown
        ttk.Label(spec_frame, text="Slicer:").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.slicer_var = tk.StringVar(value="Bambu Studio")
        slicer_combo = ttk.Combobox(spec_frame, textvariable=self.slicer_var, width=20, state="readonly")
        slicer_combo['values'] = ('Bambu Studio', 'PrusaSlicer', 'Cura', 'Simplify3D', 'Creality Slicer', 'Other')
        slicer_combo.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        
        # Add 3D Printer dropdown
        ttk.Label(spec_frame, text="3D Printer:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        self.printer_var = tk.StringVar(value="Bambu Lab X1 Carbon")
        printer_combo = ttk.Combobox(spec_frame, textvariable=self.printer_var, width=20, state="readonly")
        printer_combo['values'] = ('Bambu Lab X1 Carbon', 'Bambu Lab P1S', 'Bambu Lab X1', 'Prusa MK3S+', 'Creality Ender 3', 'Other')
        printer_combo.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        
        # Notes section
        notes_frame = ttk.LabelFrame(form_frame, text="Project Notes")
        notes_frame.grid(row=6, column=0, columnspan=3, sticky="nsew", padx=5, pady=10)
        notes_frame.columnconfigure(0, weight=1)
        notes_frame.rowconfigure(0, weight=1)
        
        # Notes text area with scrollbar
        self.notes_scrollbar = ttk.Scrollbar(notes_frame)
        self.notes_scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 5), pady=5)
        
        self.notes_text = tk.Text(notes_frame, wrap=tk.WORD, height=5,
                                yscrollcommand=self.notes_scrollbar.set)
        self.notes_text.grid(row=0, column=0, sticky="nsew", padx=(5, 0), pady=5)
        self.notes_scrollbar.config(command=self.notes_text.yview)
        
        # Create button with padding to make it larger
        create_btn = ttk.Button(form_frame, text="Create Project Structure", 
                               command=self.create_structure, padding=(20, 10))
        create_btn.grid(row=7, column=0, columnspan=3, pady=20)
        
        # Create preview panel (right side)
        preview_frame = ttk.LabelFrame(main_frame, text="Structure Preview")
        preview_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        
        # Preview text widget with scrollbar
        self.preview_scrollbar = ttk.Scrollbar(preview_frame)
        self.preview_scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.preview_text = tk.Text(preview_frame, wrap=tk.WORD, 
                                  yscrollcommand=self.preview_scrollbar.set)
        self.preview_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.preview_scrollbar.config(command=self.preview_text.yview)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, 
                                  relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=2, column=0, sticky="ew")
        
        # Define template path as constant (hidden from UI)
        self.template_dir_var = tk.StringVar(value='P:\_Structure\YYYY-MM-DD_Physical3DPrint_NameClient_NameProject')
        
        # Initialize preview
        self.update_preview()
        
        # Set up event bindings for live preview updates
        self.client_name_var.trace_add("write", lambda *args: self.update_preview())
        self.project_name_var.trace_add("write", lambda *args: self.update_preview())
        self.date_var.trace_add("write", lambda *args: self.update_preview())
        self.personal_var.trace_add("write", lambda *args: self.update_preview())
        self.houdini_var.trace_add("write", lambda *args: self.update_preview())
        self.blender_var.trace_add("write", lambda *args: self.update_preview())
        self.slicer_var.trace_add("write", lambda *args: self.update_preview())
        self.printer_var.trace_add("write", lambda *args: self.update_preview())
    
    def toggle_personal(self):
        """Toggle the Personal checkbox to auto-fill client name"""
        if self.personal_var.get():
            self.client_name_backup = self.client_name_var.get()  # Save current value
            self.client_name_var.set("Personal")
        else:
            # Restore previous value if it exists
            if hasattr(self, 'client_name_backup'):
                self.client_name_var.set(self.client_name_backup)
            else:
                self.client_name_var.set("")
        
        # Update preview
        self.update_preview()
    
    def browse_base_dir(self):
        """Open dialog to browse for base directory"""
        directory = filedialog.askdirectory()
        if directory:
            self.base_dir_var.set(directory)
            self.update_preview()
    
    def get_template_structure(self, template_dir):
        """Get directory structure from template folder"""
        if not os.path.isdir(template_dir):
            return None
        
        # Create a list to store the relative paths
        structure = []
        
        # Walk through the template directory
        for root, dirs, files in os.walk(template_dir):
            # Get the relative path
            rel_path = os.path.relpath(root, template_dir)
            if rel_path != '.':  # Skip the root directory
                structure.append(rel_path)
                
            # Add files with their relative paths
            for file in files:
                file_path = os.path.join(rel_path, file)
                if file_path != '.':
                    structure.append(file_path)
        
        return sorted(structure)
    
    def update_preview(self):
        """Update the preview of the folder structure to be created"""
        self.preview_text.delete(1.0, tk.END)
        
        # Get values from entry fields
        client = self.client_name_var.get() or "[Name Client]"
        project = self.project_name_var.get() or "[Name Project]"
        date = self.date_var.get() or datetime.now().strftime('%Y-%m-%d')
        template_dir = self.template_dir_var.get()
        
        # Get software specs
        houdini = self.houdini_var.get()
        blender = self.blender_var.get()
        slicer = self.slicer_var.get()
        printer = self.printer_var.get()
        
        # Get notes
        notes = self.notes_text.get(1.0, tk.END).strip()
        
        # Build the project directory name
        project_dir = f"{date}_{client}_{project}"
        
        # Display preview
        base_dir = self.base_dir_var.get()
        self.preview_text.insert(tk.END, f"Project will be created at:\n{base_dir}/{project_dir}\n\n")
        self.preview_text.insert(tk.END, f"Template source:\n{template_dir}\n\n")
        self.preview_text.insert(tk.END, "Software & Hardware Specifications:\n")
        self.preview_text.insert(tk.END, f"Houdini: {houdini}\n")
        self.preview_text.insert(tk.END, f"Blender: {blender}\n")
        self.preview_text.insert(tk.END, f"Slicer: {slicer}\n")
        self.preview_text.insert(tk.END, f"3D Printer: {printer}\n\n")
        
        # Preview notes
        if notes:
            self.preview_text.insert(tk.END, "Notes:\n")
            # Limit preview to first 100 characters if lengthy
            if len(notes) > 100:
                self.preview_text.insert(tk.END, f"{notes[:100]}...\n\n")
            else:
                self.preview_text.insert(tk.END, f"{notes}\n\n")
        
        # Get template structure
        self.preview_text.insert(tk.END, "Folder structure to be created:\n\n")
        
        # Check if template directory exists
        template_structure = self.get_template_structure(template_dir)
        if template_structure:
            # Build a dictionary to represent the directory tree
            dir_tree = {}
            for path in template_structure:
                parts = path.split(os.sep)
                current = dir_tree
                for part in parts:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
            
            # Function to display the directory tree
            def print_tree(tree, prefix=""):
                items = list(tree.items())
                for i, (name, subtree) in enumerate(items):
                    is_last = i == len(items) - 1
                    
                    # Replace YYY-MM-DD with actual date in the preview
                    display_name = name
                    if name == "YYY-MM-DD":
                        display_name = date
                        
                    self.preview_text.insert(tk.END, f"{prefix}{'└── ' if is_last else '├── '}{display_name}\n")
                    if subtree:  # If not a leaf node
                        extension = "    " if is_last else "│   "
                        print_tree(subtree, prefix + extension)
            
            # Display the tree
            print_tree(dir_tree)
        else:
            self.preview_text.insert(tk.END, "Template directory not found or no structure to display.\n")
            
        # Preview specifications file
        self.preview_text.insert(tk.END, "\nSpecifications file will be created at:\n")
        self.preview_text.insert(tk.END, f"_Library/Documents/project_specifications.txt\n")
    
    def create_structure(self):
        """Create the folder structure based on user input and template"""
        # Get values from entry fields
        base_dir = self.base_dir_var.get()
        client_name = self.client_name_var.get()
        project_name = self.project_name_var.get()
        date = self.date_var.get()
        template_dir = self.template_dir_var.get()
        
        # Get software specs
        houdini_version = self.houdini_var.get()
        blender_version = self.blender_var.get()
        slicer_software = self.slicer_var.get()
        printer_model = self.printer_var.get()
        
        # Validate inputs
        if not base_dir or not os.path.isdir(base_dir):
            messagebox.showerror("Error", "Please select a valid base directory.")
            return
            
        if not client_name:
            if self.personal_var.get():
                client_name = "Personal"
            else:
                messagebox.showerror("Error", "Please enter a name client.")
                return
            
        if not project_name:
            messagebox.showerror("Error", "Please enter a name project.")
            return
            
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
            
        if not template_dir or not os.path.isdir(template_dir):
            messagebox.showerror("Error", "Please select a valid template directory.")
            return

        # Build the base directory path
        project_dir = os.path.join(base_dir, f'{date}_{client_name}_{project_name}')

        try:
            # Create the project directory
            os.makedirs(project_dir, exist_ok=True)
            
            # Copy template structure
            self.copy_template(template_dir, project_dir, date)
            
            # Ensure _Library/Documents exists for specifications file
            docs_dir = os.path.join(project_dir, '_Library/Documents')
            os.makedirs(docs_dir, exist_ok=True)
            
            # Create specifications text file
            self.create_specs_file(project_dir, client_name, project_name, date, 
                                   houdini_version, blender_version, slicer_software, printer_model)
            
            self.status_var.set(f"Created project structure for {client_name}_{project_name}")
            
            # Show success message
            if messagebox.askyesno("Success", f"Project structure created successfully at:\n\n{project_dir}\n\nWould you like to open the folder?"):
                self.open_folder(project_dir)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create structure: {str(e)}")
            self.status_var.set("Error creating project structure")
    
    def copy_template(self, src, dst, date):
        """Copy template structure with date folder renaming"""
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
                
            if os.path.isdir(s):
                # Check if this is a YYY-MM-DD folder that needs to be renamed
                if item == "YYY-MM-DD":
                    d = os.path.join(os.path.dirname(d), date)
                
                os.makedirs(d, exist_ok=True)
                self.copy_template(s, d, date)
            else:
                # Copy the file
                if not os.path.exists(d) or not os.path.samefile(s, d):
                    shutil.copy2(s, d)
            
    def create_specs_file(self, project_dir, client_name, project_name, date, 
                          houdini_version, blender_version, slicer_software, printer_model):
        """Create a specifications text file in the Documents folder"""
        try:
            # Create file path
            docs_dir = os.path.join(project_dir, '_Library/Documents')
            spec_file_path = os.path.join(docs_dir, 'project_specifications.txt')
            
            # Current timestamp
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Get notes from the text area
            notes = self.notes_text.get(1.0, tk.END).strip()
            if not notes:
                notes = "No notes provided."
            
            # Create file content
            content = f"""PROJECT SPECIFICATIONS
======================
Generated: {timestamp}

Project: {project_name}
Client: {client_name}
Date: {date}

SOFTWARE VERSIONS
======================
Houdini: {houdini_version}
Blender: {blender_version}
Slicer: {slicer_software}

HARDWARE
======================
3D Printer: {printer_model}

NOTES
======================
{notes}
"""
            
            # Write to file
            with open(spec_file_path, 'w') as file:
                file.write(content)
                
            self.status_var.set(f"Created project structure and specifications file")
                
        except Exception as e:
            messagebox.showwarning("Warning", f"Created folder structure but failed to create specifications file: {str(e)}")
            self.status_var.set("Warning: Failed to create specifications file")
    
    def open_folder(self, path):
        """Open the folder in file explorer"""
        if os.path.exists(path):
            try:
                # Platform-specific folder opening
                import subprocess
                if os.name == 'nt':  # Windows
                    os.startfile(path)
                elif os.name == 'posix':  # macOS and Linux
                    if os.uname().sysname == 'Darwin':  # macOS
                        subprocess.call(['open', path])
                    else:  # Linux
                        subprocess.call(['xdg-open', path])
            except Exception as e:
                print(f"Could not open folder: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = FolderStructureCreator(root)
    root.mainloop()