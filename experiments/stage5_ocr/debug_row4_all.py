"""Debug: ALL detections in Row 4"""

import sys
import cv2
from pathlib import Path

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
print('ALL DETECTIONS IN ROW 4')
print('='*80)

# Find all row 4 detections
row4_dets = []

for det in detections:
    row, col = map_detection_to_cell(det, h_lines, v_lines)
    if row == 4:
        row4_dets.append((col, det))

# Sort by column
row4_dets.sort(key=lambda x: x[0])

print(f'\nColumn boundaries:')
for i in range(17):
    if i < len(v_lines) - 1:
        print(f'  Col {i:2d}: X[{v_lines[i]:4d} - {v_lines[i+1]:4d}]')

print(f'\n\nDetections in Row 4 (sorted by column):')
print('='*80)

for col, det in row4_dets:
    print(f'\nColumn {col:2d}: "{det["text"]}"')
    print(f'  X={det["x"]}, Y={det["y"]}')
    print(f'  Size: {det["width"]}x{det["height"]}px')
    print(f'  Confidence: {det["confidence"]:.1%}')

print('\n' + '='*80)
print('Now compare with COLUMN_HEADERS from schema:')
print('='*80)

from src.models.table_schema import COLUMN_HEADERS

for i, header in enumerate(COLUMN_HEADERS):
    # Find detection for this column
    det_text = ""
    for col, det in row4_dets:
        if col == i:
            det_text = det["text"]
            break
    
    print(f'Col {i:2d}: {header:30s} → Detected: "{det_text}"')
