"""
UI Settings Dialog - Multi-tab settings window for the Pipeline Manager.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font

from shared_logging import get_logger
from rak_settings import RakSettings
from ui_theme import COLORS, CATEGORY_COLORS

logger = get_logger("pipeline")


class SettingsDialog:
    """Settings dialog for configuring pipeline paths and preferences."""

    def __init__(self, parent, settings: RakSettings):
        """
        Initialize the settings dialog.

        Args:
            parent: Parent window
            settings: RakSettings instance
        """
        self.parent = parent
        self.settings = settings
        self.result = False  # True if saved

        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Rak Settings")
        self.dialog.geometry("750x750")
        self.dialog.minsize(700, 600)
        self.dialog.configure(bg=COLORS["bg_primary"])

        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # Store original values for cancel
        self._original_work_drive = settings.get_work_drive()
        self._original_archive_base = settings.get_archive_base()

        # Build UI
        self._build_ui()

        # Validate on open
        self._validate_paths()

    def _build_ui(self):
        """Build the settings dialog UI."""
        # Header
        header_frame = tk.Frame(self.dialog, bg=COLORS["bg_secondary"], height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        header_label = tk.Label(
            header_frame,
            text="Rak Settings",
            font=font.Font(family="Segoe UI", size=16, weight="bold"),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_secondary"]
        )
        header_label.pack(side=tk.LEFT, padx=20, pady=15)

        # Notebook for tabs
        style = ttk.Style()
        style.configure("Settings.TNotebook", background=COLORS["bg_primary"])
        style.configure("Settings.TNotebook.Tab",
                       background=COLORS["bg_secondary"],
                       foreground=COLORS["text_primary"],
                       padding=[15, 8],
                       width=20)
        style.map("Settings.TNotebook.Tab",
                 background=[("selected", COLORS["accent_dark"])],
                 foreground=[("selected", "#ffffff")],
                 padding=[("selected", [15, 8])])

        self.notebook = ttk.Notebook(self.dialog, style="Settings.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # === PATHS TAB ===
        paths_tab = tk.Frame(self.notebook, bg=COLORS["bg_primary"])
        self.notebook.add(paths_tab, text="Paths")
        self._build_paths_tab(paths_tab)

        # === SOFTWARE TAB ===
        software_tab = tk.Frame(self.notebook, bg=COLORS["bg_primary"])
        self.notebook.add(software_tab, text="Software Defaults")
        self._build_software_tab(software_tab)

        # === BUTTON ROW ===
        self._build_button_row()

    def _build_paths_tab(self, parent):
        """Build the Paths settings tab."""
        content_frame = tk.Frame(parent, bg=COLORS["bg_primary"])
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # === DRIVE CONFIGURATION SECTION ===
        drive_section = tk.LabelFrame(
            content_frame,
            text=" Drive Configuration ",
            font=font.Font(family="Segoe UI", size=11, weight="bold"),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"],
            padx=15,
            pady=10
        )
        drive_section.pack(fill=tk.X, pady=(0, 15))

        # Active Drive row
        work_frame = tk.Frame(drive_section, bg=COLORS["bg_card"])
        work_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            work_frame,
            text="Active Drive:",
            font=font.Font(family="Segoe UI", size=10),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"],
            width=15,
            anchor="w"
        ).pack(side=tk.LEFT)

        self.work_drive_var = tk.StringVar(value=self.settings.get_work_drive())
        work_entry = tk.Entry(
            work_frame,
            textvariable=self.work_drive_var,
            font=font.Font(family="Segoe UI", size=10),
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            width=30
        )
        work_entry.pack(side=tk.LEFT, padx=(0, 10))
        work_entry.bind('<KeyRelease>', lambda e: self._validate_paths())

        self.work_status_label = tk.Label(
            work_frame,
            text="",
            font=font.Font(family="Segoe UI", size=9),
            bg=COLORS["bg_card"],
            width=25,
            anchor="w"
        )
        self.work_status_label.pack(side=tk.LEFT)

        # Help text for work drive
        tk.Label(
            drive_section,
            text="Mapped via VisualSubst to your active projects directory",
            font=font.Font(family="Segoe UI", size=9, slant="italic"),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"]
        ).pack(anchor="w", padx=(15 * 10, 0), pady=(0, 5))

        # Active Base row
        active_frame = tk.Frame(drive_section, bg=COLORS["bg_card"])
        active_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            active_frame,
            text="Active Base:",
            font=font.Font(family="Segoe UI", size=10),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"],
            width=15,
            anchor="w"
        ).pack(side=tk.LEFT)

        self.active_base_var = tk.StringVar(value=self.settings.get_active_base())
        active_entry = tk.Entry(
            active_frame,
            textvariable=self.active_base_var,
            font=font.Font(family="Segoe UI", size=10),
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            width=30
        )
        active_entry.pack(side=tk.LEFT, padx=(0, 10))
        active_entry.bind('<KeyRelease>', lambda e: self._validate_paths())

        browse_active_btn = tk.Button(
            active_frame,
            text="Browse",
            command=self._browse_active,
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
            font=font.Font(family="Segoe UI", size=9),
            relief=tk.FLAT,
            cursor="hand2",
            padx=10
        )
        browse_active_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.active_status_label = tk.Label(
            active_frame,
            text="",
            font=font.Font(family="Segoe UI", size=9),
            bg=COLORS["bg_card"],
            width=20,
            anchor="w"
        )
        self.active_status_label.pack(side=tk.LEFT)

        tk.Label(
            drive_section,
            text="Real path the active drive maps to (e.g. D:\\_work\\Active)",
            font=font.Font(family="Segoe UI", size=9, slant="italic"),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"]
        ).pack(anchor="w", padx=(15 * 10, 0), pady=(0, 5))

        # Archive Base row
        archive_frame = tk.Frame(drive_section, bg=COLORS["bg_card"])
        archive_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            archive_frame,
            text="Archive Base:",
            font=font.Font(family="Segoe UI", size=10),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"],
            width=15,
            anchor="w"
        ).pack(side=tk.LEFT)

        self.archive_base_var = tk.StringVar(value=self.settings.get_archive_base())
        archive_entry = tk.Entry(
            archive_frame,
            textvariable=self.archive_base_var,
            font=font.Font(family="Segoe UI", size=10),
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            width=30
        )
        archive_entry.pack(side=tk.LEFT, padx=(0, 10))
        archive_entry.bind('<KeyRelease>', lambda e: self._validate_paths())

        browse_btn = tk.Button(
            archive_frame,
            text="Browse",
            command=self._browse_archive,
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
            font=font.Font(family="Segoe UI", size=9),
            relief=tk.FLAT,
            cursor="hand2",
            padx=10
        )
        browse_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.archive_status_label = tk.Label(
            archive_frame,
            text="",
            font=font.Font(family="Segoe UI", size=9),
            bg=COLORS["bg_card"],
            width=20,
            anchor="w"
        )
        self.archive_status_label.pack(side=tk.LEFT)

        # === CATEGORY PATHS SECTION ===
        paths_section = tk.LabelFrame(
            content_frame,
            text=" Category Paths ",
            font=font.Font(family="Segoe UI", size=11, weight="bold"),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"],
            padx=15,
            pady=10
        )
        paths_section.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Header row
        header_row = tk.Frame(paths_section, bg=COLORS["bg_card"])
        header_row.pack(fill=tk.X, pady=(0, 5))

        tk.Label(
            header_row,
            text="Category",
            font=font.Font(family="Segoe UI", size=9, weight="bold"),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"],
            width=12,
            anchor="w"
        ).pack(side=tk.LEFT)

        tk.Label(
            header_row,
            text="Active Path",
            font=font.Font(family="Segoe UI", size=9, weight="bold"),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"],
            width=25,
            anchor="w"
        ).pack(side=tk.LEFT, padx=(10, 0))

        tk.Label(
            header_row,
            text="Archive Path",
            font=font.Font(family="Segoe UI", size=9, weight="bold"),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"],
            width=30,
            anchor="w"
        ).pack(side=tk.LEFT, padx=(10, 0))

        # Separator
        sep = tk.Frame(paths_section, bg=COLORS["border"], height=1)
        sep.pack(fill=tk.X, pady=5)

        # Category rows
        self.category_labels = {}
        for category in self.settings.get_ordered_categories():
            row = tk.Frame(paths_section, bg=COLORS["bg_card"])
            row.pack(fill=tk.X, pady=2)

            # Category name with color indicator
            cat_color = CATEGORY_COLORS.get(category.upper(), COLORS["text_primary"])
            cat_label = tk.Label(
                row,
                text=f"  {category}",
                font=font.Font(family="Segoe UI", size=10),
                fg=cat_color,
                bg=COLORS["bg_card"],
                width=12,
                anchor="w"
            )
            cat_label.pack(side=tk.LEFT)

            # Work path (read-only, computed from drive + subpath)
            work_path = self.settings.get_work_path(category)
            work_label = tk.Label(
                row,
                text=work_path.replace('\\', '/'),
                font=font.Font(family="Consolas", size=9),
                fg=COLORS["text_primary"],
                bg=COLORS["bg_secondary"],
                width=25,
                anchor="w",
                padx=5
            )
            work_label.pack(side=tk.LEFT, padx=(10, 0))

            # Archive path
            archive_path = self.settings.get_archive_path(category)
            archive_label = tk.Label(
                row,
                text=archive_path.replace('\\', '/'),
                font=font.Font(family="Consolas", size=9),
                fg=COLORS["text_primary"],
                bg=COLORS["bg_secondary"],
                width=30,
                anchor="w",
                padx=5
            )
            archive_label.pack(side=tk.LEFT, padx=(10, 0))

            self.category_labels[category] = {
                "work": work_label,
                "archive": archive_label
            }

            # Show subcategories if any
            cat_config = self.settings.get_category_config(category)
            subcats = cat_config.get("subcategories", [])
            if subcats:
                for subcat in subcats:
                    sub_row = tk.Frame(paths_section, bg=COLORS["bg_card"])
                    sub_row.pack(fill=tk.X, pady=1)

                    tk.Label(
                        sub_row,
                        text=f"    {subcat}",
                        font=font.Font(family="Segoe UI", size=9),
                        fg=COLORS["text_secondary"],
                        bg=COLORS["bg_card"],
                        width=12,
                        anchor="w"
                    ).pack(side=tk.LEFT)

                    tk.Label(
                        sub_row,
                        text="(inherits)",
                        font=font.Font(family="Segoe UI", size=9, slant="italic"),
                        fg=COLORS["text_secondary"],
                        bg=COLORS["bg_card"]
                    ).pack(side=tk.LEFT, padx=(10, 0))

    def _build_software_tab(self, parent):
        """Build the Software Defaults settings tab."""
        # Scrollable frame for software settings
        canvas = tk.Canvas(parent, bg=COLORS["bg_primary"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLORS["bg_primary"])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mousewheel scrolling when mouse is over the canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Store software entry widgets for saving
        self.software_entries = {}

        # Get current software defaults (flat dict)
        software_defaults = self.settings.get_software_defaults()

        # Software grouped by section for display (vertical layout)
        software_sections = [
            ("3D", ["houdini", "blender", "freecad", "alibre", "slicer", "printer"]),
            ("2D", ["affinity"]),
            ("FX", ["fusion", "after_effects"]),
            ("RealTime", ["godot", "resolume", "touchdesigner", "python", "platform", "renderer", "resolution"]),
            ("Audio", ["ableton", "reaper", "traktor"]),
        ]

        for section_label, software_list in software_sections:
            section = tk.LabelFrame(
                scrollable_frame,
                text=f" {section_label} ",
                font=font.Font(family="Segoe UI", size=11, weight="bold"),
                fg=COLORS["text_primary"],
                bg=COLORS["bg_card"],
                padx=15,
                pady=10
            )
            section.pack(fill=tk.X, padx=10, pady=(0, 10))

            for software in software_list:
                # Skip if already has an entry (e.g. touchdesigner appears in both)
                if software in self.software_entries:
                    continue

                current_value = software_defaults.get(software, "")
                label_text = software.replace("_", " ").title()

                row = tk.Frame(section, bg=COLORS["bg_card"])
                row.pack(fill=tk.X, pady=2)

                tk.Label(
                    row,
                    text=f"{label_text}:",
                    font=font.Font(family="Segoe UI", size=10),
                    fg=COLORS["text_secondary"],
                    bg=COLORS["bg_card"],
                    width=18,
                    anchor="w"
                ).pack(side=tk.LEFT)

                var = tk.StringVar(value=current_value)
                entry = tk.Entry(
                    row,
                    textvariable=var,
                    font=font.Font(family="Segoe UI", size=10),
                    bg=COLORS["bg_secondary"],
                    fg=COLORS["text_primary"],
                    insertbackground=COLORS["text_primary"],
                    width=20
                )
                entry.pack(side=tk.LEFT)

                self.software_entries[software] = var

    def _build_button_row(self):
        """Build the button row at the bottom of the dialog."""
        button_frame = tk.Frame(self.dialog, bg=COLORS["bg_primary"])
        button_frame.pack(fill=tk.X, padx=20, pady=15)

        # Reset button (left side)
        reset_btn = tk.Button(
            button_frame,
            text="Reset Defaults",
            command=self._reset_defaults,
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
            font=font.Font(family="Segoe UI", size=10),
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        )
        reset_btn.pack(side=tk.LEFT)

        # Cancel button (right side)
        cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel,
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
            font=font.Font(family="Segoe UI", size=10),
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))

        # Save button (right side)
        save_btn = tk.Button(
            button_frame,
            text="Save",
            command=self._save,
            bg=COLORS["accent_dark"],
            fg="#ffffff",
            font=font.Font(family="Segoe UI", size=10, weight="bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=20,
            pady=8
        )
        save_btn.pack(side=tk.RIGHT)

    def _validate_paths(self):
        """Validate current path entries and update status labels."""
        # Validate work drive
        work_drive = self.work_drive_var.get()
        work_valid, work_msg = self.settings.validate_drive(work_drive)

        if work_valid:
            self.work_status_label.config(text=f"OK {work_msg}", fg=COLORS["success"])
        else:
            self.work_status_label.config(text=f"! {work_msg}", fg=COLORS["warning"])

        # Validate active base
        active_base = self.active_base_var.get()
        active_valid, active_msg = self.settings.validate_drive(active_base)

        if active_valid:
            self.active_status_label.config(text=f"OK {active_msg}", fg=COLORS["success"])
        else:
            self.active_status_label.config(text=f"! {active_msg}", fg=COLORS["warning"])

        # Validate archive base
        archive_base = self.archive_base_var.get()
        archive_valid, archive_msg = self.settings.validate_drive(archive_base)

        if archive_valid:
            self.archive_status_label.config(text=f"OK {archive_msg}", fg=COLORS["success"])
        else:
            self.archive_status_label.config(text=f"! {archive_msg}", fg=COLORS["warning"])

        # Update category path labels
        self._update_category_paths()

    def _update_category_paths(self):
        """Update category path labels based on current drive settings."""
        work_drive = self.work_drive_var.get()
        archive_base = self.archive_base_var.get()

        for category, labels in self.category_labels.items():
            cat_config = self.settings.get_category_config(category)
            work_subpath = cat_config.get("work_subpath", category)
            archive_subpath = cat_config.get("archive_subpath", category)

            work_path = f"{work_drive}\\{work_subpath}".replace('\\', '/')
            archive_path = f"{archive_base}\\{archive_subpath}".replace('\\', '/')

            labels["work"].config(text=work_path)
            labels["archive"].config(text=archive_path)

    def _browse_archive(self):
        """Open folder browser for archive base."""
        current = self.archive_base_var.get()
        initial_dir = current if os.path.isdir(current) else None

        folder = filedialog.askdirectory(
            parent=self.dialog,
            title="Select Archive Base Directory",
            initialdir=initial_dir
        )

        if folder:
            # Normalize to Windows path format
            folder = folder.replace('/', '\\')
            self.archive_base_var.set(folder)
            self._validate_paths()

    def _browse_active(self):
        """Open folder browser for active base."""
        current = self.active_base_var.get()
        initial_dir = current if os.path.isdir(current) else None

        folder = filedialog.askdirectory(
            parent=self.dialog,
            title="Select Active Base Directory",
            initialdir=initial_dir
        )

        if folder:
            folder = folder.replace('/', '\\')
            self.active_base_var.set(folder)
            self._validate_paths()

    def _reset_defaults(self):
        """Reset to default values."""
        if messagebox.askyesno(
            "Reset Defaults",
            "Reset all settings to default values?\n\n"
            "This will reset:\n"
            "- Active Drive: I:\n"
            "- Active Base: D:\\_work\\Active\n"
            "- Archive Base: D:\\_work\\Archive\n"
            "- All software version defaults",
            parent=self.dialog
        ):
            # Reset paths
            self.work_drive_var.set("I:")
            self.active_base_var.set("D:\\_work\\Active")
            self.archive_base_var.set("D:\\_work\\Archive")
            self._validate_paths()

            # Reset software defaults in UI
            if hasattr(self, 'software_entries'):
                defaults = self.settings.DEFAULT_CONFIG.get("software_defaults", {})
                for software, var in self.software_entries.items():
                    var.set(defaults.get(software, ""))

    def _save(self):
        """Save settings and close dialog."""
        work_drive = self.work_drive_var.get()
        active_base = self.active_base_var.get()
        archive_base = self.archive_base_var.get()

        # Validate before saving
        work_valid, _ = self.settings.validate_drive(work_drive)
        active_valid, _ = self.settings.validate_drive(active_base)
        archive_valid, _ = self.settings.validate_drive(archive_base)

        if not work_valid or not active_valid or not archive_valid:
            if not messagebox.askyesno(
                "Invalid Paths",
                "Some paths could not be validated.\n\n"
                "Save anyway? (You can fix this later)",
                parent=self.dialog
            ):
                return

        # Save path config
        self.settings.set_work_drive(work_drive)
        self.settings.set_active_base(active_base)
        self.settings.set_archive_base(archive_base)

        # Save software defaults
        if hasattr(self, 'software_entries'):
            versions = {software: var.get() for software, var in self.software_entries.items()}
            self.settings.set_software_defaults(**versions)

        self.result = True
        self.dialog.destroy()
        logger.info("Settings saved")

    def _cancel(self):
        """Cancel and close dialog."""
        self.result = False
        self.dialog.destroy()

    def show(self) -> bool:
        """
        Show the dialog and wait for it to close.

        Returns:
            True if settings were saved, False if cancelled
        """
        self.dialog.wait_window()
        return self.result
