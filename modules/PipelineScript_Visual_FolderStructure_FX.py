"""
VFX Project Folder Structure Creator

Creates standardized folder structure for VFX/CG projects.
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
import re
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
    create_software_chip_row, get_active_software,
    add_name_validation
)
from shared_folder_tree_parser import parse_tree_file, create_structure as tree_create_structure, create_gitkeep_files

logger = get_logger(__name__)

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


class FolderStructureCreator(FormKeyboardMixin):
    """Creates folder structure for VFX/CG projects with keyboard-first navigation."""

    def __init__(self, root_or_frame, embedded=False, on_project_created=None, on_cancel=None, project_db=None):
        """Initialize the Folder Structure Creator."""
        self.embedded = embedded
        self.on_project_created = on_project_created
        self.on_cancel = on_cancel
        self._in_text_field = False

        if embedded:
            self.root = root_or_frame.winfo_toplevel()
            self.parent = root_or_frame
        else:
            self.root = root_or_frame
            self.parent = root_or_frame
            self.root.title("FX Folder Structure")
            self.root.geometry("900x550")
            self.root.minsize(800, 450)

        self.settings = get_rak_settings()

        if project_db:
            self.project_db = project_db
        else:
            try:
                self.project_db = ProjectDatabase()
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                self.project_db = None

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
        main_frame.rowconfigure(2, weight=1)

        # ==================== ROW 1: Main inputs ====================
        row1 = create_styled_frame(main_frame)
        row1.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        row1.columnconfigure(1, weight=1)
        row1.columnconfigure(3, weight=1)

        create_styled_label(row1, "Client:").grid(row=0, column=0, sticky="e", padx=(0, 5))
        self.client_name_var = tk.StringVar()
        add_name_validation(self.client_name_var)
        if self.project_db:
            self.client_entry = AutocompleteEntry(
                row1, db=self.project_db, category="Visual",
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

        # ==================== ROW 2: Secondary inputs ====================
        row2 = create_styled_frame(main_frame)
        row2.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        self.personal_var = tk.BooleanVar(value=False)
        self.personal_check = create_styled_checkbox(
            row2, text="Personal (P)", variable=self.personal_var, command=self.toggle_personal
        )
        self.personal_check.pack(side=tk.LEFT, padx=(0, 20))

        create_styled_label(row2, "Date:").pack(side=tk.LEFT, padx=(0, 5))
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        self.date_entry = create_styled_entry(row2, textvariable=self.date_var, width=12)
        self.date_entry.pack(side=tk.LEFT, padx=(0, 20))

        # Shot folders checkbox
        self.include_shots_var = tk.BooleanVar(value=True)
        self.shots_check = create_styled_checkbox(
            row2, text="Shot folders", variable=self.include_shots_var
        )
        self.shots_check.pack(side=tk.LEFT, padx=(0, 20))

        # Software chips
        sw_defaults = self.settings.get_software_defaults("Visual", "FX")
        self.software_chip_frame, self.software_chips = create_software_chip_row(
            row2,
            ["Houdini", "Blender", "Fusion"],
            defaults={
                "Houdini": sw_defaults.get("houdini", "20.5"),
                "Blender": sw_defaults.get("blender", "4.4"),
                "Fusion": sw_defaults.get("fusion", "19"),
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

        notes_frame = create_styled_labelframe(row3, text="Notes (optional)")
        notes_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        notes_frame.columnconfigure(0, weight=1)
        notes_frame.rowconfigure(0, weight=1)

        self.notes_text = create_styled_text(notes_frame, height=6)
        self.notes_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        preview_frame = create_styled_labelframe(row3, text="Preview")
        preview_frame.grid(row=0, column=1, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.preview_text = tk.Text(
            preview_frame, bg=FORM_COLORS["bg_input"], fg=FORM_COLORS["text_dim"],
            font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED,
            highlightthickness=0, relief=tk.FLAT
        )
        self.preview_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # ==================== ROW 4: Action buttons ====================
        row4 = create_styled_frame(main_frame)
        row4.grid(row=3, column=0, sticky="e", pady=(10, 0))

        default_base = self.settings.get_work_path("Visual").replace('\\', '/')
        self.base_dir_var = tk.StringVar(value=default_base)
        self.tree_file = os.path.join(TEMPLATES_DIR, 'visual_fx_structure.txt')

        self.browse_btn = create_styled_button(row4, text="Browse...", command=self.browse_base_dir)
        self.browse_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.create_btn = create_styled_button(
            row4, text=format_button_with_shortcut("Create Project", "create"),
            command=self.create_structure, primary=True
        )
        self.create_btn.pack(side=tk.LEFT)

        self.status_var = tk.StringVar()
        self.status_var.set("Ready")

        self.update_preview()
        self.client_name_var.trace_add("write", lambda *args: self.update_preview())
        self.project_name_var.trace_add("write", lambda *args: self.update_preview())
        self.date_var.trace_add("write", lambda *args: self.update_preview())
        self.personal_var.trace_add("write", lambda *args: self.update_preview())
        self.include_shots_var.trace_add("write", lambda *args: self.update_preview())

    def _collect_focusable_widgets(self):
        """Collect widgets for keyboard navigation."""
        self._focusable_widgets = [
            self.client_entry, self.project_entry, self.personal_check,
            self.date_entry, self.shots_check, self.notes_text,
        ]
        self._create_btn = self.create_btn
        self._browse_btn = self.browse_btn
        self._notes_widget = self.notes_text
        self._personal_checkbox = self.personal_check
        self._personal_var = self.personal_var

        # Add Enter binding for checkboxes to toggle them
        self.personal_check.bind("<Return>", lambda e: self._toggle_personal_checkbox())
        self.shots_check.bind("<Return>", lambda e: self._toggle_shots_checkbox())

    def _toggle_personal_checkbox(self):
        """Toggle personal checkbox when Enter is pressed."""
        self.personal_var.set(not self.personal_var.get())
        self.toggle_personal()
        return "break"

    def _toggle_shots_checkbox(self):
        """Toggle shots checkbox when Enter is pressed."""
        self.include_shots_var.set(not self.include_shots_var.get())
        self.update_preview()
        return "break"

    def toggle_personal(self):
        """Toggle the Personal checkbox."""
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

    def get_tree_structure(self, include_shots=True):
        """Get folder paths from tree definition file."""
        if not os.path.isfile(self.tree_file):
            return None
        tree = parse_tree_file(self.tree_file)
        conditionals = {'shots': include_shots}
        return [(p, c) for p, c in tree if c is None or conditionals.get(c, True)]

    def update_preview(self):
        """Update the preview."""
        self.preview_text.configure(state=tk.NORMAL)
        self.preview_text.delete(1.0, tk.END)

        client = self.client_name_var.get() or "[Client]"
        project = self.project_name_var.get() or "[Project]"
        date = self.date_var.get() or datetime.now().strftime('%Y-%m-%d')
        include_shots = self.include_shots_var.get()

        if client and client != "Personal":
            project_dir = f"{date}_FX_{client}_{project}"
        else:
            project_dir = f"{date}_FX_{project}"
        base_dir = self.base_dir_var.get()

        if self.personal_var.get():
            preview_path = f"{base_dir}/_Personal/{project_dir}"
        else:
            preview_path = f"{base_dir}/{project_dir}"

        self.preview_text.insert(tk.END, f"Path: {preview_path}\n\n")

        # Software specs from chips
        active_software = get_active_software(self.software_chips)
        if active_software:
            software_str = "  |  ".join([f"{name}: {ver}" for name, ver in active_software.items()])
            self.preview_text.insert(tk.END, f"{software_str}\n")
        self.preview_text.insert(tk.END, f"Shot folders: {'Yes' if include_shots else 'No'}\n\n")

        tree_entries = self.get_tree_structure(include_shots)
        if tree_entries:
            self.preview_text.insert(tk.END, "Structure:\n")
            for path, _ in tree_entries:
                depth = path.count('/')
                name = path.split('/')[-1]
                if name == "YYY-MM-DD":
                    name = date
                self.preview_text.insert(tk.END, f"{'  ' * depth}{name}/\n")
        else:
            self.preview_text.insert(tk.END, "Tree structure file not found.\n")

        self.preview_text.configure(state=tk.DISABLED)

    def create_structure(self):
        """Create the folder structure."""
        base_dir = self.base_dir_var.get()
        client_name = self.client_name_var.get()
        project_name = self.project_name_var.get()
        date = self.date_var.get()
        include_shots = self.include_shots_var.get()

        software_specs = get_active_software(self.software_chips)

        if not base_dir or not os.path.isdir(base_dir):
            messagebox.showerror("Error", "Please select a valid base directory.")
            return

        if not client_name:
            if self.personal_var.get():
                client_name = "Personal"
            else:
                messagebox.showerror("Error", "Please enter a client name.")
                return

        if not project_name:
            messagebox.showerror("Error", "Please enter a project name.")
            return

        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        if not os.path.isfile(self.tree_file):
            messagebox.showerror("Error", "Tree structure file not found.")
            return

        if self.personal_var.get():
            base_dir = os.path.join(base_dir, "_Personal")
            os.makedirs(base_dir, exist_ok=True)

        if client_name and client_name != "Personal":
            folder_name = f'{date}_FX_{client_name}_{project_name}'
        else:
            folder_name = f'{date}_FX_{project_name}'
            client_name = "Personal"
        project_dir = os.path.join(base_dir, folder_name)

        try:
            os.makedirs(project_dir, exist_ok=True)
            tree = parse_tree_file(self.tree_file)
            replacements = {'YYY-MM-DD': date}
            conditionals = {'shots': include_shots}
            created = tree_create_structure(project_dir, tree, replacements, conditionals)
            create_gitkeep_files(project_dir, created)

            docs_dir = os.path.join(project_dir, '_LIBRARY', 'Documents')
            os.makedirs(docs_dir, exist_ok=True)

            self.create_specs_file(project_dir, client_name, project_name, date, software_specs)

            project_data = {
                'client_name': client_name,
                'project_name': project_name,
                'project_type': 'Visual-Visual Effects',
                'date_created': date,
                'path': project_dir,
                'base_directory': base_dir,
                'status': 'active',
                'notes': self.notes_text.get(1.0, tk.END).strip(),
                'metadata': {
                    'software_specs': software_specs,
                    'include_shots': include_shots,
                    'is_personal': self.personal_var.get()
                }
            }

            self.status_var.set(f"Created project structure for {client_name}_{project_name}")

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

    def create_specs_file(self, project_dir, client_name, project_name, date, software_specs):
        """Create specifications file."""
        try:
            docs_dir = os.path.join(project_dir, '_LIBRARY', 'Documents')
            spec_file_path = os.path.join(docs_dir, 'project_specifications.txt')
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            notes = self.notes_text.get(1.0, tk.END).strip() or "No notes provided."
            software_lines = "\n".join([f"{name}: {ver}" for name, ver in software_specs.items()]) or "None selected"

            content = f"""PROJECT SPECIFICATIONS
======================
Generated: {timestamp}

Project: {project_name}
Client: {client_name}
Date: {date}

SOFTWARE VERSIONS
======================
{software_lines}

SHOT FOLDERS
======================
{"Included" if self.include_shots_var.get() else "Excluded"}

NOTES
======================
{notes}
"""
            with open(spec_file_path, 'w') as file:
                file.write(content)

        except Exception as e:
            messagebox.showwarning("Warning", f"Failed to create specifications file: {str(e)}")

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


if __name__ == "__main__":
    root = tk.Tk()
    app = FolderStructureCreator(root)
    root.mainloop()
