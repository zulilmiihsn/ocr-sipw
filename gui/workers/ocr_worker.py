# worker thread untuk proses ocr di background
# handle multiple file ocr dengan progress reporting

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
from pipeline.utils import calculate_header_y_max, calculate_adaptive_tolerance
from config.settings import gui_settings, mapping_settings
from config.constants import EXPECTED_ROWS
from utils.exceptions import ImageLoadError, TableDetectionError, OCRProcessingError
from utils.logging_config import get_logger

logger = get_logger(__name__)


class OCRWorker(QThread):
    # worker thread untuk proses ocr di background
    # bisa handle banyak file dan laporkan progress lewat signals
    
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, file_paths: List[str]):
        # inisialisasi ocr worker
        # param:
        #   file_paths: list path file gambar yang mau diproses
        super().__init__()
        self.file_paths = file_paths if isinstance(file_paths, list) else [file_paths]
        self.is_cancelled = False
        self.processor = TableProcessor()
    
    def run(self) -> None:
        # jalankan proses ocr untuk semua file
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
        # proses satu gambar dan return data tabel
        # param:
        #   image: gambar input sebagai numpy array
        #   file_idx: index file saat ini
        #   total_files: total jumlah file
        # return:
        #   list dictionary data baris
        try:
            progress_base = 20 + (file_idx / total_files) * 60
            
            # tahap 1: deteksi region tabel
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
            
            # tahap 2: jalankan ocr
            self.progress.emit(
                gui_settings.progress_ocr_start,
                "Melakukan pemindaian OCR..."
            )
            if self.is_cancelled:
                return []
            
            ocr_results = run_full_document_ocr(cropped)
            logger.debug(f"OCR detected {len(ocr_results)} text regions")
            
            # tahap 3: deteksi struktur tabel
            self.progress.emit(
                gui_settings.progress_structure_start,
                "Mendeteksi struktur tabel..."
            )
            if self.is_cancelled:
                return []
            
            all_h_lines, vertical_lines = detect_all_lines(cropped)
            
            # tahap 4: deteksi header dan hitung posisi baris
            h_lines = self._detect_rows(
                ocr_results,
                all_h_lines,
                image_height
            )
            
            # tahap 5: pelajari struktur kolom
            self.progress.emit(
                gui_settings.progress_column_start,
                "Mempelajari struktur kolom..."
            )
            if self.is_cancelled:
                return []
            
            header_groups = detect_header_rows(ocr_results)
            column_structure = learn_column_structure(header_groups, vertical_lines)
            header_y_max = calculate_header_y_max(
                header_groups=header_groups,
                sorted_h_lines=all_h_lines,
                ocr_results=ocr_results,
                image_height=image_height
            )
            
            # tahap 6: mapping deteksi ke cell
            self.progress.emit(
                gui_settings.progress_build_start,
                "Membangun tabel..."
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
            
            # validasi tambahan (keep logic yang ada untuk sekarang)
            # ini bisa di-refactor nanti kalau perlu
            
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
        # deteksi posisi baris dari hasil ocr dan garis horizontal
        # param:
        #   ocr_results: hasil deteksi ocr
        #   all_h_lines: garis horizontal yang terdeteksi
        #   image_height: tinggi gambar yang sudah di-crop
        # return:
        #   list posisi Y dari garis horizontal untuk baris
        sorted_h_lines = sorted(all_h_lines)
        
        # hitung tolerance adaptif pakai utility function
        adaptive_tolerance = calculate_adaptive_tolerance(
            image_height=image_height,
            h_lines=sorted_h_lines
        )
        
        # deteksi batas header pakai utility function
        header_y_max = calculate_header_y_max(
            header_groups=None,
            sorted_h_lines=sorted_h_lines,
            ocr_results=ocr_results,
            image_height=image_height
        )
        
        # kumpulkan center Y dari data (di bawah header)
        data_y_centers = []
        for det in ocr_results:
            y_center = (det['y_min'] + det['y_max']) / 2
            if y_center > header_y_max + 10:
                data_y_centers.append(y_center)
        
        if len(data_y_centers) > 0:
            # kelompokkan deteksi yang berdekatan jadi baris
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
            
            # hitung rata-rata Y untuk setiap grup baris
            row_y_positions = [sum(group) / len(group) for group in row_groups]
            
            # paksa jadi tepat EXPECTED_ROWS baris
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
            
            # bikin garis horizontal
            h_lines = [int(header_y_max + 10)]
            for y in row_y_positions:
                h_lines.append(int(y))
            
            # tambahkan garis bawah
            bottom_line = max(sorted_h_lines) if sorted_h_lines else image_height
            h_lines.append(int(bottom_line))
            
            # hapus duplikat dan urutkan
            h_lines = sorted(list(set(h_lines)))
            
            # pastikan tepat EXPECTED_ROWS + 1 garis
            if len(h_lines) > EXPECTED_ROWS + 1:
                start = h_lines[0]
                end = h_lines[-1]
                step = (end - start) / EXPECTED_ROWS
                h_lines = [int(start + i * step) for i in range(EXPECTED_ROWS + 1)]
        else:
            # fallback: bagi rata
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
    
    def cancel(self) -> None:
        # batalkan proses ocr
        logger.info("Cancelling OCR processing")
        self.is_cancelled = True

