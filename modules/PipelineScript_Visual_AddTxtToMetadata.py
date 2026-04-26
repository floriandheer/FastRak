import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image as PilImage
import pyexiv2
import threading
import queue

class ImageMetadataApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Metadata Tool")
        self.root.geometry("750x650")
        self.root.minsize(700, 550)
        
        # Queue for thread communication
        self.queue = queue.Queue()
        
        # Configure main window
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        
        # Create header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header_frame.grid_propagate(False)
        
        # Add title to header
        title_label = tk.Label(header_frame, text="Image Metadata Tool", 
                              font=("Arial", 16, "bold"), fg="white", bg="#2c3e50")
        title_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Create main frame
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)  # Give more weight to preview/log
        main_frame.rowconfigure(0, weight=1)
        
        # Create settings panel (left side)
        form_frame = ttk.LabelFrame(main_frame, text="Settings")
        form_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Image directory
        ttk.Label(form_frame, text="Image Directory:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        self.image_dir_var = tk.StringVar()
        image_dir_entry = ttk.Entry(form_frame, textvariable=self.image_dir_var, width=40)
        image_dir_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=10)
        ttk.Button(form_frame, text="Browse", command=self.browse_image_dir).grid(row=0, column=2, padx=5, pady=10)
        
        # Destination directory
        ttk.Label(form_frame, text="Destination Directory:").grid(row=1, column=0, sticky="w", padx=10, pady=10)
        self.dest_dir_var = tk.StringVar()
        dest_dir_entry = ttk.Entry(form_frame, textvariable=self.dest_dir_var, width=40)
        dest_dir_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=10)
        ttk.Button(form_frame, text="Browse", command=self.browse_dest_dir).grid(row=1, column=2, padx=5, pady=10)
        
        # Same as source directory option
        self.same_dir_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="Same as Source Directory", 
                      variable=self.same_dir_var, command=self.toggle_dest_dir).grid(row=2, column=0, columnspan=3, sticky="w", padx=10, pady=(0, 10))
        
        # Options frame
        options_frame = ttk.LabelFrame(form_frame, text="Options")
        options_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=10)
        
        # Process subdirectories option
        self.process_subdirs_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Process Subdirectories", 
                      variable=self.process_subdirs_var).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        # Delete text files option
        self.delete_txt_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Delete Text Files After Processing", 
                      variable=self.delete_txt_var).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        
        # Convert non-JPEG images option
        self.convert_images_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Convert Non-JPEG Images to JPG", 
                      variable=self.convert_images_var).grid(row=2, column=0, sticky="w", padx=10, pady=5)
        
        # Delete original images after conversion option
        self.delete_originals_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Delete Original Images After Conversion", 
                      variable=self.delete_originals_var).grid(row=3, column=0, sticky="w", padx=10, pady=5)
        
        # Create Process button
        process_btn = ttk.Button(form_frame, text="Process Images", 
                               command=self.start_processing, padding=(20, 10))
        process_btn.grid(row=4, column=0, columnspan=3, pady=20)
        
        # Create log panel (right side)
        log_frame = ttk.LabelFrame(main_frame, text="Processing Log")
        log_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        
        # Log text widget with scrollbar
        self.log_scrollbar = ttk.Scrollbar(log_frame)
        self.log_scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, 
                               yscrollcommand=self.log_scrollbar.set,
                               background="#f8f8f8")
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.log_scrollbar.config(command=self.log_text.yview)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, 
                                  relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=2, column=0, sticky="ew")
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(self.root, orient="horizontal", 
                                         length=100, mode="determinate")
        self.progress_bar.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        
        # Set up periodic checks for the queue
        self.root.after(100, self.check_queue)
    
    def browse_image_dir(self):
        """Open dialog to browse for image directory"""
        directory = filedialog.askdirectory()
        if directory:
            self.image_dir_var.set(directory)
            # If "Same as Source Directory" is checked, update destination directory too
            if self.same_dir_var.get():
                self.dest_dir_var.set(directory)
    
    def browse_dest_dir(self):
        """Open dialog to browse for destination directory"""
        directory = filedialog.askdirectory()
        if directory:
            self.dest_dir_var.set(directory)
    
    def toggle_dest_dir(self):
        """Toggle destination directory based on checkbox"""
        if self.same_dir_var.get():
            # Use source directory as destination
            self.dest_dir_var.set(self.image_dir_var.get())
            # Disable destination directory entry
            for widget in self.root.winfo_children():
                if isinstance(widget, ttk.Entry) and widget.cget("textvariable") == str(self.dest_dir_var):
                    widget.configure(state="disabled")
        else:
            # Enable destination directory entry
            for widget in self.root.winfo_children():
                if isinstance(widget, ttk.Entry) and widget.cget("textvariable") == str(self.dest_dir_var):
                    widget.configure(state="normal")
    
    def log_message(self, message):
        """Add a message to the log"""
        self.queue.put(("log", message))
    
    def update_status(self, message):
        """Update the status bar message"""
        self.queue.put(("status", message))
    
    def update_progress(self, value):
        """Update the progress bar value"""
        self.queue.put(("progress", value))
    
    def check_queue(self):
        """Check the queue for messages from the worker thread"""
        try:
            while True:
                message_type, message = self.queue.get_nowait()
                
                if message_type == "log":
                    self.log_text.insert(tk.END, message + "\n")
                    self.log_text.see(tk.END)  # Scroll to the end
                elif message_type == "status":
                    self.status_var.set(message)
                elif message_type == "progress":
                    self.progress_bar["value"] = message
                elif message_type == "done":
                    messagebox.showinfo("Complete", message)
                    self.progress_bar["value"] = 0
                    self.status_var.set("Ready")
                
                self.queue.task_done()
        except queue.Empty:
            # No more messages, schedule another check
            self.root.after(100, self.check_queue)
    
    def start_processing(self):
        """Start processing images in a separate thread"""
        # Get the image directory
        image_directory = self.image_dir_var.get()
        
        if not image_directory or not os.path.isdir(image_directory):
            messagebox.showerror("Error", "Please select a valid image directory.")
            return
        
        # Get destination directory
        if self.same_dir_var.get():
            dest_directory = image_directory
        else:
            dest_directory = self.dest_dir_var.get()
            if not dest_directory:
                messagebox.showerror("Error", "Please select a destination directory.")
                return
            
            # Create destination directory if it doesn't exist
            if not os.path.exists(dest_directory):
                try:
                    os.makedirs(dest_directory)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create destination directory: {e}")
                    return
        
        # Clear the log
        self.log_text.delete(1.0, tk.END)
        
        # Get options
        process_subdirs = self.process_subdirs_var.get()
        delete_txt = self.delete_txt_var.get()
        convert_images = self.convert_images_var.get()
        delete_originals = self.delete_originals_var.get()
        
        # Start processing in a separate thread
        self.processing_thread = threading.Thread(
            target=self.process_images,
            args=(image_directory, dest_directory, process_subdirs, delete_txt, convert_images, delete_originals)
        )
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
        self.update_status("Processing images...")
    
    def process_images(self, image_folder, dest_folder, process_subdirs, delete_txt, convert_images, delete_originals):
        """Process images and add metadata from text files"""
        try:
            # Define supported image formats
            jpeg_formats = ['.jpg', '.jpeg']
            convertible_formats = ['.png', '.webp', '.bmp', '.tiff', '.tif', '.gif']
            supported_formats = jpeg_formats + (convertible_formats if convert_images else [])
            
            # Get all image files
            all_files = []
            total_processed = 0
            
            if process_subdirs:
                for root, dirs, files in os.walk(image_folder):
                    for file in files:
                        file_lower = file.lower()
                        if any(file_lower.endswith(ext) for ext in supported_formats):
                            all_files.append(os.path.join(root, file))
            else:
                for file in os.listdir(image_folder):
                    file_lower = file.lower()
                    if any(file_lower.endswith(ext) for ext in supported_formats):
                        all_files.append(os.path.join(image_folder, file))
            
            if not all_files:
                self.log_message("No supported image files found in the selected directory.")
                self.update_status("No images found")
                self.queue.put(("done", "No images found"))
                return
            
            self.log_message(f"Found {len(all_files)} image files")
            
            # Process each image
            for i, image_path in enumerate(all_files):
                try:
                    # Update progress
                    progress = int((i / len(all_files)) * 100)
                    self.update_progress(progress)
                    
                    self.log_message(f"Processing {image_path}")
                    
                    # Get file extension and name
                    file_ext = os.path.splitext(image_path)[1].lower()
                    file_name = os.path.basename(image_path)
                    base_name = os.path.splitext(file_name)[0]
                    
                    # Create relative path structure if needed
                    if image_folder != dest_folder and process_subdirs:
                        # Get the relative path from source folder
                        rel_path = os.path.dirname(os.path.relpath(image_path, image_folder))
                        target_dir = os.path.join(dest_folder, rel_path)
                        
                        # Create the directory structure in destination
                        if not os.path.exists(target_dir):
                            os.makedirs(target_dir)
                    else:
                        target_dir = dest_folder
                    
                    # Determine if this is a JPEG or needs conversion
                    needs_conversion = file_ext not in jpeg_formats and convert_images
                    
                    # Prepare target path
                    if needs_conversion:
                        target_path = os.path.join(target_dir, base_name + '.jpg')
                    else:
                        target_path = os.path.join(target_dir, file_name)
                    
                    # Copy or convert the image
                    if image_folder == dest_folder and not needs_conversion:
                        # No need to copy, use the original path
                        metadata_target = image_path
                    else:
                        if needs_conversion:
                            try:
                                self.log_message(f"Converting {file_ext} to JPEG: {image_path}")
                                
                                # Open and convert image to JPEG
                                image = PilImage.open(image_path)
                                rgb_image = image.convert('RGB')
                                rgb_image.save(target_path, 'JPEG')
                                
                                # Use the new JPEG path for metadata
                                metadata_target = target_path
                            except Exception as e:
                                self.log_message(f"Error converting image: {str(e)}")
                                # Skip to next file if conversion failed
                                continue
                        else:
                            # Copy the JPEG file to destination
                            import shutil
                            shutil.copy2(image_path, target_path)
                            metadata_target = target_path
                    
                    # Check for corresponding text file
                    text_file_path = os.path.splitext(image_path)[0] + '.txt'
                    
                    # Get caption from text file if it exists
                    caption_text = ""
                    if os.path.exists(text_file_path):
                        with open(text_file_path, 'r', encoding='utf-8') as file:
                            caption_text = file.read().strip()
                        self.log_message(f"Found text file: {text_file_path}")
                        
                        # Add metadata to the image if text file exists and has content
                        if caption_text:
                            self.add_metadata_to_image(metadata_target, caption_text)
                            total_processed += 1
                        
                        # Delete the text file if requested
                        if delete_txt:
                            os.remove(text_file_path)
                            self.log_message(f"Deleted text file: {text_file_path}")
                    
                    # Delete original if requested and we're not already in the same directory
                    if delete_originals and needs_conversion and os.path.exists(image_path):
                        os.remove(image_path)
                        self.log_message(f"Deleted original image: {image_path}")
                
                except Exception as e:
                    self.log_message(f"Error processing {image_path}: {str(e)}")
            
            # Final update
            self.update_progress(100)
            message = f"Completed! Processed {total_processed} images."
            self.log_message(message)
            self.queue.put(("done", message))
            
        except Exception as e:
            error_message = f"Error during processing: {str(e)}"
            self.log_message(error_message)
            self.queue.put(("done", error_message))
    
    def add_metadata_to_image(self, image_path, metadata_text):
        """Add metadata to an image file using pyexiv2"""
        try:
            # Open the image with pyexiv2
            image = pyexiv2.Image(image_path)
            
            # Create metadata dictionary
            metadata = {}
            
            # Add caption to metadata fields
            if metadata_text:
                metadata['Exif.Image.ImageDescription'] = metadata_text
                metadata['Exif.Photo.UserComment'] = metadata_text
            
            # Write metadata to the image
            image.modify_exif(metadata)
            
            # Close the image
            image.close()
            
            self.log_message(f"Added metadata to: {image_path}")
            return True
            
        except Exception as e:
            self.log_message(f"Error adding metadata to {image_path}: {str(e)}")
            return False

# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = ImageMetadataApp(root)
    # Pre-seed source/dest from a project folder passed by the launcher.
    # The user can still browse to a different folder afterwards.
    if len(sys.argv) > 1 and sys.argv[1] and os.path.isdir(sys.argv[1]):
        app.image_dir_var.set(sys.argv[1])
        app.dest_dir_var.set(sys.argv[1])
    root.mainloop()