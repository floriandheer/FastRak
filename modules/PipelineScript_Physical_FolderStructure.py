"""
Physical (3D Printing) Project Folder Structure Creator

Creates standardized folder structure for 3D printing projects.

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

from rak_settings import get_rak_settings
from shared_autocomplete_widget import AutocompleteEntry
from shared_form_keyboard import (
    FormKeyboardMixin, FORM_COLORS,
    create_styled_entry, create_styled_text, create_styled_button,
    create_styled_label, create_styled_checkbox, create_styled_frame,
    create_styled_labelframe, create_styled_combobox, format_button_with_shortcut,
    create_software_chip_row, get_active_software,
    add_name_validation
)
from shared_folder_tree_parser import parse_tree_file, create_structure as tree_create_structure

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


class PhysicalFolderStructureCreator(FormKeyboardMixin):
    """Creates folder structure for 3D printing projects with keyboard-first navigation."""

    def __init__(self, root_or_frame, embedded=False, on_project_created=None, on_cancel=None, project_db=None):
        """Initialize the Physical Folder Structure Creator."""
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
            self.root.title("3D Printing Folder Structure")
            self.root.geometry("900x550")
            self.root.minsize(800, 450)

        # Initialize path config
        self.settings = get_rak_settings()

        self._build_form()
        self._collect_focusable_widgets()
        self._setup_keyboard_navigation()
        self._setup_project_type_shortcuts()

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
        main_frame.rowconfigure(3, weight=1)  # Notes/Preview row expands

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
                row1, db=self.project_db, category="Physical",
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

        # ==================== ROW 2: Project Type, Date, Structure Options ====================
        row2 = create_styled_frame(main_frame)
        row2.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # Project type checkboxes
        type_frame = create_styled_frame(row2)
        type_frame.pack(side=tk.LEFT, padx=(0, 20))

        self.personal_var = tk.BooleanVar(value=False)
        self.personal_check = create_styled_checkbox(
            type_frame, text="Personal (P)", variable=self.personal_var,
            command=lambda: self.toggle_project_type('personal')
        )
        self.personal_check.pack(side=tk.LEFT, padx=(0, 10))

        self.product_var = tk.BooleanVar(value=False)
        self.product_check = create_styled_checkbox(
            type_frame, text="Product (O)", variable=self.product_var,
            command=lambda: self.toggle_project_type('product')
        )
        self.product_check.pack(side=tk.LEFT, padx=(0, 10))

        self.project_var = tk.BooleanVar(value=False)
        self.project_check = create_styled_checkbox(
            type_frame, text="Project (J)", variable=self.project_var,
            command=lambda: self.toggle_project_type('project')
        )
        self.project_check.pack(side=tk.LEFT)

        # Date
        date_frame = create_styled_frame(row2)
        date_frame.pack(side=tk.LEFT, padx=(0, 20))
        create_styled_label(date_frame, "Date:").pack(side=tk.LEFT, padx=(0, 5))
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        self.date_entry = create_styled_entry(date_frame, textvariable=self.date_var, width=12)
        self.date_entry.pack(side=tk.LEFT)

        # Structure options (inline)
        self.include_preproduction_var = tk.BooleanVar(value=False)
        create_styled_checkbox(row2, text="Preproduction",
                              variable=self.include_preproduction_var,
                              command=self.update_preview).pack(side=tk.LEFT, padx=(0, 10))

        self.include_library_var = tk.BooleanVar(value=False)
        create_styled_checkbox(row2, text="_LIBRARY",
                              variable=self.include_library_var,
                              command=self.update_preview).pack(side=tk.LEFT)

        # Base directory
        default_base = self.settings.get_work_path("Physical").replace('\\', '/')
        self.base_dir_var = tk.StringVar(value=default_base)

        # ==================== ROW 3: Software & Hardware ====================
        row3 = create_styled_frame(main_frame)
        row3.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        row3.columnconfigure(0, weight=1)
        row3.columnconfigure(1, weight=1)

        # Production Tools (left) - using software chips
        tools_frame = create_styled_labelframe(row3, text="Software (click to toggle)")
        tools_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Get software defaults from config
        sw_defaults = self.settings.get_software_defaults("Physical")

        # Create software chips row
        self.software_chip_frame, self.software_chips = create_software_chip_row(
            tools_frame,
            ["Houdini", "Blender", "FreeCAD", "Alibre", "Affinity"],
            defaults={
                "Houdini": sw_defaults.get("houdini", "20.5"),
                "Blender": sw_defaults.get("blender", "4.4"),
                "FreeCAD": sw_defaults.get("freecad", ""),
                "Alibre": sw_defaults.get("alibre", ""),
                "Affinity": sw_defaults.get("affinity", ""),
            },
            on_change=lambda *args: self.update_preview()
        )
        self.software_chip_frame.pack(fill=tk.X, padx=10, pady=8)

        # Hardware (right)
        hw_frame = create_styled_labelframe(row3, text="Hardware")
        hw_frame.grid(row=0, column=1, sticky="nsew")

        hw_inner = create_styled_frame(hw_frame)
        hw_inner.pack(fill=tk.X, padx=10, pady=5)

        hw_row1 = create_styled_frame(hw_inner)
        hw_row1.pack(fill=tk.X, pady=2)
        create_styled_label(hw_row1, "Slicer:").pack(side=tk.LEFT)
        self.slicer_var = tk.StringVar(value=sw_defaults.get("slicer", "Bambu Studio"))
        self.slicer_combo = create_styled_combobox(
            hw_row1, textvariable=self.slicer_var, width=18,
            values=['Bambu Studio', 'PrusaSlicer', 'Cura', 'Simplify3D', 'Creality Slicer', 'Other']
        )
        self.slicer_combo.pack(side=tk.LEFT, padx=(5, 0))

        hw_row2 = create_styled_frame(hw_inner)
        hw_row2.pack(fill=tk.X, pady=2)
        create_styled_label(hw_row2, "Printer:").pack(side=tk.LEFT)
        self.printer_var = tk.StringVar(value=sw_defaults.get("printer", "Bambu Lab X1 Carbon"))
        self.printer_combo = create_styled_combobox(
            hw_row2, textvariable=self.printer_var, width=18,
            values=['Bambu Lab X1 Carbon', 'Bambu Lab P1S', 'Bambu Lab X1', 'Prusa MK3S+', 'Creality Ender 3', 'Other']
        )
        self.printer_combo.pack(side=tk.LEFT, padx=(5, 0))

        # ==================== ROW 4: Notes and Preview ====================
        row4 = create_styled_frame(main_frame)
        row4.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        row4.columnconfigure(0, weight=1)
        row4.columnconfigure(1, weight=2)
        row4.rowconfigure(0, weight=1)

        # Notes (left)
        notes_frame = create_styled_labelframe(row4, text="Notes (optional)")
        notes_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        notes_frame.columnconfigure(0, weight=1)
        notes_frame.rowconfigure(0, weight=1)

        self.notes_text = create_styled_text(notes_frame, height=6)
        self.notes_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.notes_text.bind("<FocusIn>", lambda e: setattr(self, '_in_text_field', True))
        self.notes_text.bind("<FocusOut>", lambda e: setattr(self, '_in_text_field', False))

        # Preview (right)
        preview_frame = create_styled_labelframe(row4, text="Preview")
        preview_frame.grid(row=0, column=1, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.preview_text = tk.Text(
            preview_frame, bg=FORM_COLORS["bg_input"], fg=FORM_COLORS["text_dim"],
            font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED,
            highlightthickness=0, relief=tk.FLAT
        )
        self.preview_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # ==================== ROW 5: Action buttons ====================
        row5 = create_styled_frame(main_frame)
        row5.grid(row=4, column=0, sticky="e", pady=(10, 0))

        self.browse_btn = create_styled_button(row5, text="Browse...", command=self.browse_base_dir)
        self.browse_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.create_btn = create_styled_button(
            row5, text=format_button_with_shortcut("Create Project", "create"),
            command=self.create_structure, primary=True
        )
        self.create_btn.pack(side=tk.LEFT)

        self.status_var = tk.StringVar()
        self.status_var.set("Ready")

        self.tree_file = os.path.join(TEMPLATES_DIR, 'physical_3dprint_structure.txt')

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
        self.slicer_var.trace_add("write", lambda *args: self.update_preview())
        self.printer_var.trace_add("write", lambda *args: self.update_preview())
        self.include_preproduction_var.trace_add("write", lambda *args: self.update_preview())
        self.include_library_var.trace_add("write", lambda *args: self.update_preview())

    def _collect_focusable_widgets(self):
        """Collect widgets for keyboard navigation."""
        self._focusable_widgets = [
            self.client_entry, self.project_entry, self.personal_check,
            self.date_entry, self.notes_text,
        ]
        self._create_btn = self.create_btn
        self._browse_btn = self.browse_btn
        self._notes_widget = self.notes_text
        self._personal_checkbox = self.personal_check
        self._personal_var = self.personal_var

        # Add Enter binding for checkboxes to toggle them
        self.personal_check.bind("<Return>", lambda e: self._toggle_checkbox(self.personal_var, 'personal'))
        self.product_check.bind("<Return>", lambda e: self._toggle_checkbox(self.product_var, 'product'))
        self.project_check.bind("<Return>", lambda e: self._toggle_checkbox(self.project_var, 'project'))

    def _toggle_checkbox(self, var, toggle_type=None):
        """Toggle a checkbox when Enter is pressed on it."""
        if toggle_type:
            self.toggle_project_type(toggle_type)
        else:
            var.set(not var.get())
        return "break"

    def _setup_project_type_shortcuts(self):
        """Set up additional shortcuts for project types."""
        root = self.parent.winfo_toplevel()
        # O for prOduct
        root.bind("<o>", self._on_o_key)
        root.bind("<O>", self._on_o_key)
        # J for proJect
        root.bind("<j>", self._on_j_key)
        root.bind("<J>", self._on_j_key)

    def _on_o_key(self, event):
        """Handle O key to toggle Product checkbox."""
        if hasattr(self, '_in_text_field') and self._in_text_field:
            return
        self.toggle_project_type('product')
        return "break"

    def _on_j_key(self, event):
        """Handle J key to toggle Project checkbox."""
        if hasattr(self, '_in_text_field') and self._in_text_field:
            return
        self.toggle_project_type('project')
        return "break"

    def toggle_project_type(self, clicked_type):
        """Toggle project type checkboxes and update related fields."""
        # Ensure only one project type is selected at a time
        if clicked_type == 'personal':
            if not self.personal_var.get():
                self.personal_var.set(True)
            self.product_var.set(False)
            self.project_var.set(False)
        elif clicked_type == 'product':
            if not self.product_var.get():
                self.product_var.set(True)
            self.personal_var.set(False)
            self.project_var.set(False)
        elif clicked_type == 'project':
            if not self.project_var.get():
                self.project_var.set(True)
            self.personal_var.set(False)
            self.product_var.set(False)

        # Save current values if switching to a special project type
        if (self.personal_var.get() or self.product_var.get() or self.project_var.get()) and not hasattr(self, 'client_name_backup'):
            self.client_name_backup = self.client_name_var.get()
            self.base_dir_backup = self.base_dir_var.get()

        # Set appropriate values based on project type
        if self.personal_var.get():
            self.client_name_var.set("Personal")
            physical_base = self.settings.get_work_path("Physical").replace('\\', '/')
            self.base_dir_var.set(physical_base + "/_personal")
        elif self.product_var.get():
            physical_base = self.settings.get_work_path("Physical").replace('\\', '/')
            self.client_name_var.set("alles3d")
            self.base_dir_var.set(physical_base + "/Product")
        elif self.project_var.get():
            physical_base = self.settings.get_work_path("Physical").replace('\\', '/')
            self.base_dir_var.set(physical_base + "/Project")
            if hasattr(self, 'client_name_backup'):
                self.client_name_var.set(self.client_name_backup)
        else:
            if hasattr(self, 'client_name_backup'):
                self.client_name_var.set(self.client_name_backup)
            else:
                self.client_name_var.set("")
            if hasattr(self, 'base_dir_backup'):
                self.base_dir_var.set(self.base_dir_backup)
            else:
                self.base_dir_var.set(self.settings.get_work_path("Physical").replace('\\', '/'))

        self.update_preview()

    def browse_base_dir(self):
        """Open dialog to browse for base directory."""
        directory = filedialog.askdirectory()
        if directory:
            self.base_dir_var.set(directory)
            self.update_preview()

    def _get_conditionals(self):
        """Build conditionals dict from current form state."""
        active_software = get_active_software(self.software_chips)
        return {
            'preproduction': self.include_preproduction_var.get(),
            'library': self.include_library_var.get(),
            'houdini': 'Houdini' in active_software,
            'blender': 'Blender' in active_software,
            'freecad': 'FreeCAD' in active_software,
            'alibre': 'Alibre' in active_software,
            'affinity': 'Affinity' in active_software,
        }

    def get_folder_structure_preview(self):
        """Generate the folder structure that will be created."""
        if not os.path.isfile(self.tree_file):
            return []
        tree = parse_tree_file(self.tree_file)
        conditionals = self._get_conditionals()
        date = self.date_var.get() or datetime.now().strftime('%Y-%m-%d')
        replacements = {'YYY-MM-DD': date}

        folders = []
        skipped_prefixes = []
        for path, cond in tree:
            skip = False
            for prefix in skipped_prefixes:
                if path.startswith(prefix + '/'):
                    skip = True
                    break
            if skip:
                continue
            if cond and not conditionals.get(cond, True):
                skipped_prefixes.append(path)
                continue
            for placeholder, value in replacements.items():
                path = path.replace(placeholder, value)
            folders.append(path)
        return folders

    def update_preview(self):
        """Update the preview of the folder structure."""
        self.preview_text.configure(state=tk.NORMAL)
        self.preview_text.delete(1.0, tk.END)

        client = self.client_name_var.get() or "[Client]"
        project = self.project_name_var.get() or "[Project]"
        date = self.date_var.get() or datetime.now().strftime('%Y-%m-%d')

        if self.personal_var.get() or self.product_var.get():
            project_dir = f"{date}_3DPrint_{project}"
        else:
            project_dir = f"{date}_3DPrint_{client}_{project}"

        base_dir = self.base_dir_var.get()
        self.preview_text.insert(tk.END, f"Path: {base_dir}/{project_dir}\n\n")

        # Software specs from chips
        active_software = get_active_software(self.software_chips)
        software_list = [f"{name} {ver}" for name, ver in active_software.items() if ver]

        if software_list:
            self.preview_text.insert(tk.END, f"Tools: {', '.join(software_list)}\n")
        self.preview_text.insert(tk.END, f"Hardware: {self.slicer_var.get()} / {self.printer_var.get()}\n\n")

        self.preview_text.insert(tk.END, "Structure:\n")
        folders = self.get_folder_structure_preview()

        dir_tree = {}
        for path in folders:
            parts = path.split('/')
            current = dir_tree
            for part in parts:
                if part not in current:
                    current[part] = {}
                current = current[part]

        def print_tree(tree, prefix=""):
            items = list(tree.items())
            for i, (name, subtree) in enumerate(items):
                is_last = i == len(items) - 1
                self.preview_text.insert(tk.END, f"{prefix}{'└── ' if is_last else '├── '}{name}\n")
                if subtree:
                    extension = "    " if is_last else "│   "
                    print_tree(subtree, prefix + extension)

        print_tree(dir_tree)

        self.preview_text.configure(state=tk.DISABLED)

    def validate_inputs(self):
        """Validate all required inputs."""
        client_name = self.client_name_var.get().strip()
        project_name = self.project_name_var.get().strip()
        date = self.date_var.get().strip()
        base_dir = self.base_dir_var.get()

        if not base_dir or not os.path.isdir(base_dir):
            messagebox.showerror("Error", "Please select a valid base directory.")
            return False

        if not client_name:
            if self.personal_var.get():
                self.client_name_var.set("Personal")
            elif self.product_var.get():
                self.client_name_var.set("alles3d")
            elif not self.project_var.get():
                messagebox.showerror("Error", "Please enter a client name.")
                return False

        if not project_name:
            messagebox.showerror("Error", "Please enter a project name.")
            return False

        if not date:
            self.date_var.set(datetime.now().strftime('%Y-%m-%d'))

        return True

    def create_structure(self):
        """Create the folder structure based on user input."""
        if not self.validate_inputs():
            return

        base_dir = self.base_dir_var.get()
        client_name = self.client_name_var.get()
        project_name = self.project_name_var.get()
        date = self.date_var.get()

        # Get software specs from chips
        software_specs = get_active_software(self.software_chips)

        slicer_software = self.slicer_var.get()
        printer_model = self.printer_var.get()

        if self.personal_var.get() or self.product_var.get():
            project_dir = os.path.join(base_dir, f'{date}_3DPrint_{project_name}')
        else:
            project_dir = os.path.join(base_dir, f'{date}_3DPrint_{client_name}_{project_name}')

        try:
            os.makedirs(project_dir, exist_ok=True)
            self.create_folder_structure(project_dir, date, software_specs)
            self.create_specs_file(project_dir, client_name, project_name, date,
                                   software_specs, slicer_software, printer_model)

            self.status_var.set(f"Created project structure for {project_name}")

            project_data = {
                'client_name': client_name,
                'project_name': project_name,
                'project_type': 'Physical',
                'date_created': date,
                'path': project_dir,
                'base_directory': base_dir,
                'status': 'active',
                'notes': self.notes_text.get(1.0, tk.END).strip(),
                'metadata': {
                    'software_specs': software_specs,
                    'slicer': slicer_software,
                    'printer': printer_model,
                    'is_personal': self.personal_var.get(),
                    'is_product': self.product_var.get()
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

    def create_folder_structure(self, project_dir, date, software_specs):
        """Create the folder structure from tree definition."""
        tree = parse_tree_file(self.tree_file)
        replacements = {'YYY-MM-DD': date}
        conditionals = self._get_conditionals()
        tree_create_structure(project_dir, tree, replacements, conditionals)

    def create_specs_file(self, project_dir, client_name, project_name, date,
                          software_specs, slicer_software, printer_model):
        """Create a specifications text file."""
        try:
            if self.include_library_var.get():
                docs_dir = os.path.join(project_dir, '_LIBRARY/Documents')
                spec_file_path = os.path.join(docs_dir, 'project_specifications.txt')
            else:
                spec_file_path = os.path.join(project_dir, 'project_specifications.txt')

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            notes = self.notes_text.get(1.0, tk.END).strip()
            if not notes:
                notes = "No notes provided."

            software_content = "PRODUCTION TOOLS\n======================\n"
            if software_specs:
                for software, version in software_specs.items():
                    software_content += f"{software}: {version}\n"
            else:
                software_content += "No production tools selected.\n"

            structure_content = "PROJECT STRUCTURE\n======================\n"
            if self.include_preproduction_var.get():
                structure_content += "Preproduction folder included\n"
            else:
                structure_content += "Preproduction folder not included\n"

            if self.include_library_var.get():
                structure_content += "_LIBRARY folder included\n"
            else:
                structure_content += "_LIBRARY folder not included\n"

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
FolderStructureCreator = PhysicalFolderStructureCreator


if __name__ == "__main__":
    root = tk.Tk()
    app = PhysicalFolderStructureCreator(root)
    root.mainloop()
