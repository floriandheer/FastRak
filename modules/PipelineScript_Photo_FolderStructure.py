import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import re

class PhotoFolderStructureCreator:
    def __init__(self, root_or_frame, embedded=False, on_project_created=None, on_cancel=None):
        """
        Initialize the Photo Folder Structure Creator.

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
            self.root.title("Photo Project Folder Structure")
            self.root.geometry("750x600")
            self.root.minsize(700, 500)

        if not embedded:
            # Configure main window (standalone only)
            self.root.columnconfigure(0, weight=1)
            self.root.rowconfigure(1, weight=1)

            # Create header (standalone only)
            header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
            header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
            header_frame.grid_propagate(False)

            # Add title to header
            title_label = tk.Label(header_frame, text="Photo Project Folder Structure",
                                  font=("Arial", 16, "bold"), fg="white", bg="#2c3e50")
            title_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Create main frame
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
        
        # Base directory (fixed to I:/Photo)
        ttk.Label(form_frame, text="Base Directory:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        self.base_dir_var = tk.StringVar(value='I:/Photo')
        base_dir_entry = ttk.Entry(form_frame, textvariable=self.base_dir_var, width=40)
        base_dir_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=10)
        ttk.Button(form_frame, text="Browse", command=self.browse_base_dir).grid(row=0, column=2, padx=5, pady=10)
        
        # Project date
        ttk.Label(form_frame, text="Date (YYYY-MM-DD):").grid(row=1, column=0, sticky="w", padx=10, pady=10)
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        date_entry = ttk.Entry(form_frame, textvariable=self.date_var, width=40)
        date_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=10)
        
        # Location
        ttk.Label(form_frame, text="Location:").grid(row=2, column=0, sticky="w", padx=10, pady=10)
        self.location_var = tk.StringVar()
        location_entry = ttk.Entry(form_frame, textvariable=self.location_var, width=40)
        location_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=5, pady=10)
        
        # Activity & People
        ttk.Label(form_frame, text="Activity & People:").grid(row=3, column=0, sticky="w", padx=10, pady=10)
        self.activity_var = tk.StringVar()
        activity_entry = ttk.Entry(form_frame, textvariable=self.activity_var, width=40)
        activity_entry.grid(row=3, column=1, columnspan=2, sticky="ew", padx=5, pady=10)
        
        # Directory options frame
        options_frame = ttk.Frame(form_frame)
        options_frame.grid(row=4, column=0, columnspan=3, sticky="w", padx=5, pady=(0, 10))

        # Directory label and checkbox
        ttk.Label(options_frame, text="Directory:").grid(row=0, column=0, sticky="w", padx=10, pady=(0, 10))

        # Sandbox checkbox
        self.sandbox_var = tk.BooleanVar(value=False)
        sandbox_check = ttk.Checkbutton(options_frame, text="Sandbox",
                                       variable=self.sandbox_var, command=self.on_sandbox_toggle)
        sandbox_check.grid(row=0, column=1, sticky="w", padx=5, pady=(0, 10))
        
        # Button frame for Create and Cancel buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=20)

        # Create button
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
        self.date_var.trace_add("write", lambda *args: self.update_preview())
        self.location_var.trace_add("write", lambda *args: self.update_preview())
        self.activity_var.trace_add("write", lambda *args: self.update_preview())
        self.sandbox_var.trace_add("write", lambda *args: self.update_preview())
        self.base_dir_var.trace_add("write", lambda *args: self.update_preview())
    
    def on_sandbox_toggle(self):
        """Handle sandbox checkbox toggle"""
        self.update_preview()
    
    def browse_base_dir(self):
        """Open dialog to browse for base directory"""
        directory = filedialog.askdirectory()
        if directory:
            self.base_dir_var.set(directory)
            self.update_preview()
    
    def sanitize_folder_name(self, name):
        """Remove special characters that might cause issues in Windows file paths"""
        # Replace problematic characters with safe alternatives or remove them
        # Keep spaces, letters, numbers, hyphens, underscores, and common punctuation
        sanitized = re.sub(r'[<>:"/\\|?*]', '', name)  # Remove Windows forbidden chars
        sanitized = re.sub(r'[^\w\s\-_.,&()]+', '', sanitized)  # Keep only safe chars
        sanitized = re.sub(r'\s+', ' ', sanitized)  # Replace multiple spaces with single
        sanitized = sanitized.strip()  # Remove leading/trailing spaces
        return sanitized
    
    def build_folder_name(self):
        """Build the folder name from input fields with sanitization"""
        date = self.date_var.get().strip()
        location = self.location_var.get().strip()
        activity = self.activity_var.get().strip()
        
        # Sanitize each component
        date_clean = self.sanitize_folder_name(date)
        location_clean = self.sanitize_folder_name(location)
        activity_clean = self.sanitize_folder_name(activity)
        
        return f"{date_clean}_{location_clean}_{activity_clean}"
    
    def get_target_directory(self):
        """Determine the target directory based on checkbox selections"""
        base_dir = self.base_dir_var.get()

        if self.sandbox_var.get():
            return os.path.join(base_dir, "_Sandbox")
        else:
            return base_dir
    
    def update_preview(self):
        """Update the preview of the folder structure to be created"""
        self.preview_text.delete(1.0, tk.END)
        
        # Get values from entry fields
        date = self.date_var.get() or "[Date]"
        location = self.location_var.get() or "[Location]"
        activity = self.activity_var.get() or "[Activity & People]"
        
        # Show original input
        self.preview_text.insert(tk.END, "Input:\n")
        self.preview_text.insert(tk.END, f"Date: {date}\n")
        self.preview_text.insert(tk.END, f"Location: {location}\n")
        self.preview_text.insert(tk.END, f"Activity & People: {activity}\n\n")
        
        # Build folder name and show sanitized version
        folder_name = self.build_folder_name()
        self.preview_text.insert(tk.END, f"Sanitized folder name:\n{folder_name}\n\n")
        
        # Determine target directory
        target_dir = self.get_target_directory()
        full_path = os.path.join(target_dir, folder_name)
        
        # Show full path
        self.preview_text.insert(tk.END, f"Project will be created at:\n{full_path}\n\n")
        
        # Show directory option status
        if self.sandbox_var.get():
            self.preview_text.insert(tk.END, "Directory: Sandbox\n")
        else:
            self.preview_text.insert(tk.END, "Directory: Main Photo folder\n")
        
        # Show structure
        self.preview_text.insert(tk.END, "\nFolder structure to be created:\n\n")
        self.preview_text.insert(tk.END, f"└── {folder_name}/\n")
        self.preview_text.insert(tk.END, f"    └── RAW/\n")
    
    def validate_inputs(self):
        """Validate all required inputs are provided"""
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
        
        # Validate date format
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Error", "Please enter date in YYYY-MM-DD format.")
            return False
            
        return True
    
    def create_structure(self):
        """Create the folder structure based on user input"""
        # Validate inputs
        if not self.validate_inputs():
            return
        
        # Get target directory and folder name
        target_dir = self.get_target_directory()
        folder_name = self.build_folder_name()
        project_path = os.path.join(target_dir, folder_name)
        
        # Check if base directory exists
        if not os.path.exists(self.base_dir_var.get()):
            messagebox.showerror("Error", f"Base directory does not exist: {self.base_dir_var.get()}")
            return
        
        try:
            # Create target directory if it doesn't exist (for _Sandbox)
            os.makedirs(target_dir, exist_ok=True)
            
            # Create project directory
            if os.path.exists(project_path):
                if not messagebox.askyesno("Directory Exists", 
                                         f"Directory already exists:\n{project_path}\n\nDo you want to continue?"):
                    return
            
            os.makedirs(project_path, exist_ok=True)
            
            # Create RAW subdirectory
            raw_path = os.path.join(project_path, "RAW")
            os.makedirs(raw_path, exist_ok=True)
            
            self.status_var.set(f"Created project structure: {folder_name}")

            # Build project data for callback
            project_data = {
                'client_name': 'Personal',  # Photo projects don't have clients
                'project_name': folder_name,
                'project_type': 'Photo',
                'date_created': self.date_var.get(),
                'path': project_path,
                'base_directory': target_dir,
                'status': 'active',
                'notes': '',
                'metadata': {
                    'location': self.location_var.get(),
                    'activity': self.activity_var.get(),
                    'is_sandbox': self.sandbox_var.get()
                }
            }

            # Handle success based on mode
            if self.embedded and self.on_project_created:
                # In embedded mode, call the callback with project data
                self.on_project_created(project_data)
            else:
                # Show success message and offer to open folder
                if messagebox.askyesno("Success",
                                     f"Project structure created successfully!\n\n{project_path}\n\nWould you like to open the folder?"):
                    self.open_folder(project_path)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create structure: {str(e)}")
            self.status_var.set("Error creating project structure")

    def _handle_cancel(self):
        """Handle cancel button click in embedded mode."""
        if self.on_cancel:
            self.on_cancel()

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
                messagebox.showwarning("Warning", f"Folder created but could not open it: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoFolderStructureCreator(root)
    root.mainloop()