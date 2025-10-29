"""
Stage 5 (ADAPTIVE v2): Improved Column Detection + Post-Processing

Improvements:
1. Use VERTICAL LINES for accurate column boundaries (not X-position clustering)
2. Map detections to columns based on vertical line boundaries
3. Post-processing to remove bracket artifacts
4. Better empty cell handling

Expected: 90%+ accuracy!
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np
import json
import re
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


# ============================================================================
# STEP 1: Run Full Document OCR (Same as v1)
# ============================================================================

class PaddleOCREngine:
    """Singleton PaddleOCR instance"""
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            print('  [Loading PaddleOCR models...]')
            start = time.time()
            from paddleocr import PaddleOCR
            cls._instance = PaddleOCR(lang='en', use_textline_orientation=False)
            print(f'  [Models loaded in {time.time() - start:.2f}s]')
        return cls._instance


def run_full_document_ocr(image):
    """Run PaddleOCR on full document"""
    ocr = PaddleOCREngine.get_instance()
    
    print('  [Running full document OCR...]')
    start = time.time()
    result = ocr.predict(image)
    print(f'  [OCR completed in {time.time() - start:.2f}s]')
    
    detections = []
    if result and len(result) > 0 and isinstance(result[0], dict):
        dt_polys = result[0].get('dt_polys', [])
        rec_texts = result[0].get('rec_texts', [])
        rec_scores = result[0].get('rec_scores', [])
        
        for bbox, text, confidence in zip(dt_polys, rec_texts, rec_scores):
            bbox_array = np.array(bbox)
            x_min = int(bbox_array[:, 0].min())
            y_min = int(bbox_array[:, 1].min())
            x_max = int(bbox_array[:, 0].max())
            y_max = int(bbox_array[:, 1].max())
            
            center_x = (x_min + x_max) // 2
            center_y = (y_min + y_max) // 2
            
            detections.append({
                'text': text,
                'confidence': float(confidence),
                'x': center_x,
                'y': center_y,
                'x_min': x_min,
                'y_min': y_min,
                'x_max': x_max,
                'y_max': y_max,
                'width': x_max - x_min,
                'height': y_max - y_min
            })
    
    print(f'  [Found {len(detections)} text detections]')
    return detections


# ============================================================================
# STEP 2: Detect Table Structure (Lines)
# ============================================================================

def detect_horizontal_lines(image, min_line_length=None):
    """Detect horizontal lines"""
    if min_line_length is None:
        min_line_length = image.shape[1] // 3
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 15, 2)
    
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_line_length, 1))
    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    
    contours, _ = cv2.findContours(h_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    y_positions = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w > min_line_length:
            y_positions.append(y)
    
    return sorted(set(y_positions))


def detect_vertical_lines(image, min_line_length=None):
    """Detect vertical lines"""
    if min_line_length is None:
        min_line_length = image.shape[0] // 5
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 15, 2)
    
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, min_line_length))
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
    
    contours, _ = cv2.findContours(v_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    x_positions = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if h > min_line_length:
            x_positions.append(x)
    
    return sorted(set(x_positions))


# ============================================================================
# STEP 3: Learn Column Names from Headers
# ============================================================================

def detect_header_rows(detections, y_threshold=200):
    """Detect which Y positions contain header text"""
    header_keywords = ['Kode', 'Nama', 'Jumlah', 'Perkiraan', 'Contact', 
                      'Apakah', 'Shift', 'Operasional', 'Wilayah', 'Muatan',
                      'BTT', 'BKU', 'BBTT', 'Total']
    
    header_detections = []
    for det in detections:
        if det['y'] < y_threshold:
            if any(keyword in det['text'] for keyword in header_keywords):
                header_detections.append(det)
    
    # Group by Y position
    y_tolerance = 20
    header_y_groups = []
    
    for det in header_detections:
        y = det['y']
        found = False
        for group in header_y_groups:
            if abs(group['y_center'] - y) < y_tolerance:
                group['detections'].append(det)
                found = True
                break
        
        if not found:
            header_y_groups.append({
                'y_center': y,
                'detections': [det]
            })
    
    header_y_groups.sort(key=lambda g: g['y_center'])
    return header_y_groups


def learn_column_names_from_lines(header_groups, v_lines):
    """
    NEW: Learn column names by mapping headers to vertical line boundaries
    More accurate than X-position clustering!
    """
    # Combine all header detections
    all_header_dets = []
    for group in header_groups:
        all_header_dets.extend(group['detections'])
    
    # Create columns based on vertical lines
    num_cols = len(v_lines) - 1
    columns = []
    
    for i in range(num_cols):
        x_left = v_lines[i]
        x_right = v_lines[i + 1]
        x_center = (x_left + x_right) // 2
        
        # Find all header texts in this column
        col_headers = []
        for det in all_header_dets:
            # Check if detection center is within this column
            if x_left <= det['x'] < x_right:
                col_headers.append(det['text'])
        
        # Combine multi-line headers
        col_name = ' '.join(col_headers) if col_headers else f'Column {i}'
        
        columns.append({
            'index': i,
            'name': col_name,
            'x_left': x_left,
            'x_right': x_right,
            'x_center': x_center
        })
    
    return columns


# ============================================================================
# STEP 4: Map Detections to Table
# ============================================================================

def map_detection_to_cell(det, h_lines, v_lines, header_y_max):
    """Map a detection to (row, col) based on line boundaries"""
    x = det['x']
    y = det['y']
    
    # Skip if in header area
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
    for j in range(len(v_lines) - 1):
        if v_lines[j] <= x < v_lines[j + 1]:
            col = j
            break
    
    return row, col


def map_to_table(detections, columns, h_lines, v_lines, header_y_max):
    """Map detections to table structure using line boundaries"""
    
    # Create table structure
    table = defaultdict(lambda: {'detections': []})
    
    # Map each detection
    for det in detections:
        row, col = map_detection_to_cell(det, h_lines, v_lines, header_y_max)
        
        if row >= 0 and col >= 0:
            table[(row, col)]['detections'].append(det)
    
    # Merge multiple detections per cell
    for (row, col), cell in table.items():
        dets = cell['detections']
        if len(dets) == 1:
            cell['text'] = dets[0]['text']
            cell['confidence'] = dets[0]['confidence']
        else:
            # Sort by X and merge
            dets.sort(key=lambda d: d['x'])
            merged_text = ' '.join(d['text'] for d in dets)
            avg_conf = sum(d['confidence'] for d in dets) / len(dets)
            cell['text'] = merged_text
            cell['confidence'] = avg_conf
    
    # Create rows
    rows = []
    for row_idx in range(len(h_lines) - 1):
        # Skip header rows
        y_center = (h_lines[row_idx] + h_lines[row_idx + 1]) // 2
        if y_center <= header_y_max:
            continue
        
        row_data = {
            'row_index': len(rows),
            'y_top': h_lines[row_idx],
            'y_bottom': h_lines[row_idx + 1],
            'cells': {}
        }
        
        # Add cells for this row
        for col_idx in range(len(columns)):
            cell = table.get((row_idx, col_idx), {})
            row_data['cells'][col_idx] = {
                'text': cell.get('text', ''),
                'confidence': cell.get('confidence', 0.0)
            }
        
        rows.append(row_data)
    
    return rows


# ============================================================================
# STEP 5: Post-Processing
# ============================================================================

def post_process_text(text, column_name):
    """
    Post-process text to fix common issues:
    1. Remove bracket artifacts ([15 → 15)
    2. Clean whitespace
    3. Column-specific fixes
    """
    if not text:
        return ''
    
    # Remove leading bracket artifacts
    text = re.sub(r'^\[+', '', text)
    
    # Clean whitespace
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    
    # Column-specific processing
    # Numbers: remove non-numeric chars (except spaces for merged cells)
    if any(keyword in column_name for keyword in ['Jumlah', 'BTT', 'BKU', 'BBTT', 'Total', 'Shift', 'Muatan']):
        # Keep only digits and spaces
        text = re.sub(r'[^\d\s]', '', text)
        text = text.strip()
    
    # Time: keep dots, dashes, colons, digits
    if 'Operasional' in column_name or 'Jam' in column_name:
        text = re.sub(r'[^\d.\-:]', '', text)
    
    # Contact: keep digits, slashes, @ for email
    if 'Contact' in column_name:
        text = re.sub(r'[^\d\w@./\-]', '', text)
    
    return text


# ============================================================================
# MAIN TEST
# ============================================================================

def test_adaptive_mapping_v2():
    """Test improved adaptive OCR with vertical line detection"""
    
    print('='*80)
    print('STAGE 5 (ADAPTIVE v2): IMPROVED COLUMN DETECTION')
    print('='*80)
    print('Improvements: Vertical lines + Post-processing')
    print('='*80)
    
    total_start = time.time()
    
    # Load image
    print('\n[1/7] Loading BLOK III table...')
    image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
    
    if not image_path.exists():
        print(f'  X ERROR: {image_path} not found')
        return False
    
    image = cv2.imread(str(image_path))
    print(f'  ✓ Image loaded: {image.shape}')
    
    # Run full document OCR
    print('\n[2/7] Running full document OCR...')
    detections = run_full_document_ocr(image)
    
    # Detect table structure
    print('\n[3/7] Detecting table structure (lines)...')
    h_lines = detect_horizontal_lines(image, min_line_length=image.shape[1] // 3)
    v_lines = detect_vertical_lines(image, min_line_length=image.shape[0] // 5)
    print(f'  ✓ Found {len(h_lines)} horizontal lines')
    print(f'  ✓ Found {len(v_lines)} vertical lines')
    print(f'  ✓ Grid: {len(h_lines)-1} rows × {len(v_lines)-1} columns')
    
    # Detect headers
    print('\n[4/7] Learning column names from headers...')
    header_groups = detect_header_rows(detections, y_threshold=200)
    print(f'  ✓ Found {len(header_groups)} header row groups')
    
    # Learn columns from vertical lines
    columns = learn_column_names_from_lines(header_groups, v_lines)
    print(f'  ✓ Mapped {len(columns)} columns to vertical lines:')
    for i, col in enumerate(columns[:10]):  # Show first 10
        print(f'     Col {i:2d} [X:{col["x_left"]:4d}-{col["x_right"]:4d}]: "{col["name"][:40]}"')
    if len(columns) > 10:
        print(f'     ... and {len(columns)-10} more columns')
    
    # Determine header boundary
    header_y_max = max(g['y_center'] for g in header_groups) + 30 if header_groups else 200
    print(f'  ✓ Header area ends at Y={header_y_max}')
    
    # Map to table
    print('\n[5/7] Mapping detections to table cells...')
    rows = map_to_table(detections, columns, h_lines, v_lines, header_y_max)
    print(f'  ✓ Created {len(rows)} data rows')
    
    # Post-process
    print('\n[6/7] Post-processing text...')
    processed_count = 0
    for row in rows:
        for col_idx, cell in row['cells'].items():
            if cell['text']:
                original = cell['text']
                col_name = columns[col_idx]['name']
                processed = post_process_text(original, col_name)
                cell['text_final'] = processed
                if processed != original:
                    processed_count += 1
            else:
                cell['text_final'] = ''
    print(f'  ✓ Post-processed {processed_count} cells')
    
    # Save results
    print('\n[7/7] Saving results...')
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    # Format output
    output_data = {
        'metadata': {
            'method': 'Adaptive OCR v2 (Improved)',
            'total_time': f'{time.time() - total_start:.2f}s',
            'grid_size': f'{len(h_lines)-1} rows × {len(v_lines)-1} columns',
            'learned_columns': len(columns),
            'data_rows': len(rows),
            'total_detections': len(detections)
        },
        'columns': [{'index': col['index'], 'name': col['name'], 
                    'x_range': [col['x_left'], col['x_right']]} 
                   for col in columns],
        'rows': []
    }
    
    # Add rows
    for row in rows:
        row_data = {
            'row': row['row_index'],
            'y_range': [row['y_top'], row['y_bottom']],
            'cells': []
        }
        
        for col_idx in range(len(columns)):
            cell = row['cells'].get(col_idx, {'text': '', 'text_final': '', 'confidence': 0.0})
            row_data['cells'].append({
                'column': col_idx,
                'column_name': columns[col_idx]['name'],
                'text_raw': cell.get('text', ''),
                'text_final': cell.get('text_final', ''),
                'confidence': cell.get('confidence', 0.0)
            })
        
        output_data['rows'].append(row_data)
    
    # Save JSON
    json_path = results_dir / 'stage5_adaptive_v2_results.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f'  ✓ Results saved: {json_path.name}')
    
    # Print summary
    total_time = time.time() - total_start
    
    print('\n' + '='*80)
    print('SUMMARY')
    print('='*80)
    print(f'Total processing time: {total_time:.2f}s')
    print(f'Table size: {len(h_lines)-1} rows × {len(v_lines)-1} columns')
    print(f'Learned columns: {len(columns)}')
    print(f'Data rows: {len(rows)}')
    
    # Sample output
    print(f'\nSample data (first 3 rows):')
    print('='*80)
    
    for row in rows[:3]:
        print(f"\nRow {row['row_index']}:")
        filled = 0
        for col_idx, cell in row['cells'].items():
            if cell.get('text_final', ''):
                col_name = columns[col_idx]['name'][:25]
                text = cell['text_final'][:25]
                conf = cell['confidence']
                print(f"  Col {col_idx:2d} [{col_name:25s}] = \"{text}\" ({conf:.1%})")
                filled += 1
        print(f'  → {filled}/{len(columns)} cells filled')
        print('-'*80)
    
    print('\n' + '='*80)
    print('✓ ADAPTIVE v2 COMPLETE!')
    print('  Improvements:')
    print('  1. ✓ Vertical line detection for accurate column boundaries')
    print('  2. ✓ Post-processing to remove bracket artifacts')
    print('  3. ✓ Column-specific text cleaning')
    print('='*80)
    
    return True


if __name__ == '__main__':
    success = test_adaptive_mapping_v2()
    sys.exit(0 if success else 1)
