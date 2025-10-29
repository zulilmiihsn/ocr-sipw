"""Debug: What's in cell (Row 4, Column 3)?"""

import sys
import cv2
from pathlib import Path
from collections import defaultdict

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load image
image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
image = cv2.imread(str(image_path))

# Import functions
from experiments.stage5_ocr.test_smart_mapping_ocr import (
    detect_horizontal_lines,
    detect_vertical_lines,
    map_detection_to_cell,
    run_full_document_ocr
)

# Detect lines
h_lines = detect_horizontal_lines(image, min_line_length=image.shape[1] // 3)
v_lines = detect_vertical_lines(image, min_line_length=image.shape[0] // 5)

# Run OCR
detections = run_full_document_ocr(image)

print('='*80)
print('CELL (4, 3) DEBUG')
print('='*80)

# Identify header rows
header_keywords = ['Kode', 'Nama', 'Jumlah', 'Perkiraan', 'Contact', 'Apakah']
header_rows = set()

for det in detections:
    if any(keyword in det['text'] for keyword in header_keywords):
        row, _ = map_detection_to_cell(det, h_lines, v_lines)
        if row >= 0 and row < 4:
            header_rows.add(row)

print(f'\nHeader rows: {sorted(header_rows)}')

# Find all detections that map to (4, 3)
cell_43_dets = []

for det in detections:
    row, col = map_detection_to_cell(det, h_lines, v_lines)
    
    if row == 4 and col == 3:
        cell_43_dets.append(det)

print(f'\nDetections mapped to Cell (4, 3):')
print('-'*80)

for det in cell_43_dets:
    is_header = any(keyword in det['text'] for keyword in header_keywords)
    skip = (det['text'] in [d['text'] for d in cell_43_dets if any(k in d['text'] for k in header_keywords)])
    
    print(f'\nText: "{det["text"]}"')
    print(f'  Position: X={det["x"]}, Y={det["y"]}')
    print(f'  Size: {det["width"]}x{det["height"]}px')
    print(f'  Confidence: {det["confidence"]:.1%}')
    print(f'  Is Header Keyword: {is_header}')
    
    # Check if in header row
    row, _ = map_detection_to_cell(det, h_lines, v_lines)
    if row in header_rows:
        print(f'  >>> SKIPPED (Row {row} is header row)')

print('\n' + '='*80)
print('Expected: "RT 001 RW 001"')
print('Actual: ???')
print('='*80)
