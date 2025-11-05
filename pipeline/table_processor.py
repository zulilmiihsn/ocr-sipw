# module untuk pemrosesan tabel: mapping cell ocr dan validasi
# dipisahkan dari main_window.py untuk separation of concerns yang lebih baik

import re
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

from config.constants import (
    NUMERIC_COLS,
    MANDATORY_NUMERIC_COLS,
    COL_CONTACT_PERSON,
    COL_MUATAN_DOMINAN,
    COL_RT_RW,
    COL_NAMA_WILAYAH,
)
from config.settings import mapping_settings
from pipeline.ocr_engine import validate_and_correct_by_template
from pipeline.utils import calculate_adaptive_tolerance
from utils.exceptions import OCRProcessingError
from utils.logging_config import get_logger

logger = get_logger(__name__)

# regex pattern yang sudah dikompilasi (lebih cepat)
PHONE_PATTERN = re.compile(r'(08\d{8,11}|\+62\d{9,12})')


class TableProcessor:
    # proses hasil ocr dan mapping ke cell tabel
    
    def __init__(self):
        self.settings = mapping_settings
    
    def process_table(
        self,
        ocr_results: List[Dict[str, Any]],
        h_lines: List[int],
        vertical_lines: List[int],
        header_y_max: int,
        column_structure: List[Dict[str, Any]],
        image_height: int
    ) -> List[Dict[str, Any]]:
        # pipeline utama untuk mapping deteksi ocr ke cell tabel
        # param:
        #   ocr_results: list dictionary hasil deteksi ocr
        #   h_lines: posisi garis horizontal
        #   vertical_lines: posisi garis vertikal
        #   header_y_max: posisi Y maksimum dari header
        #   column_structure: struktur kolom dari pembelajaran header
        #   image_height: tinggi gambar yang sudah di-crop
        # return:
        #   list dictionary data baris
        try:
            # hitung tolerance adaptif pakai utility function
            adaptive_tolerance = calculate_adaptive_tolerance(
                image_height=image_height,
                h_lines=h_lines
            )
            
            # mapping deteksi ke cell
            cells = self._map_detections_to_cells(
                ocr_results,
                h_lines,
                column_structure,
                header_y_max,
                adaptive_tolerance
            )
            
            # isi kolom yang wajib
            self._fill_mandatory_columns(
                cells,
                ocr_results,
                h_lines,
                column_structure,
                header_y_max,
                adaptive_tolerance
            )
            
            # validasi dan perbaiki baris
            self._validate_and_correct_rows(
                cells,
                h_lines,
                column_structure,
                header_y_max
            )
            
            # bikin struktur tabel akhir
            table_data = self._build_table_data(
                cells,
                h_lines,
                column_structure,
                header_y_max
            )
            
            return table_data
            
        except Exception as e:
            logger.error(f"Error processing table: {e}", exc_info=True)
            raise OCRProcessingError(f"Failed to process table: {str(e)}") from e
    
    def _map_detections_to_cells(
        self,
        ocr_results: List[Dict[str, Any]],
        h_lines: List[int],
        column_structure: List[Dict[str, Any]],
        header_y_max: int,
        adaptive_tolerance: int
    ) -> Dict[Tuple[int, int], Dict[str, Any]]:
        # mapping deteksi ocr ke cell tabel pakai fuzzy matching
        cells = defaultdict(lambda: {'detections': []})
        
        # bikin spatial index untuk akses cepat
        row_ranges = [(h_lines[i], h_lines[i+1], i) for i in range(len(h_lines)-1)]
        col_ranges = [
            (col['x_left'], col['x_right'], idx)
            for idx, col in enumerate(column_structure)
        ]
        
        # mapping setiap deteksi
        for det in ocr_results:
            det_center_x = (det['x_min'] + det['x_max']) / 2
            det_center_y = (det['y_min'] + det['y_max']) / 2
            
            # skip header
            if det_center_y <= header_y_max:
                continue
            
            # cari baris kandidat
            candidate_rows = self._find_candidate_rows(
                det_center_y, row_ranges, adaptive_tolerance
            )
            
            # coba strict X matching dulu
            matched_col = self._find_strict_x_match(det_center_x, column_structure)
            
            if matched_col >= 0:
                # ketemu kolom yang pas, cari baris terbaik
                best_row = self._find_best_row_for_column(
                    det,
                    matched_col,
                    candidate_rows,
                    h_lines,
                    column_structure,
                    adaptive_tolerance
                )
                
                if best_row >= 0:
                    cells[(best_row, matched_col)]['detections'].append(det)
                    continue
            
            # fallback: pakai fuzzy matching
            self._fuzzy_match_detection(
                det,
                candidate_rows,
                col_ranges,
                h_lines,
                column_structure,
                cells,
                adaptive_tolerance
            )
        
        # gabungkan deteksi di cell yang sama
        self._merge_cell_detections(cells)
        
        return cells
    
    def _find_candidate_rows(
        self,
        det_center_y: float,
        row_ranges: List[Tuple[int, int, int]],
        tolerance: int
    ) -> List[int]:
        # cari baris kandidat untuk sebuah deteksi
        candidates = []
        for y_min, y_max, idx in row_ranges:
            if y_min - tolerance <= det_center_y <= y_max + tolerance:
                candidates.append(idx)
        return candidates
    
    def _find_strict_x_match(
        self,
        det_center_x: float,
        column_structure: List[Dict[str, Any]]
    ) -> int:
        # cari kolom yang pas berdasarkan posisi X
        for col_idx, col in enumerate(column_structure):
            if col['x_left'] <= det_center_x < col['x_right']:
                return col_idx
        return -1
    
    def _find_best_row_for_column(
        self,
        det: Dict[str, Any],
        col_idx: int,
        candidate_rows: List[int],
        h_lines: List[int],
        column_structure: List[Dict[str, Any]],
        tolerance: int
    ) -> int:
        # cari baris terbaik untuk deteksi dengan kolom yang sudah diketahui
        best_row = -1
        best_score = 0.0
        
        det_center_y = (det['y_min'] + det['y_max']) / 2
        
        for row_idx in candidate_rows:
            row_y_min = h_lines[row_idx]
            row_y_max = h_lines[row_idx + 1]
            
            if row_y_min - tolerance <= det_center_y <= row_y_max + tolerance:
                col_x_min = column_structure[col_idx]['x_left']
                col_x_max = column_structure[col_idx]['x_right']
                cell_box = (col_x_min, row_y_min, col_x_max, row_y_max)
                
                score = self._fuzzy_score(
                    det, cell_box, det['confidence'], col_idx
                )
                
                if score > best_score:
                    best_score = score
                    best_row = row_idx
        
        return best_row
    
    def _fuzzy_match_detection(
        self,
        det: Dict[str, Any],
        candidate_rows: List[int],
        col_ranges: List[Tuple[int, int, int]],
        h_lines: List[int],
        column_structure: List[Dict[str, Any]],
        cells: Dict[Tuple[int, int], Dict[str, Any]],
        tolerance: int
    ) -> None:
        # lakukan fuzzy matching untuk deteksi yang ambigu
        # cari kolom kandidat (yang overlap)
        candidate_cols = []
        for x_min, x_max, idx in col_ranges:
            if not (det['x_max'] < x_min or det['x_min'] > x_max):
                candidate_cols.append(idx)
        
        best_score = 0.0
        best_row = -1
        best_col = -1
        
        for row_idx in candidate_rows:
            row_y_min = h_lines[row_idx]
            row_y_max = h_lines[row_idx + 1]
            
            for col_idx in candidate_cols:
                col_x_min = column_structure[col_idx]['x_left']
                col_x_max = column_structure[col_idx]['x_right']
                cell_box = (col_x_min, row_y_min, col_x_max, row_y_max)
                
                score = self._fuzzy_score(
                    det, cell_box, det['confidence'], col_idx
                )
                
                if score > best_score and score > self.settings.fuzzy_score_threshold:
                    best_score = score
                    best_row = row_idx
                    best_col = col_idx
        
        if best_row >= 0 and best_col >= 0:
            cells[(best_row, best_col)]['detections'].append(det)
    
    def _fuzzy_score(
        self,
        det: Dict[str, Any],
        cell_box: Tuple[int, int, int, int],
        confidence: float,
        column_index: int
    ) -> float:
        # hitung skor fuzzy matching untuk assignment cell
        det_box = (det['x_min'], det['y_min'], det['x_max'], det['y_max'])
        cell_x_min, cell_y_min, cell_x_max, cell_y_max = cell_box
        
        det_center_x = (det['x_min'] + det['x_max']) / 2
        det_center_y = (det['y_min'] + det['y_max']) / 2
        
        cell_width = cell_x_max - cell_x_min
        cell_height = cell_y_max - cell_y_min
        cell_center_x = (cell_x_min + cell_x_max) / 2
        cell_center_y = (cell_y_min + cell_y_max) / 2
        
        # skor posisi center
        in_x = cell_x_min <= det_center_x < cell_x_max
        in_y = cell_y_min <= det_center_y < cell_y_max
        
        is_important_col = column_index in (COL_CONTACT_PERSON, COL_MUATAN_DOMINAN)
        
        if is_important_col:
            if in_x and in_y:
                center_score = 1.0
            elif in_y:
                if det_center_x < cell_x_min:
                    dist = cell_x_min - det_center_x
                    center_score = max(0.0, 1.0 - (dist / cell_width) * 2)
                else:
                    dist = det_center_x - cell_x_max
                    center_score = max(0.0, 1.0 - (dist / cell_width) * 2)
            else:
                center_score = 0.0
            center_weight = self.settings.center_weight_important
        else:
            center_score = 1.0 if (in_x and in_y) else 0.0
            center_weight = self.settings.center_weight_normal
        
        # skor IoU (Intersection over Union)
        iou = self._calculate_iou(det_box, cell_box)
        
        # skor jarak
        distance = ((det_center_x - cell_center_x)**2 + 
                   (det_center_y - cell_center_y)**2)**0.5
        max_distance = ((cell_width/2)**2 + (cell_height/2)**2)**0.5
        distance_score = (
            1.0 - min(distance / max_distance, 1.0)
            if max_distance > 0 else 0.0
        )
        
        # gabungkan skor
        if is_important_col:
            total_score = (
                center_score * center_weight +
                iou * self.settings.iou_weight_important +
                distance_score * self.settings.distance_weight_important +
                confidence * self.settings.confidence_weight
            )
        else:
            total_score = (
                center_score * center_weight +
                iou * self.settings.iou_weight_normal +
                distance_score * self.settings.distance_weight_normal +
                confidence * self.settings.confidence_weight
            )
        
        # tambahkan rule prior
        rule_prior = self._compute_rule_prior(
            det.get('text', ''), column_index
        )
        total_score += rule_prior
        
        return total_score
    
    def _calculate_iou(
        self,
        box1: Tuple[int, int, int, int],
        box2: Tuple[int, int, int, int]
    ) -> float:
        # hitung Intersection over Union (IoU) dari dua box
        x1_min, y1_min, x1_max, y1_max = box1
        x2_min, y2_min, x2_max, y2_max = box2
        
        inter_x_min = max(x1_min, x2_min)
        inter_y_min = max(y1_min, y2_min)
        inter_x_max = min(x1_max, x2_max)
        inter_y_max = min(y1_max, y2_max)
        
        if inter_x_max < inter_x_min or inter_y_max < inter_y_min:
            return 0.0
        
        inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
        
        box1_area = (x1_max - x1_min) * (y1_max - y1_min)
        box2_area = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = box1_area + box2_area - inter_area
        
        return inter_area / union_area if union_area > 0 else 0.0
    
    def _compute_rule_prior(self, text_value: str, column_index: int) -> float:
        # hitung rule-based prior untuk matching konten kolom
        if not text_value:
            return 0.0
        
        t = str(text_value).strip()
        t_clean = self._clean_text(t)
        t_upper = t.upper()
        is_digits = t_clean.isdigit()
        
        # kolom 15 (Contact Person)
        if column_index == COL_CONTACT_PERSON:
            phone_match = PHONE_PATTERN.match(t_clean)
            has_email = '@' in t or t.startswith('/')
            if phone_match or has_email:
                return 0.25
            if is_digits and 10 <= len(t_clean) <= 13:
                return 0.20
            return 0.0
        
        # kolom 16 (Muatan Dominan)
        if column_index == COL_MUATAN_DOMINAN:
            if len(t_clean) == 1 and t_clean.isdigit() and t_clean in '123456789':
                return 0.30
            if is_digits and len(t_clean) >= 10:
                return -0.20  # penalty
            return 0.0
        
        # kolom 3 (RT/RW)
        if column_index == COL_RT_RW:
            has_rt = 'RT' in t_upper
            has_rw = 'RW' in t_upper
            if has_rt and has_rw:
                return 0.15
            if has_rt or has_rw:
                return 0.10
            return 0.0
        
        # kolom numerik
        if column_index in NUMERIC_COLS:
            return 0.12 if is_digits else 0.0
        
        # kolom 11 (Nama Wilayah)
        if column_index == COL_NAMA_WILAYAH:
            return 0.08 if not is_digits else 0.0
        
        return 0.0
    
    def _clean_text(self, text: str) -> str:
        # bersihkan text dengan hapus spasi dan separator umum
        return text.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    
    def _merge_cell_detections(
        self,
        cells: Dict[Tuple[int, int], Dict[str, Any]]
    ) -> None:
        # gabungkan beberapa deteksi di cell yang sama
        for (row, col), cell in cells.items():
            dets = cell['detections']
            if len(dets) == 1:
                cell['text'] = dets[0]['text']
                cell['confidence'] = dets[0]['confidence']
            else:
                dets.sort(key=lambda d: d['x_min'])
                cell['text'] = ' '.join(d['text'] for d in dets)
                cell['confidence'] = sum(d['confidence'] for d in dets) / len(dets)
    
    def _fill_mandatory_columns(
        self,
        cells: Dict[Tuple[int, int], Dict[str, Any]],
        ocr_results: List[Dict[str, Any]],
        h_lines: List[int],
        column_structure: List[Dict[str, Any]],
        header_y_max: int,
        adaptive_tolerance: int
    ) -> None:
        # isi kolom numerik wajib yang kosong pakai deteksi overlap
        for row_idx in range(len(h_lines) - 1):
            y_center = (h_lines[row_idx] + h_lines[row_idx + 1]) / 2
            if y_center <= header_y_max:
                continue
            
            row_y_min = h_lines[row_idx]
            row_y_max = h_lines[row_idx + 1]
            
            for col_idx in MANDATORY_NUMERIC_COLS:
                key = (row_idx, col_idx)
                if cells.get(key, {}).get('text'):
                    continue
                
                col_x_min = column_structure[col_idx]['x_left']
                col_x_max = column_structure[col_idx]['x_right']
                cell_box = (col_x_min, row_y_min, col_x_max, row_y_max)
                
                best_det = None
                best_score = 0.0
                
                for det in ocr_results:
                    det_center_y = (det['y_min'] + det['y_max']) / 2
                    if det_center_y <= header_y_max:
                        continue
                    
                    if (det['y_max'] < row_y_min - adaptive_tolerance or
                        det['y_min'] > row_y_max + adaptive_tolerance):
                        continue
                    
                    if (det['x_max'] < (col_x_min - 8) or
                        det['x_min'] > (col_x_max + 8)):
                        continue
                    
                    iou = self._calculate_iou(
                        (det['x_min'], det['y_min'], det['x_max'], det['y_max']),
                        cell_box
                    )
                    if iou <= 0.01:
                        continue
                    
                    prior = self._compute_rule_prior(det.get('text', ''), col_idx)
                    
                    det_center_x = (det['x_min'] + det['x_max']) / 2
                    cell_cx = (col_x_min + col_x_max) / 2
                    cell_cy = (row_y_min + row_y_max) / 2
                    cell_w = max(1, col_x_max - col_x_min)
                    cell_h = max(1, row_y_max - row_y_min)
                    max_d = ((cell_w/2)**2 + (cell_h/2)**2)**0.5
                    dist = ((det_center_x - cell_cx)**2 + 
                           (det_center_y - cell_cy)**2)**0.5
                    dist_score = 1.0 - min(dist / max_d, 1.0)
                    
                    txt = str(det.get('text', '')).strip()
                    is_digits = self._clean_text(txt).isdigit()
                    digits_bonus = 0.06 if is_digits else 0.0
                    
                    score = iou * 0.6 + dist_score * 0.28 + prior * 0.4 + digits_bonus
                    
                    if score > best_score:
                        best_score = score
                        best_det = det
                
                if best_det and best_score > 0.12:
                    cells[key]['detections'] = [best_det]
                    cells[key]['text'] = best_det['text']
                    cells[key]['confidence'] = best_det['confidence']
    
    def _validate_and_correct_rows(
        self,
        cells: Dict[Tuple[int, int], Dict[str, Any]],
        h_lines: List[int],
        column_structure: List[Dict[str, Any]],
        header_y_max: int
    ) -> None:
        # validasi dan perbaiki pola baris (swap kolom yang berdekatan kalau perlu)
        # ini versi sederhana - implementasi lengkapnya bakal panjang banget
        # untuk sekarang, keep logic validasi utama di worker
        # bisa di-refactor nanti kalau perlu
        pass
    
    def _build_table_data(
        self,
        cells: Dict[Tuple[int, int], Dict[str, Any]],
        h_lines: List[int],
        column_structure: List[Dict[str, Any]],
        header_y_max: int
    ) -> List[Dict[str, Any]]:
        # bikin struktur data tabel akhir
        table_data = []
        
        for row_idx in range(len(h_lines) - 1):
            y_center = (h_lines[row_idx] + h_lines[row_idx + 1]) / 2
            if y_center <= header_y_max:
                continue
            
            row_cells = {}
            for col_idx in range(len(column_structure)):
                cell = cells.get((row_idx, col_idx), {})
                text = cell.get('text', '')
                
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
        
        return table_data

