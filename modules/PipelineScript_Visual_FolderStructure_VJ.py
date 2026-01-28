"""
Live Video Project Folder Structure Creator

Creates standardized folder structure for Live Video (VJ/performance) projects.
Registers projects in the central database for tracking.

Keyboard Navigation:
- Tab/Enter: Move to next field
- Shift+Tab: Move to previous field
- Ctrl+Enter: Create project (from anywhere)
- Escape: Close form
- P: Toggle Personal checkbox (when not typing)
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
from rak_settings import get_rak_settings
from shared_form_keyboard import (
    FormKeyboardMixin, FORM_COLORS,
    create_styled_entry, create_styled_text, create_styled_button,
    create_styled_label, create_styled_checkbox, create_styled_frame,
    create_styled_labelframe, format_button_with_shortcut,
    create_software_chip_row, get_active_software
)

logger = get_logger(__name__)


class VJFolderStructureCreator(FormKeyboardMixin):
    """Creates folder structure for Live Video projects with keyboard-first navigation."""

    # Default folder structure for Live Video projects
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

    def __init__(self, root_or_frame, embedded=False, on_project_created=None, on_cancel=None, project_db=None):
        """
        Initialize the VJ Folder Structure Creator.

        Args:
            root_or_frame: Either a Tk root window (standalone) or a Frame (embedded)
            embedded: If True, build UI into provided frame without window configuration
            on_project_created: Callback function called with project_data when project is created
            on_cancel: Callback function called when user cancels
        """
        self.embedded = embedded
        self.on_project_created = on_project_created
        self.on_cancel = on_cancel
        self._in_text_field = False

        if embedded:
            # Embedded mode: root_or_frame is the parent frame
            self.root = root_or_frame.winfo_toplevel()
            self.parent = root_or_frame
        else:
            # Standalone mode: root_or_frame is the Tk root
            self.root = root_or_frame
            self.parent = root_or_frame
            self.root.title("Live Video Folder Structure")
            self.root.geometry("900x550")
            self.root.minsize(800, 450)

        # Initialize path config
        self.settings = get_rak_settings()

        # Initialize project database
        if project_db:
            self.project_db = project_db
        else:
            try:
                self.project_db = ProjectDatabase()
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                self.project_db = None

        # Build the form
        self._build_form()

        # Set up keyboard navigation (from mixin)
        self._collect_focusable_widgets()
        self._setup_keyboard_navigation()

    def _build_form(self):
        """Build the keyboard-optimized form layout."""
        # Configure dark background for embedded mode
        if self.embedded:
            self.parent.configure(bg=FORM_COLORS["bg"])

        if not self.embedded:
            # Configure main window (standalone only)
            self.root.configure(bg=FORM_COLORS["bg"])
            self.root.columnconfigure(0, weight=1)
            self.root.rowconfigure(0, weight=1)

        # Main container
        if self.embedded:
            main_frame = create_styled_frame(self.parent)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        else:
            main_frame = create_styled_frame(self.root)
            main_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)

        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)  # Preview row expands

        # ==================== ROW 1: Main inputs ====================
        row1 = create_styled_frame(main_frame)
        row1.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        row1.columnconfigure(1, weight=1)
        row1.columnconfigure(3, weight=1)

        # Client Name
        create_styled_label(row1, "Client:").grid(row=0, column=0, sticky="e", padx=(0, 5))
        self.client_name_var = tk.StringVar()
        if self.project_db:
            self.client_entry = AutocompleteEntry(
                row1,
                db=self.project_db,
                category="Visual",
                textvariable=self.client_name_var,
                width=25,
                bg=FORM_COLORS["bg"]
            )
        else:
            self.client_entry = create_styled_entry(row1, textvariable=self.client_name_var, width=25)
        self.client_entry.grid(row=0, column=1, sticky="ew", padx=(0, 20))

        # Project Name
        create_styled_label(row1, "Project:").grid(row=0, column=2, sticky="e", padx=(0, 5))
        self.project_name_var = tk.StringVar()
        self.project_entry = create_styled_entry(row1, textvariable=self.project_name_var, width=25)
        self.project_entry.grid(row=0, column=3, sticky="ew")

        # ==================== ROW 2: Secondary inputs ====================
        row2 = create_styled_frame(main_frame)
        row2.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # Personal checkbox
        self.personal_var = tk.BooleanVar(value=False)
        self.personal_check = create_styled_checkbox(
            row2, text="Personal (P)", variable=self.personal_var, command=self.toggle_personal
        )
        self.personal_check.pack(side=tk.LEFT, padx=(0, 20))

        # Date
        create_styled_label(row2, "Date:").pack(side=tk.LEFT, padx=(0, 5))
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        self.date_entry = create_styled_entry(row2, textvariable=self.date_var, width=12)
        self.date_entry.pack(side=tk.LEFT, padx=(0, 20))

        # Software chips
        sw_defaults = self.settings.get_software_defaults("Visual", "VJ")
        self.software_chip_frame, self.software_chips = create_software_chip_row(
            row2,
            ["Resolume", "After Effects", "TouchDesigner"],
            defaults={
                "Resolume": sw_defaults.get("resolume", "Arena 7"),
                "After Effects": sw_defaults.get("after_effects", "2024"),
                "TouchDesigner": sw_defaults.get("touchdesigner", ""),
            },
            on_change=lambda *args: self.update_preview()
        )
        self.software_chip_frame.pack(side=tk.LEFT)

        # ==================== ROW 3: Notes and Preview ====================
        row3 = create_styled_frame(main_frame)
        row3.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        row3.columnconfigure(0, weight=1)
        row3.columnconfigure(1, weight=2)
        row3.rowconfigure(0, weight=1)

        # Notes (left side, compact)
        notes_frame = create_styled_labelframe(row3, text="Notes (optional)")
        notes_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        notes_frame.columnconfigure(0, weight=1)
        notes_frame.rowconfigure(0, weight=1)

        self.notes_text = create_styled_text(notes_frame, height=6)
        self.notes_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Preview (right side)
        preview_frame = create_styled_labelframe(row3, text="Preview")
        preview_frame.grid(row=0, column=1, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.preview_text = tk.Text(
            preview_frame,
            bg=FORM_COLORS["bg_input"],
            fg=FORM_COLORS["text_dim"],
            font=("Consolas", 9),
            wrap=tk.WORD,
            state=tk.DISABLED,
            highlightthickness=0,
            relief=tk.FLAT
        )
        self.preview_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # ==================== ROW 4: Action buttons ====================
        row4 = create_styled_frame(main_frame)
        row4.grid(row=3, column=0, sticky="e", pady=(10, 0))

        # Base directory (hidden from main view, accessible via browse)
        default_base = self.settings.get_work_path("Visual").replace('\\', '/')
        self.base_dir_var = tk.StringVar(value=default_base)

        # Browse button (secondary)
        self.browse_btn = create_styled_button(
            row4, text="Browse...", command=self.browse_base_dir
        )
        self.browse_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Create button (primary)
        self.create_btn = create_styled_button(
            row4,
            text=format_button_with_shortcut("Create Project", "create"),
            command=self.create_structure,
            primary=True
        )
        self.create_btn.pack(side=tk.LEFT)

        # Status variable (for compatibility)
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")

        # Initialize preview
        self.update_preview()

        # Set up event bindings for live preview updates
        self.project_name_var.trace_add("write", lambda *args: self.update_preview())
        self.client_name_var.trace_add("write", lambda *args: self.update_preview())
        self.date_var.trace_add("write", lambda *args: self.update_preview())
        self.personal_var.trace_add("write", lambda *args: self.update_preview())

    def _collect_focusable_widgets(self):
        """Collect widgets for keyboard navigation."""
        self._focusable_widgets = [
            self.client_entry,
            self.project_entry,
            self.personal_check,
            self.date_entry,
            self.notes_text,
        ]
        self._create_btn = self.create_btn
        self._browse_btn = self.browse_btn
        self._notes_widget = self.notes_text
        self._personal_checkbox = self.personal_check
        self._personal_var = self.personal_var

        # Add Enter binding for personal checkbox to toggle it
        self.personal_check.bind("<Return>", lambda e: self._toggle_personal_checkbox())

    def _toggle_personal_checkbox(self):
        """Toggle personal checkbox when Enter is pressed."""
        self.personal_var.set(not self.personal_var.get())
        self.toggle_personal()
        return "break"

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
        self.preview_text.configure(state=tk.NORMAL)
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
        if self.personal_var.get():
            preview_path = f"{base_dir}/_Personal/{folder_name}"
        else:
            preview_path = f"{base_dir}/{folder_name}"

        self.preview_text.insert(tk.END, f"Path: {preview_path}\n\n")

        # Software specs from chips
        active_software = get_active_software(self.software_chips)
        if active_software:
            software_str = "  |  ".join([f"{name}: {ver}" for name, ver in active_software.items()])
            self.preview_text.insert(tk.END, f"{software_str}\n\n")
        else:
            self.preview_text.insert(tk.END, "No software selected\n\n")

        # Folder structure (abbreviated)
        self.preview_text.insert(tk.END, "Structure:\n")
        for path in self.DEFAULT_STRUCTURE[:8]:  # Show first 8
            depth = path.count('/')
            name = path.split('/')[-1]
            indent = "  " * depth
            self.preview_text.insert(tk.END, f"{indent}{name}/\n")
        self.preview_text.insert(tk.END, "  ...\n")

        self.preview_text.configure(state=tk.DISABLED)

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

            software_specs = get_active_software(self.software_chips)
            project_data = {
                'client_name': client_name,
                'project_name': project_name,
                'project_type': 'Visual-Live Video',
                'date_created': date,
                'path': project_dir,
                'base_directory': base_dir,
                'status': 'active',
                'notes': self.notes_text.get(1.0, tk.END).strip(),
                'metadata': {
                    'subtype': 'VJ',
                    'software_specs': software_specs,
                    'is_personal': self.personal_var.get()
                }
            }

            self.status_var.set(f"Created Live Video project: {folder_name}")

            # Handle success based on mode
            if self.embedded and self.on_project_created:
                # In embedded mode, call the callback with project data
                self.on_project_created(project_data)
            else:
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

    def _handle_cancel(self):
        """Handle cancel button click in embedded mode."""
        if self.on_cancel:
            self.on_cancel()

    def create_specs_file(self, project_dir, project_name, client_name, date):
        """Create a specifications text file."""
        try:
            spec_file = os.path.join(project_dir, "_Library", "Documents", "project_specifications.txt")
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            notes = self.notes_text.get(1.0, tk.END).strip() or "No notes provided."

            software_specs = get_active_software(self.software_chips)
            software_lines = "\n".join([f"{name}: {ver}" for name, ver in software_specs.items()]) or "None selected"

            content = f"""LIVE VIDEO PROJECT SPECIFICATIONS
==================================
Generated: {timestamp}

Project: {project_name}
Client: {client_name}
Date: {date}
Type: Live Video

SOFTWARE VERSIONS
=========================
{software_lines}

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
