import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Common RAW extensions (case-insensitive matching is used)
RAW_EXTENSIONS = {
    ".cr2", ".cr3", ".nef", ".arw", ".raf", ".orf",
    ".rw2", ".dng", ".pef", ".srw", ".raw", ".3fr",
}

JPG_EXTENSIONS = {".jpg", ".jpeg"}


class PhotoRawCleanup:
    def __init__(self, root, initial_dir=None):
        self.root = root
        self.root.title("RAW Cleanup")
        self.root.geometry("800x600")
        self.root.minsize(700, 500)

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # Orphaned RAW files found by scan
        self.orphaned_files = []

        # Header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_propagate(False)

        title_label = tk.Label(header_frame, text="RAW Cleanup",
                               font=("Arial", 16, "bold"), fg="white", bg="#2c3e50")
        title_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Controls frame
        controls_frame = ttk.LabelFrame(main_frame, text="Folder")
        controls_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        controls_frame.columnconfigure(1, weight=1)

        ttk.Label(controls_frame, text="Directory:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        default_dir = initial_dir if initial_dir and os.path.isdir(initial_dir) else "E:/_photo"
        self.dir_var = tk.StringVar(value=default_dir)
        dir_entry = ttk.Entry(controls_frame, textvariable=self.dir_var, width=60)
        dir_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=10)

        browse_btn = ttk.Button(controls_frame, text="Browse...", command=self.browse_folder)
        browse_btn.grid(row=0, column=2, padx=5, pady=10)

        self.recursive_var = tk.BooleanVar(value=True)
        recursive_check = ttk.Checkbutton(controls_frame, text="Include subfolders",
                                          variable=self.recursive_var)
        recursive_check.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10))

        btn_frame = ttk.Frame(controls_frame)
        btn_frame.grid(row=1, column=2, padx=5, pady=(0, 10))

        scan_btn = ttk.Button(btn_frame, text="Scan", command=self.scan_folder, padding=(20, 5))
        scan_btn.pack(side=tk.LEFT)

        # Results frame
        results_frame = ttk.LabelFrame(main_frame, text="Orphaned RAW Files (no matching JPG)")
        results_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        results_frame.rowconfigure(0, weight=1)
        results_frame.columnconfigure(0, weight=1)

        scrollbar = ttk.Scrollbar(results_frame)
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.results_text = tk.Text(results_frame, wrap=tk.WORD,
                                    yscrollcommand=scrollbar.set, state=tk.DISABLED)
        self.results_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scrollbar.config(command=self.results_text.yview)

        # Bottom buttons
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)

        self.delete_btn = ttk.Button(bottom_frame, text="Delete Orphaned RAW Files",
                                     command=self.delete_orphaned, state=tk.DISABLED,
                                     padding=(20, 10))
        self.delete_btn.pack(side=tk.RIGHT)

        # Status bar
        self.status_var = tk.StringVar(value="Ready — choose a folder and click Scan")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1,
                                   relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=2, column=0, sticky="ew")

    def browse_folder(self):
        initial = self.dir_var.get()
        if not os.path.isdir(initial):
            initial = ""
        folder = filedialog.askdirectory(initialdir=initial, title="Select Photo Folder")
        if folder:
            self.dir_var.set(folder)

    def scan_folder(self):
        folder = self.dir_var.get().strip()
        if not os.path.isdir(folder):
            messagebox.showerror("Error", f"Directory does not exist:\n{folder}")
            return

        self.status_var.set("Scanning...")
        self.root.update_idletasks()

        # Collect all files grouped by directory
        jpg_stems_by_dir = {}  # dir -> set of lowercase stems
        raw_files_by_dir = {}  # dir -> list of (full_path, stem_lower)

        if self.recursive_var.get():
            for dirpath, _, filenames in os.walk(folder):
                self._index_dir(dirpath, filenames, jpg_stems_by_dir, raw_files_by_dir)
        else:
            try:
                filenames = os.listdir(folder)
            except OSError:
                filenames = []
            self._index_dir(folder, filenames, jpg_stems_by_dir, raw_files_by_dir)

        # Find orphaned RAW files (no JPG with same stem in the same directory)
        self.orphaned_files = []
        for dirpath, raw_list in raw_files_by_dir.items():
            jpg_stems = jpg_stems_by_dir.get(dirpath, set())
            for full_path, stem_lower in raw_list:
                if stem_lower not in jpg_stems:
                    self.orphaned_files.append(full_path)

        self.orphaned_files.sort()

        # Display results
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)

        if self.orphaned_files:
            total_size = 0
            for f in self.orphaned_files:
                try:
                    total_size += os.path.getsize(f)
                except OSError:
                    pass
                rel = os.path.relpath(f, folder)
                self.results_text.insert(tk.END, f"{rel}\n")

            size_mb = total_size / (1024 * 1024)
            self.status_var.set(
                f"Found {len(self.orphaned_files)} orphaned RAW file(s) "
                f"({size_mb:.1f} MB) that can be deleted"
            )
            self.delete_btn.config(state=tk.NORMAL)
        else:
            self.results_text.insert(tk.END, "No orphaned RAW files found — all RAW files have a matching JPG.")
            self.status_var.set("Scan complete — nothing to clean up")
            self.delete_btn.config(state=tk.DISABLED)

        self.results_text.config(state=tk.DISABLED)

    @staticmethod
    def _index_dir(dirpath, filenames, jpg_stems_by_dir, raw_files_by_dir):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            stem = os.path.splitext(fname)[0].lower()
            if ext in JPG_EXTENSIONS:
                jpg_stems_by_dir.setdefault(dirpath, set()).add(stem)
            elif ext in RAW_EXTENSIONS:
                full = os.path.join(dirpath, fname)
                raw_files_by_dir.setdefault(dirpath, []).append((full, stem))

    def delete_orphaned(self):
        if not self.orphaned_files:
            return

        count = len(self.orphaned_files)
        if not messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to permanently delete {count} RAW file(s)?\n\n"
            "This cannot be undone."
        ):
            return

        deleted = 0
        errors = []
        for f in self.orphaned_files:
            try:
                os.remove(f)
                deleted += 1
            except OSError as e:
                errors.append(f"{f}: {e}")

        self.orphaned_files.clear()
        self.delete_btn.config(state=tk.DISABLED)

        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)

        if errors:
            self.results_text.insert(tk.END, f"Deleted {deleted} file(s). Errors:\n\n")
            for err in errors:
                self.results_text.insert(tk.END, f"{err}\n")
            self.status_var.set(f"Deleted {deleted}, {len(errors)} error(s)")
        else:
            self.results_text.insert(tk.END, f"Successfully deleted {deleted} RAW file(s).")
            self.status_var.set(f"Done — deleted {deleted} file(s)")

        self.results_text.config(state=tk.DISABLED)


if __name__ == "__main__":
    initial_dir = sys.argv[1] if len(sys.argv) > 1 else None
    root = tk.Tk()
    app = PhotoRawCleanup(root, initial_dir=initial_dir)
    root.mainloop()
