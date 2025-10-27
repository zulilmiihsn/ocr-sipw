"""
Review window untuk review dan edit hasil OCR
"""

import tkinter as tk
from tkinter import messagebox, filedialog
from pathlib import Path
from typing import List, Dict
import customtkinter as ctk

from src.utils.csv_exporter import export_to_csv


class ReviewWindow(ctk.CTkToplevel):
    def __init__(self, parent, ocr_results: List[Dict], source_file: str):
        super().__init__(parent)
        
        self.title("Review OCR Results")
        self.geometry("1400x600")
        
        self.ocr_results = ocr_results
        self.source_file = source_file
        self.modified_results = [row.copy() for row in ocr_results]
        
        # Setup UI
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup user interface"""
        
        # Header
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill=tk.X, padx=20, pady=10)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="Review & Edit OCR Results",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        # Toolbar
        toolbar_frame = ctk.CTkFrame(self)
        toolbar_frame.pack(fill=tk.X, padx=20, pady=10)
        
        export_button = ctk.CTkButton(
            toolbar_frame,
            text="Export to CSV",
            command=self._export_csv,
            width=150,
            height=35,
            font=ctk.CTkFont(size=14)
        )
        export_button.pack(side=tk.LEFT, padx=10)
        
        # Info label
        info_label = ctk.CTkLabel(
            toolbar_frame,
            text="Double-click cell untuk edit",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        info_label.pack(side=tk.LEFT, padx=20)
        
        # Table view
        self._setup_table()
        
    def _setup_table(self):
        """Setup table view"""
        
        # Create scrollable frame
        scrollable_frame = ctk.CTkScrollableFrame(self)
        scrollable_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        if not self.modified_results:
            empty_label = ctk.CTkLabel(
                scrollable_frame,
                text="No data to display",
                font=ctk.CTkFont(size=14)
            )
            empty_label.pack(pady=50)
            return
        
        # Get all column names
        from src.models import COLUMN_HEADERS
        
        # Create table headers
        headers = COLUMN_HEADERS
        self.table_widgets = {}
        
        # Header row
        header_row = ctk.CTkFrame(scrollable_frame)
        header_row.pack(fill=tk.X, pady=5)
        
        for i, header in enumerate(headers):
            header_label = ctk.CTkLabel(
                header_row,
                text=header,
                font=ctk.CTkFont(size=11, weight="bold"),
                width=150,
                anchor="w",
                justify="left"
            )
            header_label.pack(side=tk.LEFT, padx=2)
        
        # Data rows
        for row_idx, row_data in enumerate(self.modified_results):
            row_frame = ctk.CTkFrame(scrollable_frame)
            row_frame.pack(fill=tk.X, pady=2)
            self.table_widgets[row_idx] = {}
            
            for col_idx, header in enumerate(headers):
                value = row_data.get(header, "")
                
                entry = ctk.CTkEntry(
                    row_frame,
                    width=150,
                    font=ctk.CTkFont(size=10)
                )
                entry.insert(0, str(value))
                entry.pack(side=tk.LEFT, padx=2, ipady=5)
                
                # Store references untuk callback
                entry.bind("<Double-Button-1>", 
                          self._create_edit_handler(row_idx, header))
                
                self.table_widgets[row_idx][header] = entry
        
    def _create_edit_handler(self, row_idx: int, col_name: str):
        """Create edit handler untuk cell"""
        def handler(event):
            entry = self.table_widgets[row_idx][col_name]
            
            # Create edit dialog
            dialog = ctk.CTkInputDialog(
                text=f"Edit {col_name}:",
                title="Edit Cell"
            )
            
            new_value = dialog.get_input()
            
            if new_value is not None:
                # Update entry
                entry.delete(0, tk.END)
                entry.insert(0, new_value)
                
                # Update data
                self.modified_results[row_idx][col_name] = new_value
        
        return handler
    
    def _export_csv(self):
        """Export results ke CSV"""
        try:
            # Show save dialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile="ocr_result.csv"
            )
            
            if not filename:
                return
            
            # Export to CSV
            file_path = export_to_csv(self.modified_results, filename=Path(filename).name)
            
            messagebox.showinfo(
                "Success",
                f"Data berhasil diekspor ke:\n{file_path}"
            )
            
        except Exception as e:
            messagebox.showerror("Error", f"Error exporting CSV:\n{str(e)}")
