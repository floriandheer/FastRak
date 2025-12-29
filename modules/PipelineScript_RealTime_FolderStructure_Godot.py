import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import shutil

class FolderStructureCreator:
    def __init__(self, root):
        self.root = root
        self.root.title("Godot Folder Structure")
        self.root.geometry("750x700")
        self.root.minsize(700, 550)

        # Configure main window
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # Create header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header_frame.grid_propagate(False)

        # Add title to header
        title_label = tk.Label(header_frame, text="Godot Folder Structure",
                              font=("Arial", 16, "bold"), fg="white", bg="#2c3e50")
        title_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Create main frame with preview only
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=1)

        # Create form panel (left side)
        form_frame = ttk.LabelFrame(main_frame, text="Project Settings")
        form_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        form_frame.columnconfigure(1, weight=1)

        # Base directory
        ttk.Label(form_frame, text="Base Directory:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        self.base_dir_var = tk.StringVar(value='I:/RealTime')
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

        # Godot version
        ttk.Label(spec_frame, text="Godot:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.godot_var = tk.StringVar(value="4.3")
        ttk.Entry(spec_frame, textvariable=self.godot_var, width=15).grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # Target platform
        ttk.Label(spec_frame, text="Platform:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.platform_var = tk.StringVar(value="PC/Desktop")
        platform_combo = ttk.Combobox(spec_frame, textvariable=self.platform_var, width=13,
                                     values=["PC/Desktop", "Mobile", "Web", "Console", "Multi-platform"])
        platform_combo.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # Renderer
        ttk.Label(spec_frame, text="Renderer:").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.renderer_var = tk.StringVar(value="Forward+")
        renderer_combo = ttk.Combobox(spec_frame, textvariable=self.renderer_var, width=13,
                                     values=["Forward+", "Mobile", "Compatibility"])
        renderer_combo.grid(row=2, column=1, sticky="w", padx=5, pady=5)

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

        # Create button with padding
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

        # Initialize preview
        self.update_preview()

        # Set up event bindings for live preview updates
        self.client_name_var.trace_add("write", lambda *args: self.update_preview())
        self.project_name_var.trace_add("write", lambda *args: self.update_preview())
        self.date_var.trace_add("write", lambda *args: self.update_preview())
        self.personal_var.trace_add("write", lambda *args: self.update_preview())
        self.godot_var.trace_add("write", lambda *args: self.update_preview())
        self.platform_var.trace_add("write", lambda *args: self.update_preview())
        self.renderer_var.trace_add("write", lambda *args: self.update_preview())

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
        """Define the Godot folder structure"""
        return {
            'Production': {
                'Scenes': {
                    'Main': {},
                    'Levels': {},
                    'UI': {},
                    'Characters': {},
                    'Environment': {}
                },
                'Scripts': {
                    'Characters': {},
                    'Gameplay': {},
                    'UI': {},
                    'Systems': {},
                    'Utilities': {}
                },
                'Assets': {
                    'Textures': {
                        'Characters': {},
                        'Environment': {},
                        'UI': {},
                        'VFX': {}
                    },
                    'Models': {
                        'Characters': {},
                        'Props': {},
                        'Environment': {}
                    },
                    'Audio': {
                        'Music': {},
                        'SFX': {},
                        'Voice': {}
                    },
                    'Fonts': {},
                    'Materials': {},
                    'Animations': {}
                },
                'Addons': {},
                'Autoload': {},
                'Resources': {
                    'Themes': {},
                    'Materials': {},
                    'Shaders': {}
                },
                'Shaders': {},
                'Prefabs': {},
                'Exports': {
                    'Builds': {
                        'Windows': {},
                        'Linux': {},
                        'MacOS': {},
                        'Android': {},
                        'iOS': {},
                        'Web': {}
                    },
                    'Screenshots': {}
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
        godot = self.godot_var.get()
        platform = self.platform_var.get()
        renderer = self.renderer_var.get()

        # Get notes
        notes = self.notes_text.get(1.0, tk.END).strip()

        # Build the project directory name
        project_dir = f"{date}_Godot_{client}_{project}"

        # Display preview
        base_dir = self.base_dir_var.get()
        # If Personal project, show _Personal subfolder in preview
        if self.personal_var.get():
            preview_path = f"{base_dir}/_Personal/{project_dir}"
        else:
            preview_path = f"{base_dir}/{project_dir}"
        self.preview_text.insert(tk.END, f"Project will be created at:\n{preview_path}\n\n")
        self.preview_text.insert(tk.END, "Software Specifications:\n")
        self.preview_text.insert(tk.END, f"Godot: {godot}\n")
        self.preview_text.insert(tk.END, f"Platform: {platform}\n")
        self.preview_text.insert(tk.END, f"Renderer: {renderer}\n\n")

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
        godot_version = self.godot_var.get()
        platform = self.platform_var.get()
        renderer = self.renderer_var.get()

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

        project_dir = os.path.join(base_dir, f'{date}_Godot_{client_name}_{project_name}')

        try:
            # Create the folder structure
            self.create_folders(project_dir, self.get_folder_structure(), date)

            # Create Godot project file
            self.create_godot_project_file(project_dir, project_name, renderer)

            # Create specifications file
            self.create_specs_file(project_dir, client_name, project_name, date,
                                   godot_version, platform, renderer)

            # Create .gitignore
            self.create_gitignore(project_dir)

            self.status_var.set(f"Created project structure for {client_name}_{project_name}")

            # Show success message
            if messagebox.askyesno("Success", f"Project structure created successfully at:\n\n{project_dir}\n\nWould you like to open the folder?"):
                self.open_folder(project_dir)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create structure: {str(e)}")
            self.status_var.set("Error creating project structure")

    def create_folders(self, base_path, structure, date):
        """Recursively create folder structure"""
        for folder_name, subfolders in structure.items():
            # Replace YYY-MM-DD with actual date
            if folder_name == "YYY-MM-DD":
                folder_name = date

            folder_path = os.path.join(base_path, folder_name)
            os.makedirs(folder_path, exist_ok=True)

            # Create .gdignore in certain folders to prevent Godot from importing
            if folder_name in ['_Library', '_Delivery', 'Backup']:
                gdignore_path = os.path.join(folder_path, '.gdignore')
                open(gdignore_path, 'a').close()

            if subfolders:
                self.create_folders(folder_path, subfolders, date)

    def create_godot_project_file(self, project_dir, project_name, renderer):
        """Create a basic project.godot file"""
        try:
            production_dir = os.path.join(project_dir, 'Production')
            project_file_path = os.path.join(production_dir, 'project.godot')

            # Map renderer names to Godot config values
            renderer_map = {
                "Forward+": "forward_plus",
                "Mobile": "mobile",
                "Compatibility": "gl_compatibility"
            }

            renderer_value = renderer_map.get(renderer, "forward_plus")

            content = f"""; Engine configuration file.
; It's best edited using the editor UI and not directly,
; since the parameters that go here are not all obvious.
;
; Format:
;   [section] ; section goes between []
;   param=value ; assign values to parameters

config_version=5

[application]

config/name="{project_name}"
config/features=PackedStringArray("4.3", "{renderer_value}")

[rendering]

renderer/rendering_method="{renderer_value}"
"""

            with open(project_file_path, 'w', encoding='utf-8') as file:
                file.write(content)

        except Exception as e:
            print(f"Could not create project.godot file: {str(e)}")

    def create_gitignore(self, project_dir):
        """Create a .gitignore file for Godot projects"""
        try:
            production_dir = os.path.join(project_dir, 'Production')
            gitignore_path = os.path.join(production_dir, '.gitignore')

            content = """# Godot 4+ specific ignores
.godot/
.import/

# Exported builds
exports/
*.exe
*.pck
*.apk
*.dmg

# Mono-specific ignores
.mono/
data_*/
mono_crash.*.json

# System/tool-specific ignores
.DS_Store
Thumbs.db
*.swp
*.swo
*~
"""

            with open(gitignore_path, 'w', encoding='utf-8') as file:
                file.write(content)

        except Exception as e:
            print(f"Could not create .gitignore file: {str(e)}")

    def create_specs_file(self, project_dir, client_name, project_name, date,
                          godot_version, platform, renderer):
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
Godot: {godot_version}
Target Platform: {platform}
Renderer: {renderer}

PROJECT STRUCTURE
======================
Production/
├── Scenes/           # Game scenes organized by type
│   ├── Main/        # Main/core scenes
│   ├── Levels/      # Level scenes
│   ├── UI/          # UI scenes
│   ├── Characters/  # Character scenes
│   └── Environment/ # Environment scenes
├── Scripts/          # GDScript files organized by function
├── Assets/          # All game assets
│   ├── Textures/    # Image files and sprites
│   ├── Models/      # 3D models
│   ├── Audio/       # Sound effects, music, voice
│   ├── Fonts/       # Font files
│   ├── Materials/   # Material resources
│   └── Animations/  # Animation files
├── Addons/          # Third-party addons and plugins
├── Autoload/        # Singleton/autoload scripts
├── Resources/       # Reusable resources (themes, materials, etc)
├── Shaders/         # Custom shader files
├── Prefabs/         # Reusable scene prefabs
└── Exports/         # Build outputs

IMPORTANT FILES
======================
- project.godot      # Main Godot project configuration
- .gitignore         # Git ignore rules for Godot projects

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
