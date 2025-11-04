"""
Main GUI application for Screen Machine.
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import customtkinter as ctk
import time

from config import ProcessingConfig, get_default_output_dir, ensure_output_dir
from video_processor import find_video_files, extract_screenshots, get_video_metadata
from image_composer import create_grid, save_grid_image
from utils import calculate_output_path
from PIL import Image, ImageTk


# Configure customtkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ScreenMachineApp(ctk.CTk):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        self.title("Screen Machine")
        self.geometry("900x820+0+0")  # Position at top-left corner
        self.resizable(True, True)
        
        # Processing state
        self.is_processing = False
        self.processing_thread: Optional[threading.Thread] = None
        self.current_config: Optional[ProcessingConfig] = None
        self.processing_start_time: Optional[float] = None
        
        # Variables
        self.input_dir = tk.StringVar(value="")
        self.output_dir = tk.StringVar(value="")
        self.suffix_var = tk.StringVar(value="")
        
        # Performance defaults
        self.workers_var = tk.StringVar(value="2")
        
        # Preview state
        self.current_preview_image = None
        self.preview_photo = None
        
        # Canvas references for initialization
        self.left_canvas = None
        self.left_window = None
        self.right_canvas = None
        self.right_window = None
        
        self.setup_ui()
        # Set window icon after UI is initialized (needs to be done after window is created)
        self.after(100, self._set_window_icon)
        # Initialize canvas sizes after window is displayed
        self.after(100, self.initialize_canvas_sizes)
        
    def setup_ui(self):
        """Create and layout UI components in a 2-column layout."""
        # Main container with padding
        main_frame = ctk.CTkFrame(self, fg_color="#252525")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Create 2-column container
        columns_frame = ctk.CTkFrame(main_frame, fg_color="#252525")
        columns_frame.pack(fill="both", expand=True, pady=(0, 15), padx=5)
        
        # Left column (scrollable with conditional scrollbar)
        left_column_container = ctk.CTkFrame(columns_frame, fg_color="#252525")
        left_column_container.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        left_canvas = tk.Canvas(left_column_container, highlightthickness=0, bg="#242424")
        left_scrollbar = ctk.CTkScrollbar(left_column_container, orientation="vertical", command=left_canvas.yview)
        left_scrollable_frame = ctk.CTkFrame(left_canvas)
        
        left_window = left_canvas.create_window((0, 0), window=left_scrollable_frame, anchor="nw")
        
        # Store references for initialization
        self.left_canvas = left_canvas
        self.left_window = left_window
        
        def update_left_scrollbar():
            """Update scrollbar visibility based on content overflow."""
            left_canvas.update_idletasks()
            scrollregion = left_canvas.bbox("all")
            if scrollregion:
                left_canvas.configure(scrollregion=scrollregion)
                canvas_height = left_canvas.winfo_height()
                frame_height = left_scrollable_frame.winfo_reqheight()
                if frame_height > canvas_height:
                    left_scrollbar.pack(side="right", fill="y")
                else:
                    left_scrollbar.pack_forget()
        
        def on_left_frame_configure(event):
            """Called when scrollable frame size changes."""
            canvas_width = event.width
            left_canvas.itemconfig(left_window, width=canvas_width)
            update_left_scrollbar()
        
        def on_left_canvas_configure(event):
            """Called when canvas size changes."""
            canvas_width = event.width
            left_canvas.itemconfig(left_window, width=canvas_width)
            update_left_scrollbar()
        
        def on_mousewheel_left(event):
            """Handle mouse wheel scrolling."""
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        def on_enter_left(event):
            """Bind mouse wheel when entering left canvas area."""
            left_canvas.bind_all("<MouseWheel>", on_mousewheel_left)
        
        def on_leave_left(event):
            """Unbind mouse wheel when leaving left canvas area."""
            left_canvas.unbind_all("<MouseWheel>")
        
        left_scrollable_frame.bind("<Configure>", on_left_frame_configure)
        left_canvas.bind("<Configure>", on_left_canvas_configure)
        left_canvas.bind("<Enter>", on_enter_left)
        left_canvas.bind("<Leave>", on_leave_left)
        left_scrollable_frame.bind("<Enter>", on_enter_left)
        left_scrollable_frame.bind("<Leave>", on_leave_left)
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        
        # Start with scrollbar hidden
        left_scrollbar.pack_forget()
        
        left_column = left_scrollable_frame  # Alias for easier reference
        left_canvas.pack(side="left", fill="both", expand=True)
        
        # Right column (scrollable with conditional scrollbar)
        right_column_container = ctk.CTkFrame(columns_frame, fg_color="#252525")
        right_column_container.pack(side="right", fill="both", expand=True, padx=(10, 0))
        
        right_canvas = tk.Canvas(right_column_container, highlightthickness=0, bg="#242424")
        right_scrollbar = ctk.CTkScrollbar(right_column_container, orientation="vertical", command=right_canvas.yview)
        right_scrollable_frame = ctk.CTkFrame(right_canvas)
        
        right_window = right_canvas.create_window((0, 0), window=right_scrollable_frame, anchor="nw")
        
        # Store references for initialization
        self.right_canvas = right_canvas
        self.right_window = right_window
        
        def update_right_scrollbar():
            """Update scrollbar visibility based on content overflow."""
            right_canvas.update_idletasks()
            scrollregion = right_canvas.bbox("all")
            if scrollregion:
                right_canvas.configure(scrollregion=scrollregion)
                canvas_height = right_canvas.winfo_height()
                frame_height = right_scrollable_frame.winfo_reqheight()
                if frame_height > canvas_height:
                    right_scrollbar.pack(side="right", fill="y")
                else:
                    right_scrollbar.pack_forget()
        
        def on_right_frame_configure(event):
            """Called when scrollable frame size changes."""
            canvas_width = event.width
            right_canvas.itemconfig(right_window, width=canvas_width)
            update_right_scrollbar()
        
        def on_right_canvas_configure(event):
            """Called when canvas size changes."""
            canvas_width = event.width
            right_canvas.itemconfig(right_window, width=canvas_width)
            update_right_scrollbar()
        
        def on_mousewheel_right(event):
            """Handle mouse wheel scrolling."""
            right_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        def on_enter_right(event):
            """Bind mouse wheel when entering right canvas area."""
            right_canvas.bind_all("<MouseWheel>", on_mousewheel_right)
        
        def on_leave_right(event):
            """Unbind mouse wheel when leaving right canvas area."""
            right_canvas.unbind_all("<MouseWheel>")
        
        right_scrollable_frame.bind("<Configure>", on_right_frame_configure)
        right_canvas.bind("<Configure>", on_right_canvas_configure)
        right_canvas.bind("<Enter>", on_enter_right)
        right_canvas.bind("<Leave>", on_leave_right)
        right_scrollable_frame.bind("<Enter>", on_enter_right)
        right_scrollable_frame.bind("<Leave>", on_leave_right)
        right_canvas.configure(yscrollcommand=right_scrollbar.set)
        
        # Start with scrollbar hidden
        right_scrollbar.pack_forget()
        
        right_column = right_scrollable_frame  # Alias for easier reference
        right_canvas.pack(side="left", fill="both", expand=True)
        
        # LEFT COLUMN CONTENT
        # Directory selection section (LEFT COLUMN)
        dir_frame = ctk.CTkFrame(left_column)
        dir_frame.pack(fill="x", padx=10, pady=(10, 13))
        
        ctk.CTkLabel(dir_frame, text="Input Directory:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))
        input_frame = ctk.CTkFrame(dir_frame)
        input_frame.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkEntry(input_frame, textvariable=self.input_dir, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.input_browse_button = ctk.CTkButton(input_frame, text="Browse", command=self.browse_input_dir, width=100)
        self.input_browse_button.pack(side="right")
        
        ctk.CTkLabel(dir_frame, text="Output Directory:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(5, 5))
        output_frame = ctk.CTkFrame(dir_frame)
        output_frame.pack(fill="x", padx=10, pady=(0, 5))
        ctk.CTkEntry(output_frame, textvariable=self.output_dir, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.output_browse_button = ctk.CTkButton(output_frame, text="Browse", command=self.browse_output_dir, width=100)
        self.output_browse_button.pack(side="right")
        
        # Filename suffix input
        ctk.CTkLabel(dir_frame, text="Filename Suffix:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(5, 5))
        suffix_frame = ctk.CTkFrame(dir_frame)
        suffix_frame.pack(fill="x", padx=10, pady=(0, 5))
        self.suffix_entry = ctk.CTkEntry(suffix_frame, textvariable=self.suffix_var, placeholder_text="e.g., _thumb")
        self.suffix_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        # Follow directory structure checkbox
        self.follow_structure_var = tk.BooleanVar(value=True)
        self.follow_structure_checkbox = ctk.CTkCheckBox(dir_frame, text="Follow directory structure", variable=self.follow_structure_var)
        self.follow_structure_checkbox.pack(anchor="w", padx=10, pady=(0, 5))
        
        # Overwrite existing images checkbox
        self.overwrite_var = tk.BooleanVar(value=False)
        self.overwrite_checkbox = ctk.CTkCheckBox(dir_frame, text="Overwrite existing images", variable=self.overwrite_var)
        self.overwrite_checkbox.pack(anchor="w", padx=10, pady=(0, 10))
        
        # Workers setting
        workers_frame = ctk.CTkFrame(left_column)
        workers_frame.pack(fill="x", padx=10, pady=(10, 6))
        
        ctk.CTkLabel(workers_frame, text="Number of Workers", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(8, 5))
        
        workers_inner = ctk.CTkFrame(workers_frame)
        workers_inner.pack(pady=(0, 8), padx=2)
        
        ctk.CTkLabel(workers_inner, text="Workers:").grid(row=0, column=0, padx=8, pady=3, sticky="w")
        self.workers_entry = ctk.CTkEntry(workers_inner, textvariable=self.workers_var, width=80)
        self.workers_entry.grid(row=0, column=1, padx=8, pady=3)
        ctk.CTkLabel(workers_inner, text="(2-6 for HDD, 6+ for NAS)", font=ctk.CTkFont(size=10)).grid(row=0, column=2, padx=8, pady=3, sticky="w")
        
        # Grid settings section (moved back to left column)
        grid_frame = ctk.CTkFrame(left_column)
        grid_frame.pack(fill="x", padx=10, pady=(10, 6))
        
        ctk.CTkLabel(grid_frame, text="Grid Layout", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(8, 5))
        
        grid_inner = ctk.CTkFrame(grid_frame)
        grid_inner.pack(pady=(0, 8), padx=2)
        
        ctk.CTkLabel(grid_inner, text="Rows:").grid(row=0, column=0, padx=8, pady=3, sticky="w")
        self.rows_var = tk.StringVar(value="5")
        self.rows_entry = ctk.CTkEntry(grid_inner, textvariable=self.rows_var, width=70)
        self.rows_entry.grid(row=0, column=1, padx=8, pady=3)
        
        ctk.CTkLabel(grid_inner, text="Columns:").grid(row=0, column=2, padx=8, pady=3, sticky="w")
        self.columns_var = tk.StringVar(value="6")
        self.columns_entry = ctk.CTkEntry(grid_inner, textvariable=self.columns_var, width=70)
        self.columns_entry.grid(row=0, column=3, padx=8, pady=3)
        
        # Screenshot size settings (moved back to left column)
        size_frame = ctk.CTkFrame(left_column)
        size_frame.pack(fill="x", padx=10, pady=(10, 6))
        
        ctk.CTkLabel(size_frame, text="Screenshot Size", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(8, 5))
        
        size_inner = ctk.CTkFrame(size_frame)
        size_inner.pack(pady=(0, 8), padx=2)
        
        ctk.CTkLabel(size_inner, text="Max Width:").grid(row=0, column=0, padx=8, pady=3, sticky="w")
        self.max_width_var = tk.StringVar(value="320")
        self.width_entry = ctk.CTkEntry(size_inner, textvariable=self.max_width_var, width=80)
        self.width_entry.grid(row=0, column=1, padx=8, pady=3)
        
        ctk.CTkLabel(size_inner, text="Max Height:").grid(row=0, column=2, padx=8, pady=3, sticky="w")
        self.max_height_var = tk.StringVar(value="240")
        self.height_entry = ctk.CTkEntry(size_inner, textvariable=self.max_height_var, width=80)
        self.height_entry.grid(row=0, column=3, padx=8, pady=3)
        
        # Metadata labels section (moved back to left column)
        labels_frame = ctk.CTkFrame(left_column)
        labels_frame.pack(fill="x", padx=10, pady=(10, 6))
        
        ctk.CTkLabel(labels_frame, text="Metadata Labels", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(8, 3))
        
        label_options = ctk.CTkFrame(labels_frame)
        label_options.pack(pady=(0, 8), padx=2)
        
        self.show_title_var = tk.BooleanVar(value=True)
        self.show_title_checkbox = ctk.CTkCheckBox(label_options, text="Title", variable=self.show_title_var)
        self.show_title_checkbox.grid(row=0, column=0, padx=4, pady=3, sticky="w")
        
        self.show_resolution_var = tk.BooleanVar(value=True)
        self.show_resolution_checkbox = ctk.CTkCheckBox(label_options, text="Resolution", variable=self.show_resolution_var)
        self.show_resolution_checkbox.grid(row=0, column=1, padx=4, pady=3, sticky="w")
        
        self.show_file_size_var = tk.BooleanVar(value=True)
        self.show_file_size_checkbox = ctk.CTkCheckBox(label_options, text="File Size", variable=self.show_file_size_var)
        self.show_file_size_checkbox.grid(row=1, column=0, padx=4, pady=3, sticky="w")
        
        self.show_duration_var = tk.BooleanVar(value=True)
        self.show_duration_checkbox = ctk.CTkCheckBox(label_options, text="Duration", variable=self.show_duration_var)
        self.show_duration_checkbox.grid(row=1, column=1, padx=4, pady=3, sticky="w")
        
        self.show_codec_var = tk.BooleanVar(value=False)
        self.show_codec_checkbox = ctk.CTkCheckBox(label_options, text="Codec", variable=self.show_codec_var)
        self.show_codec_checkbox.grid(row=2, column=0, padx=4, pady=3, sticky="w")
        
        self.show_timestamps_var = tk.BooleanVar(value=False)
        self.show_timestamps_checkbox = ctk.CTkCheckBox(label_options, text="Timestamps", variable=self.show_timestamps_var)
        self.show_timestamps_checkbox.grid(row=2, column=1, padx=4, pady=3, sticky="w")
        
        # RIGHT COLUMN CONTENT
        # Output format setting (at top of right column)
        format_frame = ctk.CTkFrame(right_column)
        format_frame.pack(fill="x", padx=10, pady=(10, 6))
        
        ctk.CTkLabel(format_frame, text="Output Format", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(8, 5))
        self.output_format_var = tk.StringVar(value="JPG")
        
        format_inner = ctk.CTkFrame(format_frame)
        format_inner.pack(pady=(0, 8), padx=2)
        
        self.jpg_radio = ctk.CTkRadioButton(format_inner, text="JPG", variable=self.output_format_var, value="JPG",
                          command=self.on_format_change)
        self.jpg_radio.grid(row=0, column=0, padx=10, pady=3, sticky="w")
        self.png_radio = ctk.CTkRadioButton(format_inner, text="PNG", variable=self.output_format_var, value="PNG",
                          command=self.on_format_change)
        self.png_radio.grid(row=0, column=1, padx=10, pady=3, sticky="w")
        
        # JPG quality setting (moved to top of right column, disabled for PNG)
        quality_frame = ctk.CTkFrame(right_column)
        quality_frame.pack(fill="x", padx=10, pady=(10, 6))
        
        ctk.CTkLabel(quality_frame, text="JPG Quality", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(8, 3))
        self.quality_var = tk.IntVar(value=75)
        self.quality_slider = ctk.CTkSlider(quality_frame, from_=1, to=100, variable=self.quality_var, 
                                       command=lambda v: self.quality_label.configure(text=f"Quality: {int(v)}"))
        self.quality_slider.pack(fill="x", padx=15, pady=(0, 3))
        self.quality_label = ctk.CTkLabel(quality_frame, text="Quality: 75")
        self.quality_label.pack(pady=(0, 8))
        
        # Initialize format state
        self.on_format_change()
        
        # Preview checkbox (in right column)
        preview_check_frame = ctk.CTkFrame(right_column)
        preview_check_frame.pack(fill="x", padx=10, pady=(10, 6))
        
        self.show_preview_var = tk.BooleanVar(value=True)
        self.show_preview_checkbox = ctk.CTkCheckBox(preview_check_frame, text="Show preview", variable=self.show_preview_var)
        self.show_preview_checkbox.pack(pady=8)
        
        # Preview window (fixed size to prevent squishing buttons)
        # Use regular Frame wrapper for proper size control
        preview_container = tk.Frame(right_column, bg="#2b2b2b")
        preview_container.pack(fill="both", expand=True, padx=10, pady=(10, 15))
        preview_container.pack_propagate(False)
        preview_container.config(width=400, height=300)
        
        preview_frame = ctk.CTkFrame(preview_container)
        preview_frame.pack(fill="both", expand=True)
        
        ctk.CTkLabel(preview_frame, text="Screenshot Preview", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(10, 10))
        
        # Preview label (using regular tkinter Label for image display)
        self.preview_label = tk.Label(preview_frame, bg="#212121", text="No preview available", 
                                      fg="white", font=("Arial", 10))
        self.preview_label.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        
        # Processing time label (under preview)
        self.processing_time_label = ctk.CTkLabel(preview_frame, text="", font=ctk.CTkFont(size=11))
        self.processing_time_label.pack(pady=(0, 10))
        
        # Progress section (right column, after preview)
        progress_frame = ctk.CTkFrame(right_column)
        progress_frame.pack(fill="x", padx=10, pady=(10, 15))
        
        self.status_label = ctk.CTkLabel(progress_frame, text="Ready", font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=(10, 5))
        
        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 10))
        self.progress_bar.set(0)
        
        # Control buttons (right column, bottom)
        button_frame = ctk.CTkFrame(right_column)
        button_frame.pack(fill="x", padx=10, pady=(10, 10))
        
        self.start_button = ctk.CTkButton(button_frame, text="Start Processing", 
                                          command=self.start_processing, width=200, height=45,
                                          font=ctk.CTkFont(size=15, weight="bold"))
        self.start_button.pack(side="left", padx=15, pady=10)
        
        self.stop_button = ctk.CTkButton(button_frame, text="Stop", 
                                         command=self.stop_processing, width=200, height=45,
                                         font=ctk.CTkFont(size=15, weight="bold"),
                                         state="disabled")
        self.stop_button.pack(side="left", padx=15, pady=10)
    
    def _set_window_icon(self):
        """Set window icon (called after window is initialized)."""
        # When running from PyInstaller, use sys._MEIPASS to find bundled resources
        # When running from source, use __file__ directory
        # For customtkinter CTk, we need to set icon on the underlying tk window
        try:
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                # Running from PyInstaller bundle
                base_path = sys._MEIPASS
            else:
                # Running from source
                base_path = os.path.dirname(__file__)
            
            icon_path = os.path.join(base_path, 'icon.ico')
            if os.path.exists(icon_path):
                # For customtkinter CTk, access the underlying tk window
                # Try multiple methods to ensure icon is set
                try:
                    # Method 1: Set on CTk window directly
                    self.iconbitmap(icon_path)
                except:
                    try:
                        # Method 2: Set on underlying tk window using tk call
                        self.tk.call('wm', 'iconbitmap', self._w, icon_path)
                    except:
                        try:
                            # Method 3: Use iconphoto as fallback
                            icon_img = Image.open(icon_path)
                            icon_photo = ImageTk.PhotoImage(icon_img)
                            self.iconphoto(False, icon_photo)
                            # Keep a reference to prevent garbage collection
                            self._icon_photo = icon_photo
                        except Exception as e:
                            if not getattr(sys, 'frozen', False):
                                print(f"Warning: Could not set window icon (method 3): {e}")
        except Exception as e:
            # Log error for debugging (only in development)
            if not getattr(sys, 'frozen', False):
                print(f"Warning: Could not set window icon: {e}")
    
    def initialize_canvas_sizes(self):
        """Initialize canvas window sizes after the window is displayed."""
        if self.left_canvas and self.left_window:
            self.left_canvas.update_idletasks()
            canvas_width = self.left_canvas.winfo_width()
            if canvas_width > 1:  # Only update if canvas has been sized
                self.left_canvas.itemconfig(self.left_window, width=canvas_width)
                # Update scroll region
                self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))
                self.left_canvas.update_idletasks()
        
        if self.right_canvas and self.right_window:
            self.right_canvas.update_idletasks()
            canvas_width = self.right_canvas.winfo_width()
            if canvas_width > 1:  # Only update if canvas has been sized
                self.right_canvas.itemconfig(self.right_window, width=canvas_width)
                # Update scroll region
                self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all"))
                self.right_canvas.update_idletasks()
    
    def browse_input_dir(self):
        """Open dialog to select input directory."""
        directory = filedialog.askdirectory(title="Select Input Directory")
        if directory:
            self.input_dir.set(directory)
            # Auto-set output directory to match input directory every time
            default_output = get_default_output_dir(directory)
            self.output_dir.set(default_output)
    
    def browse_output_dir(self):
        """Open dialog to select output directory."""
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_dir.set(directory)
    
    def on_format_change(self):
        """Enable/disable quality slider based on output format."""
        if self.output_format_var.get() == "PNG":
            self.quality_slider.configure(state="disabled")
            self.quality_label.configure(text="PNG (lossless)")
        else:
            self.quality_slider.configure(state="normal")
            self.quality_label.configure(text=f"Quality: {self.quality_var.get()}")
    
    def disable_controls(self):
        """Disable all controls except 'Show preview' checkbox and stop button."""
        self.input_browse_button.configure(state="disabled")
        self.output_browse_button.configure(state="disabled")
        self.suffix_entry.configure(state="disabled")
        self.follow_structure_checkbox.configure(state="disabled")
        self.overwrite_checkbox.configure(state="disabled")
        self.workers_entry.configure(state="disabled")
        self.rows_entry.configure(state="disabled")
        self.columns_entry.configure(state="disabled")
        self.width_entry.configure(state="disabled")
        self.height_entry.configure(state="disabled")
        self.show_title_checkbox.configure(state="disabled")
        self.show_resolution_checkbox.configure(state="disabled")
        self.show_file_size_checkbox.configure(state="disabled")
        self.show_duration_checkbox.configure(state="disabled")
        self.show_codec_checkbox.configure(state="disabled")
        self.show_timestamps_checkbox.configure(state="disabled")
        self.jpg_radio.configure(state="disabled")
        self.png_radio.configure(state="disabled")
        self.quality_slider.configure(state="disabled")
        self.start_button.configure(state="disabled")
    
    def enable_controls(self):
        """Re-enable all controls."""
        self.input_browse_button.configure(state="normal")
        self.output_browse_button.configure(state="normal")
        self.suffix_entry.configure(state="normal")
        self.follow_structure_checkbox.configure(state="normal")
        self.overwrite_checkbox.configure(state="normal")
        self.workers_entry.configure(state="normal")
        self.rows_entry.configure(state="normal")
        self.columns_entry.configure(state="normal")
        self.width_entry.configure(state="normal")
        self.height_entry.configure(state="normal")
        self.show_title_checkbox.configure(state="normal")
        self.show_resolution_checkbox.configure(state="normal")
        self.show_file_size_checkbox.configure(state="normal")
        self.show_duration_checkbox.configure(state="normal")
        self.show_codec_checkbox.configure(state="normal")
        self.show_timestamps_checkbox.configure(state="normal")
        self.jpg_radio.configure(state="normal")
        self.png_radio.configure(state="normal")
        # Re-enable quality slider and restore format state
        self.on_format_change()
        self.start_button.configure(state="normal")
    
    def get_config(self) -> ProcessingConfig:
        """Get current configuration from UI with validation."""
        # Helper function to safely get integer from string
        def get_int(var, default, min_val=1):
            try:
                value = int(var.get())
                return max(min_val, value) if value > 0 else default
            except (ValueError, tk.TclError):
                return default
        
        # Get integer values with defaults
        rows = get_int(self.rows_var, 5, min_val=1)
        columns = get_int(self.columns_var, 6, min_val=1)
        max_width = get_int(self.max_width_var, 320, min_val=1)
        max_height = get_int(self.max_height_var, 240, min_val=1)
        
        # Quality is an IntVar (slider), so it should be safe
        try:
            quality = self.quality_var.get()
            if not isinstance(quality, int) or quality < 1 or quality > 100:
                quality = 75
        except (ValueError, tk.TclError):
            quality = 75
        
        return ProcessingConfig(
            rows=rows,
            columns=columns,
            max_screenshot_width=max_width,
            max_screenshot_height=max_height,
            jpg_quality=quality,
            overwrite_existing=self.overwrite_var.get(),
            show_title=self.show_title_var.get(),
            show_resolution=self.show_resolution_var.get(),
            show_file_size=self.show_file_size_var.get(),
            show_duration=self.show_duration_var.get(),
            show_codec=self.show_codec_var.get(),
            show_timestamps=self.show_timestamps_var.get()
        )
        # Add output_format setting (not in ProcessingConfig, handle separately)
        config.output_format = self.output_format_var.get()
        return config
    
    def update_status(self, message: str, progress: float = None):
        """Update status label and progress bar."""
        self.status_label.configure(text=message)
        if progress is not None:
            self.progress_bar.set(progress)
        self.update_idletasks()
    
    def update_preview(self, grid_image):
        """Update the preview window with a completed grid image (thread-safe)."""
        if not grid_image:
            self.after(0, lambda: self.preview_label.config(image="", text="No preview available"))
            return
        
        try:
            # Resize grid image to fit preview window (max width to match column width)
            preview_max_width = 400
            preview_max_height = 600
            img_width, img_height = grid_image.size
            
            # Calculate scaling to fit preview window
            width_scale = preview_max_width / img_width
            height_scale = preview_max_height / img_height
            scale = min(width_scale, height_scale, 1.0)
            
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            
            # Resize image
            preview_img = grid_image.resize((new_width, new_height), Image.Resampling.NEAREST)
            
            # Convert to PhotoImage (must be done in main thread)
            # Schedule the UI update on the main thread
            def update_ui():
                try:
                    self.preview_photo = ImageTk.PhotoImage(preview_img)
                    self.preview_label.config(image=self.preview_photo, text="")
                except Exception as e:
                    self.preview_label.config(image="", text=f"Preview error: {str(e)}")
            
            self.after(0, update_ui)
        except Exception as e:
            self.after(0, lambda: self.preview_label.config(image="", text=f"Preview error: {str(e)}"))
    
    def start_processing(self):
        """Start video processing in a separate thread."""
        if self.is_processing:
            return
        
        # Validate inputs
        input_dir = self.input_dir.get()
        output_dir = self.output_dir.get()
        
        if not input_dir or not os.path.isdir(input_dir):
            self.update_status("Error: Please select a valid input directory")
            return
        
        if not output_dir:
            output_dir = get_default_output_dir(input_dir)
            self.output_dir.set(output_dir)
        
        # Ensure output directory exists
        ensure_output_dir(output_dir)
        
        # Get configuration
        try:
            config = self.get_config()
        except ValueError as e:
            self.update_status(f"Error: {str(e)}")
            return
        
        # Clear preview
        self.preview_label.config(image="", text="Ready to process...")
        
        # Reset processing time
        self.processing_time_label.configure(text="")
        self.processing_start_time = time.time()
        
        # Start processing thread
        self.is_processing = True
        self.current_config = config
        self.stop_button.configure(state="normal")
        
        # Disable all controls except show preview and stop button
        self.disable_controls()
        
        self.processing_thread = threading.Thread(target=self.process_videos, 
                                                  args=(input_dir, output_dir, config),
                                                  daemon=True)
        self.processing_thread.start()
    
    def stop_processing(self):
        """Stop video processing."""
        self.is_processing = False
        self.update_status("Stopping...")
    
    def process_single_video(self, video_path: str, input_dir: str, output_dir: str, config: ProcessingConfig, 
                            video_index: int, total_videos: int, follow_structure: bool, 
                            output_format_override: str = None):
        """Process a single video (for parallel execution)."""
        video_name = os.path.basename(video_path)
        
        try:
            # Determine output format
            format_to_use = output_format_override if output_format_override else getattr(config, 'output_format', 'JPG')
            
            # Get suffix from UI
            suffix = self.suffix_var.get().strip()
            
            # Calculate output path
            output_path = calculate_output_path(video_path, input_dir, output_dir, format_to_use, follow_structure, suffix)
            
            # Check if file exists and overwrite setting
            exists_check = os.path.exists(output_path)
            
            if exists_check and not config.overwrite_existing:
                # If overwrite is disabled, skip existing files
                # Provide specific message for duplicate filenames when not following structure
                if not follow_structure:
                    return {'status': 'skipped', 'video': video_name, 
                           'message': 'Duplicate filename (not following structure)'}
                return {'status': 'skipped', 'video': video_name}
            
            # Get metadata first (necessary for aspect ratio calculation)
            metadata = get_video_metadata(video_path)
            if not metadata:
                return {'status': 'error', 'video': video_name, 
                       'message': 'Could not read metadata'}
            
            # Extract screenshots
            num_screenshots = config.total_screenshots
            try:
                screenshots = extract_screenshots(video_path, num_screenshots, 
                                                config.max_screenshot_width, 
                                                config.max_screenshot_height,
                                                preview_callback=None,
                                                full_resolution=True,  # Extract full-res, resize later
                                                original_resolution=metadata.get('resolution'),  # Pass original resolution for aspect ratio
                                                duration=metadata.get('duration'),  # Pass duration to avoid redundant metadata call
                                                fps=metadata.get('fps'))  # Pass fps to avoid redundant metadata call
            except Exception as e:
                return {'status': 'error', 'video': video_name,
                       'message': f'Could not extract screenshots: {str(e)}'}
            
            if not screenshots:
                return {'status': 'error', 'video': video_name,
                       'message': 'Could not extract screenshots'}
            
            # Create grid with full-res images, resize entire grid once at end
            grid_image = create_grid(screenshots, config, metadata, resize_after_compose=True)
            
            # Update preview with final result image (check setting at update time, not start time)
            if self.show_preview_var.get():
                self.update_preview(grid_image)
            
            # Save image (output_path already has correct extension from calculate_output_path)
            format_to_use = output_format_override if output_format_override else getattr(config, 'output_format', 'JPG')
            output_format_upper = str(format_to_use).upper().strip()
            
            # Save with explicit format
            if output_format_upper == 'PNG':
                save_grid_image(grid_image, output_path, None, format='PNG')
            else:
                save_grid_image(grid_image, output_path, config.jpg_quality, format='JPG')
            
            return {'status': 'success', 'video': video_name}
            
        except Exception as e:
            return {'status': 'error', 'video': video_name, 'message': str(e)}
    
    def process_videos(self, input_dir: str, output_dir: str, config: ProcessingConfig):
        """Process all videos in the directory with parallel processing."""
        try:
            # Find all video files
            self.update_status("Scanning for video files...")
            video_files = find_video_files(input_dir)
            
            if not video_files:
                self.update_status("No video files found in the selected directory")
                return
            
            total_videos = len(video_files)
            self.update_status(f"Found {total_videos} video(s)")
            
            # Get follow_structure setting
            follow_structure = self.follow_structure_var.get()
            
            # Filter out videos that should be skipped (check first, before parallel processing)
            videos_to_process = []
            skipped = 0
            
            for video_path in video_files:
                video_name = os.path.basename(video_path)
                
                # Calculate output path
                output_format = getattr(config, 'output_format', 'JPG')
                suffix = self.suffix_var.get().strip()
                output_path = calculate_output_path(video_path, input_dir, output_dir, output_format, follow_structure, suffix)
                
                # Check if file exists and overwrite setting
                exists_check = os.path.exists(output_path)
                if exists_check and not config.overwrite_existing:
                    skipped += 1
                else:
                    videos_to_process.append(video_path)
            
            if not videos_to_process:
                self.update_status(f"All {total_videos} video(s) already processed (skipped)")
                return
            
            # Get worker count (with validation)
            try:
                worker_count = int(self.workers_var.get())
                worker_count = max(1, min(worker_count, len(videos_to_process), 16))  # Limit to 1-16
            except (ValueError, tk.TclError):
                worker_count = 2  # Default to 2 workers
            
            max_workers = worker_count
            processed = 0
            errors = 0
            completed = 0
            
            # Preview setup
            show_preview = self.show_preview_var.get()
            if show_preview:
                self.after(0, lambda: self.preview_label.config(image="", text="Processing videos...\nPreview will show completed grid images"))
            else:
                self.after(0, lambda: self.preview_label.config(image="", text="Processing videos...\nPreview disabled"))
            
            # Get output format from UI (read fresh, not from config)
            output_format = self.output_format_var.get()  # Read directly from UI
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_video = {
                    executor.submit(self.process_single_video, video_path, input_dir, output_dir, config, idx, total_videos, follow_structure, output_format): 
                    (idx, video_path) 
                    for idx, video_path in enumerate(videos_to_process)
                }
                
                # Process completed tasks as they finish
                for future in as_completed(future_to_video):
                    if not self.is_processing:
                        # Cancel remaining tasks
                        for f in future_to_video:
                            f.cancel()
                        self.update_status("Processing stopped by user")
                        break
                    
                    idx, video_path = future_to_video[future]
                    completed += 1
                    
                    try:
                        result = future.result()
                        if result['status'] == 'success':
                            processed += 1
                        elif result['status'] == 'error':
                            errors += 1
                            self.update_status(f"Error: {result.get('message', 'Unknown error')} for {result['video']}")
                        elif result['status'] == 'skipped':
                            skipped += 1
                            self.update_status(f"Skipped: {result['video']} ({result.get('message', 'already exists')})")
                        
                        # Update progress
                        self.update_status(f"Processing... ({completed}/{len(videos_to_process)} completed)", 
                                         progress=(skipped + completed) / total_videos)
                    except Exception as e:
                        errors += 1
                        self.update_status(f"Error processing {os.path.basename(video_path)}: {str(e)}")
            
            # Final status
            if self.is_processing:
                status_msg = f"Complete! Processed: {processed}, Skipped: {skipped}"
                if errors > 0:
                    status_msg += f", Errors: {errors}"
                self.update_status(status_msg, progress=1.0)
                
                # Update processing time label
                if self.processing_start_time:
                    total_time = time.time() - self.processing_start_time
                    minutes = int(total_time // 60)
                    seconds = int(total_time % 60)
                    if minutes > 0:
                        time_str = f"Total time: {minutes}m {seconds}s"
                    else:
                        time_str = f"Total time: {seconds}s"
                    self.after(0, lambda: self.processing_time_label.configure(text=time_str))
            
        except Exception as e:
            self.update_status(f"Error: {str(e)}")
        finally:
            # Reset UI state
            self.is_processing = False
            self.stop_button.configure(state="disabled")
            # Re-enable all controls
            self.enable_controls()


def main():
    """Main entry point."""
    app = ScreenMachineApp()
    app.mainloop()


if __name__ == "__main__":
    main()

