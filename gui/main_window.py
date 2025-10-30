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
    QStatusBar, QMessageBox, QHeaderView, QApplication, QGroupBox,
    QStyledItemDelegate, QLineEdit, QListWidget, QListWidgetItem, QAbstractItemView,
    QStyle
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QEvent, QRect, QSize
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QFontMetrics

# Import QtAwesome for professional icons
import qtawesome as qta

# Add parent directory to path for pipeline imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.lib.table_detector import detect_table_region, crop_table
from pipeline.ocr_engine import (
    run_full_document_ocr, detect_vertical_lines, detect_horizontal_lines,
    detect_header_rows, learn_column_structure, build_table,
    validate_and_correct_by_template
)


class OCRWorker(QThread):
    """Background worker for OCR processing (supports multi-file/multi-page)"""
    
    # Signals
    progress = pyqtSignal(int, str)  # (percentage, stage_name)
    finished = pyqtSignal(dict)  # OCR results (now includes 'pages' list)
    error = pyqtSignal(str)  # Error message
    
    def __init__(self, file_paths):
        super().__init__()
        # Accept both single file (string) or multiple files (list)
        self.file_paths = file_paths if isinstance(file_paths, list) else [file_paths]
        self.is_cancelled = False
    
    def run(self):
        """Run OCR pipeline in background (supports multi-file/multi-page)"""
        try:
            start_time = time.time()
            
            # Aggregate all results from all files/pages
            all_results = []
            total_files = len(self.file_paths)
            
            # Process each file
            for file_idx, file_path in enumerate(self.file_paths):
                if self.is_cancelled:
                    return
                
                file_num = file_idx + 1
                file_name = Path(file_path).name
                
                # Stage 1: Load Image
                self.progress.emit(
                    int(10 + (file_idx / total_files) * 5),
                    f"[{file_num}/{total_files}] Loading {file_name}..."
                )
                
                # Load image file
                import cv2
                image = cv2.imread(file_path)
                if image is None:
                    self.error.emit(f"Failed to load image: {file_name}")
                    continue
                
                if self.is_cancelled:
                    return
                
                # Process this image
                page_results = self._process_single_image(
                    image, file_idx, 0, total_files, 1
                )
                
                if page_results:
                    # Add source info to each row
                    for row in page_results:
                        row['_source_file'] = file_name
                        row['_source_page'] = 1
                    
                    # Append to aggregated results
                    all_results.extend(page_results)
            
            # All files/pages processed - emit results (no auto-sort)
            if not all_results:
                self.error.emit("No data extracted from any file")
                return
            
            # Calculate total time
            total_time = time.time() - start_time
            
            # Emit aggregated results
            self.progress.emit(100, "Complete!")
            self.finished.emit({
                'table': all_results,
                'metadata': {
                    'total_time': total_time,
                    'num_files': total_files,
                    'num_rows': len(all_results)
                }
            })
            
        except Exception as e:
            self.error.emit(f"OCR Error: {str(e)}")
    
    def _process_single_image(self, image, file_idx, page_idx, total_files, total_pages):
        """Process a single image/page and return table rows"""
        try:
            # Stage 2: Detect BLOK III
            progress_base = 20 + (file_idx / total_files) * 60
            self.progress.emit(int(progress_base), "Detecting BLOK III region...")
            if self.is_cancelled:
                return
            bbox = detect_table_region(image)
            if bbox is None:
                self.error.emit("Failed to detect BLOK III table region")
                return
            cropped = crop_table(image, bbox)
            
            # Stage 3: OCR Scan (Full Document)
            self.progress.emit(30, "Stage 3/6: Performing OCR scan...")
            if self.is_cancelled:
                return
            ocr_results = run_full_document_ocr(cropped)
            
            # Stage 4: Detect Lines
            self.progress.emit(70, "Stage 4/6: Detecting table structure...")
            if self.is_cancelled:
                return
            all_h_lines = detect_horizontal_lines(cropped)
            vertical_lines = detect_vertical_lines(cropped)
            
            # Improved smart row detection using Y-clustering from OCR
            image_height = cropped.shape[0]
            
            # ADAPTIVE TOLERANCE: Scale with image size for robustness
            adaptive_tolerance = max(10, int(image_height * 0.015))  # 1.5% of image height, min 10px
            
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
            
            # Collect Y-centers of data detections (below header)
            data_y_centers = []
            for det in ocr_results:
                y_center = (det['y_min'] + det['y_max']) / 2
                if y_center > header_y_max + 10:  # Below header with margin
                    data_y_centers.append(y_center)
            
            if len(data_y_centers) > 0:
                # Cluster Y positions into rows
                data_y_centers = sorted(data_y_centers)
                
                # Group detections that are close together (same row)
                row_groups = []
                current_group = [data_y_centers[0]]
                tolerance = adaptive_tolerance  # ADAPTIVE tolerance based on image size
                
                for y in data_y_centers[1:]:
                    if y - current_group[-1] <= tolerance:
                        current_group.append(y)
                    else:
                        row_groups.append(current_group)
                        current_group = [y]
                row_groups.append(current_group)
                
                # Get average Y for each row group
                row_y_positions = [sum(group) / len(group) for group in row_groups]
                
                # Force exactly 10 rows by merging or splitting
                if len(row_y_positions) > 10:
                    # Too many rows, keep first 10
                    row_y_positions = row_y_positions[:10]
                elif len(row_y_positions) < 10:
                    # Too few rows, interpolate missing ones
                    if len(row_y_positions) >= 2:
                        start_y = row_y_positions[0]
                        end_y = row_y_positions[-1]
                        step = (end_y - start_y) / 9
                        row_y_positions = [start_y + i * step for i in range(10)]
                
                # Create horizontal lines from row positions
                h_lines = [int(header_y_max + 10)]  # Start line
                for y in row_y_positions:
                    h_lines.append(int(y))
                
                # Add end line
                lines = sorted(all_h_lines)
                bottom_line = max(lines) if lines else image_height
                h_lines.append(int(bottom_line))
                
                # Remove duplicates and sort
                h_lines = sorted(list(set(h_lines)))
                
                # Ensure exactly 11 lines for 10 rows
                if len(h_lines) > 11:
                    # Keep first and last, interpolate middle
                    start = h_lines[0]
                    end = h_lines[-1]
                    step = (end - start) / 10
                    h_lines = [int(start + i * step) for i in range(11)]
            else:
                # Fallback: equal division
                lines = sorted(all_h_lines)
                data_region_start = header_y_max + 10
                data_region_end = max(lines) if lines else image_height
                data_height = data_region_end - data_region_start
                row_height = data_height / 10
                
                h_lines = []
                for i in range(11):
                    y = data_region_start + i * row_height
                    h_lines.append(int(y))
            
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
            
            # Calculate adaptive row tolerance for cell mapping
            if len(h_lines) > 1:
                avg_row_height = (h_lines[-1] - h_lines[0]) / max(len(h_lines) - 1, 1)
                adaptive_row_tolerance = max(8, int(avg_row_height * 0.25))  # 25% of row height, min 8px
            else:
                adaptive_row_tolerance = 10
            
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
                    
                    # Skip if detection is far from this row (ADAPTIVE tolerance)
                    if y_center < row_y_min - adaptive_row_tolerance or y_center > row_y_max + adaptive_row_tolerance:
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
                    
                    # Apply template-based validation for BLOK III accuracy
                    text_final = validate_and_correct_by_template(text, col_idx)
                    
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
            
            # Return table data for this image/page
            return table_data
            
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            return []  # Return empty list on error
    
    def cancel(self):
        """Cancel the operation"""
        self.is_cancelled = True


class HeaderDelegate(QStyledItemDelegate):
    """Custom delegate for table headers with word wrap support"""
    
    def paint(self, painter, option, index):
        """Paint header with word wrapping"""
        painter.save()
        
        # Get text
        text = index.data(Qt.DisplayRole)
        if not text:
            text = ""
        
        # Setup font
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        
        # Draw background
        if option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, QColor("#F1F5F9"))
        else:
            painter.fillRect(option.rect, QColor("#F8FAFC"))
        
        # Draw border
        painter.setPen(QColor("#E2E8F0"))
        painter.drawLine(option.rect.topRight(), option.rect.bottomRight())
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        
        # Draw text with word wrap
        painter.setPen(QColor("#475569"))
        text_rect = option.rect.adjusted(8, 4, -8, -4)
        painter.drawText(
            text_rect,
            Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap,
            text
        )
        
        painter.restore()
    
    def sizeHint(self, option, index):
        """Calculate size hint for wrapped text"""
        text = index.data(Qt.DisplayRole)
        if not text:
            return QSize(100, 50)
        
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        
        fm = QFontMetrics(font)
        text_rect = fm.boundingRect(
            QRect(0, 0, option.rect.width() - 16, 1000),
            Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap,
            text
        )
        
        return QSize(option.rect.width(), max(50, text_rect.height() + 8))


class CellDelegate(QStyledItemDelegate):
    """Custom delegate for table cells - handles Enter key and sizing"""
    
    def createEditor(self, parent, option, index):
        """Create editor that fills the entire cell"""
        editor = QLineEdit(parent)
        editor.setFrame(False)  # Remove border
        return editor
    
    def setEditorData(self, editor, index):
        """Set initial data in editor"""
        value = index.model().data(index, Qt.EditRole)
        editor.setText(str(value) if value else "")
    
    def setModelData(self, editor, model, index):
        """Save data from editor to model"""
        model.setData(index, editor.text(), Qt.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        """Make editor fill entire cell"""
        editor.setGeometry(option.rect)
    
    def eventFilter(self, editor, event):
        """Handle Enter key to commit and move to next cell"""
        if event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                # Commit the data
                self.commitData.emit(editor)
                self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)
                return True
        return super().eventFilter(editor, event)


class CustomTableWidget(QTableWidget):
    """Custom table widget with enhanced navigation and floating row controls"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._moving_after_edit = False
        self.hovered_row = -1
        self.parent_window = None
        
        # Floating buttons (akan dibuat oleh parent window)
        self.add_row_floating_btn = None
        self.remove_row_floating_btn = None
        
        # Enable mouse tracking for vertical header
        self.verticalHeader().setMouseTracking(True)
        self.verticalHeader().viewport().setMouseTracking(True)
        
        # Install event filter on vertical header
        self.verticalHeader().viewport().installEventFilter(self)
    
    def eventFilter(self, obj, event):
        """Handle vertical header hover events"""
        if obj == self.verticalHeader().viewport():
            if event.type() == event.MouseMove:
                # Get row from mouse position
                pos = event.pos()
                row = self.verticalHeader().logicalIndexAt(pos)
                
                if row >= 0 and row < self.rowCount():
                    if self.hovered_row != row:
                        self.hovered_row = row
                        self.show_floating_buttons(row)
                else:
                    self.hide_floating_buttons()
            
            elif event.type() == event.Leave:
                # Hide buttons when mouse leaves vertical header
                self.hide_floating_buttons()
        
        return super().eventFilter(obj, event)
    
    def show_floating_buttons(self, row):
        """Show floating buttons for the hovered row"""
        if self.add_row_floating_btn and self.remove_row_floating_btn:
            # Calculate button position
            header_rect = self.verticalHeader().sectionViewportPosition(row)
            header_height = self.verticalHeader().sectionSize(row)
            
            # Position buttons on the left side of vertical header
            x = 2
            y = header_rect + (header_height - 24) // 2
            
            # Show and position buttons
            self.add_row_floating_btn.setParent(self.verticalHeader().viewport())
            self.remove_row_floating_btn.setParent(self.verticalHeader().viewport())
            
            self.add_row_floating_btn.setGeometry(x, y, 12, 24)
            self.remove_row_floating_btn.setGeometry(x + 12, y, 12, 24)
            
            self.add_row_floating_btn.show()
            self.remove_row_floating_btn.show()
    
    def hide_floating_buttons(self):
        """Hide floating buttons"""
        self.hovered_row = -1
        if self.add_row_floating_btn:
            self.add_row_floating_btn.hide()
        if self.remove_row_floating_btn:
            self.remove_row_floating_btn.hide()
    
    def keyPressEvent(self, event):
        """Override key press for smart navigation"""
        current_row = self.currentRow()
        current_col = self.currentColumn()
        is_editing = self.state() == QTableWidget.EditingState
        
        # Handle Enter key - commit and move to next cell
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if is_editing:
                # Close editor (delegate will commit data)
                self.closeEditor(self.itemDelegate().createEditor(self, None, self.model().index(current_row, current_col)), QStyledItemDelegate.NoHint)
            
            # Move to next cell
            total_cols = self.columnCount()
            total_rows = self.rowCount()
            
            if current_col < total_cols - 1:
                self.setCurrentCell(current_row, current_col + 1)
            elif current_row < total_rows - 1:
                self.setCurrentCell(current_row + 1, 0)
            else:
                self.setCurrentCell(0, 0)
            
            event.accept()
            return
        
        # Arrow key navigation
        elif event.key() == Qt.Key_Up and not is_editing:
            total_rows = self.rowCount()
            new_row = current_row - 1 if current_row > 0 else total_rows - 1
            self.setCurrentCell(new_row, current_col)
            event.accept()
            return
        
        elif event.key() == Qt.Key_Down and not is_editing:
            total_rows = self.rowCount()
            new_row = current_row + 1 if current_row < total_rows - 1 else 0
            self.setCurrentCell(new_row, current_col)
            event.accept()
            return
        
        # Default behavior for other keys
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.ocr_results = None
        self.ocr_worker = None
        self.edited_cells = {}  # Track edited cells
        
        self.init_ui()
    
    def _get_icon(self, name: str, **kwargs):
        """Get icon from QtAwesome"""
        return qta.icon(name, **kwargs)
    
    def load_stylesheet(self):
        """Load modern QSS stylesheet"""
        style_path = Path(__file__).parent / 'styles.qss'
        if style_path.exists():
            with open(style_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("OCR SiPW")
        self.setMinimumSize(1280, 800)
        self.setWindowIcon(self._get_icon('fa5s.table', color='#2563EB'))
        
        # Load QSS stylesheet
        self.load_stylesheet()
        
        # Create central widget (no menu bar for clean interface)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout - professional spacing
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 16)
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
        
        # Export button
        export_btn = QPushButton(" Ekspor Hasil")
        export_btn.setIcon(self._get_icon('fa5s.file-export', color='white'))
        export_btn.setObjectName("exportButton")
        export_btn.clicked.connect(self.export_results)
        export_btn.setEnabled(False)
        export_btn.setMinimumHeight(44)
        self.export_button = export_btn
        main_layout.addWidget(export_btn)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("Siap - Pilih file untuk memulai")
    
    
    def create_file_selection_group(self):
        """Create file selection UI group with interactive file list"""
        group = QGroupBox("Pilih File & Proses")
        layout = QVBoxLayout()
        
        # Top row: Browse button
        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        
        # Browse button
        browse_btn = QPushButton(" Pilih File Gambar")
        browse_btn.setIcon(self._get_icon('fa5s.folder-open', color='#64748B'))
        browse_btn.setObjectName("browse_btn")
        browse_btn.clicked.connect(self.browse_file)
        browse_btn.setMinimumWidth(160)
        browse_btn.setMinimumHeight(40)
        top_row.addWidget(browse_btn)
        
        # Info label
        info_label = QLabel("Drag & drop untuk mengubah urutan")
        info_label.setStyleSheet("font-size: 8pt; color: #94A3B8; font-style: italic;")
        top_row.addWidget(info_label, 1)
        
        layout.addLayout(top_row)
        
        # Interactive file list (drag & drop enabled)
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(120)
        self.file_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.setStyleSheet("""
            QListWidget {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 4px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 3px;
                margin: 2px 0px;
            }
            QListWidget::item:hover {
                background-color: #EFF6FF;
            }
            QListWidget::item:selected {
                background-color: #DBEAFE;
                color: #1E293B;
            }
        """)
        self.file_list.setVisible(False)  # Hidden until files selected
        layout.addWidget(self.file_list)
        
        # Bottom row: Action buttons
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)
        
        # Start OCR button
        self.start_btn = QPushButton(" Mulai OCR")
        self.start_btn.setIcon(self._get_icon('fa5s.play', color='white'))
        self.start_btn.setObjectName("start_btn")
        self.start_btn.clicked.connect(self.start_ocr)
        self.start_btn.setEnabled(False)  # Disabled until file selected
        self.start_btn.setMinimumWidth(130)
        self.start_btn.setMinimumHeight(40)
        bottom_row.addWidget(self.start_btn)
        
        # Sort button
        self.sort_btn = QPushButton(" Urutkan")
        self.sort_btn.setIcon(self._get_icon('fa5s.sort-amount-down', color='#3B82F6'))
        self.sort_btn.setObjectName("sort_btn")
        self.sort_btn.clicked.connect(self.sort_table)
        self.sort_btn.setEnabled(False)  # Disabled until OCR done
        self.sort_btn.setMinimumWidth(130)
        self.sort_btn.setMinimumHeight(40)
        self.sort_btn.setToolTip("Urutkan tabel berdasarkan Kode SLS (↑) dan Sub-SLS (↓)")
        bottom_row.addWidget(self.sort_btn)
        
        # Reset button
        self.reset_btn = QPushButton(" Reset")
        self.reset_btn.setIcon(self._get_icon('fa5s.redo', color='#64748B'))
        self.reset_btn.setObjectName("reset_btn")
        self.reset_btn.clicked.connect(self.reset_all)
        self.reset_btn.setEnabled(False)  # Disabled initially
        self.reset_btn.setMinimumWidth(130)
        self.reset_btn.setMinimumHeight(40)
        bottom_row.addWidget(self.reset_btn)
        
        bottom_row.addStretch()  # Push buttons to the left
        
        layout.addLayout(bottom_row)
        
        group.setLayout(layout)
        return group
    
    def create_table_group(self):
        """Create table UI group"""
        group = QGroupBox("Hasil Ekstraksi Tabel")
        layout = QVBoxLayout()
        
        # Create custom table widget with arrow key navigation and floating controls
        self.table = CustomTableWidget()
        self.table.parent_window = self
        self.table.setColumnCount(16)
        self.table.setRowCount(10)
        
        # Set custom delegate for better cell editing
        self.table.setItemDelegate(CellDelegate())
        
        # Set headers (column names) - WITHOUT "No" column
        headers = [
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
            "Muatan Dominan",
            "Apakah memiliki perubahan batas (reko)?)\n1 = Ya\n2 = Tidak"
        ]
        self.table.setHorizontalHeaderLabels(headers)
        
        # Apply custom header delegate for word wrapping
        header_delegate = HeaderDelegate(self.table)
        self.table.horizontalHeader().setItemDelegate(header_delegate)
        
        # Set vertical headers (row numbers 1-10) - auto-generated
        for i in range(10):
            self.table.setVerticalHeaderItem(i, QTableWidgetItem(str(i + 1)))
        
        # Set vertical header (row numbers) width - COMPACT
        self.table.verticalHeader().setFixedWidth(40)
        
        # Configure horizontal header for responsive behavior
        header = self.table.horizontalHeader()
        
        # Set resize mode: Stretch to fill window width proportionally
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        
        # Enable text wrapping in headers for long labels
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # Set minimum column widths (responsive)
        min_widths = [
            70,   # Kode SLS/Non-SLS
            65,   # Kode Sub-SLS
            100,  # Nama SLS/Non-SLS
            80,   # Perkiraan Jumlah Muatan KK
            60,   # BTT
            70,   # BTT Kosong
            60,   # BKU
            90,   # Bangunan Bukan Tempat Tinggal
            75,   # Perkiraan Jumlah Muatan Usaha
            65,   # Total Muatan
            90,   # Nama Wilayah Konsentrasi
            75,   # Jumlah Shift
            75,   # Jam Operasional
            90,   # Contact - Telepon/Email
            75,   # Contact - Muatan Dominan
            65    # Perubahan batas (reko)
        ]
        
        for i, min_width in enumerate(min_widths):
            header.setMinimumSectionSize(min_width)
            header.resizeSection(i, min_width)
        
        # Enable single-click editing
        self.table.setEditTriggers(
            QTableWidget.CurrentChanged |  # Single-click to edit
            QTableWidget.SelectedClicked |  # Click on selected cell
            QTableWidget.EditKeyPressed |   # Any key press
            QTableWidget.AnyKeyPressed      # Start typing immediately
        )
        self.table.itemChanged.connect(self.on_cell_edited)
        
        # Navigation handled by CustomTableWidget.keyPressEvent
        
        # Create floating buttons for row control (hidden by default)
        self.create_floating_row_buttons()
        
        layout.addWidget(self.table)
        
        group.setLayout(layout)
        return group
    
    def create_floating_row_buttons(self):
        """Create floating add/remove buttons for table rows"""
        # Add button (tiny, floating)
        add_btn = QPushButton()
        add_btn.setIcon(self._get_icon('fa5s.plus', color='#10B981', scale_factor=0.6))
        add_btn.setToolTip("Tambah baris di bawah")
        add_btn.setObjectName("floating_btn")
        add_btn.clicked.connect(self.add_row_at_hover)
        add_btn.hide()
        
        # Remove button (tiny, floating)
        remove_btn = QPushButton()
        remove_btn.setIcon(self._get_icon('fa5s.minus', color='#EF4444', scale_factor=0.6))
        remove_btn.setToolTip("Hapus baris ini")
        remove_btn.setObjectName("floating_btn")
        remove_btn.clicked.connect(self.remove_row_at_hover)
        remove_btn.hide()
        
        # Assign to table
        self.table.add_row_floating_btn = add_btn
        self.table.remove_row_floating_btn = remove_btn
    
    
    def browse_file(self):
        """Open file browser dialog (supports multi-select images only)"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Pilih File Gambar (Multi-select untuk batch)",
            str(Path.home()),
            "File Gambar (*.png *.jpg *.jpeg);;Semua File (*.*)"
        )
        
        if file_paths:
            self.current_files = file_paths
            
            # Populate interactive file list
            self.populate_file_list(file_paths)
            
            # Show file list
            self.file_list.setVisible(True)
            
            # Update status
            if len(file_paths) == 1:
                self.update_status(f"✓ 1 file dimuat - Klik 'Mulai OCR' untuk memproses")
            else:
                self.update_status(f"✓ {len(file_paths)} file dimuat - Drag & drop untuk mengubah urutan")
            
            # Enable Start and Reset buttons
            self.start_btn.setEnabled(True)
            self.reset_btn.setEnabled(True)
    
    def populate_file_list(self, file_paths):
        """Populate file list with icons and names"""
        self.file_list.clear()
        
        for file_path in file_paths:
            file_name = Path(file_path).name
            item = QListWidgetItem()
            
            # Set icon based on file extension
            ext = Path(file_path).suffix.lower()
            if ext in ['.png']:
                icon = self._get_icon('fa5s.file-image', color='#8B5CF6')  # Purple for PNG
            elif ext in ['.jpg', '.jpeg']:
                icon = self._get_icon('fa5s.file-image', color='#3B82F6')  # Blue for JPG
            else:
                icon = self._get_icon('fa5s.file', color='#64748B')  # Gray for others
            
            item.setIcon(icon)
            item.setText(file_name)
            item.setData(Qt.UserRole, file_path)  # Store full path in data
            item.setToolTip(file_path)  # Show full path on hover
            
            self.file_list.addItem(item)
    
    def get_ordered_file_paths(self):
        """Get file paths in current list order (after drag & drop)"""
        file_paths = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = item.data(Qt.UserRole)
            file_paths.append(file_path)
        return file_paths
    
    
    def start_ocr(self):
        """Start OCR processing (supports multi-file/multi-page)"""
        if not hasattr(self, 'current_files') or not self.current_files:
            return
        
        # Get file paths in current list order (respects drag & drop reorder)
        ordered_files = self.get_ordered_file_paths()
        
        # Disable Start button and export button during processing
        self.start_btn.setEnabled(False)
        self.enable_export_buttons(False)
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Menginisialisasi...")
        
        # Clear table
        self.table.clearContents()
        self.edited_cells.clear()
        
        # Start worker thread with ordered list of files (after drag & drop)
        self.ocr_worker = OCRWorker(ordered_files)
        self.ocr_worker.progress.connect(self.on_progress)
        self.ocr_worker.finished.connect(self.on_ocr_finished)
        self.ocr_worker.error.connect(self.on_ocr_error)
        self.ocr_worker.start()
        
        self.update_status("Memproses...")
    
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
        
        # Re-enable Start button, Sort button, and export button
        self.start_btn.setEnabled(True)
        self.sort_btn.setEnabled(True)
        self.enable_export_buttons(True)
        
        # Update status
        metadata = results['metadata']
        status_msg = (
            f"✓ Selesai! {metadata['num_rows']} baris diekstrak dalam "
            f"{metadata['total_time']:.1f} detik | Siap ekspor"
        )
        self.update_status(status_msg)
        
        # Show success message
        num_files = metadata.get('num_files', 1)
        file_text = f"{num_files} file" if num_files > 1 else "1 file"
        
        QMessageBox.information(
            self,
            "OCR Selesai",
            f"Berhasil mengekstrak {metadata['num_rows']} baris dari {file_text}!\n\n"
            f"Waktu proses: {metadata['total_time']:.1f} detik\n\n"
            "Data sudah diurutkan otomatis:\n"
            "• Kode SLS (ascending)\n"
            "• Kode Sub-SLS (descending)\n\n"
            "Anda dapat mengedit tabel dan mengekspor hasil."
        )
    
    def on_ocr_error(self, error_msg: str):
        """Handle OCR error"""
        self.progress_bar.setVisible(False)
        
        # Re-enable Start button on error
        self.start_btn.setEnabled(True)
        
        self.update_status(f"✗ Error: {error_msg}")
        
        QMessageBox.critical(
            self,
            "Error OCR",
            f"Terjadi kesalahan saat memproses OCR:\n\n{error_msg}"
        )
    
    def populate_table(self, table_data: List[Dict]):
        """Populate table with OCR results (supports multi-page, dynamic row count)"""
        # Block signals to avoid triggering itemChanged
        self.table.blockSignals(True)
        
        # Update table row count dynamically
        num_rows = len(table_data)
        self.table.setRowCount(num_rows)
        
        # Update vertical headers (row numbers 1, 2, 3, ...)
        for i in range(num_rows):
            self.table.setVerticalHeaderItem(i, QTableWidgetItem(str(i + 1)))
        
        # Populate cells
        for row_idx, row_data in enumerate(table_data):
            # Skip column 0 (No), start from column 1 (Kode SLS/Non-SLS)
            for ocr_col_idx in range(1, 17):  # OCR columns 1-16
                gui_col_idx = ocr_col_idx - 1  # GUI columns 0-15 (shifted left)
                
                cell_data = row_data['cells'].get(ocr_col_idx, {})
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
                
                self.table.setItem(row_idx, gui_col_idx, item)
        
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
    
    def add_row_at_hover(self):
        """Add a new row below the hovered row"""
        hovered_row = self.table.hovered_row
        if hovered_row < 0:
            return
        
        # Insert row below hovered row
        insert_pos = hovered_row + 1
        self.table.insertRow(insert_pos)
        
        # Initialize empty cells with white background
        for col in range(self.table.columnCount()):
            item = QTableWidgetItem("")
            item.setBackground(QColor(255, 255, 255))
            self.table.setItem(insert_pos, col, item)
        
        # Update all vertical headers (row numbers)
        for i in range(self.table.rowCount()):
            self.table.setVerticalHeaderItem(i, QTableWidgetItem(str(i + 1)))
        
        # Update status
        self.update_status(f"✓ Baris ditambahkan di posisi {insert_pos + 1} (Total: {self.table.rowCount()} baris)")
        
        # Scroll to new row
        self.table.scrollToItem(self.table.item(insert_pos, 0))
        
        # Hide floating buttons after action
        self.table.hide_floating_buttons()
    
    def remove_row_at_hover(self):
        """Remove the hovered row (instant, no confirmation)"""
        hovered_row = self.table.hovered_row
        if hovered_row < 0:
            return
        
        # Hide buttons first
        self.table.hide_floating_buttons()
        
        # Delete row instantly
        self.table.removeRow(hovered_row)
        
        # Update vertical headers (row numbers)
        for i in range(self.table.rowCount()):
            self.table.setVerticalHeaderItem(i, QTableWidgetItem(str(i + 1)))
        
        # Update status
        self.update_status(f"✓ Baris {hovered_row + 1} dihapus (Total: {self.table.rowCount()} baris)")
    
    def sort_table(self):
        """Sort table by Kode SLS (ASC) and Sub-SLS (DESC)"""
        # Block signals to prevent triggering itemChanged during sorting
        self.table.blockSignals(True)
        
        # Extract all rows data
        rows_data = []
        num_rows = self.table.rowCount()
        num_cols = self.table.columnCount()
        
        for row in range(num_rows):
            row_data = []
            for col in range(num_cols):
                item = self.table.item(row, col)
                row_data.append({
                    'text': item.text() if item else '',
                    'background': item.background() if item else QColor(255, 255, 255),
                    'tooltip': item.toolTip() if item else ''
                })
            rows_data.append(row_data)
        
        # Sort rows by Kode SLS (col 0) ASC, then Sub-SLS (col 1) DESC
        def sort_key(row):
            # Column 0: Kode SLS (ascending)
            col0_text = row[0]['text']
            col0_val = int(''.join(c for c in col0_text if c.isdigit()) or '0')
            
            # Column 1: Kode Sub-SLS (descending - negative for DESC)
            col1_text = row[1]['text']
            col1_val = int(''.join(c for c in col1_text if c.isdigit()) or '0')
            
            return (col0_val, -col1_val)  # ASC, DESC
        
        rows_data.sort(key=sort_key)
        
        # Repopulate table with sorted data
        for row_idx, row_data in enumerate(rows_data):
            # Update row number in vertical header
            self.table.setVerticalHeaderItem(row_idx, QTableWidgetItem(str(row_idx + 1)))
            
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(cell_data['text'])
                item.setBackground(cell_data['background'])
                item.setToolTip(cell_data['tooltip'])
                self.table.setItem(row_idx, col_idx, item)
        
        # Re-enable signals
        self.table.blockSignals(False)
        
        # Update status
        self.update_status("✓ Tabel diurutkan otomatis (Kode SLS ↑, Sub-SLS ↓)")
    
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
        dialog.setWindowTitle("Pilih Format Ekspor")
        dialog.setMinimumWidth(350)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Pilih format ekspor:"))
        layout.addSpacing(8)
        
        # Format options
        excel_radio = QRadioButton("Excel (.xlsx) - Disarankan")
        excel_radio.setChecked(True)
        csv_radio = QRadioButton("CSV (.csv) - Teks biasa")
        json_radio = QRadioButton("JSON (.json) - Dengan metadata")
        html_radio = QRadioButton("HTML (.html) - Tampilan interaktif")
        
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
            
            self.update_status(f"✓ Diekspor ke {Path(file_path).name}")
            QMessageBox.information(self, "Ekspor Berhasil", f"Hasil diekspor ke:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error Ekspor", f"Gagal mengekspor:\n{str(e)}")
    
    def export_to_excel(self, file_path: str):
        """Export to Excel with formatting (includes No column)"""
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill, Font, Alignment
        
        wb = Workbook()
        ws = wb.active
        ws.title = "BLOK III"
        
        # Headers - prepend "No" column
        headers = ["No"] + [self.table.horizontalHeaderItem(i).text() for i in range(16)]
        
        # Write headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(1, col, header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        
        # Write data (dynamic row count)
        num_rows = self.table.rowCount()
        for row in range(num_rows):
            # Write row number (No column)
            ws.cell(row + 2, 1, row + 1)
            
            # Write remaining columns
            for col in range(16):
                item = self.table.item(row, col)
                if item:
                    ws.cell(row + 2, col + 2, item.text())
        
        wb.save(file_path)
    
    def export_to_csv(self, file_path: str):
        """Export to CSV (includes No column)"""
        import csv
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Headers - prepend "No"
            headers = ["No"] + [self.table.horizontalHeaderItem(i).text() for i in range(16)]
            writer.writerow(headers)
            
            # Data (dynamic row count)
            num_rows = self.table.rowCount()
            for row in range(num_rows):
                row_data = [row + 1]  # Start with row number
                for col in range(16):
                    item = self.table.item(row, col)
                    row_data.append(item.text() if item else '')
                writer.writerow(row_data)
    
    def export_to_json(self, file_path: str):
        """Export to JSON (includes No column)"""
        data = {
            'metadata': self.ocr_results['metadata'],
            'table': []
        }
        
        # Dynamic row count
        num_rows = self.table.rowCount()
        for row in range(num_rows):
            row_data = {'row_number': row + 1, 'cells': {}}
            
            # Add "No" as column 0
            row_data['cells'][0] = {
                'text': str(row + 1),
                'edited': False
            }
            
            # Add remaining columns (shifted by 1)
            for col in range(16):
                item = self.table.item(row, col)
                if item and item.text().strip():
                    row_data['cells'][col + 1] = {
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
    <h1>BLOK III Table - Extraction Results</h1>
    <div class="metadata">
"""
        
        metadata = self.ocr_results['metadata']
        html += f"        <p><strong>Processing Time:</strong> {metadata['total_time']:.1f}s</p>\n"
        html += f"        <p><strong>Total Files:</strong> {metadata.get('num_files', 1)}</p>\n"
        html += f"        <p><strong>Total Rows:</strong> {metadata['num_rows']}</p>\n"
        html += "    </div>\n"
        
        html += "    <table>\n        <tr>\n"
        
        # Headers - prepend "No"
        headers = ["No"] + [self.table.horizontalHeaderItem(i).text() for i in range(16)]
        for header in headers:
            html += f"            <th>{header}</th>\n"
        html += "        </tr>\n"
        
        # Data (dynamic row count)
        num_rows = self.table.rowCount()
        for row in range(num_rows):
            html += "        <tr>\n"
            # Add row number
            html += f"            <td>{row + 1}</td>\n"
            # Add remaining columns
            for col in range(16):
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
    
    def reset_all(self):
        """Reset all data and UI to initial state"""
        # Confirm reset
        reply = QMessageBox.question(
            self,
            "Konfirmasi Reset",
            "Apakah Anda yakin ingin mereset?\n\nIni akan menghapus:\n• File yang dipilih\n• Hasil OCR\n• Data tabel\n• Semua editan",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        # Stop OCR worker if running
        if self.ocr_worker and self.ocr_worker.isRunning():
            self.ocr_worker.cancel()
            self.ocr_worker.wait()
        
        # Clear file selection
        self.current_files = []
        self.file_list.clear()
        self.file_list.setVisible(False)
        
        # Clear OCR results
        self.ocr_results = None
        self.edited_cells.clear()
        
        # Clear table and reset to default 10 rows
        self.table.clearContents()
        self.table.setRowCount(10)
        for i in range(10):
            self.table.setVerticalHeaderItem(i, QTableWidgetItem(str(i + 1)))
        
        # Hide progress bar
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        
        # Disable buttons
        self.start_btn.setEnabled(False)
        self.sort_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)
        self.enable_export_buttons(False)
        
        # Update status
        self.update_status("Siap - Pilih file untuk memulai")
        
        QMessageBox.information(
            self,
            "Reset Selesai",
            "Semua data telah dihapus.\n\nAnda dapat memilih file baru untuk diproses."
        )
    
    
    def closeEvent(self, event):
        """Handle window close"""
        if self.ocr_worker and self.ocr_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "OCR Sedang Berjalan",
                "Proses OCR masih berjalan. Apakah Anda yakin ingin keluar?",
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
