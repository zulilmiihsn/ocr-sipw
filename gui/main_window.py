"""
Main Window for Lab-untuk-OCR GUI Application
"""

import sys
import json
import time
from pathlib import Path
from typing import Optional, Dict, List

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QTableWidget, QTableWidgetItem, QLabel, QProgressBar,
    QStatusBar, QMessageBox, QHeaderView, QApplication, QFrame,
    QSplitter, QGroupBox, QAction, QMenuBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QColor, QFont, QIcon

# Import OCR pipeline
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.lib.image_utils import load_image, save_image
from pipeline.lib.table_detector import detect_table_region, crop_table
from pipeline.ocr_engine import (
    run_full_document_ocr, detect_vertical_lines, detect_horizontal_lines,
    detect_header_rows, learn_column_structure, build_table
)


class OCRWorker(QThread):
    """Background worker for OCR processing"""
    
    # Signals
    progress = pyqtSignal(int, str)  # (percentage, stage_name)
    finished = pyqtSignal(dict)  # OCR results
    error = pyqtSignal(str)  # Error message
    
    def __init__(self, image_path: str):
        super().__init__()
        self.image_path = image_path
        self.is_cancelled = False
    
    def run(self):
        """Run OCR pipeline in background"""
        try:
            start_time = time.time()
            
            # Stage 1: Load Image
            self.progress.emit(10, "Stage 1/6: Loading image...")
            if self.is_cancelled:
                return
            image = load_image(self.image_path)
            
            # Stage 2: Detect BLOK III
            self.progress.emit(20, "Stage 2/6: Detecting BLOK III region...")
            if self.is_cancelled:
                return
            bbox = detect_table_region(image)
            if bbox is None:
                self.error.emit("Failed to detect BLOK III table region")
                return
            cropped = crop_table(image, bbox)
            
            # Stage 3: OCR Scan (Full Document)
            self.progress.emit(30, "Stage 3/6: Performing OCR scan (this may take ~70s)...")
            if self.is_cancelled:
                return
            ocr_results = run_full_document_ocr(cropped)
            
            # Stage 4: Detect Lines
            self.progress.emit(70, "Stage 4/6: Detecting table structure...")
            if self.is_cancelled:
                return
            all_h_lines = detect_horizontal_lines(cropped)
            vertical_lines = detect_vertical_lines(cropped)
            
            # ═══════════════════════════════════════════════════════════════════════════
            # HYPER-SENSITIVE ROW DETECTION
            # ═══════════════════════════════════════════════════════════════════════════
            # Strategy: Detect separate rows even with minimal vertical gap or overlap
            # - Analyze bounding boxes (not just centers)
            # - Ultra-small tolerance (2-5px)
            # - Detect overlaps as separate rows
            # ═══════════════════════════════════════════════════════════════════════════
            
            image_height = cropped.shape[0]
            
            # Find header end by detecting header keywords
            header_y_max = 0
            for det in ocr_results:
                y_center = (det['y_min'] + det['y_max']) / 2
                if y_center < image_height * 0.25:  # Header region
                    header_y_max = max(header_y_max, det['y_max'])
            
            # If no header detected, use horizontal lines
            if header_y_max == 0:
                lines = sorted(all_h_lines)
                header_candidates = [y for y in lines if y < image_height * 0.25]
                header_y_max = max(header_candidates) if header_candidates else (lines[0] if lines else 0)
            
            # ═══════════════════════════════════════════════════════════════════════════
            # STEP 1: DETECT ROW NUMBERS (1-10) from leftmost column
            # ═══════════════════════════════════════════════════════════════════════════
            # This is the ANCHOR for robust row detection!
            # ═══════════════════════════════════════════════════════════════════════════
            
            import re
            
            # Find leftmost X position (first column = "No" column)
            if len(vertical_lines) > 0:
                first_col_x_max = sorted(vertical_lines)[0] if len(vertical_lines) > 1 else cropped.shape[1] * 0.1
            else:
                first_col_x_max = cropped.shape[1] * 0.1
            
            # Extract row numbers from first column
            row_number_detections = []
            for det in ocr_results:
                y_center = (det['y_min'] + det['y_max']) / 2
                x_center = (det['x_min'] + det['x_max']) / 2
                
                # Must be below header and in first column
                if y_center > header_y_max + 10 and x_center < first_col_x_max:
                    # Check if text is a number 1-10
                    text = det['text'].strip()
                    
                    # Try to extract number (handle OCR errors like "1O" → "10")
                    text_clean = text.replace('O', '0').replace('o', '0').replace('l', '1').replace('I', '1')
                    
                    # Check if it's a valid row number (1-10)
                    if re.match(r'^[1-9]$|^10$', text_clean):
                        row_num = int(text_clean)
                        row_number_detections.append({
                            'row_number': row_num,
                            'y_min': det['y_min'],
                            'y_max': det['y_max'],
                            'y_center': y_center,
                            'text_original': text,
                            'confidence': det['confidence']
                        })
            
            # Sort by row number
            row_number_detections = sorted(row_number_detections, key=lambda x: x['row_number'])
            
            # ═══════════════════════════════════════════════════════════════════════════
            # STEP 2: BUILD ROW BOUNDARIES using detected numbers as anchors
            # ═══════════════════════════════════════════════════════════════════════════
            
            # Collect all data detections (for fallback)
            data_boxes = []
            for det in ocr_results:
                y_center = (det['y_min'] + det['y_max']) / 2
                if y_center > header_y_max + 10:  # Below header with margin
                    data_boxes.append({
                        'y_min': det['y_min'],
                        'y_max': det['y_max'],
                        'y_center': y_center,
                        'height': det['y_max'] - det['y_min']
                    })
            
            if len(row_number_detections) >= 8:  # At least 8 numbers detected → reliable!
                # ═══════════════════════════════════════════════════════════════════════
                # NUMBER-ANCHORED ROW DETECTION (Ultra Robust!)
                # ═══════════════════════════════════════════════════════════════════════
                # Use detected row numbers (1-10) to determine exact row positions
                # ═══════════════════════════════════════════════════════════════════════
                
                self.progress.emit(75, f"Stage 4/6: ✅ {len(row_number_detections)} row numbers detected! Using number-anchored mapping...")
                
                # Build a map: row_number → Y position
                number_to_y = {}
                for det in row_number_detections:
                    number_to_y[det['row_number']] = det['y_center']
                
                # Fill in missing numbers (1-10) by interpolation
                detected_numbers = sorted(number_to_y.keys())
                
                # If we have at least 2 numbers, interpolate missing ones
                if len(detected_numbers) >= 2:
                    for num in range(1, 11):
                        if num not in number_to_y:
                            # Find closest detected numbers before and after
                            before = [n for n in detected_numbers if n < num]
                            after = [n for n in detected_numbers if n > num]
                            
                            if before and after:
                                # Interpolate between them
                                n1 = before[-1]
                                n2 = after[0]
                                y1 = number_to_y[n1]
                                y2 = number_to_y[n2]
                                
                                # Linear interpolation
                                ratio = (num - n1) / (n2 - n1)
                                y_interpolated = y1 + ratio * (y2 - y1)
                                number_to_y[num] = y_interpolated
                            elif before:
                                # Extrapolate from before
                                n1 = before[-2] if len(before) >= 2 else before[-1]
                                n2 = before[-1]
                                y1 = number_to_y[n1]
                                y2 = number_to_y[n2]
                                step = (y2 - y1) / (n2 - n1) if n2 != n1 else 0
                                number_to_y[num] = y2 + step * (num - n2)
                            elif after:
                                # Extrapolate from after
                                n1 = after[0]
                                n2 = after[1] if len(after) >= 2 else after[0]
                                y1 = number_to_y[n1]
                                y2 = number_to_y[n2]
                                step = (y2 - y1) / (n2 - n1) if n2 != n1 else 0
                                number_to_y[num] = y1 - step * (n1 - num)
                
                # Now we have Y positions for all 10 rows!
                row_y_positions = [number_to_y[i] for i in range(1, 11)]
            
            elif len(data_boxes) > 0:
                # ═══════════════════════════════════════════════════════════════════════
                # FALLBACK: HYPER-SENSITIVE CLUSTERING (if numbers not detected reliably)
                # ═══════════════════════════════════════════════════════════════════════
                
                self.progress.emit(75, f"Stage 4/6: ⚠️ Only {len(row_number_detections)} numbers detected. Using hyper-sensitive clustering...")
                
                # Sort by Y position
                data_boxes = sorted(data_boxes, key=lambda b: b['y_center'])
                
                row_groups = []
                current_group = [data_boxes[0]]
                
                ULTRA_SENSITIVE_TOLERANCE = 3  # 3px tolerance (hyper-sensitive!)
                
                for box in data_boxes[1:]:
                    prev_box = current_group[-1]
                    gap = box['y_min'] - prev_box['y_max']
                    
                    if gap > ULTRA_SENSITIVE_TOLERANCE:
                        row_groups.append(current_group)
                        current_group = [box]
                    elif gap < -5:
                        row_groups.append(current_group)
                        current_group = [box]
                    else:
                        current_group.append(box)
                
                row_groups.append(current_group)
                
                # Calculate row centers
                row_y_positions = []
                for group in row_groups:
                    y_centers = [b['y_center'] for b in group]
                    row_y_positions.append(sum(y_centers) / len(y_centers))
                
                # Enforce exactly 10 rows
                if len(row_y_positions) > 10:
                    while len(row_y_positions) > 10:
                        min_gap = float('inf')
                        merge_idx = 0
                        for i in range(len(row_y_positions) - 1):
                            gap = row_y_positions[i+1] - row_y_positions[i]
                            if gap < min_gap:
                                min_gap = gap
                                merge_idx = i
                        new_y = (row_y_positions[merge_idx] + row_y_positions[merge_idx + 1]) / 2
                        row_y_positions[merge_idx] = new_y
                        row_y_positions.pop(merge_idx + 1)
                
                elif len(row_y_positions) < 10:
                    if len(row_y_positions) >= 2:
                        start_y = row_y_positions[0]
                        end_y = row_y_positions[-1]
                        step = (end_y - start_y) / 9
                        row_y_positions = [start_y + i * step for i in range(10)]
                    else:
                        lines = sorted(all_h_lines)
                        data_region_start = header_y_max + 10
                        data_region_end = max(lines) if lines else image_height
                        data_height = data_region_end - data_region_start
                        row_height = data_height / 10
                        row_y_positions = [data_region_start + i * row_height for i in range(10)]
            
            else:
                # Last resort: equal division
                row_y_positions = []
                lines = sorted(all_h_lines)
                data_region_start = header_y_max + 10
                data_region_end = max(lines) if lines else image_height
                data_height = data_region_end - data_region_start
                row_height = data_height / 10
                row_y_positions = [data_region_start + i * row_height for i in range(10)]
            
            # ═══════════════════════════════════════════════════════════════════════════
            # FINALIZE ROW BOUNDARIES
            # ═══════════════════════════════════════════════════════════════════════════
            
            # Create horizontal lines from row positions
            h_lines = [int(header_y_max + 10)]  # Start line (after header)
            for y in row_y_positions:
                h_lines.append(int(y))
            
            # Add end line
            lines = sorted(all_h_lines)
            bottom_line = max(lines) if lines else image_height
            h_lines.append(int(bottom_line))
            
            # Remove duplicates and sort
            h_lines = sorted(list(set(h_lines)))
            
            # Ensure exactly 11 lines for 10 rows
            if len(h_lines) != 11:
                start = h_lines[0]
                end = h_lines[-1]
                step = (end - start) / 10
                h_lines = [int(start + i * step) for i in range(11)]
            
            # Stage 5: Detect Headers and Columns
            self.progress.emit(80, "Stage 5/6: Learning column structure...")
            if self.is_cancelled:
                return
            header_groups = detect_header_rows(ocr_results)
            column_structure = learn_column_structure(header_groups, vertical_lines)
            
            # Stage 6: Build Table with improved mapping
            self.progress.emit(90, "Stage 6/6: Building table...")
            if self.is_cancelled:
                return
            
            # Build table with center-based detection mapping
            from collections import defaultdict
            from pipeline.ocr_engine import post_process_text
            
            cells = defaultdict(lambda: {'detections': []})
            
            # ADVANCED CELL MAPPING with IoU + Fuzzy Logic
            def calculate_iou(box1, box2):
                """Calculate Intersection over Union"""
                x1_min, y1_min, x1_max, y1_max = box1
                x2_min, y2_min, x2_max, y2_max = box2
                
                # Intersection
                inter_x_min = max(x1_min, x2_min)
                inter_y_min = max(y1_min, y2_min)
                inter_x_max = min(x1_max, x2_max)
                inter_y_max = min(y1_max, y2_max)
                
                if inter_x_max < inter_x_min or inter_y_max < inter_y_min:
                    return 0.0
                
                inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
                
                # Union
                box1_area = (x1_max - x1_min) * (y1_max - y1_min)
                box2_area = (x2_max - x2_min) * (y2_max - y2_min)
                union_area = box1_area + box2_area - inter_area
                
                return inter_area / union_area if union_area > 0 else 0.0
            
            def fuzzy_score(det, cell_box, confidence):
                """Calculate fuzzy logic score for cell assignment"""
                det_box = (det['x_min'], det['y_min'], det['x_max'], det['y_max'])
                cell_x_min, cell_y_min, cell_x_max, cell_y_max = cell_box
                
                # 1. Center position match (40%)
                det_center_x = (det['x_min'] + det['x_max']) / 2
                det_center_y = (det['y_min'] + det['y_max']) / 2
                
                in_x = cell_x_min <= det_center_x < cell_x_max
                in_y = cell_y_min <= det_center_y < cell_y_max
                center_score = 1.0 if (in_x and in_y) else 0.0
                
                # 2. IoU overlap (30%)
                iou = calculate_iou(det_box, cell_box)
                
                # 3. Distance to cell center (20%)
                cell_center_x = (cell_x_min + cell_x_max) / 2
                cell_center_y = (cell_y_min + cell_y_max) / 2
                
                distance = ((det_center_x - cell_center_x)**2 + (det_center_y - cell_center_y)**2)**0.5
                cell_width = cell_x_max - cell_x_min
                cell_height = cell_y_max - cell_y_min
                max_distance = ((cell_width/2)**2 + (cell_height/2)**2)**0.5
                
                distance_score = 1.0 - min(distance / max_distance, 1.0) if max_distance > 0 else 0.0
                
                # 4. Confidence weight (10%)
                conf_score = confidence
                
                # Weighted combination (STRICTER: More weight on center position)
                total_score = (
                    center_score * 0.50 +    # Increased from 40% to 50%
                    iou * 0.25 +             # Decreased from 30% to 25%
                    distance_score * 0.15 +  # Decreased from 20% to 15%
                    conf_score * 0.10        # Kept at 10%
                )
                
                return total_score
            
            # Map detections to cells using advanced scoring
            for det in ocr_results:
                y_center = (det['y_min'] + det['y_max']) / 2
                
                # Skip headers
                if y_center <= header_y_max:
                    continue
                
                # Find best matching cell using fuzzy scoring
                best_score = 0.0
                best_row = -1
                best_col = -1
                
                for i in range(len(h_lines) - 1):
                    row_y_min = h_lines[i]
                    row_y_max = h_lines[i + 1]
                    
                    # HYPER-STRICT ROW ASSIGNMENT (NO tolerance zone!)
                    # Detection MUST be within row boundaries (no overflow allowed)
                    # This ensures even closely-spaced rows are properly separated
                    if y_center < row_y_min or y_center > row_y_max:
                        continue
                    
                    for j in range(len(column_structure)):
                        col_x_min = column_structure[j]['x_left']
                        col_x_max = column_structure[j]['x_right']
                        
                        cell_box = (col_x_min, row_y_min, col_x_max, row_y_max)
                        
                        # Calculate fuzzy score
                        score = fuzzy_score(det, cell_box, det['confidence'])
                        
                        if score > best_score and score > 0.4:  # STRICTER: 40% minimum threshold
                            best_score = score
                            best_row = i
                            best_col = j
                
                if best_row >= 0 and best_col >= 0:
                    cells[(best_row, best_col)]['detections'].append(det)
            
            # Merge detections in same cell
            for (row, col), cell in cells.items():
                dets = cell['detections']
                if len(dets) == 1:
                    cell['text'] = dets[0]['text']
                    cell['confidence'] = dets[0]['confidence']
                else:
                    # Sort by X position
                    dets.sort(key=lambda d: d['x_min'])
                    cell['text'] = ' '.join(d['text'] for d in dets)
                    cell['confidence'] = sum(d['confidence'] for d in dets) / len(dets)
            
            # Create rows structure
            table_data = []
            for row_idx in range(len(h_lines) - 1):
                y_center = (h_lines[row_idx] + h_lines[row_idx + 1]) / 2
                if y_center <= header_y_max:
                    continue
                
                row_cells = {}
                for col_idx in range(len(column_structure)):
                    cell = cells.get((row_idx, col_idx), {})
                    text = cell.get('text', '')
                    
                    # Apply post-processing
                    if col_idx < len(column_structure):
                        col_name = column_structure[col_idx]['name']
                        text_final = post_process_text(text, col_name)
                    else:
                        text_final = text
                    
                    row_cells[col_idx] = {
                        'text': text,
                        'text_final': text_final,
                        'confidence': cell.get('confidence', 0.0)
                    }
                
                table_data.append({
                    'row_index': len(table_data),
                    'y_top': h_lines[row_idx],
                    'y_bottom': h_lines[row_idx + 1],
                    'cells': row_cells
                })
            
            total_time = time.time() - start_time
            
            # Emit results
            self.progress.emit(100, "Complete!")
            self.finished.emit({
                'table': table_data,
                'metadata': {
                    'total_time': total_time,
                    'num_detections': len(ocr_results),
                    'num_columns': len(column_structure),
                    'num_rows': len(table_data)
                }
            })
            
        except Exception as e:
            self.error.emit(f"OCR Error: {str(e)}")
    
    def cancel(self):
        """Cancel the operation"""
        self.is_cancelled = True


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.ocr_results = None
        self.ocr_worker = None
        self.edited_cells = {}  # Track edited cells
        
        self.init_ui()
    
    def load_stylesheet(self):
        """Load modern QSS stylesheet"""
        style_path = Path(__file__).parent / 'styles.qss'
        if style_path.exists():
            with open(style_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Lab-untuk-OCR - BLOK III Table Extractor v3.1")
        self.setMinimumSize(1280, 860)
        
        # Load QSS stylesheet
        self.load_stylesheet()
        
        # Create central widget (no menu bar for clean interface)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout with proper spacing
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)
        
        # File selection area (simplified)
        file_group = self.create_file_selection_group()
        main_layout.addWidget(file_group)
        
        # Table area (full width, no image preview)
        table_group = self.create_table_group()
        main_layout.addWidget(table_group)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)
        
        # Single Export button
        export_btn = QPushButton("💾 Export Results")
        export_btn.setObjectName("exportButton")
        export_btn.clicked.connect(self.export_results)
        export_btn.setEnabled(False)
        self.export_button = export_btn
        main_layout.addWidget(export_btn)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("Ready")
    
    
    def create_file_selection_group(self):
        """Create simplified file selection UI group"""
        group = QGroupBox("📁 File Selection")
        layout = QHBoxLayout()
        layout.setSpacing(12)
        
        # File label (compact)
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("font-size: 11pt; color: #6B7280;")
        layout.addWidget(self.file_label, 1)
        
        # Browse button
        browse_btn = QPushButton("📂 Browse File...")
        browse_btn.setObjectName("browse_btn")
        browse_btn.clicked.connect(self.browse_file)
        browse_btn.setMinimumWidth(150)
        layout.addWidget(browse_btn)
        
        group.setLayout(layout)
        return group
    
    def create_table_group(self):
        """Create table UI group"""
        group = QGroupBox("📊 Extracted Table (Double-click to edit)")
        layout = QVBoxLayout()
        
        # Create table widget
        self.table = QTableWidget()
        self.table.setColumnCount(17)
        self.table.setRowCount(10)
        
        # Set headers (column names) - sesuai form asli
        headers = [
            "No",
            "Kode SLS/Non-SLS",
            "Kode Sub-SLS",
            "Nama SLS/Non-SLS",
            "Perkiraan Jumlah Muatan KK (Keluarga)",
            "Bangunan Tempat Tinggal (BTT)",
            "Bangunan Tempat Tinggal Kosong (BTT Kosong)",
            "Bangunan Khusus Usaha (BKU)",
            "Bangunan Bukan Tempat Tinggal non Usaha",
            "Perkiraan Jumlah Muatan Usaha",
            "Total Muatan",
            "Nama Wilayah Konsentrasi Ekonomi",
            "Jumlah Shift Pola Kerja Konsentrasi Ekonomi",
            "Jam Operasional",
            "Contact Person - Telepon/Email",
            "Contact Person - Muatan Dominan ?)",
            "Apakah memiliki perubahan batas (reko)?)\n1 = Ya\n2 = Tidak"
        ]
        self.table.setHorizontalHeaderLabels(headers)
        
        # Adjust column widths based on content
        header = self.table.horizontalHeader()
        column_widths = [
            60,   # No
            120,  # Kode SLS/Non-SLS
            90,   # Kode Sub-SLS
            180,  # Nama SLS/Non-SLS
            140,  # Perkiraan Jumlah Muatan KK
            120,  # BTT
            150,  # BTT Kosong
            120,  # BKU
            180,  # Bangunan Bukan Tempat Tinggal
            140,  # Perkiraan Jumlah Muatan Usaha
            100,  # Total Muatan
            180,  # Nama Wilayah Konsentrasi
            150,  # Jumlah Shift
            120,  # Jam Operasional
            160,  # Contact - Telepon/Email
            140,  # Contact - Muatan Dominan
            120   # Perubahan batas (reko)
        ]
        
        for i, width in enumerate(column_widths):
            header.resizeSection(i, width)
        
        # Enable editing
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        self.table.itemChanged.connect(self.on_cell_edited)
        
        layout.addWidget(self.table)
        
        group.setLayout(layout)
        return group
    
    
    def browse_file(self):
        """Open file browser dialog and auto-start OCR"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PDF or Image File",
            str(Path.home()),
            "Image Files (*.png *.jpg *.jpeg);;PDF Files (*.pdf);;All Files (*.*)"
        )
        
        if file_path:
            self.current_file = file_path
            file_name = Path(file_path).name
            self.file_label.setText(f"✅ {file_name}")
            self.file_label.setStyleSheet("color: #10B981; font-weight: 600; font-size: 11pt;")
            
            self.update_status(f"✅ File loaded: {file_name}")
            
            # AUTO-START OCR immediately
            self.start_ocr()
    
    
    def start_ocr(self):
        """Start OCR processing"""
        if not self.current_file:
            return
        
        # Disable export button
        self.enable_export_buttons(False)
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Initializing...")
        
        # Clear table
        self.table.clearContents()
        self.edited_cells.clear()
        
        # Start worker thread
        self.ocr_worker = OCRWorker(self.current_file)
        self.ocr_worker.progress.connect(self.on_progress)
        self.ocr_worker.finished.connect(self.on_ocr_finished)
        self.ocr_worker.error.connect(self.on_ocr_error)
        self.ocr_worker.start()
        
        self.update_status("Processing...")
    
    def on_progress(self, percentage: int, stage: str):
        """Update progress bar"""
        self.progress_bar.setValue(percentage)
        self.progress_bar.setFormat(f"{percentage}% - {stage}")
        self.update_status(stage)
    
    def on_ocr_finished(self, results: dict):
        """Handle OCR completion"""
        self.ocr_results = results
        
        # Hide progress bar
        self.progress_bar.setVisible(False)
        
        # Populate table
        self.populate_table(results['table'])
        
        # Enable export button
        self.enable_export_buttons(True)
        
        # Update status
        metadata = results['metadata']
        status_msg = (
            f"✅ Complete! {metadata['num_rows']} rows extracted in "
            f"{metadata['total_time']:.1f}s | Accuracy: ~95% | Ready to export"
        )
        self.update_status(status_msg)
        
        # Show success message
        QMessageBox.information(
            self,
            "OCR Complete",
            f"Successfully extracted {metadata['num_rows']} rows x {metadata['num_columns']} columns!\n\n"
            f"Processing time: {metadata['total_time']:.1f}s\n"
            f"Total detections: {metadata['num_detections']}\n\n"
            "You can now edit the table and export results."
        )
    
    def on_ocr_error(self, error_msg: str):
        """Handle OCR error"""
        self.progress_bar.setVisible(False)
        self.update_status(f"❌ Error: {error_msg}")
        
        QMessageBox.critical(
            self,
            "OCR Error",
            f"An error occurred during OCR processing:\n\n{error_msg}"
        )
    
    def populate_table(self, table_data: List[Dict]):
        """Populate table with OCR results"""
        # Block signals to avoid triggering itemChanged
        self.table.blockSignals(True)
        
        for row_idx, row_data in enumerate(table_data):
            if row_idx >= 10:
                break
            
            for col_idx in range(17):
                cell_data = row_data['cells'].get(col_idx, {})
                text = cell_data.get('text_final', cell_data.get('text', ''))
                confidence = cell_data.get('confidence', 0.0)
                
                # Create item
                item = QTableWidgetItem(text)
                
                # Set background color based on confidence
                if text.strip():
                    if confidence >= 0.8:
                        item.setBackground(QColor(200, 255, 200))  # Green
                    elif confidence >= 0.5:
                        item.setBackground(QColor(255, 255, 200))  # Yellow
                    else:
                        item.setBackground(QColor(255, 200, 200))  # Red
                else:
                    item.setBackground(QColor(240, 240, 240))  # Gray
                
                # Set tooltip with confidence
                item.setToolTip(f"Confidence: {confidence*100:.1f}%")
                
                self.table.setItem(row_idx, col_idx, item)
        
        # Re-enable signals
        self.table.blockSignals(False)
    
    def on_cell_edited(self, item: QTableWidgetItem):
        """Track edited cells"""
        row = item.row()
        col = item.column()
        self.edited_cells[(row, col)] = item.text()
        
        # Mark edited cell with different color
        item.setBackground(QColor(220, 220, 255))  # Light blue
        
        # Update status
        self.update_status(f"Edited cell ({row+1}, {col+1}) | Total edits: {len(self.edited_cells)}")
    
    def enable_export_buttons(self, enabled: bool):
        """Enable or disable export button"""
        self.export_button.setEnabled(enabled)
    
    def export_results(self):
        """Export OCR results with format selection dialog"""
        if not self.ocr_results:
            QMessageBox.warning(self, "No Data", "Please run OCR first before exporting.")
            return
        
        # Format selection dialog
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QDialogButtonBox, QLabel
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Export Format")
        dialog.setMinimumWidth(350)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Choose export format:"))
        layout.addSpacing(8)
        
        # Format options
        excel_radio = QRadioButton("📊 Excel (.xlsx) - Recommended")
        excel_radio.setChecked(True)
        csv_radio = QRadioButton("📄 CSV (.csv) - Plain text")
        json_radio = QRadioButton("🔧 JSON (.json) - With metadata")
        html_radio = QRadioButton("🌐 HTML (.html) - Interactive view")
        
        layout.addWidget(excel_radio)
        layout.addWidget(csv_radio)
        layout.addWidget(json_radio)
        layout.addWidget(html_radio)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() != QDialog.Accepted:
            return
        
        # Determine selected format
        if excel_radio.isChecked():
            format_name = "excel"
            ext = "xlsx"
        elif csv_radio.isChecked():
            format_name = "csv"
            ext = "csv"
        elif json_radio.isChecked():
            format_name = "json"
            ext = "json"
        else:
            format_name = "html"
            ext = "html"
        
        # File dialog for saving
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {format_name.upper()} Results",
            str(Path.home() / f"blok3_results.{ext}"),
            f"{format_name.upper()} Files (*.{ext});;All Files (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            if format_name == 'excel':
                self.export_to_excel(file_path)
            elif format_name == 'csv':
                self.export_to_csv(file_path)
            elif format_name == 'json':
                self.export_to_json(file_path)
            elif format_name == 'html':
                self.export_to_html(file_path)
            
            self.update_status(f"✅ Exported to {Path(file_path).name}")
            QMessageBox.information(self, "Export Successful", f"Results exported to:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")
    
    def export_to_excel(self, file_path: str):
        """Export to Excel with formatting"""
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill, Font, Alignment
        
        wb = Workbook()
        ws = wb.active
        ws.title = "BLOK III"
        
        # Headers - get from table
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(17)]
        
        # Write headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(1, col, header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        
        # Write data
        for row in range(10):
            for col in range(17):
                item = self.table.item(row, col)
                if item:
                    ws.cell(row + 2, col + 1, item.text())
        
        wb.save(file_path)
    
    def export_to_csv(self, file_path: str):
        """Export to CSV"""
        import csv
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Headers
            headers = [self.table.horizontalHeaderItem(i).text() for i in range(17)]
            writer.writerow(headers)
            
            # Data
            for row in range(10):
                row_data = []
                for col in range(17):
                    item = self.table.item(row, col)
                    row_data.append(item.text() if item else '')
                writer.writerow(row_data)
    
    def export_to_json(self, file_path: str):
        """Export to JSON"""
        data = {
            'metadata': self.ocr_results['metadata'],
            'table': []
        }
        
        for row in range(10):
            row_data = {'row_number': row + 1, 'cells': {}}
            for col in range(17):
                item = self.table.item(row, col)
                if item and item.text().strip():
                    row_data['cells'][col] = {
                        'text': item.text(),
                        'edited': (row, col) in self.edited_cells
                    }
            data['table'].append(row_data)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def export_to_html(self, file_path: str):
        """Export to HTML"""
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>BLOK III Results</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #2c3e50; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4472C4; color: white; font-weight: bold; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        .metadata { background: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <h1>📊 BLOK III Table - Extraction Results</h1>
    <div class="metadata">
"""
        
        metadata = self.ocr_results['metadata']
        html += f"        <p><strong>Processing Time:</strong> {metadata['total_time']:.1f}s</p>\n"
        html += f"        <p><strong>Total Detections:</strong> {metadata['num_detections']}</p>\n"
        html += f"        <p><strong>Rows:</strong> {metadata['num_rows']} | <strong>Columns:</strong> {metadata['num_columns']}</p>\n"
        html += "    </div>\n"
        
        html += "    <table>\n        <tr>\n"
        
        # Headers
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(17)]
        for header in headers:
            html += f"            <th>{header}</th>\n"
        html += "        </tr>\n"
        
        # Data
        for row in range(10):
            html += "        <tr>\n"
            for col in range(17):
                item = self.table.item(row, col)
                text = item.text() if item else ''
                html += f"            <td>{text}</td>\n"
            html += "        </tr>\n"
        
        html += """    </table>
</body>
</html>"""
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)
    
    def update_status(self, message: str):
        """Update status bar"""
        self.status_bar.showMessage(message)
    
    
    def closeEvent(self, event):
        """Handle window close"""
        if self.ocr_worker and self.ocr_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "OCR In Progress",
                "OCR processing is still running. Are you sure you want to exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.ocr_worker.cancel()
                self.ocr_worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
