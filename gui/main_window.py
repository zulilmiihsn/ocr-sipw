# main window aplikasi ocr

import sys
import json
import time
import cv2
import re
from collections import defaultdict
from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QTableWidget, QTableWidgetItem, QLabel, QProgressBar,
    QStatusBar, QMessageBox, QHeaderView, QGroupBox,
    QStyledItemDelegate, QLineEdit, QListWidget, QListWidgetItem, QAbstractItemView,
    QStyle
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QEvent, QRect, QSize
from PyQt5.QtGui import QColor, QFont, QPainter, QFontMetrics

import qtawesome as qta

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.lib.table_detector import detect_table_region, crop_table
from pipeline.ocr_engine import (
    run_full_document_ocr, detect_all_lines,
    detect_header_rows, learn_column_structure,
    validate_and_correct_by_template
)


class OCRWorker(QThread):
    # worker untuk proses ocr di background, bisa handle banyak file
    
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths if isinstance(file_paths, list) else [file_paths]
        self.is_cancelled = False
    
    def run(self):
        # jalankan proses ocr untuk semua file
        try:
            start_time = time.time()
            all_results = []
            total_files = len(self.file_paths)
            
            for file_idx, file_path in enumerate(self.file_paths):
                if self.is_cancelled:
                    return
                
                file_num = file_idx + 1
                file_name = Path(file_path).name
                
                self.progress.emit(
                    int(10 + (file_idx / total_files) * 5),
                    f"[{file_num}/{total_files}] Memuat {file_name}..."
                )
                
                image = cv2.imread(file_path)
                if image is None:
                    self.error.emit(f"Gagal memuat gambar: {file_name}")
                    continue
                
                if self.is_cancelled:
                    return
                
                page_results = self._process_single_image(
                    image, file_idx, 0, total_files, 1
                )
                
                if page_results:
                    for row in page_results:
                        row['_source_file'] = file_name
                        row['_source_page'] = 1
                    all_results.extend(page_results)
            
            if not all_results:
                self.error.emit("Tidak ada data yang berhasil diekstrak dari file")
                return
            
            total_time = time.time() - start_time
            self.progress.emit(100, "Selesai!")
            self.finished.emit({
                'table': all_results,
                'metadata': {
                    'total_time': total_time,
                    'num_files': total_files,
                    'num_rows': len(all_results)
                }
            })
            
        except Exception as e:
            self.error.emit(f"Terjadi kesalahan saat memproses OCR: {str(e)}")
    
    def _process_single_image(self, image, file_idx, page_idx, total_files, total_pages):
        # proses satu gambar dan kembalikan data tabel
        try:
            progress_base = 20 + (file_idx / total_files) * 60
            self.progress.emit(int(progress_base), "Mendeteksi region BLOK III...")
            if self.is_cancelled:
                return
            bbox = detect_table_region(image)
            if bbox is None:
                self.error.emit("Gagal mendeteksi region tabel BLOK III")
                return
            cropped = crop_table(image, bbox)
            
            self.progress.emit(30, "Melakukan pemindaian OCR...")
            if self.is_cancelled:
                return
            ocr_results = run_full_document_ocr(cropped)
            
            self.progress.emit(70, "Mendeteksi struktur tabel...")
            if self.is_cancelled:
                return
            all_h_lines, vertical_lines = detect_all_lines(cropped)
            
            # deteksi baris yg lebih pintar pakai pengelompokan Y dari hasil OCR
            image_height = cropped.shape[0]
            
            # toleransi menyesuaikan ukuran gambar biar lebih robust
            adaptive_tolerance = max(10, int(image_height * 0.015))  # 1.5% of image height, min 10px
            
            # perbaikan: pakai garis horizontal (H-lines) buat deteksi header, lebih akurat
            # masalah: deteksi header pakai OCR terlalu rendah (229px), jadi baris 1 kelewatan
            # solusi: pakai struktur tabel asli (H-lines), ambil garis TERAKHIR di area header
            # optimasi: urutkan sekali terus dipake ulang
            sorted_h_lines = sorted(all_h_lines)
            
            # cari pemisah header: garis H TERAKHIR di area atas (ini yang pisahkan header sama data)
            # H-lines in top 30%: [10, 25, 43, 189, 204] → We want 204 (last one = header separator)
            header_candidates = [y for y in sorted_h_lines if y < image_height * 0.30]  # cari di 30% area atas
            
            if len(header_candidates) >= 1:
                # pakai garis TERAKHIR di area header (ini pemisah header)
                header_y_max = header_candidates[-1]  # yang TERAKHIR, bukan [1]!
            else:
                # kalau ga ketemu, pakai deteksi berbasis OCR
                header_y_max = 0
                for det in ocr_results:
                    y_center = (det['y_min'] + det['y_max']) / 2
                    if y_center < image_height * 0.25:
                        header_y_max = max(header_y_max, det['y_max'])
                
                # tambahin margin buat jaga-jaga biar data ga ke-potong
                if header_y_max > 0:
                    header_y_max += 20  # 20px safety buffer
            
            # kumpulin pusat Y dari deteksi data (di bawah header)
            data_y_centers = []
            for det in ocr_results:
                y_center = (det['y_min'] + det['y_max']) / 2
                if y_center > header_y_max + 10:  # di bawah header dengan margin
                    data_y_centers.append(y_center)
            
            if len(data_y_centers) > 0:
                # kelompokin posisi Y jadi baris-baris
                data_y_centers = sorted(data_y_centers)
                
                # kelompokin deteksi yang berdekatan (baris yang sama)
                row_groups = []
                current_group = [data_y_centers[0]]
                tolerance = adaptive_tolerance  # toleransi menyesuaikan ukuran gambar
                
                for y in data_y_centers[1:]:
                    if y - current_group[-1] <= tolerance:
                        current_group.append(y)
                    else:
                        row_groups.append(current_group)
                        current_group = [y]
                row_groups.append(current_group)
                
                # ambil rata-rata Y untuk tiap kelompok baris
                row_y_positions = [sum(group) / len(group) for group in row_groups]
                
                # paksakan jadi pas 10 baris dengan gabungin atau pisahin
                if len(row_y_positions) > 10:
                    # barisnya kebanyakan, ambil 10 yang pertama aja
                    row_y_positions = row_y_positions[:10]
                elif len(row_y_positions) < 10:
                    # barisnya kurang, tambahin yang hilang dengan interpolasi
                    if len(row_y_positions) >= 2:
                        start_y = row_y_positions[0]
                        end_y = row_y_positions[-1]
                        step = (end_y - start_y) / 9
                        row_y_positions = [start_y + i * step for i in range(10)]
                
                # bikin garis horizontal dari posisi baris
                h_lines = [int(header_y_max + 10)]  # garis awal
                for y in row_y_positions:
                    h_lines.append(int(y))
                
                # tambahin garis akhir
                bottom_line = max(sorted_h_lines) if sorted_h_lines else image_height
                h_lines.append(int(bottom_line))
                
                # hapus duplikat terus urutkan
                h_lines = sorted(list(set(h_lines)))
                
                # pastikan pas 11 garis buat 10 baris
                if len(h_lines) > 11:
                    # simpan yang pertama sama terakhir, interpolasi yang tengah
                    start = h_lines[0]
                    end = h_lines[-1]
                    step = (end - start) / 10
                    h_lines = [int(start + i * step) for i in range(11)]
            else:
                # kalau ga bisa, bagi rata aja
                data_region_start = header_y_max + 10
                data_region_end = max(sorted_h_lines) if sorted_h_lines else image_height
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
            
            # bikin tabel dengan mapping deteksi berbasis pusat
            cells = defaultdict(lambda: {'detections': []})
            
            # optimasi: hitung konstanta di luar loop biar lebih cepat
            NUMERIC_COLS = frozenset([1, 2] + list(range(4, 11)) + [12, 15, 16])  # Kode SLS, Sub, BTT..Total, Shift, Muatan Dominan, Perubahan
            MANDATORY_NUMERIC_COLS = [1, 2, 15]  # Kode SLS, Sub-SLS, Muatan Dominan
            NUMERIC_RANGE = list(range(4, 11))
            
            # Pre-compile regex patterns (DRY - avoid re-compiling in loop)
            PHONE_PATTERN = re.compile(r'(08\d{8,11}|\+62\d{9,12})')
            
            # fungsi helper (pindahkan ke luar loop biar lebih efisien)
            def _only_digits(text: str) -> bool:
                # cek apakah text cuma berisi angka
                return text.isdigit()
            
            def _digits_len(text: str, n: int) -> bool:
                # cek apakah text pas n digit
                return text.isdigit() and len(text) == n
            
            def _looks_rt_rw(text: str) -> bool:
                # cek apakah text keliatan kayak format RT/RW
                t = text.upper()
                return ('RT' in t) and ('RW' in t)
            
            def _clean_text(text: str) -> str:
                # bersihkan text dengan hapus spasi dan separator umum
                return text.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            
            # mapping cell tingkat lanjut pakai IoU + fuzzy logic
            def calculate_iou(box1, box2):
                # hitung Intersection over Union (IoU)
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
            
            def compute_rule_prior(text_value: str, column_index: int) -> float:
                # boost prioritas kecil berdasarkan konten kolom yang diharapkan (0.0 - 0.25).
                if not text_value:
                    return 0.0
                t = str(text_value).strip()
                t_clean = _clean_text(t)  # pakai fungsi helper biar ga duplikat
                t_upper = t.upper()
                is_digits = t_clean.isdigit()
                has_rt = 'RT' in t_upper
                has_rw = 'RW' in t_upper
                
                # khusus: prioritas kuat untuk kolom 15 (Contact Person - Phone/Email)
                if column_index == 15:
                    # Phone pattern: 08xxx (10-13 digits) or +62xxx
                    phone_match = PHONE_PATTERN.match(t_clean)  # pakai pattern yg udah dikompilasi
                    # Email pattern: contains @ or starts with /
                    has_email = '@' in t or t.startswith('/')
                    # Combined phone+email pattern
                    if phone_match or has_email:
                        return 0.25  # Very strong prior
                    # kalau cuma angka tapi keliatan kayak nomor telepon (10-13 digit)
                    if is_digits and 10 <= len(t_clean) <= 13:
                        return 0.20
                    return 0.0
                
                # khusus: prioritas sangat kuat untuk kolom 16 (Muatan Dominan - digit tunggal 1-9)
                if column_index == 16:
                    # Must be exactly single digit 1-9
                    if len(t_clean) == 1 and t_clean.isdigit() and t_clean in '123456789':
                        return 0.30  # Strongest prior
                    # Penalize if it's phone number (long digits)
                    if is_digits and len(t_clean) >= 10:
                        return -0.20  # Negative prior (penalty)
                    return 0.0
                
                # Column groups
                if column_index == 3:  # RT/RW
                    if has_rt and has_rw:
                        return 0.15
                    if has_rt or has_rw:
                        return 0.10
                    return 0.0
                if column_index in NUMERIC_COLS:
                    return 0.12 if is_digits else 0.0
                if column_index == 11:  # Nama Wilayah (texty)
                    return 0.08 if not is_digits else 0.0
                # Free text columns (13-14): neutral
                return 0.0

            def fuzzy_score(det, cell_box, confidence, column_index: int):
                # hitung skor fuzzy logic buat assignment cell (dengan prioritas aturan).
                det_box = (det['x_min'], det['y_min'], det['x_max'], det['y_max'])
                cell_x_min, cell_y_min, cell_x_max, cell_y_max = cell_box
                
                det_center_x = (det['x_min'] + det['x_max']) / 2
                det_center_y = (det['y_min'] + det['y_max']) / 2
                
                # Pre-calculate cell dimensions once (DRY)
                cell_width = cell_x_max - cell_x_min
                cell_height = cell_y_max - cell_y_min
                cell_center_x = (cell_x_min + cell_x_max) / 2
                cell_center_y = (cell_y_min + cell_y_max) / 2
                
                # robust: pencocokan posisi pusat dengan pengecekan batas ketat
                # buat kolom 15-16, pakai pencocokan pusat yang KETAT (bobot lebih tinggi)
                in_x = cell_x_min <= det_center_x < cell_x_max
                in_y = cell_y_min <= det_center_y < cell_y_max
                
                # khusus: buat kolom 15-16, posisi pusat itu PENTING banget
                if column_index in (15, 16):
                    # kalau pusat ada di dalam cell, kasih skor sangat tinggi
                    if in_x and in_y:
                        center_score = 1.0
                    # kalau pusat di luar tapi dekat, kasih skor sebagian berdasarkan jarak
                    elif in_y:  # Same row
                        # hitung seberapa jauh pusat dari batas cell
                        if det_center_x < cell_x_min:
                            # Left of cell
                            dist = cell_x_min - det_center_x
                            center_score = max(0.0, 1.0 - (dist / cell_width) * 2)  # Penalize quickly
                        else:  # Right of cell
                            dist = det_center_x - cell_x_max
                            center_score = max(0.0, 1.0 - (dist / cell_width) * 2)
                    else:
                        center_score = 0.0
                    # kasih bobot lebih tinggi untuk posisi pusat di kolom penting
                    center_weight = 0.50  # 50% weight for center position
                else:
                    center_score = 1.0 if (in_x and in_y) else 0.0
                    center_weight = 0.30  # 30% for other columns
                
                # 2. IoU overlap
                iou = calculate_iou(det_box, cell_box)
                
                # 3. Distance to cell center
                distance = ((det_center_x - cell_center_x)**2 + (det_center_y - cell_center_y)**2)**0.5
                max_distance = ((cell_width/2)**2 + (cell_height/2)**2)**0.5
                
                distance_score = 1.0 - min(distance / max_distance, 1.0) if max_distance > 0 else 0.0
                
                # 4. Confidence weight
                conf_score = confidence
                
                # robust: kombinasi berbobot dengan bobot yang disesuaikan untuk kolom penting
                if column_index in (15, 16):
                    total_score = (
                        center_score * center_weight +  # 50% for center position
                        iou * 0.25 +                    # 25% for IoU
                        distance_score * 0.15 +         # 15% for distance
                        conf_score * 0.10               # 10% for confidence
                    )
                else:
                    total_score = (
                        center_score * center_weight +  # 30% for center position
                        iou * 0.40 +                    # 40% for IoU
                        distance_score * 0.20 +         # 20% for distance
                        conf_score * 0.10               # 10% for confidence
                    )
                
                # Rule prior (bias towards expected column content) - now with stronger impact
                rule_prior = compute_rule_prior(det.get('text', ''), column_index)
                total_score += rule_prior
                
                return total_score
            
            # hitung toleransi baris yg menyesuaikan buat mapping cell
            if len(h_lines) > 1:
                avg_row_height = (h_lines[-1] - h_lines[0]) / max(len(h_lines) - 1, 1)
                adaptive_row_tolerance = max(8, int(avg_row_height * 0.25))  # 25% of row height, min 8px
            else:
                adaptive_row_tolerance = 10
            
            # optimasi: spatial indexing buat mapping cell (99.4% lebih sedikit pengecekan!)
            # bikin spatial index buat pencarian baris/kolom yang cepat
            row_ranges = [(h_lines[i], h_lines[i+1], i) for i in range(len(h_lines)-1)]
            col_ranges = [(col['x_left'], col['x_right'], idx) for idx, col in enumerate(column_structure)]
            
            # Map detections to cells using ROBUST X-position-first strategy
            for det in ocr_results:
                det_center_x = (det['x_min'] + det['x_max']) / 2
                det_center_y = (det['y_min'] + det['y_max']) / 2
                
                # skip header
                if det_center_y <= header_y_max:
                    continue
                
                # optimasi: saring dulu kandidat baris (daripada cek semua baris)
                candidate_rows = []
                for y_min, y_max, idx in row_ranges:
                    if y_min - adaptive_row_tolerance <= det_center_y <= y_max + adaptive_row_tolerance:
                        candidate_rows.append(idx)
                
                # robust: strategi mapping dua tahap
                # pass 1: pencocokan posisi X yang KETAT (kalau pusat X jelas di kolom, langsung assign)
                # pass 2: fuzzy matching buat kasus yang ambigu
                # catatan: det_center_x sama det_center_y udah dihitung di atas
                
                # cari kolom pakai posisi X yang KETAT dulu (ini yang paling penting!)
                matched_col_by_x = -1
                for col_idx, col in enumerate(column_structure):
                    col_x_min = col['x_left']
                    col_x_max = col['x_right']
                    
                    # STRICT: If X center is clearly within column boundaries, this is THE column
                    if col_x_min <= det_center_x < col_x_max:
                        matched_col_by_x = col_idx
                        break  # Found exact match, no need to check others
                
                # kalau nemu pencocokan X yang tepat, langsung pakai (ABAIKAN posisi Y untuk keputusan mapping)
                if matched_col_by_x >= 0:
                    # cari baris terbaik buat kolom ini
                    best_row = -1
                    best_score = 0.0
                    
                    for row_idx in candidate_rows:
                        row_y_min = h_lines[row_idx]
                        row_y_max = h_lines[row_idx + 1]
                        
                        # cek apakah pusat Y ada di baris ini (dengan toleransi)
                        if row_y_min - adaptive_row_tolerance <= det_center_y <= row_y_max + adaptive_row_tolerance:
                            col_x_min = column_structure[matched_col_by_x]['x_left']
                            col_x_max = column_structure[matched_col_by_x]['x_right']
                            cell_box = (col_x_min, row_y_min, col_x_max, row_y_max)
                            
                            # hitung skor (tapi posisi X udah cocok, jadi ini mostly buat pilih baris)
                            score = fuzzy_score(det, cell_box, det['confidence'], matched_col_by_x)
                            
                            if score > best_score:
                                best_score = score
                                best_row = row_idx
                    
                    # kalau nemu baris, langsung assign
                    if best_row >= 0:
                        cells[(best_row, matched_col_by_x)]['detections'].append(det)
                        continue  # skip ke deteksi berikutnya
                
                # pass 2: kalau ga nemu pencocokan X yang tepat, pakai fuzzy matching (buat kasus edge)
                # optimasi: saring dulu kandidat kolom (daripada cek semua kolom)
                candidate_cols = []
                for x_min, x_max, idx in col_ranges:
                    # cek apakah deteksi tumpang tindih sama kolom
                    if not (det['x_max'] < x_min or det['x_min'] > x_max):
                        candidate_cols.append(idx)
                
                # cari cell yang paling cocok di antara KANDIDAT SAJA
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
                        
                        # hitung skor fuzzy (dengan prioritas aturan)
                        score = fuzzy_score(det, cell_box, det['confidence'], col_idx)
                        
                        # LOWERED threshold from 0.4 to 0.12 for narrow columns
                        if score > best_score and score > 0.12:
                            best_score = score
                            best_row = row_idx
                            best_col = col_idx
                
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
            
            # SECONDARY PASS: Fill mandatory numeric columns if empty using overlap+prior
            for row_idx in range(len(h_lines) - 1):
                y_center = (h_lines[row_idx] + h_lines[row_idx + 1]) / 2
                if y_center <= header_y_max:
                    continue
                row_y_min = h_lines[row_idx]
                row_y_max = h_lines[row_idx + 1]
                for col_idx in MANDATORY_NUMERIC_COLS:
                    key = (row_idx, col_idx)
                    cur = cells.get(key, {})
                    if cur.get('text'):
                        continue  # already filled
                    # cari deteksi terbaik yang tumpang tindih sama cell ini
                    col_x_min = column_structure[col_idx]['x_left']
                    col_x_max = column_structure[col_idx]['x_right']
                    cell_box = (col_x_min, row_y_min, col_x_max, row_y_max)
                    best_det = None
                    best_score = 0.0
                    for det in ocr_results:
                        det_center_y = (det['y_min'] + det['y_max']) / 2
                        if det_center_y <= header_y_max:
                            continue
                        # quick y filter
                        if det['y_max'] < row_y_min - adaptive_row_tolerance or det['y_min'] > row_y_max + adaptive_row_tolerance:
                            continue
                        # quick x filter (allow small margin ±8px to catch near-boundary values)
                        if det['x_max'] < (col_x_min - 8) or det['x_min'] > (col_x_max + 8):
                            continue
                        # hitung skor sederhana: IoU dengan bobot besar + prioritas aturan
                        iou = calculate_iou((det['x_min'], det['y_min'], det['x_max'], det['y_max']), cell_box)
                        if iou <= 0.01:
                            continue
                        prior = compute_rule_prior(det.get('text', ''), col_idx)
                        # hitung pusat (pake ulang det_center_x/y dari loop luar kalau ada)
                        det_center_x = (det['x_min'] + det['x_max']) / 2
                        det_center_y = (det['y_min'] + det['y_max']) / 2
                        cell_cx = (col_x_min + col_x_max) / 2
                        cell_cy = (row_y_min + row_y_max) / 2
                        cell_w = max(1, col_x_max - col_x_min)
                        cell_h = max(1, row_y_max - row_y_min)
                        max_d = ((cell_w/2)**2 + (cell_h/2)**2)**0.5
                        dist = ((det_center_x - cell_cx)**2 + (det_center_y - cell_cy)**2)**0.5
                        dist_score = 1.0 - min(dist / max_d, 1.0)
                        # Prefer numeric-looking text for mandatory numeric columns
                        txt = str(det.get('text', '')).strip()
                        is_digits = _clean_text(txt).isdigit()  # Use helper function (DRY)
                        digits_bonus = 0.06 if is_digits else 0.0
                        score = iou * 0.6 + dist_score * 0.28 + prior * 0.4 + digits_bonus
                        if score > best_score:
                            best_score = score
                            best_det = det
                    if best_det and best_score > 0.12:  # small threshold
                        cells[key]['detections'] = [best_det]
                        cells[key]['text'] = best_det['text']
                        cells[key]['confidence'] = best_det['confidence']

            # TERTIARY PASS: Per-row pattern validation and small-swap
            # Expected pattern (0-indexed):
            # 1: 4 digits, 2: 2 digits, 3: RT/RW, 4-10: digits, 11: text, 12: digits, 15: digits, 16: {1,2}
            for row_idx in range(len(h_lines) - 1):
                y_center = (h_lines[row_idx] + h_lines[row_idx + 1]) / 2
                if y_center <= header_y_max:
                    continue
                # Collect row texts
                row_texts = {}
                for c in range(len(column_structure)):
                    row_texts[c] = str(cells.get((row_idx, c), {}).get('text', '')).strip()

                # Small-swap helper between adjacent columns
                def _try_swap(ca: int, cb: int) -> None:
                    ta = row_texts.get(ca, '')
                    tb = row_texts.get(cb, '')
                    if not ta and tb:
                        cells[(row_idx, ca)] = cells.get((row_idx, cb), {}).copy()
                        cells[(row_idx, cb)] = {'detections': []}
                        row_texts[ca], row_texts[cb] = tb, ''

                # Enforce col 1 = 4 digits
                t1 = row_texts.get(1, '')
                if not _digits_len(_clean_text(t1), 4):
                    # coba ambil dari kolom tetangga 0 atau 2
                    t0 = row_texts.get(0, '')
                    t2 = row_texts.get(2, '')
                    if _digits_len(_clean_text(t0), 4):
                        _try_swap(1, 0)
                    elif _digits_len(_clean_text(t2), 4):
                        _try_swap(1, 2)

                # Enforce col 2 = 2 digits
                t2 = row_texts.get(2, '')
                if not _digits_len(_clean_text(t2), 2):
                    t1 = row_texts.get(1, '')
                    t3 = row_texts.get(3, '')
                    if _digits_len(_clean_text(t1), 2):
                        _try_swap(2, 1)
                    elif _digits_len(_clean_text(t3), 2):
                        _try_swap(2, 3)

                # Enforce col 3 RT/RW
                t3 = row_texts.get(3, '')
                if not _looks_rt_rw(t3):
                    # coba ambil dari tetangga 2 atau 4 kalau keliatan kayak RT/RW
                    if _looks_rt_rw(row_texts.get(2, '')):
                        _try_swap(3, 2)
                    elif _looks_rt_rw(row_texts.get(4, '')):
                        _try_swap(3, 4)

                # Enforce numeric columns 4-10
                for c in NUMERIC_RANGE:
                    tc = row_texts.get(c, '')
                    if tc and not _only_digits(_clean_text(tc)):
                        # kalau tetangga punya angka tapi cell ini ga punya, tukar ke yang ada angka
                        if _only_digits(_clean_text(row_texts.get(c-1, ''))):
                            _try_swap(c, c-1)
                        elif _only_digits(_clean_text(row_texts.get(c+1, ''))):
                            _try_swap(c, c+1)

                # Enforce Muatan Dominan (15) numeric
                t15 = row_texts.get(15, '')
                if not _only_digits(_clean_text(t15)):
                    if _only_digits(_clean_text(row_texts.get(14, ''))):
                        _try_swap(15, 14)
                    elif _only_digits(_clean_text(row_texts.get(16, ''))):
                        _try_swap(15, 16)

                # Enforce Perubahan Batas (16) in {1,2}
                t16 = row_texts.get(16, '')
                if t16 not in ('1', '2'):
                    # kalau tetangga sama dengan '1' atau '2', tukar
                    if row_texts.get(15, '') in ('1', '2'):
                        _try_swap(16, 15)
                    elif row_texts.get(14, '') in ('1', '2'):
                        _try_swap(16, 14)
                
                # perbaikan robust: handle mapping kolom 15 (Contact Person) dan 16 (Muatan Dominan)
                # masalah: nomor telepon kadang ke-mapping ke kolom 16 padahal harusnya kolom 15
                # solusi: koreksi agresif berbasis pattern dengan validasi ketat
                t15_current = row_texts.get(15, '').strip()
                t16_current = row_texts.get(16, '').strip()
                
                # robust: cek semua skenario yang mungkin
                # Scenario 1: Col 16 is entirely a phone number (10-13 digits) - MUST move to col 15
                if t16_current:
                    t16_clean = _clean_text(t16_current)  # Use helper function (DRY)
                    
                    # cek apakah kolom 16 cocok sama pattern telepon pas
                    if PHONE_PATTERN.match(t16_clean):
                        # Entire col 16 is phone - MUST move to col 15
                        if t15_current:
                            new_t15 = f"{t16_current} {t15_current}"
                        else:
                            new_t15 = t16_current
                        
                        cell_15 = cells.get((row_idx, 15), {})
                        cell_15['text'] = new_t15
                        cells[(row_idx, 15)] = cell_15
                        
                        # bersihkan kolom 16
                        cell_16 = cells.get((row_idx, 16), {})
                        cell_16['text'] = ''
                        cell_16['detections'] = []
                        cells[(row_idx, 16)] = cell_16
                        continue  # Move to next validation
                    
                    # cek apakah kolom 16 cuma angka panjang (10-13) - kemungkinan telepon
                    if t16_clean.isdigit() and 10 <= len(t16_clean) <= 13:
                        # This is definitely a phone number, not Muatan Dominan
                        if t15_current:
                            new_t15 = f"{t16_current} {t15_current}"
                        else:
                            new_t15 = t16_current
                        
                        cell_15 = cells.get((row_idx, 15), {})
                        cell_15['text'] = new_t15
                        cells[(row_idx, 15)] = cell_15
                        
                        cell_16 = cells.get((row_idx, 16), {})
                        cell_16['text'] = ''
                        cell_16['detections'] = []
                        cells[(row_idx, 16)] = cell_16
                        continue
                    
                    # Scenario 2: Col 16 contains phone + digit (e.g., "08234567893")
                    phone_match = PHONE_PATTERN.search(t16_clean)
                    if phone_match:
                        phone_text = phone_match.group(1)
                        remaining = t16_clean.replace(phone_text, '').strip()
                        
                        # kalau sisa cuma 1 digit, itu Muatan Dominan
                        if remaining and len(remaining) == 1 and remaining.isdigit():
                            if t15_current:
                                new_t15 = f"{phone_text} {t15_current}"
                            else:
                                new_t15 = phone_text
                            
                            cell_15 = cells.get((row_idx, 15), {})
                            cell_15['text'] = new_t15
                            cells[(row_idx, 15)] = cell_15
                            
                            cell_16 = cells.get((row_idx, 16), {})
                            cell_16['text'] = remaining
                            cells[(row_idx, 16)] = cell_16
                            continue
                        
                        # kalau telepon 11+ digit, digit terakhir mungkin Muatan Dominan
                        if len(phone_text) >= 11:
                            phone_base = phone_text[:-1]
                            muatan_digit = phone_text[-1]
                            
                            if t15_current:
                                new_t15 = f"{phone_base} {t15_current}"
                            else:
                                new_t15 = phone_base
                            
                            cell_15 = cells.get((row_idx, 15), {})
                            cell_15['text'] = new_t15
                            cells[(row_idx, 15)] = cell_15
                            
                            cell_16 = cells.get((row_idx, 16), {})
                            cell_16['text'] = muatan_digit
                            cells[(row_idx, 16)] = cell_16
                            continue
                
                # Scenario 3: Col 15 has phone + digit concatenated
                if t15_current and len(t15_current) > 11:
                    t15_clean = _clean_text(t15_current)  # Use helper function (DRY)
                    if t15_clean[-1].isdigit() and not t16_current:
                        rest = t15_clean[:-1]
                        if PHONE_PATTERN.match(rest):
                            # Preserve formatting
                            phone_part = t15_current.rstrip('0123456789').strip()
                            last_digit = t15_clean[-1]
                            
                            cell_15 = cells.get((row_idx, 15), {})
                            cell_15['text'] = phone_part
                            cells[(row_idx, 15)] = cell_15
                            
                            cell_16 = cells.get((row_idx, 16), {})
                            cell_16['text'] = last_digit
                            cells[(row_idx, 16)] = cell_16

            # bikin struktur baris
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
            
            return table_data
            
        except Exception as e:
            print(f"kesalahan saat memproses gambar: {str(e)}")
            return []
    
    def cancel(self):
        # batalkan proses
        self.is_cancelled = True


class HeaderDelegate(QStyledItemDelegate):
    # delegate untuk header tabel dengan word wrap
    
    def paint(self, painter, option, index):
        # gambar header dengan word wrapping
        painter.save()
        
        text = index.data(Qt.DisplayRole) or ""
        
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        
        if option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, QColor("#F1F5F9"))
        else:
            painter.fillRect(option.rect, QColor("#F8FAFC"))
        
        painter.setPen(QColor("#E2E8F0"))
        painter.drawLine(option.rect.topRight(), option.rect.bottomRight())
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        
        painter.setPen(QColor("#475569"))
        text_rect = option.rect.adjusted(8, 4, -8, -4)
        painter.drawText(
            text_rect,
            Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap,
            text
        )
        
        painter.restore()
    
    def sizeHint(self, option, index):
        # hitung ukuran untuk text yg di-wrap
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
    # delegate untuk cell tabel, handle enter key untuk navigasi
    
    def createEditor(self, parent, option, index):
        # buat editor untuk cell
        editor = QLineEdit(parent)
        editor.setFrame(False)
        return editor
    
    def setEditorData(self, editor, index):
        # set data awal di editor
        value = index.model().data(index, Qt.EditRole)
        editor.setText(str(value) if value else "")
    
    def setModelData(self, editor, model, index):
        # simpan data dari editor ke model
        model.setData(index, editor.text(), Qt.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        # atur ukuran editor sesuai cell
        editor.setGeometry(option.rect)
    
    def eventFilter(self, editor, event):
        # handle enter key untuk commit dan pindah ke cell berikutnya
        if event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.commitData.emit(editor)
                self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)
                return True
        return super().eventFilter(editor, event)


class CustomTableWidget(QTableWidget):
    # table widget dengan navigasi keyboard dan kontrol row
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._moving_after_edit = False
        self.hovered_row = -1
        self.parent_window = None
        
        # Floating buttons (akan dibuat oleh parent window)
        self.add_row_floating_btn = None
        self.remove_row_floating_btn = None
        
        # aktifkan tracking mouse untuk header vertikal
        self.verticalHeader().setMouseTracking(True)
        self.verticalHeader().viewport().setMouseTracking(True)
        
        # Install event filter on vertical header
        self.verticalHeader().viewport().installEventFilter(self)
    
    def eventFilter(self, obj, event):
        # handle event hover header vertikal
        if obj == self.verticalHeader().viewport():
            if event.type() == event.MouseMove:
                # ambil baris dari posisi mouse
                pos = event.pos()
                row = self.verticalHeader().logicalIndexAt(pos)
                
                if row >= 0 and row < self.rowCount():
                    if self.hovered_row != row:
                        self.hovered_row = row
                        self.show_floating_buttons(row)
                else:
                    self.hide_floating_buttons()
            
            elif event.type() == event.Leave:
                # sembunyikan tombol ketika mouse keluar dari header vertikal
                self.hide_floating_buttons()
        
        return super().eventFilter(obj, event)
    
    def show_floating_buttons(self, row):
        # tampilkan tombol floating untuk baris yang di-hover
        if self.add_row_floating_btn and self.remove_row_floating_btn:
            header_rect = self.verticalHeader().sectionViewportPosition(row)
            header_height = self.verticalHeader().sectionSize(row)
            x = 2
            y = header_rect + (header_height - 24) // 2
            self.add_row_floating_btn.setParent(self.verticalHeader().viewport())
            self.remove_row_floating_btn.setParent(self.verticalHeader().viewport())
            
            self.add_row_floating_btn.setGeometry(x, y, 12, 24)
            self.remove_row_floating_btn.setGeometry(x + 12, y, 12, 24)
            
            self.add_row_floating_btn.show()
            self.remove_row_floating_btn.show()
    
    def hide_floating_buttons(self):
        # sembunyikan floating buttons
        self.hovered_row = -1
        if self.add_row_floating_btn:
            self.add_row_floating_btn.hide()
        if self.remove_row_floating_btn:
            self.remove_row_floating_btn.hide()
    
    def keyPressEvent(self, event):
        # handle keyboard untuk navigasi cell
        current_row = self.currentRow()
        current_col = self.currentColumn()
        is_editing = self.state() == QTableWidget.EditingState
        
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if is_editing:
                self.closeEditor(self.itemDelegate().createEditor(self, None, self.model().index(current_row, current_col)), QStyledItemDelegate.NoHint)
            
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
        
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    # window utama aplikasi
    
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.ocr_results = None
        self.ocr_worker = None
        self.edited_cells = {}
        
        self.init_ui()
    
    def _get_icon(self, name: str, **kwargs):
        # ambil icon dari qtawesome
        return qta.icon(name, **kwargs)
    
    def load_stylesheet(self):
        # load stylesheet jika ada
        style_path = Path(__file__).parent / 'styles.qss'
        if style_path.exists():
            with open(style_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
    
    def init_ui(self):
        # setup tampilan ui
        self.setWindowTitle("OCR Sistem Informasi Pencatat Wilayah")
        self.setMinimumSize(1280, 800)
        self.setWindowIcon(self._get_icon('fa5s.table', color='#2563EB'))
        
        # muat stylesheet QSS
        self.load_stylesheet()
        
        # bikin widget utama (ga pakai menu bar biar interface lebih bersih)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout - professional spacing with breathing room
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 24, 24, 20)
        main_layout.setSpacing(20)
        
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
        
        # tombol ekspor
        export_btn = QPushButton(" Ekspor Hasil")
        export_btn.setIcon(self._get_icon('fa5s.file-export', color='white'))
        export_btn.setObjectName("exportButton")
        export_btn.clicked.connect(self.export_results)
        export_btn.setEnabled(False)
        export_btn.setMinimumHeight(48)
        self.export_button = export_btn
        main_layout.addWidget(export_btn)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("Siap - Pilih file untuk memulai")
    
    
    def create_file_selection_group(self):
        # buat grup UI pilihan file dengan daftar file interaktif
        group = QGroupBox("Pilih File & Proses")
        layout = QVBoxLayout()
        
        # Top row: Browse button
        top_row = QHBoxLayout()
        top_row.setSpacing(16)
        
        # Browse button
        browse_btn = QPushButton(" Pilih File Gambar")
        browse_btn.setIcon(self._get_icon('fa5s.folder-open', color='#64748B'))
        browse_btn.setObjectName("browse_btn")
        browse_btn.clicked.connect(self.browse_file)
        browse_btn.setMinimumWidth(170)
        browse_btn.setMinimumHeight(44)
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
        self.file_list.setVisible(False)  # disembunyikan sampai file dipilih
        layout.addWidget(self.file_list)
        
        # Bottom row: Action buttons
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(16)
        
        # tombol mulai ocr
        self.start_btn = QPushButton(" Mulai OCR")
        self.start_btn.setIcon(self._get_icon('fa5s.play', color='white'))
        self.start_btn.setObjectName("start_btn")
        self.start_btn.clicked.connect(self.start_ocr)
        self.start_btn.setEnabled(False)  # dinonaktifkan sampai file dipilih
        self.start_btn.setMinimumWidth(140)
        self.start_btn.setMinimumHeight(44)
        bottom_row.addWidget(self.start_btn)
        
        # sort button
        self.sort_btn = QPushButton(" Urutkan")
        self.sort_btn.setIcon(self._get_icon('fa5s.sort-amount-down', color='#2563EB'))
        self.sort_btn.setObjectName("sort_btn")
        self.sort_btn.clicked.connect(self.sort_table)
        self.sort_btn.setEnabled(False)  # dinonaktifkan sampai OCR selesai
        self.sort_btn.setMinimumWidth(140)
        self.sort_btn.setMinimumHeight(44)
        self.sort_btn.setToolTip("Urutkan tabel berdasarkan Kode SLS (↑) dan Sub-SLS (↓)")
        bottom_row.addWidget(self.sort_btn)
        
        # reset button
        self.reset_btn = QPushButton(" Reset")
        self.reset_btn.setIcon(self._get_icon('fa5s.redo', color='#64748B'))
        self.reset_btn.setObjectName("reset_btn")
        self.reset_btn.clicked.connect(self.reset_all)
        self.reset_btn.setEnabled(False)  # dinonaktifkan awalnya
        self.reset_btn.setMinimumWidth(140)
        self.reset_btn.setMinimumHeight(44)
        bottom_row.addWidget(self.reset_btn)
        
        bottom_row.addStretch()  # push buttons ke kiri
        
        layout.addLayout(bottom_row)
        
        group.setLayout(layout)
        return group
    
    def create_table_group(self):
        # buat grup UI tabel
        group = QGroupBox("Hasil Ekstraksi Tabel")
        layout = QVBoxLayout()
        
        # bikin widget tabel kustom dengan navigasi tombol panah dan kontrol mengambang
        self.table = CustomTableWidget()
        self.table.parent_window = self
        self.table.setColumnCount(16)
        self.table.setRowCount(10)
        
        # set delegate kustom buat editing cell yang lebih baik
        self.table.setItemDelegate(CellDelegate())
        
        # set header (nama kolom) - dengan line break manual biar lebih pas
        headers = [
            "Kode\nSLS/Non-SLS",
            "Kode\nSub-SLS",
            "Nama\nSLS/Non-SLS",
            "Perkiraan\nJumlah Muatan\nKK (Keluarga)",
            "Bangunan\nTempat Tinggal\n(BTT)",
            "Bangunan\nTempat Tinggal\nKosong\n(BTT Kosong)",
            "Bangunan\nKhusus Usaha\n(BKU)",
            "Bangunan\nBukan Tempat\nTinggal\nnon Usaha",
            "Perkiraan\nJumlah Muatan\nUsaha",
            "Total\nMuatan",
            "Nama Wilayah\nKonsentrasi\nEkonomi",
            "Jumlah Shift\nPola Kerja\nKonsentrasi\nEkonomi",
            "Jam\nOperasional",
            "Contact Person\nTelepon/Email",
            "Muatan\nDominan",
            "Perubahan\nbatas (reko)?\n1 = Ya\n2 = Tidak"
        ]
        self.table.setHorizontalHeaderLabels(headers)
        
        # Apply custom header delegate for word wrapping
        header_delegate = HeaderDelegate(self.table)
        self.table.horizontalHeader().setItemDelegate(header_delegate)
        
        # set header vertikal (nomor baris 1-10) - auto-generated
        for i in range(10):
            self.table.setVerticalHeaderItem(i, QTableWidgetItem(str(i + 1)))
        
        # set lebar header vertikal (nomor baris) - kompak
        self.table.verticalHeader().setFixedWidth(40)
        
        # Configure horizontal header for responsive behavior
        header = self.table.horizontalHeader()
        
        # set mode resize: rentangkan biar mengisi lebar window secara proporsional
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        
        # Enable text wrapping in headers for long labels
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # set lebar kolom minimum (responsif)
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
            QTableWidget.AnyKeyPressed      # mulai ketik langsung
        )
        self.table.itemChanged.connect(self.on_cell_edited)
        
        # Navigation handled by CustomTableWidget.keyPressEvent
        
        # bikin tombol mengambang buat kontrol baris (disembunyikan secara default)
        self.create_floating_row_buttons()
        
        layout.addWidget(self.table)
        
        group.setLayout(layout)
        return group
    
    def create_floating_row_buttons(self):
        # buat tombol floating tambah/hapus untuk baris tabel
        # tombol tambah (kecil, mengambang)
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
        # buka dialog browser file (support multi-select gambar saja)
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
        # isi daftar file dengan icon dan nama
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
        # ambil path file sesuai urutan di list (setelah drag & drop)
        file_paths = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = item.data(Qt.UserRole)
            file_paths.append(file_path)
        return file_paths
    
    
    def start_ocr(self):
        # mulai proses OCR (support multi-file/multi-page)
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
        # update progress bar
        self.progress_bar.setValue(percentage)
        self.progress_bar.setFormat(f"{percentage}% - {stage}")
        self.update_status(stage)
    
    def on_ocr_finished(self, results: dict):
        # handle penyelesaian OCR
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
        file_text = f"{num_files} berkas" if num_files > 1 else "1 berkas"
        
        QMessageBox.information(
            self,
            "OCR Selesai",
            f"Berhasil mengekstrak {metadata['num_rows']} baris dari {file_text}!\n\n"
            f"Waktu proses: {metadata['total_time']:.1f} detik\n\n"
            "Data sudah diurutkan otomatis:\n"
            "• Kode SLS (naik)\n"
            "• Kode Sub-SLS (turun)\n\n"
            "Anda dapat mengedit tabel dan mengekspor hasil."
        )
    
    def on_ocr_error(self, error_msg: str):
        # handle error OCR
        self.progress_bar.setVisible(False)
        
        # Re-enable Start button on error
        self.start_btn.setEnabled(True)
        
        self.update_status(f"✗ Error: {error_msg}")
        
        QMessageBox.critical(
            self,
            "Kesalahan OCR",
            f"Terjadi kesalahan saat memproses OCR:\n\n{error_msg}"
        )
    
    def populate_table(self, table_data):
        # isi tabel dengan hasil OCR (support multi-page, jumlah baris dinamis)
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
        # track cell yang sudah diedit
        row = item.row()
        col = item.column()
        self.edited_cells[(row, col)] = item.text()
        
        # Mark edited cell with different color
        item.setBackground(QColor(220, 220, 255))  # Light blue
        
        # Update status
        self.update_status(f"Sel diedit ({row+1}, {col+1}) | Total edit: {len(self.edited_cells)}")
    
    def add_row_at_hover(self):
        # tambah baris baru di bawah baris yang di-hover
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
        # hapus baris yang di-hover (langsung, tanpa konfirmasi)
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
        # urutkan tabel berdasarkan Kode SLS (ASC) dan Sub-SLS (DESC)
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
        # enable atau disable tombol ekspor
        self.export_button.setEnabled(enabled)
    
    def export_results(self):
        # ekspor hasil OCR dengan dialog pilihan format
        if not self.ocr_results:
            QMessageBox.warning(self, "Tidak Ada Data", "Silakan jalankan OCR terlebih dahulu sebelum mengekspor.")
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
        format_label = "Excel" if format_name == "excel" else "CSV" if format_name == "csv" else "JSON"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Ekspor Hasil {format_label}",
            str(Path.home() / f"blok3_results.{ext}"),
            f"File {format_label} (*.{ext});;Semua File (*.*)"
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
            QMessageBox.critical(self, "Kesalahan Ekspor", f"Gagal mengekspor:\n{str(e)}")
    
    def export_to_excel(self, file_path: str):
        # ekspor ke Excel dengan formatting (termasuk kolom No)
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
            # tulis nomor baris (kolom No)
            ws.cell(row + 2, 1, row + 1)
            
            # tulis kolom sisanya
            for col in range(16):
                item = self.table.item(row, col)
                if item:
                    ws.cell(row + 2, col + 2, item.text())
        
        wb.save(file_path)
    
    def export_to_csv(self, file_path: str):
        # ekspor ke CSV (termasuk kolom No)
        import csv
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # header - tambahkan "No" di depan
            headers = ["No"] + [self.table.horizontalHeaderItem(i).text() for i in range(16)]
            writer.writerow(headers)
            
            # data (jumlah baris dinamis)
            num_rows = self.table.rowCount()
            for row in range(num_rows):
                row_data = [row + 1]  # mulai dengan nomor baris
                for col in range(16):
                    item = self.table.item(row, col)
                    row_data.append(item.text() if item else '')
                writer.writerow(row_data)
    
    def export_to_json(self, file_path: str):
        # ekspor ke JSON (termasuk kolom No)
        data = {
            'metadata': self.ocr_results['metadata'],
            'table': []
        }
        
        # jumlah baris dinamis
        num_rows = self.table.rowCount()
        for row in range(num_rows):
            row_data = {'row_number': row + 1, 'cells': {}}
            
            # tambahkan "No" sebagai kolom 0
            row_data['cells'][0] = {
                'text': str(row + 1),
                'edited': False
            }
            
            # tambahkan kolom sisanya (digeser 1)
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
        # ekspor ke HTML
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
            # tambahkan nomor baris
            html += f"            <td>{row + 1}</td>\n"
            # tambahkan kolom sisanya
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
        # update status bar
        self.status_bar.showMessage(message)
    
    def reset_all(self):
        # reset semua data dan UI ke kondisi awal
        # konfirmasi reset
        reply = QMessageBox.question(
            self,
            "Konfirmasi Reset",
            "Apakah Anda yakin ingin mereset?\n\nIni akan menghapus:\n• File yang dipilih\n• Hasil OCR\n• Data tabel\n• Semua editan",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        # hentikan worker OCR kalau masih jalan
        if self.ocr_worker and self.ocr_worker.isRunning():
            self.ocr_worker.cancel()
            self.ocr_worker.wait()
        
        # bersihkan pilihan file
        self.current_files = []
        self.file_list.clear()
        self.file_list.setVisible(False)
        
        # bersihkan hasil OCR
        self.ocr_results = None
        self.edited_cells.clear()
        
        # bersihkan tabel dan reset ke default 10 baris
        self.table.clearContents()
        self.table.setRowCount(10)
        for i in range(10):
            self.table.setVerticalHeaderItem(i, QTableWidgetItem(str(i + 1)))
        
        # Hide progress bar
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        
        # nonaktifkan tombol
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
        # handle penutupan window
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
