"""
========================================
FINAL OCR PIPELINE - PRODUCTION SYSTEM
========================================

Complete pipeline using APPROVED methods:
- Stage 1: Image Loading (from experiments)
- Stage 2: No Preprocessing (preserves quality)
- Stage 3: OCR + Border Detection (approved 5.6s method)
- Stage 4: Morphological Line Detection (approved 0.21s method)
- Stage 5: PaddleOCR PP-OCRv5 (TERCANGGIH!)
- Stage 6: Adaptive Table Mapping
- Stage 7: Export Results

Author: Lab OCR Team
Version: FINAL
Date: October 2025
"""

import sys
import time

# Fix encoding for Windows console
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
import cv2
import numpy as np
import json
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import approved methods
from src.utils.pdf_handler import load_image
from src.ocr.table_detector import detect_table_region, crop_table


# ============================================================================
# STAGE 4: MORPHOLOGICAL LINE DETECTION (Approved Method)
# ============================================================================

def detect_horizontal_lines(image):
    """Detect horizontal table lines using morphological operations"""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Binarize
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Horizontal kernel
    kernel_width = max(3, image.shape[1] // 3)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, 1))
    
    # Detect horizontal lines
    h_lines_img = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)
    
    # Find contours
    contours, _ = cv2.findContours(h_lines_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Extract Y-coordinates
    h_lines = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w > image.shape[1] * 0.5:  # At least 50% of image width
            h_lines.append(y)
    
    # Sort and remove duplicates
    h_lines = sorted(set(h_lines))
    
    return h_lines


def detect_vertical_lines(image):
    """Detect vertical table lines using morphological operations"""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Binarize
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Vertical kernel
    kernel_height = max(3, image.shape[0] // 5)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kernel_height))
    
    # Detect vertical lines
    v_lines_img = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)
    
    # Find contours
    contours, _ = cv2.findContours(v_lines_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Extract X-coordinates
    v_lines = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if h > image.shape[0] * 0.3:  # At least 30% of image height
            v_lines.append(x)
    
    # Sort and remove duplicates
    v_lines = sorted(set(v_lines))
    
    return v_lines


# ============================================================================
# STAGE 5: PADDLEOCR PP-OCRv5 (Singleton)
# ============================================================================

class PaddleOCREngine:
    """Singleton PaddleOCR instance for efficient model reuse"""
    _instance = None
    _ocr = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_ocr(self):
        """Get or create PaddleOCR instance"""
        if self._ocr is None:
            from paddleocr import PaddleOCR
            # Use PP-OCRv5 mobile (faster and more reliable than server)
            self._ocr = PaddleOCR(
                lang='en',
                use_textline_orientation=False
            )
        return self._ocr
    
    def ocr(self, image):
        """Run OCR prediction"""
        ocr_instance = self.get_ocr()
        result = ocr_instance.predict(image)
        return result


def run_full_document_ocr(image):
    """
    Run PaddleOCR PP-OCRv5 on entire BLOK III table
    Returns list of detections with bbox, text, confidence
    """
    # SMART preprocessing: Upscale + Sharpen (tidak over!)
    # Keep 3-channel untuk PaddleOCR compatibility
    if len(image.shape) == 2:
        # Convert grayscale to BGR if needed
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    
    # 1. Upscale 2x (untuk OCR yang lebih baik)
    processed = cv2.resize(image, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    
    # 2. Denoise sedikit pada setiap channel (agar noise tidak mengganggu OCR)
    processed = cv2.fastNlMeansDenoisingColored(processed, None, h=10, hColor=10, templateWindowSize=7, searchWindowSize=21)
    
    # 3. Enhance contrast (convert to LAB, apply CLAHE on L channel, convert back)
    lab = cv2.cvtColor(processed, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    l = clahe.apply(l)
    processed = cv2.merge([l, a, b])
    processed = cv2.cvtColor(processed, cv2.COLOR_LAB2BGR)
    
    # 4. Sharpen (agar text lebih jelas)
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    processed = cv2.filter2D(processed, -1, kernel)
    
    # Run PaddleOCR
    engine = PaddleOCREngine()
    result_generator = engine.ocr(processed)
    
    # Parse results (generator -> list)
    detections = []
    results = list(result_generator)
    
    # Parse OCRResult (it's a dictionary)
    if results and len(results) > 0:
        ocr_result = results[0]
        
        # Access dictionary keys
        if 'dt_polys' in ocr_result and 'rec_texts' in ocr_result and 'rec_scores' in ocr_result:
            dt_polys = ocr_result['dt_polys']
            rec_texts = ocr_result['rec_texts']
            rec_scores = ocr_result['rec_scores']
            
            for i in range(len(dt_polys)):
                bbox_poly = dt_polys[i]
                text = rec_texts[i]
                conf = float(rec_scores[i])
                
                # Calculate bbox from polygon (scale back to original size)
                x_coords = [p[0] / 2.0 for p in bbox_poly]  # Scale back from 2x
                y_coords = [p[1] / 2.0 for p in bbox_poly]
                
                x_min = min(x_coords)
                x_max = max(x_coords)
                y_min = min(y_coords)
                y_max = max(y_coords)
                
                detections.append({
                    'bbox': [int(x_min), int(y_min), int(x_max), int(y_max)],
                    'text': text.strip(),
                    'confidence': conf,
                    'x_center': (x_min + x_max) / 2,
                    'y_center': (y_min + y_max) / 2
                })
    
    return detections


# ============================================================================
# STAGE 6: ADAPTIVE TABLE MAPPING
# ============================================================================

def detect_header_rows(detections):
    """Identify header rows based on keywords and Y-position"""
    header_keywords = [
        'Kode', 'Nama', 'Jumlah', 'Perkiraan', 'Contact', 'Wilayah',
        'Bangunan', 'Muatan', 'Shift', 'Operasional', 'SLS', 'Sub',
        'Tinggal', 'Kosong', 'Usaha', 'BBTT', 'BTT', 'BKU', 'RT', 'RW'
    ]
    
    header_y_threshold = 200
    header_detections = []
    
    for det in detections:
        text = det['text']
        y = det['y_center']
        
        # Check if in header region
        if y < header_y_threshold:
            # Check if contains header keywords
            for keyword in header_keywords:
                if keyword.lower() in text.lower():
                    header_detections.append(det)
                    break
    
    return header_detections


def learn_column_structure(detections, v_lines, h_lines):
    """Learn column names and boundaries from header detections and vertical lines"""
    header_dets = detect_header_rows(detections)
    
    # Group header detections by Y-position (same row)
    header_y_tolerance = 20
    header_groups = []
    
    for det in header_dets:
        y = det['y_center']
        added = False
        
        for group in header_groups:
            if abs(group['y_center'] - y) < header_y_tolerance:
                group['detections'].append(det)
                added = True
                break
        
        if not added:
            header_groups.append({
                'y_center': y,
                'detections': [det]
            })
    
    # Sort by Y (top to bottom)
    header_groups.sort(key=lambda g: g['y_center'])
    
    # Map header texts to vertical line boundaries
    columns = []
    
    for col_idx in range(len(v_lines) - 1):
        x_start = v_lines[col_idx]
        x_end = v_lines[col_idx + 1]
        x_center = (x_start + x_end) / 2
        
        # Find header texts that fall in this column
        col_texts = []
        for group in header_groups:
            for det in group['detections']:
                det_x = det['x_center']
                if x_start <= det_x <= x_end:
                    col_texts.append(det['text'])
        
        # Combine texts or use generic name
        if col_texts:
            col_name = ' '.join(col_texts)
        else:
            col_name = f'Column {col_idx}'
        
        columns.append({
            'index': col_idx,
            'name': col_name,
            'x_start': x_start,
            'x_end': x_end,
            'x_center': x_center
        })
    
    return columns, header_groups


def map_detection_to_cell(det, h_lines, v_lines, header_y_max):
    """Map a detection to its (row, col) position"""
    x = det['x_center']
    y = det['y_center']
    
    # Skip if in header region
    if y <= header_y_max:
        return -1, -1
    
    # Find row
    row = -1
    for i in range(len(h_lines) - 1):
        if h_lines[i] <= y < h_lines[i + 1]:
            row = i
            break
    
    # Find column
    col = -1
    for i in range(len(v_lines) - 1):
        if v_lines[i] <= x < v_lines[i + 1]:
            col = i
            break
    
    return row, col


def build_table(detections, columns, h_lines, v_lines, header_y_max):
    """Build table structure from detections"""
    cells = defaultdict(lambda: {'detections': []})
    
    # Map detections to cells
    for det in detections:
        row, col = map_detection_to_cell(det, h_lines, v_lines, header_y_max)
        if row >= 0 and col >= 0:
            cells[(row, col)]['detections'].append(det)
    
    # Build rows
    rows = []
    for row_idx in range(len(h_lines) - 1):
        row_data = {
            'row': row_idx,
            'cells': {}
        }
        
        for col_idx in range(len(columns)):
            cell_key = (row_idx, col_idx)
            cell_dets = cells.get(cell_key, {}).get('detections', [])
            
            # Combine texts
            if cell_dets:
                # Sort by X position
                cell_dets.sort(key=lambda d: d['x_center'])
                text = ' '.join(d['text'] for d in cell_dets)
                conf = sum(d['confidence'] for d in cell_dets) / len(cell_dets)
            else:
                text = ''
                conf = 0.0
            
            row_data['cells'][columns[col_idx]['name']] = {
                'text': text,
                'confidence': conf
            }
        
        rows.append(row_data)
    
    return rows


def post_process_text(text, column_name):
    """Post-process text based on column type"""
    if not text:
        return text
    
    # Remove leading bracket artifacts
    if text.startswith('['):
        text = text[1:]
    
    # Clean whitespace
    text = ' '.join(text.split())
    
    # Column-specific cleaning
    col_lower = column_name.lower()
    
    # Numeric columns
    numeric_keywords = ['jumlah', 'shift', 'kode', 'muatan', 'tinggal', 'kosong', 'usaha']
    is_numeric = any(kw in col_lower for kw in numeric_keywords)
    
    if is_numeric and not any(c in text for c in ['rt', 'rw', ':', '.', '/']):
        # Keep only digits and spaces
        text = ''.join(c for c in text if c.isdigit() or c.isspace())
        text = ' '.join(text.split())  # Clean multiple spaces
    
    # Time columns
    if 'operasional' in col_lower or 'jam' in col_lower:
        # Keep digits, dots, dashes, colons
        text = ''.join(c for c in text if c.isdigit() or c in '.-:')
    
    # Contact columns
    if 'contact' in col_lower or 'telepon' in col_lower or 'column 14' in col_lower:
        # Keep digits, slashes, spaces
        text = ''.join(c for c in text if c.isdigit() or c.isalpha() or c in '/- ')
    
    return text.strip()


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def process_full_pipeline(input_path, output_path=None, save_intermediate=True, verbose=True):
    """
    Complete FINAL pipeline with all approved stages
    
    Returns:
        dict: Complete results with metadata, columns, and data
    """
    start_time = time.time()
    
    if verbose:
        print('='*100)
        print('FINAL OCR PIPELINE - PRODUCTION SYSTEM')
        print('='*100)
        print('Using APPROVED methods from experiments/')
        print('='*100)
    
    # ========== STAGE 1: Load Image ==========
    if verbose:
        print('\n[Stage 1/7] Loading image...')
    
    stage1_start = time.time()
    image = load_image(str(input_path))
    stage1_time = time.time() - stage1_start
    
    if verbose:
        print(f'  ✓ Loaded: {image.shape}')
        print(f'  ⏱ Time: {stage1_time:.2f}s')
    
    # ========== STAGE 2: No Preprocessing ==========
    if verbose:
        print('\n[Stage 2/7] Preprocessing...')
        print('  ✓ Using original image (no preprocessing - preserves quality)')
    
    stage2_time = 0.0
    
    # ========== STAGE 3: Detect & Crop BLOK III ==========
    if verbose:
        print('\n[Stage 3/7] Detecting BLOK III (OCR + Border Detection)...')
    
    stage3_start = time.time()
    bbox = detect_table_region(image, use_rapid=False, rapid_detector=None)
    
    if not bbox:
        raise ValueError("BLOK III not detected!")
    
    blok3_cropped = crop_table(image, bbox)
    stage3_time = time.time() - stage3_start
    
    if verbose:
        print(f'  ✓ Detected: {bbox}')
        print(f'  ✓ Cropped size: {blok3_cropped.shape}')
        print(f'  ⏱ Time: {stage3_time:.2f}s')
    
    # Save intermediate
    if save_intermediate:
        inter_path = Path('experiments/results/final_blok3_cropped.jpg')
        inter_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(inter_path), blok3_cropped)
        if verbose:
            print(f'  ✓ Saved: {inter_path}')
    
    # ========== STAGE 4: Detect Table Lines ==========
    if verbose:
        print('\n[Stage 4/7] Detecting table structure (Morphological Lines)...')
    
    stage4_start = time.time()
    h_lines = detect_horizontal_lines(blok3_cropped)
    v_lines = detect_vertical_lines(blok3_cropped)
    stage4_time = time.time() - stage4_start
    
    if verbose:
        print(f'  ✓ Horizontal lines: {len(h_lines)}')
        print(f'  ✓ Vertical lines: {len(v_lines)}')
        print(f'  ✓ Grid: {len(h_lines)-1} rows × {len(v_lines)-1} columns')
        print(f'  ⏱ Time: {stage4_time:.2f}s')
    
    # ========== STAGE 5: Run PaddleOCR PP-OCRv5 ==========
    if verbose:
        print('\n[Stage 5/7] Running PaddleOCR PP-OCRv5 (TERCANGGIH!)...')
    
    stage5_start = time.time()
    detections = run_full_document_ocr(blok3_cropped)
    stage5_time = time.time() - stage5_start
    
    if verbose:
        print(f'  ✓ Detected {len(detections)} text regions')
        print(f'  ⏱ Time: {stage5_time:.2f}s')
    
    # ========== STAGE 6: Adaptive Mapping ==========
    if verbose:
        print('\n[Stage 6/7] Adaptive table mapping...')
    
    stage6_start = time.time()
    
    # Learn column structure
    columns, header_groups = learn_column_structure(detections, v_lines, h_lines)
    header_y_max = max(g['y_center'] for g in header_groups) + 30 if header_groups else 200
    
    # Build table
    rows = build_table(detections, columns, h_lines, v_lines, header_y_max)
    
    # Post-process
    for row in rows:
        for col_name, cell in row['cells'].items():
            cell['text'] = post_process_text(cell['text'], col_name)
    
    stage6_time = time.time() - stage6_start
    
    if verbose:
        print(f'  ✓ Learned {len(columns)} columns')
        print(f'  ✓ Created {len(rows)} data rows')
        print(f'  ⏱ Time: {stage6_time:.2f}s')
    
    # ========== STAGE 7: Export Results ==========
    total_time = time.time() - start_time
    
    results = {
        'metadata': {
            'method': 'FINAL Pipeline (Production)',
            'version': 'FINAL',
            'input_file': str(input_path),
            'original_size': f"{image.shape[1]}x{image.shape[0]}",
            'blok3_size': f"{blok3_cropped.shape[1]}x{blok3_cropped.shape[0]}",
            'grid_size': f"{len(h_lines)-1} rows × {len(v_lines)-1} columns",
            'total_detections': len(detections),
            'total_time_seconds': round(total_time, 2),
            'stage_times': {
                'stage1_load': round(stage1_time, 2),
                'stage2_preprocess': round(stage2_time, 2),
                'stage3_blok3_detect': round(stage3_time, 2),
                'stage4_line_detect': round(stage4_time, 2),
                'stage5_paddleocr': round(stage5_time, 2),
                'stage6_mapping': round(stage6_time, 2)
            },
            'stages': {
                'stage1': 'Image Loading (approved)',
                'stage2': 'No Preprocessing (preserves quality)',
                'stage3': 'BLOK III Detection - OCR + Border (5.6s method)',
                'stage4': 'Morphological Line Detection (0.21s method)',
                'stage5': 'PaddleOCR PP-OCRv5 (TERCANGGIH)',
                'stage6': 'Adaptive Table Mapping (self-learning)',
                'stage7': 'Export Results'
            }
        },
        'columns': [{'index': col['index'], 'name': col['name']} for col in columns],
        'data': rows
    }
    
    # Save if requested
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        if verbose:
            print(f'\n✓ Results saved to: {output_path}')
    
    if verbose:
        print(f'\n✓ PIPELINE COMPLETED in {total_time:.2f}s')
        print('='*100)
    
    return results


# ============================================================================
# CLI INTERFACE
# ============================================================================

if __name__ == '__main__':
    # Test with 1.png
    input_file = Path('contoh gambar/1.png')
    output_file = Path('experiments/final_system/FINAL_RESULTS.json')
    
    results = process_full_pipeline(
        input_path=input_file,
        output_path=output_file,
        save_intermediate=True,
        verbose=True
    )
    
    # Print sample
    print('\n' + '='*100)
    print('SAMPLE RESULTS (First 3 rows)')
    print('='*100)
    
    for row in results['data'][:3]:
        print(f"\nRow {row['row']}:")
        for col_name, cell in list(row['cells'].items())[:5]:  # First 5 columns
            print(f"  {col_name:30s}: \"{cell['text']}\" (conf: {cell['confidence']:.1%})")
