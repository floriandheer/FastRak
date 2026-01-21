"""
VJ / Resolume Project Folder Structure Creator

Creates standardized folder structure for VJ and Resolume projects.
Registers projects in the central database for tracking.
"""

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

from shared_logging import get_logger
from shared_project_db import ProjectDatabase
from shared_autocomplete_widget import AutocompleteEntry
from shared_path_config import get_path_config

logger = get_logger(__name__)


class VJFolderStructureCreator:
    """Creates folder structure for VJ and Resolume projects."""

    # Default folder structure for VJ projects
    DEFAULT_STRUCTURE = [
        "_Library",
        "_Library/Documents",
        "_Library/References",
        "_Sources",
        "_Sources/Audio",
        "_Sources/Video",
        "_Sources/Images",
        "_Sources/Fonts",
        "_Compositions",
        "_Compositions/Resolume",
        "_Compositions/Other",
        "_Exports",
        "_Exports/Clips",
        "_Exports/Decks",
        "_Renders",
        "_Renders/Preview",
        "_Renders/Final",
    ]

    def __init__(self, root):
        self.root = root
        self.root.title("VJ / Resolume Folder Structure")
        self.root.geometry("750x650")
        self.root.minsize(700, 550)

        # Initialize path config
        self.path_config = get_path_config()

        # Initialize project database
        try:
            self.project_db = ProjectDatabase()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            self.project_db = None

        # Configure main window
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # Create header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header_frame.grid_propagate(False)

        # Add title to header
        title_label = tk.Label(
            header_frame,
            text="VJ / Resolume Folder Structure",
            font=("Arial", 16, "bold"),
            fg="white",
            bg="#2c3e50"
        )
        title_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Create main frame
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
        default_base = self.path_config.get_work_path("Visual").replace('\\', '/')
        self.base_dir_var = tk.StringVar(value=default_base)
        base_dir_entry = ttk.Entry(form_frame, textvariable=self.base_dir_var, width=40)
        base_dir_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=10)
        ttk.Button(form_frame, text="Browse", command=self.browse_base_dir).grid(row=0, column=2, padx=5, pady=10)

        # Project Name
        ttk.Label(form_frame, text="Project Name:").grid(row=1, column=0, sticky="w", padx=10, pady=10)
        self.project_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.project_name_var, width=40).grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=10
        )

        # Client Name (with autocomplete) - optional for VJ projects
        ttk.Label(form_frame, text="Client (optional):").grid(row=2, column=0, sticky="w", padx=10, pady=(10, 2))
        self.client_name_var = tk.StringVar()
        if self.project_db:
            self.client_entry = AutocompleteEntry(
                form_frame,
                db=self.project_db,
                textvariable=self.client_name_var,
                width=40
            )
            self.client_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=5, pady=(10, 2))
        else:
            ttk.Entry(form_frame, textvariable=self.client_name_var, width=40).grid(
                row=2, column=1, columnspan=2, sticky="ew", padx=5, pady=(10, 2)
            )

        # Personal checkbox
        ttk.Label(form_frame, text="Personal:").grid(row=3, column=0, sticky="w", padx=10, pady=(0, 10))
        self.personal_var = tk.BooleanVar(value=True)  # Default to personal for VJ
        personal_check = ttk.Checkbutton(
            form_frame, text="", variable=self.personal_var, command=self.toggle_personal
        )
        personal_check.grid(row=3, column=1, sticky="w", padx=5, pady=(0, 10))

        # Project date
        ttk.Label(form_frame, text="Date:").grid(row=4, column=0, sticky="w", padx=10, pady=10)
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        date_entry = ttk.Entry(form_frame, textvariable=self.date_var, width=40)
        date_entry.grid(row=4, column=1, columnspan=2, sticky="ew", padx=5, pady=10)

        # Software specifications
        spec_frame = ttk.LabelFrame(form_frame, text="Software Specs")
        spec_frame.grid(row=5, column=0, columnspan=3, sticky="ew", padx=5, pady=10)
        spec_frame.columnconfigure(1, weight=1)

        # Resolume version
        ttk.Label(spec_frame, text="Resolume:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.resolume_var = tk.StringVar(value="Arena 7")
        ttk.Entry(spec_frame, textvariable=self.resolume_var, width=15).grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # After Effects version
        ttk.Label(spec_frame, text="After Effects:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.ae_var = tk.StringVar(value="2024")
        ttk.Entry(spec_frame, textvariable=self.ae_var, width=15).grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # TouchDesigner version (optional)
        ttk.Label(spec_frame, text="TouchDesigner:").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.td_var = tk.StringVar(value="")
        ttk.Entry(spec_frame, textvariable=self.td_var, width=15).grid(row=2, column=1, sticky="w", padx=5, pady=5)

        # Notes section
        notes_frame = ttk.LabelFrame(form_frame, text="Project Notes")
        notes_frame.grid(row=6, column=0, columnspan=3, sticky="nsew", padx=5, pady=10)
        notes_frame.columnconfigure(0, weight=1)
        notes_frame.rowconfigure(0, weight=1)

        self.notes_scrollbar = ttk.Scrollbar(notes_frame)
        self.notes_scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 5), pady=5)

        self.notes_text = tk.Text(
            notes_frame, wrap=tk.WORD, height=5, yscrollcommand=self.notes_scrollbar.set
        )
        self.notes_text.grid(row=0, column=0, sticky="nsew", padx=(5, 0), pady=5)
        self.notes_scrollbar.config(command=self.notes_text.yview)

        # Create button
        create_btn = ttk.Button(
            form_frame, text="Create Project Structure", command=self.create_structure, padding=(20, 10)
        )
        create_btn.grid(row=7, column=0, columnspan=3, pady=20)

        # Create preview panel (right side)
        preview_frame = ttk.LabelFrame(main_frame, text="Structure Preview")
        preview_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)

        self.preview_scrollbar = ttk.Scrollbar(preview_frame)
        self.preview_scrollbar.grid(row=0, column=1, sticky="ns")

        self.preview_text = tk.Text(
            preview_frame, wrap=tk.WORD, yscrollcommand=self.preview_scrollbar.set
        )
        self.preview_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.preview_scrollbar.config(command=self.preview_text.yview)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = tk.Label(
            self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W
        )
        self.status_bar.grid(row=2, column=0, sticky="ew")

        # Initialize preview
        self.update_preview()

        # Set up event bindings for live preview updates
        self.project_name_var.trace_add("write", lambda *args: self.update_preview())
        self.client_name_var.trace_add("write", lambda *args: self.update_preview())
        self.date_var.trace_add("write", lambda *args: self.update_preview())
        self.personal_var.trace_add("write", lambda *args: self.update_preview())

    def toggle_personal(self):
        """Toggle the Personal checkbox to auto-fill client name."""
        if self.personal_var.get():
            self.client_name_backup = self.client_name_var.get()
            self.client_name_var.set("Personal")
        else:
            if hasattr(self, 'client_name_backup'):
                self.client_name_var.set(self.client_name_backup)
            else:
                self.client_name_var.set("")
        self.update_preview()

    def browse_base_dir(self):
        """Open dialog to browse for base directory."""
        directory = filedialog.askdirectory()
        if directory:
            self.base_dir_var.set(directory)
            self.update_preview()

    def update_preview(self):
        """Update the preview of the folder structure to be created."""
        self.preview_text.delete(1.0, tk.END)

        # Get values
        project = self.project_name_var.get() or "[Project Name]"
        client = self.client_name_var.get() or "Personal"
        date = self.date_var.get() or datetime.now().strftime('%Y-%m-%d')
        base_dir = self.base_dir_var.get()

        # Build folder name: YYYY-MM-DD_VJ_Client_Project or YYYY-MM-DD_VJ_Project
        if client and client != "Personal":
            folder_name = f"{date}_VJ_{client}_{project}"
        else:
            folder_name = f"{date}_VJ_{project}"

        # Display preview
        # If Personal project, show _Personal subfolder in preview
        if self.personal_var.get():
            preview_path = f"{base_dir}/_Personal/{folder_name}"
        else:
            preview_path = f"{base_dir}/{folder_name}"
        self.preview_text.insert(tk.END, f"Project will be created at:\n{preview_path}\n\n")

        # Software specs
        self.preview_text.insert(tk.END, "Software Specifications:\n")
        self.preview_text.insert(tk.END, f"  Resolume: {self.resolume_var.get()}\n")
        self.preview_text.insert(tk.END, f"  After Effects: {self.ae_var.get()}\n")
        if self.td_var.get():
            self.preview_text.insert(tk.END, f"  TouchDesigner: {self.td_var.get()}\n")
        self.preview_text.insert(tk.END, "\n")

        # Folder structure preview
        self.preview_text.insert(tk.END, "Folder structure:\n\n")
        self.preview_text.insert(tk.END, f"{folder_name}/\n")

        # Build tree view of structure
        for path in self.DEFAULT_STRUCTURE:
            depth = path.count('/')
            name = path.split('/')[-1]
            indent = "    " * depth
            self.preview_text.insert(tk.END, f"{indent}{name}/\n")

        # Preview specs file
        self.preview_text.insert(tk.END, "\n    project_specifications.txt\n")

    def create_structure(self):
        """Create the folder structure."""
        # Get values
        base_dir = self.base_dir_var.get()
        project_name = self.project_name_var.get()
        client_name = self.client_name_var.get() or "Personal"
        date = self.date_var.get() or datetime.now().strftime('%Y-%m-%d')

        # Validate inputs
        if not base_dir or not os.path.isdir(base_dir):
            messagebox.showerror("Error", "Please select a valid base directory.")
            return

        if not project_name:
            messagebox.showerror("Error", "Please enter a project name.")
            return

        # Build folder name
        if client_name and client_name != "Personal":
            folder_name = f"{date}_VJ_{client_name}_{project_name}"
        else:
            folder_name = f"{date}_VJ_{project_name}"
            client_name = "Personal"

        # If Personal project, add _Personal subfolder
        if self.personal_var.get():
            base_dir = os.path.join(base_dir, "_Personal")
            # Create _Personal folder if it doesn't exist
            os.makedirs(base_dir, exist_ok=True)

        project_dir = os.path.join(base_dir, folder_name)

        try:
            # Create main project directory
            os.makedirs(project_dir, exist_ok=True)

            # Create folder structure
            for folder in self.DEFAULT_STRUCTURE:
                folder_path = os.path.join(project_dir, folder)
                os.makedirs(folder_path, exist_ok=True)

            # Create specifications file
            self.create_specs_file(project_dir, project_name, client_name, date)

            # Register in database
            if self.project_db:
                try:
                    project_data = {
                        'client_name': client_name,
                        'project_name': project_name,
                        'project_type': 'Visual-VJ',
                        'date_created': date,
                        'path': project_dir,
                        'base_directory': base_dir,
                        'status': 'active',
                        'notes': self.notes_text.get(1.0, tk.END).strip(),
                        'metadata': {
                            'subtype': 'VJ',
                            'software_specs': {
                                'resolume': self.resolume_var.get(),
                                'after_effects': self.ae_var.get(),
                                'touchdesigner': self.td_var.get()
                            },
                            'is_personal': self.personal_var.get()
                        }
                    }
                    project_id = self.project_db.register_project(project_data)
                    logger.info(f"Registered VJ project: {project_id}")
                except Exception as e:
                    logger.error(f"Failed to register project: {e}")

            self.status_var.set(f"Created VJ project: {folder_name}")

            # Show success and offer to open folder
            if messagebox.askyesno(
                "Success",
                f"Project structure created at:\n\n{project_dir}\n\nOpen folder?"
            ):
                self.open_folder(project_dir)

        except Exception as e:
            logger.error(f"Failed to create structure: {e}")
            messagebox.showerror("Error", f"Failed to create structure:\n{str(e)}")
            self.status_var.set("Error creating project structure")

    def create_specs_file(self, project_dir, project_name, client_name, date):
        """Create a specifications text file."""
        try:
            spec_file = os.path.join(project_dir, "_Library", "Documents", "project_specifications.txt")
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            notes = self.notes_text.get(1.0, tk.END).strip() or "No notes provided."

            content = f"""VJ PROJECT SPECIFICATIONS
=========================
Generated: {timestamp}

Project: {project_name}
Client: {client_name}
Date: {date}
Type: VJ / Resolume

SOFTWARE VERSIONS
=========================
Resolume: {self.resolume_var.get()}
After Effects: {self.ae_var.get()}
TouchDesigner: {self.td_var.get() or 'N/A'}

NOTES
=========================
{notes}
"""
            with open(spec_file, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Created specs file: {spec_file}")

        except Exception as e:
            logger.warning(f"Failed to create specs file: {e}")

    def open_folder(self, path):
        """Open the folder in file explorer."""
        if os.path.exists(path):
            try:
                if os.name == 'nt':
                    os.startfile(path)
                elif sys.platform == 'darwin':
                    os.system(f'open "{path}"')
                else:
                    os.system(f'xdg-open "{path}"')
            except Exception as e:
                logger.error(f"Could not open folder: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = VJFolderStructureCreator(root)
    root.mainloop()
