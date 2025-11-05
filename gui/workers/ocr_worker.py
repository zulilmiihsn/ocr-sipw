"""
OCR Worker thread for background processing.
Handles multi-file OCR processing with progress reporting.
"""

import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import cv2
import numpy as np

from PyQt5.QtCore import QThread, pyqtSignal

from pipeline.lib.table_detector import detect_table_region, crop_table
from pipeline.ocr_engine import (
    run_full_document_ocr,
    detect_all_lines,
    detect_header_rows,
    learn_column_structure,
    validate_and_correct_by_template
)
from pipeline.table_processor import TableProcessor
from config.settings import gui_settings, mapping_settings
from config.constants import EXPECTED_ROWS
from utils.exceptions import ImageLoadError, TableDetectionError, OCRProcessingError
from utils.logging_config import get_logger

logger = get_logger(__name__)


class OCRWorker(QThread):
    """
    Worker thread for OCR processing in background.
    Can handle multiple files and reports progress via signals.
    """
    
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, file_paths: List[str]):
        """
        Initialize OCR worker.
        
        Args:
            file_paths: List of image file paths to process
        """
        super().__init__()
        self.file_paths = file_paths if isinstance(file_paths, list) else [file_paths]
        self.is_cancelled = False
        self.processor = TableProcessor()
    
    def run(self) -> None:
        """Execute OCR processing for all files."""
        try:
            start_time = time.time()
            all_results = []
            total_files = len(self.file_paths)
            
            logger.info(f"Starting OCR processing for {total_files} file(s)")
            
            for file_idx, file_path in enumerate(self.file_paths):
                if self.is_cancelled:
                    logger.warning("OCR processing cancelled by user")
                    return
                
                file_num = file_idx + 1
                file_name = Path(file_path).name
                
                progress = int(
                    gui_settings.progress_init + 
                    (file_idx / total_files) * 5
                )
                self.progress.emit(
                    progress,
                    f"[{file_num}/{total_files}] Memuat {file_name}..."
                )
                
                try:
                    image = cv2.imread(str(file_path))
                    if image is None:
                        error_msg = f"Gagal memuat gambar: {file_name}"
                        logger.error(error_msg)
                        self.error.emit(error_msg)
                        continue
                    
                    logger.info(f"Processing file: {file_name}")
                    
                    if self.is_cancelled:
                        return
                    
                    page_results = self._process_single_image(
                        image, file_idx, total_files
                    )
                    
                    if page_results:
                        for row in page_results:
                            row['_source_file'] = file_name
                            row['_source_page'] = 1
                        all_results.extend(page_results)
                        logger.info(
                            f"Extracted {len(page_results)} rows from {file_name}"
                        )
                    
                except Exception as e:
                    error_msg = f"Error processing {file_name}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    self.error.emit(error_msg)
                    continue
            
            if not all_results:
                error_msg = "Tidak ada data yang berhasil diekstrak dari file"
                logger.warning(error_msg)
                self.error.emit(error_msg)
                return
            
            total_time = time.time() - start_time
            self.progress.emit(
                gui_settings.progress_complete,
                "Selesai!"
            )
            
            result = {
                'table': all_results,
                'metadata': {
                    'total_time': total_time,
                    'num_files': total_files,
                    'num_rows': len(all_results)
                }
            }
            
            logger.info(
                f"OCR processing completed: {len(all_results)} rows from "
                f"{total_files} file(s) in {total_time:.2f}s"
            )
            
            self.finished.emit(result)
            
        except Exception as e:
            error_msg = f"Terjadi kesalahan saat memproses OCR: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error.emit(error_msg)
    
    def _process_single_image(
        self,
        image: np.ndarray,
        file_idx: int,
        total_files: int
    ) -> List[Dict[str, Any]]:
        """
        Process a single image and return table data.
        
        Args:
            image: Input image as numpy array
            file_idx: Current file index
            total_files: Total number of files
            
        Returns:
            List of row data dictionaries
        """
        try:
            progress_base = 20 + (file_idx / total_files) * 60
            
            # Stage 1: Detect table region
            self.progress.emit(
                int(progress_base),
                "Mendeteksi region BLOK III..."
            )
            if self.is_cancelled:
                return []
            
            bbox = detect_table_region(image)
            if bbox is None:
                raise TableDetectionError("Gagal mendeteksi region tabel BLOK III")
            
            cropped = crop_table(image, bbox)
            image_height = cropped.shape[0]
            
            # Stage 2: Run OCR
            self.progress.emit(
                gui_settings.progress_ocr_start,
                "Melakukan pemindaian OCR..."
            )
            if self.is_cancelled:
                return []
            
            ocr_results = run_full_document_ocr(cropped)
            logger.debug(f"OCR detected {len(ocr_results)} text regions")
            
            # Stage 3: Detect table structure
            self.progress.emit(
                gui_settings.progress_structure_start,
                "Mendeteksi struktur tabel..."
            )
            if self.is_cancelled:
                return []
            
            all_h_lines, vertical_lines = detect_all_lines(cropped)
            
            # Stage 4: Detect header and calculate row positions
            h_lines = self._detect_rows(
                ocr_results,
                all_h_lines,
                image_height
            )
            
            # Stage 5: Learn column structure
            self.progress.emit(
                gui_settings.progress_column_start,
                "Learning column structure..."
            )
            if self.is_cancelled:
                return []
            
            header_groups = detect_header_rows(ocr_results)
            column_structure = learn_column_structure(header_groups, vertical_lines)
            header_y_max = self._calculate_header_y_max(
                header_groups,
                all_h_lines,
                ocr_results,
                image_height
            )
            
            # Stage 6: Map detections to cells
            self.progress.emit(
                gui_settings.progress_build_start,
                "Building table..."
            )
            if self.is_cancelled:
                return []
            
            table_data = self.processor.process_table(
                ocr_results=ocr_results,
                h_lines=h_lines,
                vertical_lines=vertical_lines,
                header_y_max=header_y_max,
                column_structure=column_structure,
                image_height=image_height
            )
            
            # Additional validation passes (keep existing logic for now)
            # This can be refactored later to use TableProcessor
            
            return table_data
            
        except TableDetectionError as e:
            logger.error(f"Table detection failed: {e}")
            raise
        except OCRProcessingError as e:
            logger.error(f"OCR processing failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing image: {e}", exc_info=True)
            raise OCRProcessingError(f"Failed to process image: {str(e)}") from e
    
    def _detect_rows(
        self,
        ocr_results: List[Dict[str, Any]],
        all_h_lines: List[int],
        image_height: int
    ) -> List[int]:
        """
        Detect row positions from OCR results and horizontal lines.
        
        Args:
            ocr_results: OCR detection results
            all_h_lines: Detected horizontal lines
            image_height: Height of cropped image
            
        Returns:
            List of horizontal line Y positions for rows
        """
        sorted_h_lines = sorted(all_h_lines)
        
        # Calculate adaptive tolerance
        adaptive_tolerance = max(
            mapping_settings.adaptive_tolerance_min,
            int(image_height * mapping_settings.adaptive_tolerance_ratio)
        )
        
        # Detect header boundary
        header_y_max = self._calculate_header_y_max(
            None, sorted_h_lines, ocr_results, image_height
        )
        
        # Collect data Y centers (below header)
        data_y_centers = []
        for det in ocr_results:
            y_center = (det['y_min'] + det['y_max']) / 2
            if y_center > header_y_max + 10:
                data_y_centers.append(y_center)
        
        if len(data_y_centers) > 0:
            # Group nearby detections into rows
            data_y_centers = sorted(data_y_centers)
            row_groups = []
            current_group = [data_y_centers[0]]
            
            for y in data_y_centers[1:]:
                if y - current_group[-1] <= adaptive_tolerance:
                    current_group.append(y)
                else:
                    row_groups.append(current_group)
                    current_group = [y]
            row_groups.append(current_group)
            
            # Calculate average Y for each row group
            row_y_positions = [sum(group) / len(group) for group in row_groups]
            
            # Force exactly EXPECTED_ROWS rows
            if len(row_y_positions) > EXPECTED_ROWS:
                row_y_positions = row_y_positions[:EXPECTED_ROWS]
            elif len(row_y_positions) < EXPECTED_ROWS:
                if len(row_y_positions) >= 2:
                    start_y = row_y_positions[0]
                    end_y = row_y_positions[-1]
                    step = (end_y - start_y) / (EXPECTED_ROWS - 1)
                    row_y_positions = [
                        start_y + i * step for i in range(EXPECTED_ROWS)
                    ]
            
            # Build horizontal lines
            h_lines = [int(header_y_max + 10)]
            for y in row_y_positions:
                h_lines.append(int(y))
            
            # Add bottom line
            bottom_line = max(sorted_h_lines) if sorted_h_lines else image_height
            h_lines.append(int(bottom_line))
            
            # Remove duplicates and sort
            h_lines = sorted(list(set(h_lines)))
            
            # Ensure exactly EXPECTED_ROWS + 1 lines
            if len(h_lines) > EXPECTED_ROWS + 1:
                start = h_lines[0]
                end = h_lines[-1]
                step = (end - start) / EXPECTED_ROWS
                h_lines = [int(start + i * step) for i in range(EXPECTED_ROWS + 1)]
        else:
            # Fallback: divide evenly
            data_region_start = header_y_max + 10
            data_region_end = (
                max(sorted_h_lines) if sorted_h_lines else image_height
            )
            data_height = data_region_end - data_region_start
            row_height = data_height / EXPECTED_ROWS
            
            h_lines = []
            for i in range(EXPECTED_ROWS + 1):
                y = data_region_start + i * row_height
                h_lines.append(int(y))
        
        return h_lines
    
    def _calculate_header_y_max(
        self,
        header_groups: Optional[List[Dict[str, Any]]],
        sorted_h_lines: List[int],
        ocr_results: List[Dict[str, Any]],
        image_height: int
    ) -> int:
        """
        Calculate maximum Y position of header region.
        
        Args:
            header_groups: Header detection groups (optional)
            sorted_h_lines: Sorted horizontal line positions
            ocr_results: OCR detection results
            image_height: Height of cropped image
            
        Returns:
            Maximum Y position of header
        """
        # Use H-lines in top 30% of image
        header_candidates = [
            y for y in sorted_h_lines
            if y < image_height * mapping_settings.header_search_ratio
        ]
        
        if len(header_candidates) >= 1:
            # Use last line in header area (separator)
            header_y_max = header_candidates[-1]
        else:
            # Fallback: use OCR-based detection
            header_y_max = 0
            for det in ocr_results:
                y_center = (det['y_min'] + det['y_max']) / 2
                if y_center < image_height * 0.25:
                    header_y_max = max(header_y_max, det['y_max'])
            
            # Add safety margin
            if header_y_max > 0:
                header_y_max += mapping_settings.header_margin_px
        
        return header_y_max
    
    def cancel(self) -> None:
        """Cancel OCR processing."""
        logger.info("Cancelling OCR processing")
        self.is_cancelled = True

