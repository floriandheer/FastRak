"""
TouchDesigner Project Folder Structure Creator

Creates standardized folder structure for TouchDesigner projects.

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
from pathlib import Path

# Add modules to path
MODULES_DIR = Path(__file__).parent
sys.path.insert(0, str(MODULES_DIR))

from rak_settings import get_rak_settings
from shared_autocomplete_widget import AutocompleteEntry
from shared_form_keyboard import (
    FormKeyboardMixin, FORM_COLORS,
    create_styled_entry, create_styled_text, create_styled_button,
    create_styled_label, create_styled_checkbox, create_styled_frame,
    create_styled_labelframe, format_button_with_shortcut,
    create_software_chip_row, get_active_software,
    add_name_validation
)
from shared_folder_tree_parser import parse_tree_file, create_structure as tree_create_structure

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


class TouchDesignerFolderStructureCreator(FormKeyboardMixin):
    """Creates folder structure for TouchDesigner projects with keyboard-first navigation."""

    def __init__(self, root_or_frame, embedded=False, on_project_created=None, on_cancel=None, project_db=None):
        """Initialize the TouchDesigner Folder Structure Creator."""
        self.embedded = embedded
        self.on_project_created = on_project_created
        self.on_cancel = on_cancel
        self._in_text_field = False
        self.project_db = project_db

        if embedded:
            self.root = root_or_frame.winfo_toplevel()
            self.parent = root_or_frame
        else:
            self.root = root_or_frame
            self.parent = root_or_frame
            self.root.title("TouchDesigner Folder Structure")
            self.root.geometry("900x550")
            self.root.minsize(800, 450)

        # Initialize path config
        self.settings = get_rak_settings()

        self._build_form()
        self._collect_focusable_widgets()
        self._setup_keyboard_navigation()

    def _build_form(self):
        """Build the keyboard-optimized form layout."""
        if self.embedded:
            self.parent.configure(bg=FORM_COLORS["bg"])
        else:
            self.root.configure(bg=FORM_COLORS["bg"])
            self.root.columnconfigure(0, weight=1)
            self.root.rowconfigure(0, weight=1)

        if self.embedded:
            main_frame = create_styled_frame(self.parent)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        else:
            main_frame = create_styled_frame(self.root)
            main_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)

        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)  # Notes/Preview row expands

        # ==================== ROW 1: Client and Project ====================
        row1 = create_styled_frame(main_frame)
        row1.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        row1.columnconfigure(1, weight=1)
        row1.columnconfigure(3, weight=1)

        create_styled_label(row1, "Client:").grid(row=0, column=0, sticky="e", padx=(0, 5))
        self.client_name_var = tk.StringVar()
        add_name_validation(self.client_name_var)
        if self.project_db:
            self.client_entry = AutocompleteEntry(
                row1, db=self.project_db, category="RealTime",
                textvariable=self.client_name_var, width=25,
                bg=FORM_COLORS["bg"]
            )
        else:
            self.client_entry = create_styled_entry(row1, textvariable=self.client_name_var, width=25)
        self.client_entry.grid(row=0, column=1, sticky="ew", padx=(0, 20))

        create_styled_label(row1, "Project:").grid(row=0, column=2, sticky="e", padx=(0, 5))
        self.project_name_var = tk.StringVar()
        add_name_validation(self.project_name_var)
        self.project_entry = create_styled_entry(row1, textvariable=self.project_name_var, width=25)
        self.project_entry.grid(row=0, column=3, sticky="ew")

        # ==================== ROW 2: Personal, Date, Software Specs ====================
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

        # Get software defaults from config
        sw_defaults = self.settings.get_software_defaults("RealTime", "TD")

        # Software chips for TD and Python
        self.software_chip_frame, self.software_chips = create_software_chip_row(
            row2,
            ["TouchDesigner", "Python"],
            defaults={
                "TouchDesigner": sw_defaults.get("touchdesigner", "2023.11760"),
                "Python": sw_defaults.get("python", "3.11"),
            },
            on_change=lambda *args: self.update_preview()
        )
        self.software_chip_frame.pack(side=tk.LEFT, padx=(0, 20))

        # Resolution
        create_styled_label(row2, "Resolution:").pack(side=tk.LEFT, padx=(0, 5))
        self.resolution_var = tk.StringVar(value=sw_defaults.get("resolution", "1920x1080"))
        self.resolution_entry = create_styled_entry(row2, textvariable=self.resolution_var, width=12)
        self.resolution_entry.pack(side=tk.LEFT)

        # Base directory and tree file
        default_base = self.settings.get_work_path("RealTime").replace('\\', '/')
        self.base_dir_var = tk.StringVar(value=default_base)
        self.tree_file = os.path.join(TEMPLATES_DIR, 'realtime_touchdesigner_structure.txt')

        # ==================== ROW 3: Notes and Preview ====================
        row3 = create_styled_frame(main_frame)
        row3.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        row3.columnconfigure(0, weight=1)
        row3.columnconfigure(1, weight=2)
        row3.rowconfigure(0, weight=1)

        # Notes (left)
        notes_frame = create_styled_labelframe(row3, text="Notes (N to focus)")
        notes_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        notes_frame.columnconfigure(0, weight=1)
        notes_frame.rowconfigure(0, weight=1)

        self.notes_text = create_styled_text(notes_frame, height=8)
        self.notes_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.notes_text.bind("<FocusIn>", lambda e: setattr(self, '_in_text_field', True))
        self.notes_text.bind("<FocusOut>", lambda e: setattr(self, '_in_text_field', False))

        # Preview (right)
        preview_frame = create_styled_labelframe(row3, text="Preview")
        preview_frame.grid(row=0, column=1, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.preview_text = tk.Text(
            preview_frame, bg=FORM_COLORS["bg_input"], fg=FORM_COLORS["text_dim"],
            font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED,
            highlightthickness=0, relief=tk.FLAT, height=12
        )
        self.preview_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # ==================== ROW 4: Action buttons ====================
        row4 = create_styled_frame(main_frame)
        row4.grid(row=3, column=0, sticky="e", pady=(10, 0))

        self.browse_btn = create_styled_button(row4, text="Browse...", command=self.browse_base_dir)
        self.browse_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.create_btn = create_styled_button(
            row4, text=format_button_with_shortcut("Create Project", "create"),
            command=self.create_structure, primary=True
        )
        self.create_btn.pack(side=tk.LEFT)

        self.status_var = tk.StringVar()
        self.status_var.set("Ready")

        # Initialize preview
        self.update_preview()

        # Set up event bindings for live preview updates
        self.client_name_var.trace_add("write", lambda *args: self.update_preview())
        self.project_name_var.trace_add("write", lambda *args: self.update_preview())
        self.date_var.trace_add("write", lambda *args: self.update_preview())
        self.personal_var.trace_add("write", lambda *args: self.update_preview())
        self.resolution_var.trace_add("write", lambda *args: self.update_preview())

    def _collect_focusable_widgets(self):
        """Collect widgets for keyboard navigation."""
        self._focusable_widgets = [
            self.client_entry, self.project_entry, self.personal_check,
            self.date_entry, self.resolution_entry, self.notes_text,
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
        """Update the preview of the folder structure."""
        self.preview_text.configure(state=tk.NORMAL)
        self.preview_text.delete(1.0, tk.END)

        client = self.client_name_var.get() or "[Client]"
        project = self.project_name_var.get() or "[Project]"
        date = self.date_var.get() or datetime.now().strftime('%Y-%m-%d')

        software_specs = get_active_software(self.software_chips)
        touchdesigner = software_specs.get("TouchDesigner", "2023.11760")
        python = software_specs.get("Python", "3.11")
        resolution = self.resolution_var.get()

        if client and client != "Personal":
            project_dir = f"{date}_TD_{client}_{project}"
        else:
            project_dir = f"{date}_TD_{project}"

        base_dir = self.base_dir_var.get()
        if self.personal_var.get():
            preview_path = f"{base_dir}/_Personal/{project_dir}"
        else:
            preview_path = f"{base_dir}/{project_dir}"

        self.preview_text.insert(tk.END, f"Path: {preview_path}\n\n")
        self.preview_text.insert(tk.END, f"TD: {touchdesigner}  |  Python: {python}  |  Res: {resolution}\n\n")
        self.preview_text.insert(tk.END, "Structure:\n")

        if os.path.isfile(self.tree_file):
            tree_entries = parse_tree_file(self.tree_file)
            for path, _ in tree_entries:
                depth = path.count('/')
                name = path.split('/')[-1]
                display_name = date if name == "YYY-MM-DD" else name
                indent = "  " * depth
                self.preview_text.insert(tk.END, f"{indent}{display_name}/\n")

        self.preview_text.configure(state=tk.DISABLED)

    def validate_inputs(self):
        """Validate all required inputs."""
        base_dir = self.base_dir_var.get()
        client_name = self.client_name_var.get().strip()
        project_name = self.project_name_var.get().strip()

        if not base_dir or not os.path.isdir(base_dir):
            messagebox.showerror("Error", "Please select a valid base directory.")
            return False

        if not client_name:
            if self.personal_var.get():
                self.client_name_var.set("Personal")
            else:
                messagebox.showerror("Error", "Please enter a client name.")
                return False

        if not project_name:
            messagebox.showerror("Error", "Please enter a project name.")
            return False

        return True

    def create_structure(self):
        """Create the folder structure."""
        if not self.validate_inputs():
            return

        base_dir = self.base_dir_var.get()
        client_name = self.client_name_var.get()
        project_name = self.project_name_var.get()
        date = self.date_var.get() or datetime.now().strftime('%Y-%m-%d')

        software_specs = get_active_software(self.software_chips)
        touchdesigner_version = software_specs.get("TouchDesigner", "2023.11760")
        python_version = software_specs.get("Python", "3.11")
        resolution = self.resolution_var.get()

        if self.personal_var.get():
            base_dir = os.path.join(base_dir, "_Personal")
            os.makedirs(base_dir, exist_ok=True)

        if client_name and client_name != "Personal":
            folder_name = f'{date}_TD_{client_name}_{project_name}'
        else:
            folder_name = f'{date}_TD_{project_name}'
            client_name = "Personal"
        project_dir = os.path.join(base_dir, folder_name)

        try:
            tree = parse_tree_file(self.tree_file)
            replacements = {'YYY-MM-DD': date}
            tree_create_structure(project_dir, tree, replacements)
            self.create_specs_file(project_dir, client_name, project_name, date,
                                   touchdesigner_version, python_version, resolution)

            self.status_var.set(f"Created project structure for {client_name}_{project_name}")

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

            if self.embedded and self.on_project_created:
                self.on_project_created(project_data)
            else:
                if messagebox.askyesno("Success", f"Project created at:\n\n{project_dir}\n\nOpen folder?"):
                    self.open_folder(project_dir)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create structure: {str(e)}")
            self.status_var.set("Error creating project structure")

    def _handle_cancel(self):
        """Handle cancel button click."""
        if self.on_cancel:
            self.on_cancel()

    def create_specs_file(self, project_dir, client_name, project_name, date,
                          touchdesigner_version, python_version, resolution):
        """Create a specifications text file."""
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
├── Projects/           # Main .toe project files
├── Components/         # Reusable component .tox files
├── Assets/            # Media assets organized by type
├── Preparation/       # Asset preparation workspace
├── Data/              # External data files (JSON, CSV, XML)
├── Scripts/           # Python scripts and extensions
├── Shaders/           # Custom GLSL shaders
├── Palettes/          # Color palettes
├── MIDI/              # MIDI mapping files
├── OSC/               # OSC configuration files
├── DMX/               # DMX configurations
└── Exports/           # Output files (Movies, Images, TOE)

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
        """Open the folder in file explorer."""
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


# Backwards compatibility alias
FolderStructureCreator = TouchDesignerFolderStructureCreator


if __name__ == "__main__":
    root = tk.Tk()
    app = TouchDesignerFolderStructureCreator(root)
    root.mainloop()
