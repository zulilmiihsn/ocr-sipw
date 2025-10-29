"""
Stage 5 (NEW): Full Document OCR + Smart Table Mapping

Strategy:
1. Detect table structure (horizontal & vertical lines)
2. Run PaddleOCR on full document (get all text with X, Y coordinates)
3. Map each detection to (Row, Column) based on line intersections
4. Build table from mapping
5. Post-process per column type

Expected:
- Speed: <60s (vs 481s previously)
- Accuracy: 80-90% (better RT/RW, better context)
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np
import json
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.models.table_schema import COLUMN_HEADERS


# ============================================================================
# STEP 1: Detect Table Structure (Lines)
# ============================================================================

def detect_horizontal_lines(image, min_line_length=None):
    """Detect horizontal lines using morphological operations"""
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
    """Detect vertical lines using morphological operations"""
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
# STEP 2: Run Full Document OCR
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
# STEP 3: Map Detections to Table Grid
# ============================================================================

def map_detection_to_cell(detection, h_lines, v_lines):
    """Map a detection to (row, col) based on line positions"""
    x = detection['x']
    y = detection['y']
    
    # Find row (which horizontal lines is Y between?)
    row = -1
    for i in range(len(h_lines) - 1):
        if h_lines[i] <= y < h_lines[i + 1]:
            row = i
            break
    
    # Find column (which vertical lines is X between?)
    col = -1
    for j in range(len(v_lines) - 1):
        if v_lines[j] <= x < v_lines[j + 1]:
            col = j
            break
    
    return row, col


def build_table_from_detections(detections, h_lines, v_lines):
    """Build table structure from OCR detections"""
    # Initialize table
    num_rows = len(h_lines) - 1
    num_cols = len(v_lines) - 1
    
    table = defaultdict(lambda: {
        'text': '',
        'confidence': 0.0,
        'detections': []
    })
    
    # Identify header rows (first 3-4 rows typically)
    # by checking if they contain header keywords
    header_keywords = ['Kode', 'Nama', 'Jumlah', 'Perkiraan', 'Contact', 'Apakah']
    header_rows = set()
    
    for det in detections:
        if any(keyword in det['text'] for keyword in header_keywords):
            row, _ = map_detection_to_cell(det, h_lines, v_lines)
            if row >= 0 and row < 4:  # Likely header area
                header_rows.add(row)
    
    print(f'  [Detected header rows: {sorted(header_rows)}]')
    
    # Map each detection to a cell
    mapped_count = 0
    unmapped = []
    skip_header = 0
    
    for det in detections:
        row, col = map_detection_to_cell(det, h_lines, v_lines)
        
        # Skip header rows
        if row in header_rows:
            skip_header += 1
            continue
        
        if row >= 0 and col >= 0:
            # Special handling for RT/RW (merged cells, wide text)
            # If text contains "RT" and is in early columns, map to column 3
            if 'RT' in det['text'] and 'RW' in det['text'] and col < 6:
                col = 3  # Force to RT/RW column
                det['text'] = det['text']  # Keep full string
            
            # Add detection to cell
            cell = table[(row, col)]
            cell['detections'].append(det)
            mapped_count += 1
        else:
            unmapped.append(det)
    
    # Merge multiple detections in same cell
    for (row, col), cell in table.items():
        dets = cell['detections']
        if len(dets) == 1:
            cell['text'] = dets[0]['text']
            cell['confidence'] = dets[0]['confidence']
        else:
            # Sort by X position (left to right) and merge
            dets.sort(key=lambda d: d['x'])
            merged_text = ' '.join(d['text'] for d in dets)
            avg_conf = sum(d['confidence'] for d in dets) / len(dets)
            cell['text'] = merged_text
            cell['confidence'] = avg_conf
    
    print(f'  [Mapped {mapped_count}/{len(detections)} detections to cells]')
    print(f'  [Skipped {skip_header} header detections]')
    if unmapped:
        print(f'  [Warning: {len(unmapped)} detections unmapped (outside grid)]')
    
    return table, num_rows, num_cols


# ============================================================================
# STEP 4: Post-Processing
# ============================================================================

def clean_text(text):
    """Basic text cleaning"""
    import re
    text = text.strip()
    # Remove common OCR artifacts
    text = re.sub(r'\s+', ' ', text)  # Multiple spaces → single space
    return text


def postprocess_by_column(text, col_index, confidence):
    """Apply column-specific post-processing"""
    import re
    
    text = clean_text(text)
    
    # Column 0: Kode SLS (4 digits)
    if col_index == 0:
        digits = re.sub(r'\D', '', text)
        if len(digits) == 4:
            return digits
        return text
    
    # Column 1: Kode Sub (2 digits)
    elif col_index == 1:
        digits = re.sub(r'\D', '', text)
        if len(digits) == 2:
            return digits
        return text
    
    # Column 2: RT/RW (already detected as full string!)
    elif col_index == 2:
        # Just clean up spacing
        text = re.sub(r'\s+', ' ', text)
        return text
    
    # Columns 3-9: Numbers
    elif 3 <= col_index <= 9:
        # Remove non-digits and brackets
        digits = re.sub(r'[^\d]', '', text)
        return digits if digits else ''
    
    # Column 10: Nama (text)
    elif col_index == 10:
        return text
    
    # Column 11: Jumlah Shift (number)
    elif col_index == 11:
        digits = re.sub(r'\D', '', text)
        return digits if digits else ''
    
    # Column 12: Jam Operasional (time format)
    elif col_index == 12:
        # Keep dots, dashes, and digits
        time_str = re.sub(r'[^\d.\-:]', '', text)
        return time_str if time_str else ''
    
    # Column 13: Jenis Bangunan (number.text)
    elif col_index == 13:
        return text
    
    # Column 14: Contact Person
    elif col_index == 14:
        return text
    
    # Column 15-16: Boolean (1/0)
    elif col_index in [15, 16]:
        if '1' in text:
            return '1'
        elif '0' in text or not text:
            return '0'
        return text
    
    return text


# ============================================================================
# MAIN TEST
# ============================================================================

def test_smart_mapping_ocr():
    """Test full document OCR with smart table mapping"""
    
    print('='*80)
    print('STAGE 5 (NEW): FULL DOCUMENT OCR + SMART MAPPING')
    print('='*80)
    print('Strategy: Full OCR → Line Detection → Coordinate Mapping → Table')
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
    
    # Detect table structure
    print('\n[2/6] Detecting table structure (lines)...')
    h_lines = detect_horizontal_lines(image, min_line_length=image.shape[1] // 3)
    v_lines = detect_vertical_lines(image, min_line_length=image.shape[0] // 5)
    print(f'  ✓ Found {len(h_lines)} horizontal lines')
    print(f'  ✓ Found {len(v_lines)} vertical lines')
    print(f'  ✓ Table grid: {len(h_lines)-1} rows × {len(v_lines)-1} columns')
    
    # Run full document OCR
    print('\n[3/6] Running full document OCR...')
    detections = run_full_document_ocr(image)
    
    # Map to table
    print('\n[4/6] Mapping detections to table cells...')
    table, num_rows, num_cols = build_table_from_detections(detections, h_lines, v_lines)
    
    # Post-process
    print('\n[5/6] Post-processing cells...')
    processed_count = 0
    for (row, col), cell in table.items():
        if cell['text']:
            original = cell['text']
            processed = postprocess_by_column(original, col, cell['confidence'])
            if processed != original:
                cell['text_processed'] = processed
                processed_count += 1
            else:
                cell['text_processed'] = original
        else:
            cell['text_processed'] = ''
    
    print(f'  ✓ Processed {processed_count} cells')
    
    # Save results
    print('\n[6/6] Saving results...')
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    # Format output
    output_data = {
        'metadata': {
            'method': 'Full Document OCR + Smart Mapping',
            'total_time': f'{time.time() - total_start:.2f}s',
            'grid_size': f'{num_rows} rows × {num_cols} columns',
            'total_detections': len(detections),
            'mapped_cells': len(table),
            'column_headers': COLUMN_HEADERS
        },
        'table': []
    }
    
    # Convert to row-based format
    for row_idx in range(num_rows):
        row_data = {
            'row': row_idx,
            'cells': []
        }
        
        for col_idx in range(num_cols):
            cell = table.get((row_idx, col_idx), {})
            
            col_name = COLUMN_HEADERS[col_idx] if col_idx < len(COLUMN_HEADERS) else f'Col{col_idx}'
            
            row_data['cells'].append({
                'column': col_idx,
                'column_name': col_name,
                'text_raw': cell.get('text', ''),
                'text_final': cell.get('text_processed', ''),
                'confidence': cell.get('confidence', 0.0),
                'num_detections': len(cell.get('detections', []))
            })
        
        output_data['table'].append(row_data)
    
    # Save JSON
    json_path = results_dir / 'stage5_smart_mapping_results.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f'  ✓ Results saved: {json_path.name}')
    
    # Create visualization
    vis_image = image.copy()
    
    # Draw grid
    for y in h_lines:
        cv2.line(vis_image, (0, y), (vis_image.shape[1], y), (0, 255, 0), 1)
    for x in v_lines:
        cv2.line(vis_image, (x, 0), (x, vis_image.shape[0]), (255, 0, 0), 1)
    
    # Draw detections
    for det in detections:
        cv2.circle(vis_image, (det['x'], det['y']), 3, (0, 0, 255), -1)
    
    vis_path = results_dir / 'stage5_smart_mapping_visualization.jpg'
    cv2.imwrite(str(vis_path), vis_image)
    print(f'  ✓ Visualization saved: {vis_path.name}')
    
    # Print summary
    total_time = time.time() - total_start
    
    print('\n' + '='*80)
    print('SUMMARY')
    print('='*80)
    print(f'Total processing time: {total_time:.2f}s')
    print(f'Table size: {num_rows} rows × {num_cols} columns')
    print(f'Total detections: {len(detections)}')
    print(f'Mapped cells: {len(table)} / {num_rows * num_cols}')
    print(f'Empty cells: {num_rows * num_cols - len(table)}')
    
    # Sample output
    print(f'\nSample rows (first 5 data rows):')
    print('='*80)
    
    for row_idx in range(min(5, num_rows)):
        row = output_data['table'][row_idx]
        
        # Get key columns
        kode_sls = row['cells'][0]['text_final'] if row['cells'] else ''
        nama = row['cells'][2]['text_final'] if len(row['cells']) > 2 else ''
        
        if kode_sls or nama:
            print(f"Row {row_idx}: Kode={kode_sls}, Nama/RT={nama}")
            
            # Show all cells for this row
            for cell in row['cells'][:10]:  # First 10 columns
                if cell['text_final']:
                    print(f"  Col {cell['column']:2d} ({cell['column_name'][:20]:20s}): \"{cell['text_final']}\" ({cell['confidence']:.1%})")
            print('-'*80)
    
    print('\n' + '='*80)
    print('FILES CREATED:')
    print('='*80)
    print(f'1. {json_path.name}')
    print(f'2. {vis_path.name}')
    print('='*80)
    
    return True


if __name__ == '__main__':
    success = test_smart_mapping_ocr()
    sys.exit(0 if success else 1)
