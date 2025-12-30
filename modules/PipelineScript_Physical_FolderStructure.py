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
        self.root.title("3D Printing Folder Structure")
        self.root.geometry("750x850")
        self.root.minsize(700, 900)

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
        title_label = tk.Label(header_frame, text="3D Printing Folder Structure", 
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
        default_base = self.path_config.get_work_path("Physical").replace('\\', '/')
        self.base_dir_var = tk.StringVar(value=default_base)
        base_dir_entry = ttk.Entry(form_frame, textvariable=self.base_dir_var, width=40)
        base_dir_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=10)
        ttk.Button(form_frame, text="Browse", command=self.browse_base_dir).grid(row=0, column=2, padx=5, pady=10)
        
        # Name Client (formerly Client Name)
        ttk.Label(form_frame, text="Name Client:").grid(row=1, column=0, sticky="w", padx=10, pady=(10, 2))
        self.client_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.client_name_var, width=40).grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=(10, 2))
        
        # Project type checkboxes (Personal, Product, Project)
        project_type_frame = ttk.Frame(form_frame)
        project_type_frame.grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=(0, 10))

        # Personal checkbox
        ttk.Label(project_type_frame, text="Project Type:").grid(row=0, column=0, sticky="w", padx=10, pady=(0, 10))

        self.personal_var = tk.BooleanVar(value=False)
        personal_check = ttk.Checkbutton(project_type_frame, text="Personal", variable=self.personal_var,
                                       command=lambda: self.toggle_project_type('personal'))
        personal_check.grid(row=0, column=1, sticky="w", padx=5, pady=(0, 10))

        # Product checkbox
        self.product_var = tk.BooleanVar(value=False)
        product_check = ttk.Checkbutton(project_type_frame, text="Product", variable=self.product_var,
                                      command=lambda: self.toggle_project_type('product'))
        product_check.grid(row=0, column=2, sticky="w", padx=20, pady=(0, 10))

        # Project checkbox
        self.project_var = tk.BooleanVar(value=False)
        project_check = ttk.Checkbutton(project_type_frame, text="Project", variable=self.project_var,
                                       command=lambda: self.toggle_project_type('project'))
        project_check.grid(row=0, column=3, sticky="w", padx=20, pady=(0, 10))
        
        # Name Project (formerly Project Name)
        ttk.Label(form_frame, text="Name Project:").grid(row=3, column=0, sticky="w", padx=10, pady=10)
        self.project_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.project_name_var, width=40).grid(row=3, column=1, columnspan=2, sticky="ew", padx=5, pady=10)
        
        # Project date
        ttk.Label(form_frame, text="Date:").grid(row=4, column=0, sticky="w", padx=10, pady=10)
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        date_entry = ttk.Entry(form_frame, textvariable=self.date_var, width=40)
        date_entry.grid(row=4, column=1, columnspan=2, sticky="ew", padx=5, pady=10)
        
        # Production Tools section
        production_frame = ttk.LabelFrame(form_frame, text="Production Tools")
        production_frame.grid(row=5, column=0, columnspan=3, sticky="ew", padx=5, pady=10)
        production_frame.columnconfigure(2, weight=1)
        
        # Houdini version with checkbox
        self.use_houdini_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(production_frame, variable=self.use_houdini_var, 
                       command=self.toggle_software_fields).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        ttk.Label(production_frame, text="Houdini:").grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.houdini_var = tk.StringVar(value="20.5")
        self.houdini_entry = ttk.Entry(production_frame, textvariable=self.houdini_var, width=15)
        self.houdini_entry.grid(row=0, column=2, sticky="w", padx=5, pady=5)
        
        # Blender version with checkbox
        self.use_blender_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(production_frame, variable=self.use_blender_var, 
                       command=self.toggle_software_fields).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        
        ttk.Label(production_frame, text="Blender:").grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.blender_var = tk.StringVar(value="4.4")
        self.blender_entry = ttk.Entry(production_frame, textvariable=self.blender_var, width=15)
        self.blender_entry.grid(row=1, column=2, sticky="w", padx=5, pady=5)
        
        # FreeCAD version with checkbox
        self.use_freecad_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(production_frame, variable=self.use_freecad_var, 
                       command=self.toggle_software_fields).grid(row=2, column=0, sticky="w", padx=5, pady=5)
        
        ttk.Label(production_frame, text="FreeCAD:").grid(row=2, column=1, sticky="w", padx=5, pady=5)
        self.freecad_var = tk.StringVar(value="0.21")
        self.freecad_entry = ttk.Entry(production_frame, textvariable=self.freecad_var, width=15)
        self.freecad_entry.grid(row=2, column=2, sticky="w", padx=5, pady=5)
        
        # Alibre version with checkbox
        self.use_alibre_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(production_frame, variable=self.use_alibre_var, 
                       command=self.toggle_software_fields).grid(row=3, column=0, sticky="w", padx=5, pady=5)
        
        ttk.Label(production_frame, text="Alibre:").grid(row=3, column=1, sticky="w", padx=5, pady=5)
        self.alibre_var = tk.StringVar(value="2024")
        self.alibre_entry = ttk.Entry(production_frame, textvariable=self.alibre_var, width=15)
        self.alibre_entry.grid(row=3, column=2, sticky="w", padx=5, pady=5)
        
        # Affinity version with checkbox
        self.use_affinity_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(production_frame, variable=self.use_affinity_var, 
                       command=self.toggle_software_fields).grid(row=4, column=0, sticky="w", padx=5, pady=5)
        
        ttk.Label(production_frame, text="Affinity:").grid(row=4, column=1, sticky="w", padx=5, pady=5)
        self.affinity_var = tk.StringVar(value="2.0")
        self.affinity_entry = ttk.Entry(production_frame, textvariable=self.affinity_var, width=15)
        self.affinity_entry.grid(row=4, column=2, sticky="w", padx=5, pady=5)
        
        # Hardware specifications
        hardware_frame = ttk.LabelFrame(form_frame, text="Hardware Specifications")
        hardware_frame.grid(row=6, column=0, columnspan=3, sticky="ew", padx=5, pady=10)
        hardware_frame.columnconfigure(2, weight=1)
        
        # Slicer dropdown
        ttk.Label(hardware_frame, text="Slicer:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.slicer_var = tk.StringVar(value="Bambu Studio")
        slicer_combo = ttk.Combobox(hardware_frame, textvariable=self.slicer_var, width=20, state="readonly")
        slicer_combo['values'] = ('Bambu Studio', 'PrusaSlicer', 'Cura', 'Simplify3D', 'Creality Slicer', 'Other')
        slicer_combo.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        # 3D Printer dropdown
        ttk.Label(hardware_frame, text="3D Printer:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.printer_var = tk.StringVar(value="Bambu Lab X1 Carbon")
        printer_combo = ttk.Combobox(hardware_frame, textvariable=self.printer_var, width=20, state="readonly")
        printer_combo['values'] = ('Bambu Lab X1 Carbon', 'Bambu Lab P1S', 'Bambu Lab X1', 'Prusa MK3S+', 'Creality Ender 3', 'Other')
        printer_combo.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        # Project Structure Options
        structure_frame = ttk.LabelFrame(form_frame, text="Project Structure Options")
        structure_frame.grid(row=7, column=0, columnspan=3, sticky="ew", padx=5, pady=10)
        
        # Preproduction folder checkbox
        self.include_preproduction_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(structure_frame, text="Include Preproduction folder", 
                       variable=self.include_preproduction_var,
                       command=self.update_preview).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        # Library folder checkbox
        self.include_library_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(structure_frame, text="Include _LIBRARY folder", 
                       variable=self.include_library_var,
                       command=self.update_preview).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        
        # Notes section
        notes_frame = ttk.LabelFrame(form_frame, text="Project Notes")
        notes_frame.grid(row=8, column=0, columnspan=3, sticky="nsew", padx=5, pady=10)
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
        create_btn.grid(row=9, column=0, columnspan=3, pady=20)
        
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
        
        # Initialize field states
        self.toggle_software_fields()
        
        # Initialize preview
        self.update_preview()
        
        # Set up event bindings for live preview updates
        self.client_name_var.trace_add("write", lambda *args: self.update_preview())
        self.project_name_var.trace_add("write", lambda *args: self.update_preview())
        self.date_var.trace_add("write", lambda *args: self.update_preview())
        self.personal_var.trace_add("write", lambda *args: self.update_preview())
        self.product_var.trace_add("write", lambda *args: self.update_preview())
        self.project_var.trace_add("write", lambda *args: self.update_preview())
        self.base_dir_var.trace_add("write", lambda *args: self.update_preview())
        self.houdini_var.trace_add("write", lambda *args: self.update_preview())
        self.blender_var.trace_add("write", lambda *args: self.update_preview())
        self.alibre_var.trace_add("write", lambda *args: self.update_preview())
        self.affinity_var.trace_add("write", lambda *args: self.update_preview())
        self.use_houdini_var.trace_add("write", lambda *args: self.update_preview())
        self.use_blender_var.trace_add("write", lambda *args: self.update_preview())
        self.use_alibre_var.trace_add("write", lambda *args: self.update_preview())
        self.use_affinity_var.trace_add("write", lambda *args: self.update_preview())
        self.slicer_var.trace_add("write", lambda *args: self.update_preview())
        self.printer_var.trace_add("write", lambda *args: self.update_preview())
        self.include_preproduction_var.trace_add("write", lambda *args: self.update_preview())
        self.include_library_var.trace_add("write", lambda *args: self.update_preview())
    
    def toggle_project_type(self, clicked_type):
        """Toggle project type checkboxes and update related fields"""
        # Ensure only one project type is selected at a time
        if clicked_type == 'personal':
            if self.personal_var.get():
                self.product_var.set(False)
                self.project_var.set(False)
        elif clicked_type == 'product':
            if self.product_var.get():
                self.personal_var.set(False)
                self.project_var.set(False)
        elif clicked_type == 'project':
            if self.project_var.get():
                self.personal_var.set(False)
                self.product_var.set(False)

        # Save current values if switching to a special project type
        if (self.personal_var.get() or self.product_var.get() or self.project_var.get()) and not hasattr(self, 'client_name_backup'):
            self.client_name_backup = self.client_name_var.get()
            self.base_dir_backup = self.base_dir_var.get()

        # Set appropriate values based on project type
        if self.personal_var.get():
            self.client_name_var.set("Personal")
            self.base_dir_var.set("I:/Physical/_personal")
        elif self.product_var.get():
            self.client_name_var.set("alles3d")
            self.base_dir_var.set("I:/Physical/Product")
        elif self.project_var.get():
            # Only set base directory, let user enter client name
            self.base_dir_var.set("I:/Physical/Project")
            # Restore client name if previously saved
            if hasattr(self, 'client_name_backup'):
                self.client_name_var.set(self.client_name_backup)
        else:
            # Restore previous values if they exist
            if hasattr(self, 'client_name_backup'):
                self.client_name_var.set(self.client_name_backup)
            else:
                self.client_name_var.set("")

            if hasattr(self, 'base_dir_backup'):
                self.base_dir_var.set(self.base_dir_backup)
            else:
                self.base_dir_var.set("I:/Physical")

        # Update preview
        self.update_preview()
    
    def toggle_software_fields(self):
        """Enable/disable software version fields based on checkbox states"""
        # Houdini
        if self.use_houdini_var.get():
            self.houdini_entry.configure(state="normal")
        else:
            self.houdini_entry.configure(state="disabled")
        
        # Blender
        if self.use_blender_var.get():
            self.blender_entry.configure(state="normal")
        else:
            self.blender_entry.configure(state="disabled")
            
        # FreeCAD
        if self.use_freecad_var.get():
            self.freecad_entry.configure(state="normal")
        else:
            self.freecad_entry.configure(state="disabled")
            
        # Alibre
        if self.use_alibre_var.get():
            self.alibre_entry.configure(state="normal")
        else:
            self.alibre_entry.configure(state="disabled")
            
        # Affinity
        if self.use_affinity_var.get():
            self.affinity_entry.configure(state="normal")
        else:
            self.affinity_entry.configure(state="disabled")
        
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
    
    def get_folder_structure_preview(self):
        """Generate the folder structure that will be created"""
        folders = []

        # Track numbered folders in the correct order
        numbered_folders = []

        # Incoming folder (always first - starts at 00)
        numbered_folders.append("Incoming")

        # Optional preproduction folder (comes after Incoming)
        if self.include_preproduction_var.get():
            numbered_folders.append("Preproduction")

        # Production folder (always included)
        numbered_folders.append("Production")

        # Outgoing folder (always included)
        numbered_folders.append("Outgoing")

        # Apply numbering to main folders starting at 00
        counter = 0
        folder_mapping = {}  # Map from unnumbered to numbered names
        for folder_name in numbered_folders:
            numbered_name = f"{counter:02d}_{folder_name}"
            folder_mapping[folder_name] = numbered_name
            folders.append(numbered_name)
            counter += 1

        # Software-specific folders in Production organized by 3D and 2D
        production_folder = folder_mapping.get("Production", "Production")

        # 3D tools
        if self.use_houdini_var.get():
            folders.append(f"{production_folder}/3D/Houdini")
        if self.use_blender_var.get():
            folders.append(f"{production_folder}/3D/Blender")
        if self.use_freecad_var.get():
            folders.append(f"{production_folder}/3D/FreeCAD")
        if self.use_alibre_var.get():
            folders.append(f"{production_folder}/3D/Alibre")

        # 2D tools
        if self.use_affinity_var.get():
            folders.append(f"{production_folder}/2D/Affinity")

        # Documentation folder in Production
        folders.append(f"{production_folder}/Documentation")
        folders.append(f"{production_folder}/Documentation/Photo")
        folders.append(f"{production_folder}/Documentation/Photo/RAW")
        folders.append(f"{production_folder}/Documentation/Video")
        folders.append(f"{production_folder}/Documentation/Video/Footage")

        # Outgoing subfolders - date folder only
        outgoing_folder = folder_mapping.get("Outgoing", "Outgoing")
        # Get date for date-named folder
        date = self.date_var.get() or datetime.now().strftime('%Y-%m-%d')
        folders.append(f"{outgoing_folder}/{date}")

        # Optional library folder (not numbered, underscore prefix)
        if self.include_library_var.get():
            folders.append("_LIBRARY")
            folders.append("_LIBRARY/Documents")
            folders.append("_LIBRARY/Pipeline")
            folders.append("_LIBRARY/Pipeline/Plugins")
            folders.append("_LIBRARY/Pipeline/Scripts")

        return sorted(folders)
    
    def update_preview(self):
        """Update the preview of the folder structure to be created"""
        self.preview_text.delete(1.0, tk.END)
        
        # Get values from entry fields
        client = self.client_name_var.get() or "[Name Client]"
        project = self.project_name_var.get() or "[Name Project]"
        date = self.date_var.get() or datetime.now().strftime('%Y-%m-%d')
        
        # Get software specs
        software_list = []
        if self.use_houdini_var.get():
            software_list.append(f"Houdini: {self.houdini_var.get()}")
        if self.use_blender_var.get():
            software_list.append(f"Blender: {self.blender_var.get()}")
        if self.use_freecad_var.get():
            software_list.append(f"FreeCAD: {self.freecad_var.get()}")
        if self.use_alibre_var.get():
            software_list.append(f"Alibre: {self.alibre_var.get()}")
        if self.use_affinity_var.get():
            software_list.append(f"Affinity: {self.affinity_var.get()}")
        
        slicer = self.slicer_var.get()
        printer = self.printer_var.get()
        
        # Get notes
        notes = self.notes_text.get(1.0, tk.END).strip()
        
        # Build the project directory name based on project type
        if self.personal_var.get() or self.product_var.get():
            project_dir = f"{date}_3DPrint_{project}"
        else:
            project_dir = f"{date}_3DPrint_{client}_{project}"
        
        # Display preview
        base_dir = self.base_dir_var.get()
        self.preview_text.insert(tk.END, f"Project will be created at:\n{base_dir}/{project_dir}\n\n")
        
        # Software & Hardware Specifications
        self.preview_text.insert(tk.END, "Production Tools:\n")
        if software_list:
            for software in software_list:
                self.preview_text.insert(tk.END, f"• {software}\n")
        else:
            self.preview_text.insert(tk.END, "• No production tools selected\n")
        
        self.preview_text.insert(tk.END, f"\nHardware:\n")
        self.preview_text.insert(tk.END, f"• Slicer: {slicer}\n")
        self.preview_text.insert(tk.END, f"• 3D Printer: {printer}\n\n")
        
        # Preview notes
        if notes:
            self.preview_text.insert(tk.END, "Notes:\n")
            # Limit preview to first 100 characters if lengthy
            if len(notes) > 100:
                self.preview_text.insert(tk.END, f"{notes[:100]}...\n\n")
            else:
                self.preview_text.insert(tk.END, f"{notes}\n\n")
        
        # Folder structure to be created
        self.preview_text.insert(tk.END, "Folder structure to be created:\n\n")
        
        folders = self.get_folder_structure_preview()
        
        # Build a dictionary to represent the directory tree
        dir_tree = {}
        for path in folders:
            parts = path.split('/')
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
                
                self.preview_text.insert(tk.END, f"{prefix}{'└── ' if is_last else '├── '}{name}\n")
                if subtree:  # If not a leaf node
                    extension = "    " if is_last else "│   "
                    print_tree(subtree, prefix + extension)
        
        # Display the tree
        print_tree(dir_tree)
        
        # Preview specifications file
        self.preview_text.insert(tk.END, "\nSpecifications file will be created at:\n")
        if self.include_library_var.get():
            self.preview_text.insert(tk.END, f"_LIBRARY/Documents/project_specifications.txt\n")
        else:
            self.preview_text.insert(tk.END, f"project_specifications.txt (in project root)\n")
    
    def create_structure(self):
        """Create the folder structure based on user input"""
        # Get values from entry fields
        base_dir = self.base_dir_var.get()
        client_name = self.client_name_var.get()
        project_name = self.project_name_var.get()
        date = self.date_var.get()
        
        # Get software specs
        software_specs = {}
        if self.use_houdini_var.get():
            software_specs['Houdini'] = self.houdini_var.get()
        if self.use_blender_var.get():
            software_specs['Blender'] = self.blender_var.get()
        if self.use_freecad_var.get():
            software_specs['FreeCAD'] = self.freecad_var.get()
        if self.use_alibre_var.get():
            software_specs['Alibre'] = self.alibre_var.get()
        if self.use_affinity_var.get():
            software_specs['Affinity'] = self.affinity_var.get()
        
        slicer_software = self.slicer_var.get()
        printer_model = self.printer_var.get()
        
        # Validate inputs
        if not base_dir or not os.path.isdir(base_dir):
            messagebox.showerror("Error", "Please select a valid base directory.")
            return

        if not client_name:
            if self.personal_var.get():
                client_name = "Personal"
            elif self.product_var.get():
                client_name = "alles3d"
            elif not self.project_var.get():
                messagebox.showerror("Error", "Please enter a name client.")
                return

        if not project_name:
            messagebox.showerror("Error", "Please enter a name project.")
            return

        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        # Build the base directory path based on project type
        if self.personal_var.get() or self.product_var.get():
            project_dir = os.path.join(base_dir, f'{date}_3DPrint_{project_name}')
        else:
            project_dir = os.path.join(base_dir, f'{date}_3DPrint_{client_name}_{project_name}')

        try:
            # Create the project directory
            os.makedirs(project_dir, exist_ok=True)
            
            # Create folder structure
            self.create_folder_structure(project_dir, date, software_specs)
            
            # Create specifications text file
            self.create_specs_file(project_dir, client_name, project_name, date, 
                                   software_specs, slicer_software, printer_model)
            
            self.status_var.set(f"Created project structure for {project_name}")
            
            # Show success message
            if messagebox.askyesno("Success", f"Project structure created successfully at:\n\n{project_dir}\n\nWould you like to open the folder?"):
                self.open_folder(project_dir)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create structure: {str(e)}")
            self.status_var.set("Error creating project structure")
    
    def create_folder_structure(self, project_dir, date, software_specs):
        """Create the folder structure dynamically"""
        folders_to_create = []

        # Track numbered folders in the correct order
        numbered_folders = []

        # Incoming folder (always first - starts at 00)
        numbered_folders.append("Incoming")

        # Optional preproduction folder (comes after Incoming)
        if self.include_preproduction_var.get():
            numbered_folders.append("Preproduction")

        # Production folder (always included)
        numbered_folders.append("Production")

        # Outgoing folder (always included)
        numbered_folders.append("Outgoing")

        # Apply numbering to main folders starting at 00
        counter = 0
        folder_mapping = {}  # Map from unnumbered to numbered names
        for folder_name in numbered_folders:
            numbered_name = f"{counter:02d}_{folder_name}"
            folder_mapping[folder_name] = numbered_name
            folders_to_create.append(numbered_name)
            counter += 1

        # Software-specific folders in Production organized by 3D and 2D
        production_folder = folder_mapping.get("Production", "Production")

        # 3D tools
        if 'Houdini' in software_specs:
            folders_to_create.append(f"{production_folder}/3D/Houdini")
        if 'Blender' in software_specs:
            folders_to_create.append(f"{production_folder}/3D/Blender")
        if 'FreeCAD' in software_specs:
            folders_to_create.append(f"{production_folder}/3D/FreeCAD")
        if 'Alibre' in software_specs:
            folders_to_create.append(f"{production_folder}/3D/Alibre")

        # 2D tools
        if 'Affinity' in software_specs:
            folders_to_create.append(f"{production_folder}/2D/Affinity")

        # Documentation folder in Production
        folders_to_create.append(f"{production_folder}/Documentation")
        folders_to_create.append(f"{production_folder}/Documentation/Product_Photo")
        folders_to_create.append(f"{production_folder}/Documentation/Product_Photo/RAW")
        folders_to_create.append(f"{production_folder}/Documentation/Product_Video")
        folders_to_create.append(f"{production_folder}/Documentation/Product_Video/Footage")

        # Outgoing subfolders - date folder only
        outgoing_folder = folder_mapping.get("Outgoing", "Outgoing")
        folders_to_create.append(f"{outgoing_folder}/{date}")

        # Optional library folder (not numbered, underscore prefix)
        if self.include_library_var.get():
            folders_to_create.append("_LIBRARY")
            folders_to_create.append("_LIBRARY/Documents")
            folders_to_create.append("_LIBRARY/Pipeline")
            folders_to_create.append("_LIBRARY/Pipeline/Plugins")
            folders_to_create.append("_LIBRARY/Pipeline/Scripts")

        # Create all folders
        for folder in folders_to_create:
            folder_path = os.path.join(project_dir, folder)
            os.makedirs(folder_path, exist_ok=True)
    
    def create_specs_file(self, project_dir, client_name, project_name, date, 
                          software_specs, slicer_software, printer_model):
        """Create a specifications text file"""
        try:
            # Determine file location based on _LIBRARY folder setting
            if self.include_library_var.get():
                docs_dir = os.path.join(project_dir, '_LIBRARY/Documents')
                spec_file_path = os.path.join(docs_dir, 'project_specifications.txt')
            else:
                spec_file_path = os.path.join(project_dir, 'project_specifications.txt')
            
            # Current timestamp
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Get notes from the text area
            notes = self.notes_text.get(1.0, tk.END).strip()
            if not notes:
                notes = "No notes provided."
            
            # Create software section content
            software_content = "PRODUCTION TOOLS\n======================\n"
            if software_specs:
                for software, version in software_specs.items():
                    software_content += f"{software}: {version}\n"
            else:
                software_content += "No production tools selected.\n"
            
            # Create project structure info
            structure_content = "PROJECT STRUCTURE\n======================\n"
            if self.include_preproduction_var.get():
                structure_content += "✓ Preproduction folder included\n"
            else:
                structure_content += "✗ Preproduction folder not included\n"
                
            if self.include_library_var.get():
                structure_content += "✓ _LIBRARY folder included\n"
            else:
                structure_content += "✗ _LIBRARY folder not included\n"
            
            # Create file content
            content = f"""PROJECT SPECIFICATIONS
======================
Generated: {timestamp}

Project: {project_name}
Client: {client_name}
Date: {date}

{software_content}
HARDWARE
======================
Slicer: {slicer_software}
3D Printer: {printer_model}

{structure_content}
NOTES
======================
{notes}
"""
            
            # Write to file
            with open(spec_file_path, 'w', encoding='utf-8') as file:
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