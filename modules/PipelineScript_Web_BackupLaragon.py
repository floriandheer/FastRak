#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PipelineScript_BackupLaragon.py
Description: UI wrapper for Laragon Backup functionality
Location: P:\_Script\floriandheer\PipelineScript_BackupLaragon.py
"""

import os
import sys
import time
import datetime
import argparse
import threading
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess

# Setup logging using shared utility
from shared_logging import get_logger, setup_logging as setup_shared_logging

# Get logger reference (configured in main())
logger = get_logger("laragon_backup")

class LaragonBackupUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Laragon Backup Tool")
        self.root.geometry("750x600")
        self.root.minsize(750, 500)
        
        # Configure main window
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        
        # Create header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header_frame.grid_propagate(False)
        
        # Add title to header
        title_label = tk.Label(header_frame, text="Laragon Backup Tool", 
                              font=("Arial", 16, "bold"), fg="white", bg="#2c3e50")
        title_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Create main frame
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Create config panel
        self.create_config_panel(main_frame)
        
        # Create results panel
        self.create_results_panel(main_frame)
        
        # Create status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, 
                                  relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=2, column=0, sticky="ew")
        
        # Initialize variables
        self.backup_running = False
        self.initialize_default_paths()
        
    def initialize_default_paths(self):
        """Set default paths based on user's system"""
        # Default source path for Laragon
        default_source = "C:\\laragon"
        if os.path.exists(default_source):
            self.source_dir_var.set(default_source)
        
        # Default destination path
        default_dest = "I:\\Web\\01_Work\\laragon"
        self.destination_dir_var.set(default_dest)
        
        # Default log file path - use centralized PipelineManager logs folder
        log_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "PipelineManager", "logs")
        os.makedirs(log_dir, exist_ok=True)
        default_log = os.path.join(log_dir, "laragon_backup.log")
        self.log_file_var.set(default_log)
        
    def create_config_panel(self, parent):
        """Create the configuration panel with path settings and options"""
        config_frame = ttk.LabelFrame(parent, text="Backup Configuration")
        config_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        config_frame.columnconfigure(1, weight=1)
        
        # Source directory
        ttk.Label(config_frame, text="Source (Laragon):").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        self.source_dir_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.source_dir_var, width=50).grid(row=0, column=1, sticky="ew", padx=5, pady=10)
        ttk.Button(config_frame, text="Browse", command=self.browse_source_dir).grid(row=0, column=2, padx=5, pady=10)
        
        # Destination directory
        ttk.Label(config_frame, text="Destination Base:").grid(row=1, column=0, sticky="w", padx=10, pady=10)
        self.destination_dir_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.destination_dir_var, width=50).grid(row=1, column=1, sticky="ew", padx=5, pady=10)
        ttk.Button(config_frame, text="Browse", command=self.browse_destination_dir).grid(row=1, column=2, padx=5, pady=10)
        
        # Log file path
        ttk.Label(config_frame, text="Log File:").grid(row=2, column=0, sticky="w", padx=10, pady=10)
        self.log_file_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.log_file_var, width=50).grid(row=2, column=1, sticky="ew", padx=5, pady=10)
        ttk.Button(config_frame, text="Browse", command=self.browse_log_file).grid(row=2, column=2, padx=5, pady=10)
        
        # Options section
        options_frame = ttk.LabelFrame(config_frame, text="Robocopy Options")
        options_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        options_frame.columnconfigure(0, weight=1)
        
        # Robocopy options
        option_frame1 = ttk.Frame(options_frame)
        option_frame1.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        self.mirror_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(option_frame1, text="Mirror directories (/MIR)", variable=self.mirror_var).pack(side=tk.LEFT, padx=10)
        
        ttk.Label(option_frame1, text="Retry count:").pack(side=tk.LEFT, padx=(20, 5))
        self.retry_var = tk.StringVar(value="5")
        ttk.Spinbox(option_frame1, from_=1, to=10, width=5, textvariable=self.retry_var).pack(side=tk.LEFT)
        
        ttk.Label(option_frame1, text="Wait time (sec):").pack(side=tk.LEFT, padx=(20, 5))
        self.wait_var = tk.StringVar(value="5")
        ttk.Spinbox(option_frame1, from_=1, to=30, width=5, textvariable=self.wait_var).pack(side=tk.LEFT)
        
        option_frame2 = ttk.Frame(options_frame)
        option_frame2.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        
        ttk.Label(option_frame2, text="Multi-threading:").pack(side=tk.LEFT, padx=10)
        self.thread_var = tk.StringVar(value="8")
        ttk.Spinbox(option_frame2, from_=1, to=32, width=5, textvariable=self.thread_var).pack(side=tk.LEFT)
        
        self.update_timestamp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(option_frame2, text="Add timestamp to destination folder", 
                      variable=self.update_timestamp_var).pack(side=tk.LEFT, padx=(20, 5))
        
        # Action buttons
        btn_frame = ttk.Frame(config_frame)
        btn_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=10)
        btn_frame.columnconfigure(1, weight=1)
        
        self.check_robocopy_btn = ttk.Button(btn_frame, text="Check Robocopy", command=self.check_robocopy, width=15)
        self.check_robocopy_btn.grid(row=0, column=0, padx=10)
        
        self.backup_btn = ttk.Button(btn_frame, text="Start Backup", command=self.start_backup, width=15)
        self.backup_btn.grid(row=0, column=2, padx=10)
        
    def create_results_panel(self, parent):
        """Create the panel for displaying results and logs"""
        results_frame = ttk.LabelFrame(parent, text="Backup Progress and Results")
        results_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Create notebook for different result tabs
        self.results_notebook = ttk.Notebook(results_frame)
        self.results_notebook.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Analysis tab
        self.analysis_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(self.analysis_frame, text="System Analysis")
        self.analysis_frame.columnconfigure(0, weight=1)
        self.analysis_frame.rowconfigure(0, weight=1)
        
        self.analysis_text = tk.Text(self.analysis_frame, wrap=tk.WORD)
        self.analysis_text.grid(row=0, column=0, sticky="nsew")
        
        analysis_scrollbar = ttk.Scrollbar(self.analysis_frame, command=self.analysis_text.yview)
        analysis_scrollbar.grid(row=0, column=1, sticky="ns")
        self.analysis_text.config(yscrollcommand=analysis_scrollbar.set)
        
        # Backup tab
        self.backup_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(self.backup_frame, text="Backup Progress")
        self.backup_frame.columnconfigure(0, weight=1)
        self.backup_frame.rowconfigure(0, weight=1)
        
        self.backup_text = tk.Text(self.backup_frame, wrap=tk.WORD)
        self.backup_text.grid(row=0, column=0, sticky="nsew")
        
        backup_scrollbar = ttk.Scrollbar(self.backup_frame, command=self.backup_text.yview)
        backup_scrollbar.grid(row=0, column=1, sticky="ns")
        self.backup_text.config(yscrollcommand=backup_scrollbar.set)
    
    def browse_source_dir(self):
        """Browse for source directory"""
        directory = filedialog.askdirectory(title="Select Laragon Source Directory")
        if directory:
            self.source_dir_var.set(directory)
    
    def browse_destination_dir(self):
        """Browse for destination directory"""
        directory = filedialog.askdirectory(title="Select Backup Destination Base Directory")
        if directory:
            self.destination_dir_var.set(directory)
    
    def browse_log_file(self):
        """Browse for log file location"""
        filename = filedialog.asksaveasfilename(
            title="Select Log File Location",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if filename:
            self.log_file_var.set(filename)
    
    def check_robocopy(self):
        """Check if robocopy is available"""
        self.status_var.set("Checking for Robocopy...")
        
        # Clear text field
        self.analysis_text.delete(1.0, tk.END)
        self.analysis_text.insert(tk.END, "Checking for Robocopy...\n\n")
        self.root.update_idletasks()
        
        try:
            result = subprocess.run(["robocopy", "/?"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode < 8:  # Robocopy returns 0-7 for success
                self.analysis_text.insert(tk.END, f"✓ Robocopy is installed and available\n\n")
                
                # Display source directory info
                source_dir = self.source_dir_var.get()
                if os.path.exists(source_dir):
                    size = self.get_directory_size(source_dir)
                    size_text = self.format_size(size)
                    self.analysis_text.insert(tk.END, f"Source Directory: {source_dir}\n")
                    self.analysis_text.insert(tk.END, f"Total Size: {size_text}\n")
                    self.analysis_text.insert(tk.END, f"Last Modified: {datetime.datetime.fromtimestamp(os.path.getmtime(source_dir))}\n\n")
                else:
                    self.analysis_text.insert(tk.END, f"Source Directory: {source_dir} (NOT FOUND)\n\n")
                
                # Display destination directory info
                dest_dir = self.destination_dir_var.get()
                if os.path.exists(dest_dir):
                    self.analysis_text.insert(tk.END, f"Destination Base: {dest_dir}\n")
                    
                    # Find previous backups
                    parent_dir = os.path.dirname(dest_dir)
                    base_name = os.path.basename(dest_dir)
                    
                    if os.path.exists(parent_dir):
                        previous_backups = []
                        for item in os.listdir(parent_dir):
                            if item.startswith(base_name + "_") and os.path.isdir(os.path.join(parent_dir, item)):
                                previous_backups.append(item)
                        
                        if previous_backups:
                            previous_backups.sort(reverse=True)
                            self.analysis_text.insert(tk.END, f"Found {len(previous_backups)} previous backups:\n")
                            for i, backup in enumerate(previous_backups[:5]):  # Show most recent 5
                                backup_path = os.path.join(parent_dir, backup)
                                backup_size = self.get_directory_size(backup_path)
                                backup_size_text = self.format_size(backup_size)
                                self.analysis_text.insert(tk.END, f"  {i+1}. {backup} - {backup_size_text}\n")
                            
                            if len(previous_backups) > 5:
                                self.analysis_text.insert(tk.END, f"  ... and {len(previous_backups) - 5} more\n")
                        else:
                            self.analysis_text.insert(tk.END, "No previous backups found\n")
                else:
                    self.analysis_text.insert(tk.END, f"Destination Base: {dest_dir} (NOT FOUND)\n")
                    self.analysis_text.insert(tk.END, "The destination parent directory will be created if needed\n")
            else:
                self.analysis_text.insert(tk.END, "❌ Error checking Robocopy\n\n")
                self.analysis_text.insert(tk.END, "Output:\n")
                self.analysis_text.insert(tk.END, result.stdout)
                self.analysis_text.insert(tk.END, result.stderr)
            
            self.status_var.set("System check complete")
            
        except FileNotFoundError:
            self.analysis_text.insert(tk.END, "❌ Robocopy is not available on this system.\n\n")
            self.analysis_text.insert(tk.END, "This script requires Robocopy, which is included with Windows.\n")
            self.analysis_text.insert(tk.END, "Please run this script on a Windows system with Robocopy available.\n")
            self.status_var.set("Robocopy not found")
        except Exception as e:
            self.analysis_text.insert(tk.END, f"Error checking for Robocopy: {e}\n")
            self.status_var.set("Error checking for Robocopy")
    
    def get_directory_size(self, path):
        """Get the total size of a directory in bytes (top level only for speed)"""
        try:
            if not os.path.exists(path):
                return 0
                
            # For performance, just show the size of the top-level directories
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(path, topdown=True):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total_size += os.path.getsize(fp)
                
                # Skip subdirectories for speed
                break
                
            return total_size
        except Exception as e:
            self.append_to_text_widget(self.analysis_text, f"Error calculating directory size: {e}\n")
            return 0
    
    def format_size(self, size_bytes):
        """Format size in bytes to human readable format"""
        if size_bytes == 0:
            return "0B"
        
        size_names = ("B", "KB", "MB", "GB", "TB")
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024
            i += 1
        
        return f"{size_bytes:.2f} {size_names[i]}"
    
    def start_backup(self):
        """Start the backup process"""
        source_dir = self.source_dir_var.get()
        destination_base = self.destination_dir_var.get()
        log_file = self.log_file_var.get()
        
        # Validate inputs
        if not source_dir or not os.path.exists(source_dir):
            messagebox.showerror("Error", "Source directory not found!")
            return
        
        if not destination_base:
            messagebox.showerror("Error", "Please specify a destination base path!")
            return
        
        # Create destination parent directory if it doesn't exist
        dest_parent = os.path.dirname(destination_base)
        if not os.path.exists(dest_parent):
            try:
                os.makedirs(dest_parent, exist_ok=True)
                self.append_to_text_widget(self.analysis_text, f"Created destination parent directory: {dest_parent}\n")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create destination parent directory: {e}")
                return
        
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
                self.append_to_text_widget(self.analysis_text, f"Created log directory: {log_dir}\n")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create log directory: {e}")
                return
        
        # Disable buttons during backup
        self.backup_btn.config(state=tk.DISABLED)
        self.check_robocopy_btn.config(state=tk.DISABLED)
        self.backup_running = True
        
        # Clear results
        self.backup_text.delete(1.0, tk.END)
        
        # Start backup in a background thread
        thread = threading.Thread(target=self.backup_process, daemon=True)
        thread.start()
    
    def backup_process(self):
        """Main backup process running in a background thread"""
        try:
            # Get configuration
            source_dir = self.source_dir_var.get()
            destination_base = self.destination_dir_var.get()
            log_file = self.log_file_var.get()
            mirror = self.mirror_var.get()
            retry_count = self.retry_var.get()
            wait_time = self.wait_var.get()
            thread_count = self.thread_var.get()
            add_timestamp = self.update_timestamp_var.get()
            
            start_time = time.time()
            
            # Check if robocopy is available
            self.status_var.set("Verifying Robocopy...")
            self.append_to_text_widget(self.backup_text, "Verifying Robocopy is available...\n")
            self.results_notebook.select(1)  # Switch to Backup tab
            
            try:
                subprocess.run(["robocopy", "/?"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except FileNotFoundError:
                self.append_to_text_widget(self.backup_text, "Error: Robocopy not found. Please run this on Windows.\n")
                self.status_var.set("Error: Robocopy not found")
                messagebox.showerror("Error", "Robocopy is not available on this system!")
                self.root.after(0, self.enable_buttons)
                return
            
            # Set up destination with timestamp if enabled
            if add_timestamp:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                destination = f"{destination_base}_{timestamp}"
            else:
                destination = destination_base
            
            # Begin backup
            self.status_var.set("Backing up Laragon...")
            self.append_to_text_widget(self.backup_text, f"Starting backup of {source_dir} to {destination}...\n")
            self.append_to_text_widget(self.backup_text, f"Log file: {log_file}\n\n")
            
            # Build robocopy command
            robocopy_cmd = ["robocopy", source_dir, destination]
            
            if mirror:
                robocopy_cmd.append("/MIR")
            
            robocopy_cmd.extend([f"/R:{retry_count}", f"/W:{wait_time}", f"/MT:{thread_count}"])
            
            # Log the command
            self.append_to_text_widget(self.backup_text, "Running command:\n" + " ".join(robocopy_cmd) + "\n\n")
            
            # Start robocopy process
            process = subprocess.Popen(
                robocopy_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Track output and update the UI
            output_buffer = []
            for line in iter(process.stdout.readline, ''):
                self.append_to_text_widget(self.backup_text, line)
                output_buffer.append(line)
                # Write periodically to the log file to avoid memory issues with large outputs
                if len(output_buffer) >= 100:
                    self.write_to_log(log_file, output_buffer)
                    output_buffer = []
            
            # Write any remaining output
            if output_buffer:
                self.write_to_log(log_file, output_buffer)
            
            # Get final exit code
            exit_code = process.wait()
            
            # Interpret exit code (Robocopy exit codes are special)
            success = exit_code < 8  # Codes 0-7 indicate success with warnings
            status_message = self.interpret_robocopy_exit_code(exit_code)
            
            # Complete the process
            total_time = time.time() - start_time
            self.append_to_text_widget(self.backup_text, f"\n{status_message}\n")
            self.append_to_text_widget(self.backup_text, f"Backup completed in {total_time:.2f} seconds\n")
            
            if success:
                self.status_var.set("Backup complete!")
                self.root.after(0, lambda: messagebox.showinfo("Backup Complete", 
                    f"Laragon backup completed in {total_time:.2f} seconds."))
            else:
                self.status_var.set("Backup failed!")
                self.root.after(0, lambda: messagebox.showerror("Backup Failed", 
                    f"Laragon backup failed with code {exit_code}: {status_message}"))
            
        except Exception as e:
            error_msg = f"Error during backup process: {str(e)}"
            logger.error(error_msg)
            self.append_to_text_widget(self.backup_text, f"\n{error_msg}\n")
            self.status_var.set("Error during backup")
            
            # Show error message
            self.root.after(0, lambda: messagebox.showerror("Backup Error", error_msg))
        
        finally:
            # Re-enable buttons
            self.root.after(0, self.enable_buttons)
            self.backup_running = False
    
    def write_to_log(self, log_file, lines):
        """Write output lines to the log file"""
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                for line in lines:
                    f.write(line)
        except Exception as e:
            self.append_to_text_widget(self.backup_text, f"Error writing to log file: {e}\n")
    
    def interpret_robocopy_exit_code(self, code):
        """Interpret Robocopy exit codes"""
        if code == 0:
            return "Success: No files were copied."
        elif code == 1:
            return "Success: Files were copied successfully."
        elif code == 2:
            return "Success: Extra files/dirs were detected but not copied."
        elif code == 3:
            return "Success: Some files were copied, extra files were detected."
        elif code == 4:
            return "Warning: Some mismatched files/dirs were detected."
        elif code == 5:
            return "Warning: Some files were copied, some mismatch."
        elif code == 6:
            return "Warning: Extra files + mismatched files, no copies."
        elif code == 7:
            return "Warning: Files were copied, extras, and mismatches."
        elif code == 8:
            return "Error: Some files or directories could not be copied."
        elif code == 16:
            return "Fatal Error: Robocopy usage error or resource error."
        else:
            return f"Error: Unknown error code {code}."
    
    def enable_buttons(self):
        """Re-enable buttons after backup process completes"""
        self.backup_btn.config(state=tk.NORMAL)
        self.check_robocopy_btn.config(state=tk.NORMAL)
    
    def append_to_text_widget(self, text_widget, message):
        """Thread-safe way to append text to a text widget"""
        def update_text():
            text_widget.insert(tk.END, message)
            text_widget.see(tk.END)
            text_widget.update_idletasks()
        
        self.root.after(0, update_text)

def main():
    # Setup logging when the app actually runs (not at import time)
    setup_shared_logging("laragon_backup")

    # Check if we should run in command-line mode
    if len(sys.argv) > 1:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Laragon Backup Tool")
        parser.add_argument("--source", default="C:\\laragon", help="Source Laragon folder path")
        parser.add_argument("--destination", default="I:\\Web\\01_Work\\laragon", help="Base destination path")
        parser.add_argument("--log", default="P:\\_Scripts\\_LOGS\\backup_log.txt", help="Log file path")
        parser.add_argument("--no-timestamp", action="store_true", help="Don't add timestamp to destination folder")
        parser.add_argument("--retry", type=int, default=5, help="Retry count for robocopy")
        parser.add_argument("--wait", type=int, default=5, help="Wait time between retries (seconds)")
        parser.add_argument("--threads", type=int, default=8, help="Number of threads for robocopy")
        parser.add_argument("--auto-run", action="store_true", help="Run without confirmation")
        
        args = parser.parse_args()
        
        # Check if source exists
        if not os.path.exists(args.source):
            print(f"Error: Source directory not found at {args.source}")
            return 1
        
        # Create destination parent directory if it doesn't exist
        destination_parent = os.path.dirname(args.destination)
        if not os.path.exists(destination_parent):
            try:
                os.makedirs(destination_parent, exist_ok=True)
                print(f"Created destination parent directory: {destination_parent}")
            except Exception as e:
                print(f"Error creating destination parent directory: {e}")
                return 1
        
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(args.log)
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
                print(f"Created log directory: {log_dir}")
            except Exception as e:
                print(f"Error creating log directory: {e}")
                return 1
        
        # Set up destination with timestamp if enabled
        if not args.no_timestamp:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            destination = f"{args.destination}_{timestamp}"
        else:
            destination = args.destination
        
        # Get confirmation if not auto-run
        if not args.auto_run:
            print(f"This will back up {args.source} to {destination}")
            response = input("Do you want to continue? (y/n): ").strip().lower()
            if response != 'y':
                print("Backup cancelled by user")
                return 0
        
        # Build robocopy command
        robocopy_cmd = ["robocopy", args.source, destination, "/MIR",
                     f"/R:{args.retry}", f"/W:{args.wait}", f"/MT:{args.threads}"]
        
        print(f"Running: {' '.join(robocopy_cmd)}")
        
        # Run robocopy
        try:
            # Start robocopy and redirect output to log file
            with open(args.log, 'a', encoding='utf-8') as log:
                log.write(f"\n\n===== LARAGON BACKUP STARTED: {datetime.datetime.now()} =====\n")
                start_time = time.time()
                
                process = subprocess.Popen(
                    robocopy_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                # Write output to log and console
                for line in iter(process.stdout.readline, ''):
                    log.write(line)
                    print(line, end='')
                
                # Get exit code
                exit_code = process.wait()
                total_time = time.time() - start_time
                
                # Log completion
                log.write(f"\n===== LARAGON BACKUP COMPLETED: {datetime.datetime.now()} =====\n")
                log.write(f"Exit code: {exit_code}\n")
                log.write(f"Total time: {total_time:.2f} seconds\n")
                
                # Interpret exit code
                status_message = LaragonBackupUI.interpret_robocopy_exit_code(None, exit_code)
                log.write(f"Status: {status_message}\n")
                
                print(f"\nBackup completed in {total_time:.2f} seconds")
                print(f"Status: {status_message}")
                
                return 0 if exit_code < 8 else 1
                
        except FileNotFoundError:
            print("Error: Robocopy not found. Please run this on Windows.")
            return 1
        except Exception as e:
            print(f"Error during backup: {str(e)}")
            return 1
                
    else:
        # Run in GUI mode
        root = tk.Tk()
        app = LaragonBackupUI(root)
        root.mainloop()
        return 0

if __name__ == "__main__":
    sys.exit(main())