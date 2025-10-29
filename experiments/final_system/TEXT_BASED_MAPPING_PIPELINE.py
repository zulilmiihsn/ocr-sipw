"""
========================================
TEXT-BASED MAPPING PIPELINE
========================================

Strategy:
1. Scan full document with PaddleOCR (text + positions)
2. Identify HEADER texts and their X positions
3. Use header X positions as COLUMN ANCHORS
4. Map data texts to columns by CLOSEST X distance
5. Use horizontal lines for ROW boundaries

This is more intelligent than vertical line detection!

Author: Lab OCR Team
Version: Smart Mapping v3.0
Date: October 2025
"""

import sys
import time
import re
from pathlib import Path
import cv2
import numpy as np
import json
from collections import defaultdict
from difflib import SequenceMatcher

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.pdf_handler import load_image
from src.ocr.table_detector import detect_table_region, crop_table


# ============================================================================
# PADDLEOCR ENGINE (Singleton)
# ============================================================================

class PaddleOCREngine:
    """Singleton PaddleOCR instance"""
    _instance = None
    _ocr = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._ocr is None:
            from paddleocr import PaddleOCR
            print("  🔄 Loading PaddleOCR PP-OCRv5...")
            self._ocr = PaddleOCR(
                lang='en'
            )
            print("  ✓ PaddleOCR loaded")
    
    def predict(self, image):
        return self._ocr.predict(image)


# ============================================================================
# STAGE 4: HORIZONTAL LINE DETECTION (for rows only)
# ============================================================================

def detect_horizontal_lines(image):
    """Detect horizontal table lines"""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Binary threshold
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Horizontal kernel
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    detect_horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    
    # Find contours
    contours, _ = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Extract Y positions
    h_lines = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w > image.shape[1] * 0.5:  # At least 50% width
            h_lines.append(y)
    
    # Sort and deduplicate
    h_lines = sorted(list(set(h_lines)))
    
    return h_lines


# ============================================================================
# STAGE 5: FULL DOCUMENT OCR WITH PADDLEOCR
# ============================================================================

def preprocess_for_ocr(image):
    """Smart preprocessing for PaddleOCR"""
    # Ensure 3-channel BGR
    if len(image.shape) == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    
    # 2x upscale
    h, w = image.shape[:2]
    image = cv2.resize(image, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
    
    # Denoise (colored)
    image = cv2.fastNlMeansDenoisingColored(image, None, 3, 3, 7, 21)
    
    # CLAHE in LAB space
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge([l, a, b])
    image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    
    # Sharpen
    kernel = np.array([[-1, -1, -1],
                       [-1,  9, -1],
                       [-1, -1, -1]])
    image = cv2.filter2D(image, -1, kernel)
    
    return image


def run_full_document_ocr(image):
    """Run PaddleOCR on full document and extract all detections"""
    # Preprocess
    image_processed = preprocess_for_ocr(image)
    
    # Get scale factor
    scale_x = image_processed.shape[1] / image.shape[1]
    scale_y = image_processed.shape[0] / image.shape[0]
    
    # Run OCR
    engine = PaddleOCREngine()
    result = engine.predict(image_processed)
    
    # Parse results
    detections = []
    
    if hasattr(result, '__iter__'):
        result_list = list(result)
        
        if len(result_list) > 0:
            ocr_result = result_list[0]
            
            if isinstance(ocr_result, dict):
                # OCRResult object format
                dt_polys = ocr_result.get('dt_polys', [])
                rec_texts = ocr_result.get('rec_texts', [])
                rec_scores = ocr_result.get('rec_scores', [])
                
                for i, (poly, text, conf) in enumerate(zip(dt_polys, rec_texts, rec_scores)):
                    poly_array = np.array(poly)
                    
                    # Scale back to original
                    x_coords = poly_array[:, 0] / scale_x
                    y_coords = poly_array[:, 1] / scale_y
                    
                    x_min = min(x_coords)
                    x_max = max(x_coords)
                    y_min = min(y_coords)
                    y_max = max(y_coords)
                    
                    detections.append({
                        'bbox': [int(x_min), int(y_min), int(x_max), int(y_max)],
                        'text': text.strip(),
                        'confidence': float(conf),
                        'x_center': (x_min + x_max) / 2,
                        'y_center': (y_min + y_max) / 2,
                        'x_min': x_min,
                        'x_max': x_max,
                        'y_min': y_min,
                        'y_max': y_max
                    })
    
    return detections


# ============================================================================
# STAGE 6: INTELLIGENT COLUMN LEARNING FROM HEADERS
# ============================================================================

def identify_header_detections(detections, h_lines):
    """
    Identify header rows based on Y-position ONLY.
    All text in the header region = column headers.
    
    The header has 2-3 rows:
    - Row 1: Main column names (Y ~0-30)
    - Row 2: Sub-column names (Y ~30-60)
    - Row 3: Column numbers (1), (2), ... (Y ~160-190)
    """
    # Header region: before 4th or 5th horizontal line (to include column numbers)
    if len(h_lines) >= 5:
        header_y_max = h_lines[4]  # After column numbers row
    elif len(h_lines) >= 4:
        header_y_max = h_lines[3]
    elif len(h_lines) >= 3:
        header_y_max = h_lines[2]
    else:
        # Fallback: Y=200 (covers typical header height)
        header_y_max = 200
    
    header_dets = []
    
    for det in detections:
        y_center = det['y_center']
        
        # ALL text in header region is considered a column header
        if y_center < header_y_max:
            header_dets.append(det)
    
    return header_dets, header_y_max


def learn_columns_from_headers(header_dets):
    """
    Learn column structure from header detections.
    Each unique X-center becomes a column anchor.
    """
    # Group headers by X position with tolerance
    x_tolerance = 30  # pixels
    column_groups = []
    
    for det in header_dets:
        x_center = det['x_center']
        text = det['text']
        
        # Try to add to existing column
        added = False
        for col in column_groups:
            if abs(col['x_center'] - x_center) < x_tolerance:
                col['texts'].append(text)
                col['x_positions'].append(x_center)
                added = True
                break
        
        if not added:
            column_groups.append({
                'x_center': x_center,
                'texts': [text],
                'x_positions': [x_center]
            })
    
    # Sort by X position (left to right)
    column_groups.sort(key=lambda c: c['x_center'])
    
    # Refine X-center by averaging
    columns = []
    for idx, col_group in enumerate(column_groups):
        avg_x = np.mean(col_group['x_positions'])
        col_name = ' '.join(col_group['texts'])
        
        columns.append({
            'index': idx,
            'name': col_name,
            'x_center': avg_x,
            'texts': col_group['texts']
        })
    
    return columns


# ============================================================================
# STAGE 7: MAP DATA TO TABLE
# ============================================================================

def map_data_to_table(detections, columns, h_lines, header_y_max):
    """
    Map each data detection to (row, col) based on:
    - Row: which horizontal line pair it falls between
    - Col: closest column X-center
    """
    # Initialize table
    num_rows = len(h_lines) - 1
    num_cols = len(columns)
    
    table = []
    for r in range(num_rows):
        row = {
            'row_index': r,
            'y_start': h_lines[r],
            'y_end': h_lines[r + 1],
            'cells': {}
        }
        for c in range(num_cols):
            row['cells'][c] = {
                'text': '',
                'confidence': 0.0,
                'detections': []
            }
        table.append(row)
    
    # Map each detection
    for det in detections:
        x = det['x_center']
        y = det['y_center']
        
        # Skip headers
        if y < header_y_max:
            continue
        
        # Find row
        row_idx = -1
        for r in range(len(h_lines) - 1):
            if h_lines[r] <= y < h_lines[r + 1]:
                row_idx = r
                break
        
        if row_idx == -1:
            continue
        
        # Find closest column
        col_idx = -1
        min_dist = float('inf')
        for c_idx, col in enumerate(columns):
            dist = abs(x - col['x_center'])
            if dist < min_dist:
                min_dist = dist
                col_idx = c_idx
        
        if col_idx == -1:
            continue
        
        # Add to table
        cell = table[row_idx]['cells'][col_idx]
        cell['detections'].append(det)
    
    # Consolidate multi-detection cells
    for row in table:
        for col_idx, cell in row['cells'].items():
            if cell['detections']:
                # Sort by X position (left to right)
                cell['detections'].sort(key=lambda d: d['x_center'])
                
                # Combine texts
                texts = [d['text'] for d in cell['detections']]
                confidences = [d['confidence'] for d in cell['detections']]
                
                cell['text'] = ' '.join(texts)
                cell['confidence'] = np.mean(confidences) if confidences else 0.0
    
    return table


# ============================================================================
# STAGE 8: POST-PROCESSING
# ============================================================================

def clean_text(text, column_name):
    """Column-specific text cleaning"""
    text = text.strip()
    
    # Remove brackets
    text = re.sub(r'^\[+', '', text)
    text = re.sub(r'\]+$', '', text)
    
    # Column-specific rules (PRIORITIZE specific keywords first)
    col_lower = column_name.lower()
    
    # Wilayah: always keep as text (check first!)
    if 'wilayah' in col_lower:
        pass  # Keep as-is
    
    # Contact: always keep as text
    elif 'contact' in col_lower or 'telepon' in col_lower or 'email' in col_lower:
        pass  # Keep as-is
    
    # RT/RW: format as "RT XXX RW YYY"
    elif ('rt' in col_lower or 'rw' in col_lower) and 'nama' in col_lower:
        # Extract digits
        digits = re.findall(r'\d+', text)
        if len(digits) >= 2:
            text = f"RT {digits[0]} RW {digits[1]}"
        elif len(digits) == 1:
            text = f"RT {digits[0]} RW 001"
    
    # Time: keep only time format
    elif 'jam' in col_lower or 'operasional' in col_lower:
        time_match = re.search(r'\d{1,2}\.\d{2}\s*-\s*\d{1,2}\.\d{2}', text)
        if time_match:
            text = time_match.group(0)
    
    # Numeric columns: only digits and spaces
    elif any(kw in col_lower for kw in ['kode', 'jumlah muatan kk', 'jumlah muatan usaha', 'shift', 'total', 'dominan', 'perubahan', 'no', 'bangunan']):
        text = re.sub(r'[^0-9\s]', '', text)
        text = text.strip()
    
    # For all other columns: keep as-is
    
    return text


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def process_with_text_mapping(input_path='contoh gambar/1.png', output_path='experiments/final_system/TEXT_MAPPING_RESULTS.json'):
    """Complete pipeline with text-based column mapping"""
    
    print("=" * 100)
    print("TEXT-BASED MAPPING PIPELINE")
    print("=" * 100)
    print("Strategy: Use header text positions as column anchors (no vertical lines!)")
    print("=" * 100)
    
    total_start = time.time()
    
    # Stage 1: Load
    print("\n[Stage 1/7] Loading image...")
    t1 = time.time()
    image = load_image(input_path)
    print(f"  ✓ Loaded: {image.shape}")
    print(f"  ⏱ Time: {time.time() - t1:.2f}s")
    
    # Stage 2: No preprocessing
    print("\n[Stage 2/7] Preprocessing...")
    print(f"  ✓ Using original image (preserves quality)")
    
    # Stage 3: Detect BLOK III
    print("\n[Stage 3/7] Detecting BLOK III...")
    t3 = time.time()
    bbox = detect_table_region(image)
    blok3_img = crop_table(image, bbox)
    print(f"  ✓ Cropped: {blok3_img.shape}")
    print(f"  ⏱ Time: {time.time() - t3:.2f}s")
    
    # Stage 4: Detect horizontal lines only
    print("\n[Stage 4/7] Detecting horizontal lines (for rows)...")
    t4 = time.time()
    h_lines = detect_horizontal_lines(blok3_img)
    print(f"  ✓ Horizontal lines: {len(h_lines)}")
    print(f"  ⏱ Time: {time.time() - t4:.2f}s")
    
    # Stage 5: Full document OCR
    print("\n[Stage 5/7] Running PaddleOCR...")
    t5 = time.time()
    detections = run_full_document_ocr(blok3_img)
    print(f"  ✓ Detected {len(detections)} text regions")
    print(f"  ⏱ Time: {time.time() - t5:.2f}s")
    
    # Stage 6: Learn columns from headers
    print("\n[Stage 6/7] Learning column structure from headers...")
    t6 = time.time()
    header_dets, header_y_max = identify_header_detections(detections, h_lines)
    columns = learn_columns_from_headers(header_dets)
    print(f"  ✓ Found {len(header_dets)} header texts")
    print(f"  ✓ Learned {len(columns)} columns:")
    for col in columns:
        print(f"     Col {col['index']:2d} @ X={col['x_center']:4.0f}: {col['name'][:40]}")
    print(f"  ⏱ Time: {time.time() - t6:.2f}s")
    
    # Stage 7: Map data to table
    print("\n[Stage 7/7] Mapping data to table...")
    t7 = time.time()
    table = map_data_to_table(detections, columns, h_lines, header_y_max)
    
    # Post-process
    for row in table:
        for col_idx, cell in row['cells'].items():
            col_idx_int = int(col_idx)  # Convert string key to int
            col_name = columns[col_idx_int]['name'] if col_idx_int < len(columns) else ''
            cell['text_cleaned'] = clean_text(cell['text'], col_name)
    
    print(f"  ✓ Created {len(table)} rows × {len(columns)} columns")
    print(f"  ⏱ Time: {time.time() - t7:.2f}s")
    
    # Save results
    results = {
        'metadata': {
            'method': 'Text-Based Column Mapping v3.0',
            'input': input_path,
            'total_time': f"{time.time() - total_start:.2f}s",
            'detections': len(detections),
            'columns': len(columns),
            'rows': len(table)
        },
        'columns': columns,
        'table': []
    }
    
    for row in table:
        row_data = {
            'row_index': row['row_index'],
            'cells': {}
        }
        for col_idx, cell in row['cells'].items():
            row_data['cells'][col_idx] = {
                'text': cell['text_cleaned'],
                'text_raw': cell['text'],
                'confidence': cell['confidence']
            }
        results['table'].append(row_data)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Results saved to: {output_path}")
    print(f"\n✓ PIPELINE COMPLETED in {time.time() - total_start:.2f}s")
    print("=" * 100)
    
    # Show sample
    print("\n" + "=" * 100)
    print("SAMPLE RESULTS (First 3 rows)")
    print("=" * 100)
    
    for row_idx in range(min(3, len(table))):
        row = table[row_idx]
        print(f"\nRow {row_idx}:")
        for col_idx in range(min(5, len(columns))):
            if col_idx in row['cells']:
                cell = row['cells'][col_idx]
                col_name = columns[col_idx]['name'][:25].ljust(25)
                text = cell['text_cleaned'][:20].ljust(20)
                conf = cell['confidence']
                print(f"  {col_name}: \"{text}\" (conf: {conf:.1%})")
    
    return results


# ============================================================================
# RUN
# ============================================================================

if __name__ == '__main__':
    process_with_text_mapping(
        input_path='contoh gambar/1.png',
        output_path='experiments/final_system/TEXT_MAPPING_RESULTS.json'
    )
