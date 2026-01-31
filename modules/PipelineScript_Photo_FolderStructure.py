"""
Photo Project Folder Structure Creator

Creates standardized folder structure for photo projects.

Keyboard Navigation:
- Tab/Enter: Move to next field
- Shift+Tab: Move to previous field
- Ctrl+Enter: Create project (from anywhere)
- Escape: Close form
- S: Toggle Sandbox checkbox (when not typing)
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

from shared_form_keyboard import (
    FormKeyboardMixin, FORM_COLORS,
    create_styled_entry, create_styled_text, create_styled_button,
    create_styled_label, create_styled_checkbox, create_styled_frame,
    create_styled_labelframe, format_button_with_shortcut
)
from shared_folder_tree_parser import parse_tree_file, create_structure as tree_create_structure

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


class PhotoFolderStructureCreator(FormKeyboardMixin):
    """Creates folder structure for photo projects with keyboard-first navigation."""

    def __init__(self, root_or_frame, embedded=False, on_project_created=None, on_cancel=None):
        """Initialize the Photo Folder Structure Creator."""
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
            self.root.title("Photo Folder Structure")
            self.root.geometry("900x550")
            self.root.minsize(800, 450)

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

        # ==================== ROW 1: Main inputs ====================
        row1 = create_styled_frame(main_frame)
        row1.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        row1.columnconfigure(1, weight=1)
        row1.columnconfigure(3, weight=1)
        row1.columnconfigure(5, weight=1)

        create_styled_label(row1, "Date:").grid(row=0, column=0, sticky="e", padx=(0, 5))
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        self.date_entry = create_styled_entry(row1, textvariable=self.date_var, width=12)
        self.date_entry.grid(row=0, column=1, sticky="w", padx=(0, 20))

        create_styled_label(row1, "Location:").grid(row=0, column=2, sticky="e", padx=(0, 5))
        self.location_var = tk.StringVar()
        self.location_entry = create_styled_entry(row1, textvariable=self.location_var, width=20)
        self.location_entry.grid(row=0, column=3, sticky="ew", padx=(0, 20))

        create_styled_label(row1, "Activity/People:").grid(row=0, column=4, sticky="e", padx=(0, 5))
        self.activity_var = tk.StringVar()
        self.activity_entry = create_styled_entry(row1, textvariable=self.activity_var, width=20)
        self.activity_entry.grid(row=0, column=5, sticky="ew")

        # ==================== ROW 2: Sandbox option ====================
        row2 = create_styled_frame(main_frame)
        row2.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        self.sandbox_var = tk.BooleanVar(value=False)
        self.sandbox_check = create_styled_checkbox(
            row2, text="Sandbox (S)", variable=self.sandbox_var, command=self.on_sandbox_toggle
        )
        self.sandbox_check.pack(side=tk.LEFT)

        # ==================== ROW 3: Notes and Preview ====================
        row3 = create_styled_frame(main_frame)
        row3.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        row3.columnconfigure(0, weight=1)
        row3.columnconfigure(1, weight=2)
        row3.rowconfigure(0, weight=1)

        # Notes (left)
        notes_frame = create_styled_labelframe(row3, text="Notes (optional)")
        notes_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        notes_frame.columnconfigure(0, weight=1)
        notes_frame.rowconfigure(0, weight=1)

        self.notes_text = create_styled_text(notes_frame, height=6)
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
            highlightthickness=0, relief=tk.FLAT
        )
        self.preview_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # ==================== ROW 4: Action buttons ====================
        row4 = create_styled_frame(main_frame)
        row4.grid(row=3, column=0, sticky="e", pady=(10, 0))

        self.base_dir_var = tk.StringVar(value='I:/Photo')

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
        self.date_var.trace_add("write", lambda *args: self.update_preview())
        self.location_var.trace_add("write", lambda *args: self.update_preview())
        self.activity_var.trace_add("write", lambda *args: self.update_preview())
        self.sandbox_var.trace_add("write", lambda *args: self.update_preview())

    def _collect_focusable_widgets(self):
        """Collect widgets for keyboard navigation."""
        self._focusable_widgets = [
            self.date_entry, self.location_entry, self.activity_entry,
            self.sandbox_check, self.notes_text,
        ]
        self._create_btn = self.create_btn
        self._browse_btn = self.browse_btn
        self._notes_widget = self.notes_text
        self._personal_checkbox = self.sandbox_check
        self._personal_var = self.sandbox_var

        # Add Enter binding for sandbox checkbox to toggle it
        self.sandbox_check.bind("<Return>", lambda e: self._toggle_sandbox_checkbox())

    def _toggle_sandbox_checkbox(self):
        """Toggle sandbox checkbox when Enter is pressed."""
        self.sandbox_var.set(not self.sandbox_var.get())
        self.on_sandbox_toggle()
        return "break"

    def _setup_keyboard_navigation(self):
        """Set up keyboard navigation with S key for Sandbox toggle."""
        super()._setup_keyboard_navigation()

        # Override P key to use S for Sandbox instead
        root = self.parent.winfo_toplevel()
        root.unbind("<p>")
        root.unbind("<P>")
        root.bind("<s>", self._on_s_key)
        root.bind("<S>", self._on_s_key)

    def _on_s_key(self, event):
        """Handle S key to toggle Sandbox checkbox."""
        if hasattr(self, '_in_text_field') and self._in_text_field:
            return
        self.sandbox_var.set(not self.sandbox_var.get())
        return "break"

    def on_sandbox_toggle(self):
        """Handle sandbox checkbox toggle."""
        self.update_preview()

    def browse_base_dir(self):
        """Open dialog to browse for base directory."""
        directory = filedialog.askdirectory()
        if directory:
            self.base_dir_var.set(directory)
            self.update_preview()

    def sanitize_folder_name(self, name):
        """Remove special characters that might cause issues in file paths."""
        sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
        sanitized = re.sub(r'[^\w\s\-_.,&()]+', '', sanitized)
        sanitized = re.sub(r'\s+', ' ', sanitized)
        return sanitized.strip()

    def build_folder_name(self):
        """Build the folder name from input fields."""
        date = self.sanitize_folder_name(self.date_var.get().strip())
        location = self.sanitize_folder_name(self.location_var.get().strip())
        activity = self.sanitize_folder_name(self.activity_var.get().strip())
        return f"{date}_{location}_{activity}"

    def get_target_directory(self):
        """Determine the target directory based on checkbox selections."""
        base_dir = self.base_dir_var.get()
        if self.sandbox_var.get():
            return os.path.join(base_dir, "_Sandbox")
        return base_dir

    def update_preview(self):
        """Update the preview."""
        self.preview_text.configure(state=tk.NORMAL)
        self.preview_text.delete(1.0, tk.END)

        date = self.date_var.get() or "[Date]"
        location = self.location_var.get() or "[Location]"
        activity = self.activity_var.get() or "[Activity]"

        folder_name = self.build_folder_name()
        target_dir = self.get_target_directory()
        full_path = os.path.join(target_dir, folder_name)

        self.preview_text.insert(tk.END, f"Path: {full_path}\n\n")

        if self.sandbox_var.get():
            self.preview_text.insert(tk.END, "Directory: Sandbox\n\n")
        else:
            self.preview_text.insert(tk.END, "Directory: Main Photo folder\n\n")

        self.preview_text.insert(tk.END, "Structure:\n")
        self.preview_text.insert(tk.END, f"  {folder_name}/\n")
        self.preview_text.insert(tk.END, f"    RAW/\n")

        self.preview_text.configure(state=tk.DISABLED)

    def validate_inputs(self):
        """Validate all required inputs."""
        date = self.date_var.get().strip()
        location = self.location_var.get().strip()
        activity = self.activity_var.get().strip()

        if not date:
            messagebox.showerror("Error", "Please enter a date.")
            return False

        if not location:
            messagebox.showerror("Error", "Please enter a location.")
            return False

        if not activity:
            messagebox.showerror("Error", "Please enter activity & people information.")
            return False

        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Error", "Please enter date in YYYY-MM-DD format.")
            return False

        return True

    def create_structure(self):
        """Create the folder structure."""
        if not self.validate_inputs():
            return

        target_dir = self.get_target_directory()
        folder_name = self.build_folder_name()
        project_path = os.path.join(target_dir, folder_name)

        if not os.path.exists(self.base_dir_var.get()):
            messagebox.showerror("Error", f"Base directory does not exist: {self.base_dir_var.get()}")
            return

        try:
            os.makedirs(target_dir, exist_ok=True)

            if os.path.exists(project_path):
                if not messagebox.askyesno("Directory Exists",
                                          f"Directory already exists:\n{project_path}\n\nContinue?"):
                    return

            os.makedirs(project_path, exist_ok=True)
            tree_file = os.path.join(TEMPLATES_DIR, 'photo_structure.txt')
            tree = parse_tree_file(tree_file)
            tree_create_structure(project_path, tree)

            self.status_var.set(f"Created project structure: {folder_name}")

            project_data = {
                'client_name': 'Personal',
                'project_name': folder_name,
                'project_type': 'Photo',
                'date_created': self.date_var.get(),
                'path': project_path,
                'base_directory': target_dir,
                'status': 'active',
                'notes': self.notes_text.get(1.0, tk.END).strip(),
                'metadata': {
                    'location': self.location_var.get(),
                    'activity': self.activity_var.get(),
                    'is_sandbox': self.sandbox_var.get()
                }
            }

            if self.embedded and self.on_project_created:
                self.on_project_created(project_data)
            else:
                if messagebox.askyesno("Success", f"Project created at:\n\n{project_path}\n\nOpen folder?"):
                    self.open_folder(project_path)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create structure: {str(e)}")
            self.status_var.set("Error creating project structure")

    def _handle_cancel(self):
        """Handle cancel button click."""
        if self.on_cancel:
            self.on_cancel()

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
    app = PhotoFolderStructureCreator(root)
    root.mainloop()
