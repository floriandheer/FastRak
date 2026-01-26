import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import shutil
from pathlib import Path

# Add modules to path
MODULES_DIR = Path(__file__).parent
sys.path.insert(0, str(MODULES_DIR))

from shared_path_config import get_path_config

class FolderStructureCreator:
    def __init__(self, root_or_frame, embedded=False, on_project_created=None, on_cancel=None):
        """
        Initialize the Folder Structure Creator.

        Args:
            root_or_frame: Either a Tk root window (standalone) or a Frame (embedded)
            embedded: If True, build UI into provided frame without window configuration
            on_project_created: Callback function called with project_data when project is created
            on_cancel: Callback function called when user cancels
        """
        self.embedded = embedded
        self.on_project_created = on_project_created
        self.on_cancel = on_cancel

        if embedded:
            # Embedded mode: root_or_frame is the parent frame
            self.root = root_or_frame.winfo_toplevel()
            self.parent = root_or_frame
        else:
            # Standalone mode: root_or_frame is the Tk root
            self.root = root_or_frame
            self.parent = root_or_frame
            self.root.title("TouchDesigner Folder Structure")
            self.root.geometry("750x700")
            self.root.minsize(700, 550)

        # Initialize path config
        self.path_config = get_path_config()

        if not embedded:
            # Configure main window (standalone only)
            self.root.columnconfigure(0, weight=1)
            self.root.rowconfigure(1, weight=1)

            # Create header (standalone only)
            header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
            header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
            header_frame.grid_propagate(False)

            # Add title to header
            title_label = tk.Label(header_frame, text="TouchDesigner Folder Structure",
                                  font=("Arial", 16, "bold"), fg="white", bg="#2c3e50")
            title_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Create main frame with preview only
        if embedded:
            main_frame = ttk.Frame(self.parent)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        else:
            main_frame = ttk.Frame(self.root)
            main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=1)

        # Create form panel (left side)
        form_frame = ttk.LabelFrame(main_frame, text="Project Settings")
        form_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        form_frame.columnconfigure(1, weight=1)

        # Base directory (from path config)
        ttk.Label(form_frame, text="Base Directory:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        default_base = self.path_config.get_work_path("RealTime").replace('\\', '/')
        self.base_dir_var = tk.StringVar(value=default_base)
        base_dir_entry = ttk.Entry(form_frame, textvariable=self.base_dir_var, width=40)
        base_dir_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=10)
        ttk.Button(form_frame, text="Browse", command=self.browse_base_dir).grid(row=0, column=2, padx=5, pady=10)

        # Name Client
        ttk.Label(form_frame, text="Name Client:").grid(row=1, column=0, sticky="w", padx=10, pady=(10, 2))
        self.client_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.client_name_var, width=40).grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=(10, 2))

        # Personal checkbox
        ttk.Label(form_frame, text="Personal:").grid(row=2, column=0, sticky="w", padx=10, pady=(0, 10))
        self.personal_var = tk.BooleanVar(value=False)
        personal_check = ttk.Checkbutton(form_frame, text="", variable=self.personal_var,
                                      command=self.toggle_personal)
        personal_check.grid(row=2, column=1, sticky="w", padx=5, pady=(0, 10))

        # Name Project
        ttk.Label(form_frame, text="Name Project:").grid(row=3, column=0, sticky="w", padx=10, pady=10)
        self.project_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.project_name_var, width=40).grid(row=3, column=1, columnspan=2, sticky="ew", padx=5, pady=10)

        # Project date
        ttk.Label(form_frame, text="Date:").grid(row=4, column=0, sticky="w", padx=10, pady=10)
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        date_entry = ttk.Entry(form_frame, textvariable=self.date_var, width=40)
        date_entry.grid(row=4, column=1, columnspan=2, sticky="ew", padx=5, pady=10)

        # Software version specifications
        spec_frame = ttk.LabelFrame(form_frame, text="Software Specs")
        spec_frame.grid(row=5, column=0, columnspan=3, sticky="ew", padx=5, pady=10)
        spec_frame.columnconfigure(1, weight=1)

        # TouchDesigner version
        ttk.Label(spec_frame, text="TouchDesigner:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.touchdesigner_var = tk.StringVar(value="2023.11760")
        ttk.Entry(spec_frame, textvariable=self.touchdesigner_var, width=15).grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # Python version
        ttk.Label(spec_frame, text="Python:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.python_var = tk.StringVar(value="3.11")
        ttk.Entry(spec_frame, textvariable=self.python_var, width=15).grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # Resolution/aspect ratio
        ttk.Label(spec_frame, text="Resolution:").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.resolution_var = tk.StringVar(value="1920x1080")
        ttk.Entry(spec_frame, textvariable=self.resolution_var, width=15).grid(row=2, column=1, sticky="w", padx=5, pady=5)

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

        # Button frame for Create and Cancel buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=7, column=0, columnspan=3, pady=20)

        # Create button with padding
        create_btn = ttk.Button(button_frame, text="Create Project Structure",
                               command=self.create_structure, padding=(20, 10))
        create_btn.pack(side=tk.LEFT, padx=5)

        # Cancel button (shown in embedded mode)
        if self.embedded:
            cancel_btn = ttk.Button(button_frame, text="Cancel",
                                   command=self._handle_cancel, padding=(20, 10))
            cancel_btn.pack(side=tk.LEFT, padx=5)

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

        # Status bar (only in standalone mode)
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        if not self.embedded:
            self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1,
                                      relief=tk.SUNKEN, anchor=tk.W)
            self.status_bar.grid(row=2, column=0, sticky="ew")

        # Initialize preview
        self.update_preview()

        # Set up event bindings for live preview updates
        self.client_name_var.trace_add("write", lambda *args: self.update_preview())
        self.project_name_var.trace_add("write", lambda *args: self.update_preview())
        self.date_var.trace_add("write", lambda *args: self.update_preview())
        self.personal_var.trace_add("write", lambda *args: self.update_preview())
        self.touchdesigner_var.trace_add("write", lambda *args: self.update_preview())
        self.python_var.trace_add("write", lambda *args: self.update_preview())
        self.resolution_var.trace_add("write", lambda *args: self.update_preview())

    def toggle_personal(self):
        """Toggle the Personal checkbox to auto-fill client name"""
        if self.personal_var.get():
            self.client_name_backup = self.client_name_var.get()
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

    def get_folder_structure(self):
        """Define the TouchDesigner folder structure"""
        return {
            'Production': {
                'Projects': {},
                'Components': {},
                'Assets': {
                    '3D': {
                        'Source': {},
                        'Optimized': {},
                        'References': {}
                    },
                    'Textures': {
                        'Source': {},
                        'Optimized': {}
                    },
                    'Images': {},
                    'Videos': {},
                    'Audio': {},
                    'Fonts': {}
                },
                'Preparation': {
                    'Blender': {},
                    'Substance': {},
                    'Houdini': {},
                    'Tests': {}
                },
                'Data': {
                    'JSON': {},
                    'CSV': {},
                    'XML': {}
                },
                'Scripts': {
                    'Extensions': {},
                    'Modules': {}
                },
                'Shaders': {
                    'GLSL': {},
                    'MAT': {}
                },
                'Palettes': {},
                'MIDI': {},
                'OSC': {},
                'DMX': {},
                'Exports': {
                    'Movies': {},
                    'Images': {},
                    'TOE': {}
                }
            },
            '_Library': {
                'Documents': {},
                'References': {},
                'Backup': {
                    'YYY-MM-DD': {}
                }
            },
            '_Delivery': {
                'YYY-MM-DD': {}
            }
        }

    def update_preview(self):
        """Update the preview of the folder structure"""
        self.preview_text.delete(1.0, tk.END)

        # Get values
        client = self.client_name_var.get() or "[Name Client]"
        project = self.project_name_var.get() or "[Name Project]"
        date = self.date_var.get() or datetime.now().strftime('%Y-%m-%d')

        # Get software specs
        touchdesigner = self.touchdesigner_var.get()
        python = self.python_var.get()
        resolution = self.resolution_var.get()

        # Get notes
        notes = self.notes_text.get(1.0, tk.END).strip()

        # Build the project directory name
        project_dir = f"{date}_TD_{client}_{project}"

        # Display preview
        base_dir = self.base_dir_var.get()
        # If Personal project, show _Personal subfolder in preview
        if self.personal_var.get():
            preview_path = f"{base_dir}/_Personal/{project_dir}"
        else:
            preview_path = f"{base_dir}/{project_dir}"
        self.preview_text.insert(tk.END, f"Project will be created at:\n{preview_path}\n\n")
        self.preview_text.insert(tk.END, "Software Specifications:\n")
        self.preview_text.insert(tk.END, f"TouchDesigner: {touchdesigner}\n")
        self.preview_text.insert(tk.END, f"Python: {python}\n")
        self.preview_text.insert(tk.END, f"Resolution: {resolution}\n\n")

        # Preview notes
        if notes:
            self.preview_text.insert(tk.END, "Notes:\n")
            if len(notes) > 100:
                self.preview_text.insert(tk.END, f"{notes[:100]}...\n\n")
            else:
                self.preview_text.insert(tk.END, f"{notes}\n\n")

        # Display folder structure
        self.preview_text.insert(tk.END, "Folder structure to be created:\n\n")

        structure = self.get_folder_structure()

        def print_tree(tree, prefix=""):
            items = list(tree.items())
            for i, (name, subtree) in enumerate(items):
                is_last = i == len(items) - 1

                # Replace YYY-MM-DD with actual date
                display_name = name
                if name == "YYY-MM-DD":
                    display_name = date

                self.preview_text.insert(tk.END, f"{prefix}{'└── ' if is_last else '├── '}{display_name}\n")
                if subtree:
                    extension = "    " if is_last else "│   "
                    print_tree(subtree, prefix + extension)

        print_tree(structure)

        self.preview_text.insert(tk.END, "\nSpecifications file will be created at:\n")
        self.preview_text.insert(tk.END, f"_Library/Documents/project_specifications.txt\n")

    def create_structure(self):
        """Create the folder structure"""
        # Get values
        base_dir = self.base_dir_var.get()
        client_name = self.client_name_var.get()
        project_name = self.project_name_var.get()
        date = self.date_var.get()

        # Get software specs
        touchdesigner_version = self.touchdesigner_var.get()
        python_version = self.python_var.get()
        resolution = self.resolution_var.get()

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

        # Build the project directory path
        # If Personal project, add _Personal subfolder
        if self.personal_var.get():
            base_dir = os.path.join(base_dir, "_Personal")
            # Create _Personal folder if it doesn't exist
            os.makedirs(base_dir, exist_ok=True)

        project_dir = os.path.join(base_dir, f'{date}_TD_{client_name}_{project_name}')

        try:
            # Create the folder structure
            self.create_folders(project_dir, self.get_folder_structure(), date)

            # Create specifications file
            self.create_specs_file(project_dir, client_name, project_name, date,
                                   touchdesigner_version, python_version, resolution)

            self.status_var.set(f"Created project structure for {client_name}_{project_name}")

            # Build project data for callback
            project_data = {
                'client_name': client_name,
                'project_name': project_name,
                'project_type': 'TD',
                'date_created': date,
                'path': project_dir,
                'base_directory': base_dir,
                'status': 'active',
                'notes': self.notes_text.get(1.0, tk.END).strip(),
                'metadata': {
                    'software_specs': {
                        'touchdesigner': touchdesigner_version,
                        'python': python_version,
                        'resolution': resolution
                    },
                    'is_personal': self.personal_var.get()
                }
            }

            # Handle success based on mode
            if self.embedded and self.on_project_created:
                # In embedded mode, call the callback with project data
                self.on_project_created(project_data)
            else:
                # Show success message
                if messagebox.askyesno("Success", f"Project structure created successfully at:\n\n{project_dir}\n\nWould you like to open the folder?"):
                    self.open_folder(project_dir)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create structure: {str(e)}")
            self.status_var.set("Error creating project structure")

    def _handle_cancel(self):
        """Handle cancel button click in embedded mode."""
        if self.on_cancel:
            self.on_cancel()

    def create_folders(self, base_path, structure, date):
        """Recursively create folder structure"""
        for folder_name, subfolders in structure.items():
            # Replace YYY-MM-DD with actual date
            if folder_name == "YYY-MM-DD":
                folder_name = date

            folder_path = os.path.join(base_path, folder_name)
            os.makedirs(folder_path, exist_ok=True)

            if subfolders:
                self.create_folders(folder_path, subfolders, date)

    def create_specs_file(self, project_dir, client_name, project_name, date,
                          touchdesigner_version, python_version, resolution):
        """Create a specifications text file"""
        try:
            docs_dir = os.path.join(project_dir, '_Library/Documents')
            spec_file_path = os.path.join(docs_dir, 'project_specifications.txt')

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            notes = self.notes_text.get(1.0, tk.END).strip()
            if not notes:
                notes = "No notes provided."

            content = f"""PROJECT SPECIFICATIONS
======================
Generated: {timestamp}

Project: {project_name}
Client: {client_name}
Date: {date}

SOFTWARE VERSIONS
======================
TouchDesigner: {touchdesigner_version}
Python: {python_version}
Resolution: {resolution}

PROJECT STRUCTURE
======================
Production/
├── Projects/                    # Main .toe project files
├── Components/                  # Reusable component .tox files
├── Assets/                     # Media assets organized by type
│   ├── 3D/
│   │   ├── Source/            # Original/unoptimized 3D models
│   │   ├── Optimized/         # TouchDesigner-ready optimized models
│   │   └── References/        # Reference models and concept art
│   ├── Textures/
│   │   ├── Source/            # Original high-resolution textures
│   │   └── Optimized/         # Real-time optimized textures
│   ├── Images/                # Image files and sprites
│   ├── Videos/                # Video files
│   ├── Audio/                 # Audio files
│   └── Fonts/                 # Font files
├── Preparation/                # Asset preparation workspace
│   ├── Blender/               # Blender working files (.blend)
│   ├── Substance/             # Substance Painter/Designer files
│   ├── Houdini/               # Houdini working files (if needed)
│   └── Tests/                 # Test exports before finalizing
├── Data/                       # External data files
│   ├── JSON/
│   ├── CSV/
│   └── XML/
├── Scripts/                    # Python scripts
│   ├── Extensions/            # TouchDesigner extensions
│   └── Modules/               # Python modules
├── Shaders/                    # Custom shaders
│   ├── GLSL/                  # GLSL shader files
│   └── MAT/                   # Material files
├── Palettes/                   # Color palettes
├── MIDI/                       # MIDI mapping files
├── OSC/                        # OSC configuration files
├── DMX/                        # DMX configurations
└── Exports/                    # Output files
    ├── Movies/                # Rendered video files
    ├── Images/                # Rendered images
    └── TOE/                   # Exported TouchDesigner projects

WORKFLOW GUIDE
======================
3D Asset Workflow:
1. Receive/Source models → Assets/3D/Source/
2. Work in Blender → Preparation/Blender/
3. Optimize & export → Assets/3D/Optimized/
4. Source textures → Assets/Textures/Source/
5. Optimized textures → Assets/Textures/Optimized/
6. Test exports → Preparation/Tests/
7. Final integration → Reference optimized assets in Projects/

File Naming Convention:
- Source: ClientName_AssetName_v01_source.fbx
- Optimized: ClientName_AssetName_v01_optimized.fbx
- Working: ClientName_AssetName_v01.blend

NOTES
======================
{notes}
"""

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
                import subprocess
                if os.name == 'nt':
                    os.startfile(path)
                elif os.name == 'posix':
                    if os.uname().sysname == 'Darwin':
                        subprocess.call(['open', path])
                    else:
                        subprocess.call(['xdg-open', path])
            except Exception as e:
                print(f"Could not open folder: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = FolderStructureCreator(root)
    root.mainloop()
