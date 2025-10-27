"""
Main window GUI untuk aplikasi OCR Form Scanner
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import threading
from typing import Optional
import customtkinter as ctk
from PIL import Image, ImageTk
import io

from src.ocr.pipeline import OCRPipeline


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("OCR Form Scanner")
        self.geometry("900x700")
        
        # State
        self.current_file_path = None
        self.ocr_results = None
        self.pipeline = OCRPipeline()
        
        # Setup UI
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup user interface"""
        
        # Header
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill=tk.X, padx=20, pady=20)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="OCR Form Scanner",
            font=ctk.CTkFont(size=32, weight="bold")
        )
        title_label.pack(pady=20)
        
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Scanning Form Statistik BLOK III REKAPITULASI MUATAN",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        subtitle_label.pack()
        
        # Main content area
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Upload section
        upload_frame = ctk.CTkFrame(main_frame)
        upload_frame.pack(fill=tk.X, padx=20, pady=20)
        
        upload_label = ctk.CTkLabel(
            upload_frame,
            text="Upload Form File",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        upload_label.pack(pady=10)
        
        upload_button = ctk.CTkButton(
            upload_frame,
            text="Choose File (PDF, JPG, PNG)",
            command=self._select_file,
            width=300,
            height=40,
            font=ctk.CTkFont(size=14)
        )
        upload_button.pack(pady=10)
        
        self.file_label = ctk.CTkLabel(
            upload_frame,
            text="No file selected",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.file_label.pack(pady=5)
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            upload_frame,
            width=300,
            mode='indeterminate'
        )
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            upload_frame,
            text="",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(pady=5)
        
        # Preview section (placeholder)
        preview_frame = ctk.CTkFrame(main_frame)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        self.preview_label = ctk.CTkLabel(
            preview_frame,
            text="Preview akan muncul di sini",
            font=ctk.CTkFont(size=12)
        )
        self.preview_label.pack(pady=50)
        
        # Process button
        process_button = ctk.CTkButton(
            upload_frame,
            text="Process OCR",
            command=self._process_ocr,
            width=300,
            height=40,
            font=ctk.CTkFont(size=14),
            state="disabled"
        )
        self.process_button = process_button
        process_button.pack(pady=10)
        
    def _select_file(self):
        """Handle file selection"""
        filetypes = [
            ("All supported", "*.pdf *.jpg *.jpeg *.png"),
            ("PDF files", "*.pdf"),
            ("Image files", "*.jpg *.jpeg *.png"),
            ("All files", "*.*")
        ]
        
        file_path = filedialog.askopenfilename(
            title="Select Form File",
            filetypes=filetypes
        )
        
        if file_path:
            self.current_file_path = file_path
            filename = Path(file_path).name
            self.file_label.configure(text=f"Selected: {filename}")
            self.process_button.configure(state="normal")
            
    def _process_ocr(self):
        """Process OCR on selected file"""
        if not self.current_file_path:
            messagebox.showerror("Error", "Please select a file first")
            return
            
        # Disable button during processing
        self.process_button.configure(state="disabled", text="Processing...")
        self.progress_bar.start()
        self.status_label.configure(text="Processing OCR...")
        
        # Run in thread to avoid blocking UI
        thread = threading.Thread(target=self._process_ocr_thread)
        thread.daemon = True
        thread.start()
        
    def _process_ocr_thread(self):
        """OCR processing dalam separate thread"""
        try:
            # Process file
            self.pipeline.process_file(self.current_file_path)
            
            # Get results
            self.ocr_results = self.pipeline.get_results_structured()
            
            # Update UI in main thread
            self.after(0, self._process_complete)
            
        except Exception as e:
            self.after(0, lambda: self._process_error(str(e)))
    
    def _process_complete(self):
        """Callback ketika processing selesai"""
        self.progress_bar.stop()
        self.process_button.configure(state="normal", text="Process OCR")
        self.status_label.configure(text="Processing complete!")
        
        # Open review window
        from src.gui.review_window import ReviewWindow
        review_window = ReviewWindow(self, self.ocr_results, self.current_file_path)
        
    def _process_error(self, error_msg: str):
        """Callback ketika terjadi error"""
        self.progress_bar.stop()
        self.process_button.configure(state="normal", text="Process OCR")
        self.status_label.configure(text="")
        
        messagebox.showerror("Error", f"Error processing OCR:\n{error_msg}")
