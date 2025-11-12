import os
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
import re

class PhotoCollectionCreator:
    def __init__(self, root):
        self.root = root
        self.root.title("New Photo Collection")
        self.root.geometry("750x600")
        self.root.minsize(700, 500)

        # Configure main window
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # Create header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header_frame.grid_propagate(False)

        # Add title to header
        title_label = tk.Label(header_frame, text="New Photo Collection",
                              font=("Arial", 16, "bold"), fg="white", bg="#2c3e50")
        title_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Create main frame
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=1)

        # Create form panel (left side)
        form_frame = ttk.LabelFrame(main_frame, text="Collection Settings")
        form_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        form_frame.columnconfigure(1, weight=1)

        # Base directory (fixed to E:/_photo)
        ttk.Label(form_frame, text="Base Directory:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        self.base_dir_var = tk.StringVar(value='E:/_photo')
        base_dir_entry = ttk.Entry(form_frame, textvariable=self.base_dir_var, width=40, state='readonly')
        base_dir_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=5, pady=10)

        # Collection date
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

        # Create button
        create_btn = ttk.Button(form_frame, text="Create Collection Folder",
                               command=self.create_structure, padding=(20, 10))
        create_btn.grid(row=4, column=0, columnspan=3, pady=20)

        # Create preview panel (right side)
        preview_frame = ttk.LabelFrame(main_frame, text="Folder Preview")
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
        self.date_var.trace_add("write", lambda *args: self.update_preview())
        self.location_var.trace_add("write", lambda *args: self.update_preview())
        self.activity_var.trace_add("write", lambda *args: self.update_preview())

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

        # Show full path
        base_dir = self.base_dir_var.get()
        full_path = os.path.join(base_dir, folder_name)

        # Show full path
        self.preview_text.insert(tk.END, f"Collection will be created at:\n{full_path}\n\n")

        # Show structure
        self.preview_text.insert(tk.END, "Folder structure to be created:\n\n")
        self.preview_text.insert(tk.END, f"└── {folder_name}/\n")

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

        # Get folder name
        folder_name = self.build_folder_name()
        base_dir = self.base_dir_var.get()
        collection_path = os.path.join(base_dir, folder_name)

        # Check if base directory exists
        if not os.path.exists(base_dir):
            messagebox.showerror("Error", f"Base directory does not exist: {base_dir}")
            return

        try:
            # Create collection directory
            if os.path.exists(collection_path):
                if not messagebox.askyesno("Directory Exists",
                                         f"Directory already exists:\n{collection_path}\n\nDo you want to continue?"):
                    return

            os.makedirs(collection_path, exist_ok=True)

            self.status_var.set(f"Created collection: {folder_name}")

            # Show success message and offer to open folder
            if messagebox.askyesno("Success",
                                 f"Collection created successfully!\n\n{collection_path}\n\nWould you like to open the folder?"):
                self.open_folder(collection_path)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create collection: {str(e)}")
            self.status_var.set("Error creating collection")

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
    app = PhotoCollectionCreator(root)
    root.mainloop()
