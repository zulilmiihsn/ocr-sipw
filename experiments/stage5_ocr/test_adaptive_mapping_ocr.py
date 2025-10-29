"""
Stage 5 (ADAPTIVE): Full Document OCR + Self-Learning Mapping

Strategy:
1. Run PaddleOCR on full document (get all text with X, Y coordinates)
2. Detect HEADER rows automatically (rows with keywords like "Kode", "Nama", etc.)
3. Extract COLUMN NAMES from header rows based on X position
4. Detect table structure (horizontal & vertical lines)
5. Map data rows to columns using LEARNED column positions
6. Build table with ACTUAL column names from document

This is FULLY ADAPTIVE - works even if table structure changes!
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np
import json
from collections import defaultdict
import re

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


# ============================================================================
# STEP 1: Run Full Document OCR
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
# STEP 2: Detect Headers & Learn Column Structure
# ============================================================================

def detect_header_rows(detections, y_threshold=200):
    """Detect which Y positions contain header text"""
    # Header keywords
    header_keywords = ['Kode', 'Nama', 'Jumlah', 'Perkiraan', 'Contact', 
                      'Apakah', 'Shift', 'Operasional', 'Wilayah', 'Muatan']
    
    # Find all detections with header keywords
    header_detections = []
    for det in detections:
        if det['y'] < y_threshold:  # Only look in top area
            if any(keyword in det['text'] for keyword in header_keywords):
                header_detections.append(det)
    
    # Group by Y position (approximate rows)
    y_tolerance = 20  # pixels
    header_y_groups = []
    
    for det in header_detections:
        y = det['y']
        # Find existing group
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
    
    # Sort groups by Y
    header_y_groups.sort(key=lambda g: g['y_center'])
    
    return header_y_groups


def learn_column_structure(header_groups):
    """Learn column names and X positions from headers"""
    # Combine all header detections
    all_header_dets = []
    for group in header_groups:
        all_header_dets.extend(group['detections'])
    
    # Sort by X position
    all_header_dets.sort(key=lambda d: d['x'])
    
    # Build column structure
    columns = []
    x_tolerance = 50  # pixels
    
    for det in all_header_dets:
        x = det['x']
        text = det['text']
        
        # Check if this X position already has a column
        found = False
        for col in columns:
            if abs(col['x_center'] - x) < x_tolerance:
                # Append to existing column name
                col['texts'].append(text)
                col['x_positions'].append(x)
                found = True
                break
        
        if not found:
            columns.append({
                'x_center': x,
                'texts': [text],
                'x_positions': [x]
            })
    
    # Finalize columns
    for col in columns:
        # Average X position
        col['x_center'] = int(np.mean(col['x_positions']))
        # Combine texts (multi-line headers)
        col['name'] = ' '.join(col['texts'])
    
    # Sort by X
    columns.sort(key=lambda c: c['x_center'])
    
    return columns


# ============================================================================
# STEP 3: Detect Table Lines for Row Boundaries
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


# ============================================================================
# STEP 4: Map Detections to Table
# ============================================================================

def map_to_table(detections, columns, h_lines, header_y_max):
    """Map detections to table structure"""
    # Filter data detections (below headers)
    data_detections = [d for d in detections if d['y'] > header_y_max]
    
    # Create rows based on horizontal lines
    rows = []
    for i in range(len(h_lines) - 1):
        y_top = h_lines[i]
        y_bottom = h_lines[i + 1]
        
        # Skip header area
        if y_bottom <= header_y_max:
            continue
        
        # Find detections in this row
        row_dets = [d for d in data_detections if y_top <= d['y'] < y_bottom]
        
        if row_dets:
            rows.append({
                'row_index': len(rows),
                'y_top': y_top,
                'y_bottom': y_bottom,
                'y_center': (y_top + y_bottom) // 2,
                'detections': row_dets
            })
    
    # Map each row's detections to columns
    for row in rows:
        row['cells'] = {}
        
        for det in row['detections']:
            x = det['x']
            
            # Find closest column
            min_dist = float('inf')
            best_col_idx = -1
            
            for col_idx, col in enumerate(columns):
                dist = abs(x - col['x_center'])
                if dist < min_dist:
                    min_dist = dist
                    best_col_idx = col_idx
            
            # Assign to column (handle multiple detections per cell)
            if best_col_idx >= 0:
                if best_col_idx not in row['cells']:
                    row['cells'][best_col_idx] = []
                row['cells'][best_col_idx].append(det)
    
    # Merge multiple detections in same cell
    for row in rows:
        for col_idx, dets in row['cells'].items():
            if len(dets) == 1:
                row['cells'][col_idx] = {
                    'text': dets[0]['text'],
                    'confidence': dets[0]['confidence']
                }
            else:
                # Sort by X and merge
                dets.sort(key=lambda d: d['x'])
                merged_text = ' '.join(d['text'] for d in dets)
                avg_conf = sum(d['confidence'] for d in dets) / len(dets)
                row['cells'][col_idx] = {
                    'text': merged_text,
                    'confidence': avg_conf
                }
    
    return rows


# ============================================================================
# MAIN TEST
# ============================================================================

def test_adaptive_mapping_ocr():
    """Test adaptive OCR that learns table structure from document"""
    
    print('='*80)
    print('STAGE 5 (ADAPTIVE): SELF-LEARNING TABLE MAPPING')
    print('='*80)
    print('Strategy: Learn table structure FROM the document itself!')
    print('='*80)
    
    total_start = time.time()
    
    # Load image
    print('\n[1/6] Loading BLOK III table...')
    image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
    
    if not image_path.exists():
        print(f'  X ERROR: {image_path} not found')
        return False
    
    image = cv2.imread(str(image_path))
    print(f'  ✓ Image loaded: {image.shape}')
    
    # Run full document OCR
    print('\n[2/6] Running full document OCR...')
    detections = run_full_document_ocr(image)
    
    # Detect headers and learn columns
    print('\n[3/6] Learning table structure from headers...')
    header_groups = detect_header_rows(detections, y_threshold=200)
    print(f'  ✓ Found {len(header_groups)} header row groups')
    
    columns = learn_column_structure(header_groups)
    print(f'  ✓ Learned {len(columns)} columns from document:')
    for i, col in enumerate(columns):
        print(f'     Col {i:2d} (X≈{col["x_center"]:4d}): "{col["name"]}"')
    
    # Detect horizontal lines for rows
    print('\n[4/6] Detecting row boundaries...')
    h_lines = detect_horizontal_lines(image, min_line_length=image.shape[1] // 3)
    print(f'  ✓ Found {len(h_lines)} horizontal lines')
    
    # Determine where headers end
    header_y_max = max(g['y_center'] for g in header_groups) + 30 if header_groups else 200
    print(f'  ✓ Header area ends at Y={header_y_max}')
    
    # Map to table
    print('\n[5/6] Mapping detections to table...')
    rows = map_to_table(detections, columns, h_lines, header_y_max)
    print(f'  ✓ Created {len(rows)} data rows')
    
    # Save results
    print('\n[6/6] Saving results...')
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    # Format output
    output_data = {
        'metadata': {
            'method': 'Adaptive OCR (Self-Learning)',
            'total_time': f'{time.time() - total_start:.2f}s',
            'learned_columns': len(columns),
            'data_rows': len(rows),
            'total_detections': len(detections)
        },
        'columns': [{'index': i, 'name': col['name'], 'x_center': col['x_center']} 
                   for i, col in enumerate(columns)],
        'rows': []
    }
    
    # Add rows
    for row in rows:
        row_data = {
            'row': row['row_index'],
            'y_position': row['y_center'],
            'cells': []
        }
        
        for col_idx in range(len(columns)):
            cell = row['cells'].get(col_idx, {'text': '', 'confidence': 0.0})
            row_data['cells'].append({
                'column': col_idx,
                'column_name': columns[col_idx]['name'],
                'text': cell.get('text', ''),
                'confidence': cell.get('confidence', 0.0)
            })
        
        output_data['rows'].append(row_data)
    
    # Save JSON
    json_path = results_dir / 'stage5_adaptive_results.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f'  ✓ Results saved: {json_path.name}')
    
    # Print summary
    total_time = time.time() - total_start
    
    print('\n' + '='*80)
    print('SUMMARY')
    print('='*80)
    print(f'Total processing time: {total_time:.2f}s')
    print(f'Learned columns: {len(columns)}')
    print(f'Data rows: {len(rows)}')
    print(f'Total cells: {len(rows) * len(columns)}')
    
    # Sample output
    print(f'\nSample data (first 5 rows):')
    print('='*80)
    
    for row in rows[:5]:
        print(f"\nRow {row['row_index']}:")
        for col_idx, cell in row['cells'].items():
            col_name = columns[col_idx]['name'][:30]
            text = cell['text'][:30]
            conf = cell['confidence']
            if text:
                print(f"  [{col_name:30s}] = \"{text}\" ({conf:.1%})")
        print('-'*80)
    
    print('\n' + '='*80)
    print('✓ ADAPTIVE MAPPING COMPLETE!')
    print('  Table structure learned FROM the document itself!')
    print('='*80)
    
    return True


if __name__ == '__main__':
    success = test_adaptive_mapping_ocr()
    sys.exit(0 if success else 1)
