"""Debug: Where do RT/RW detections get mapped?"""

import sys
import cv2
import numpy as np
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

print('='*80)
print('RT/RW MAPPING DEBUG')
print('='*80)

print(f'\nHorizontal lines (Y positions): {h_lines}')
print(f'\nVertical lines (X positions): {v_lines}')

print(f'\nColumn boundaries:')
for i in range(len(v_lines) - 1):
    print(f'  Column {i}: X from {v_lines[i]} to {v_lines[i+1]}')

# Run OCR
detections = run_full_document_ocr(image)

# Find RT/RW detections
rt_dets = [d for d in detections if 'RT' in d['text'] and 'RW' in d['text']]

print(f'\n\nFound {len(rt_dets)} RT/RW detections:')
print('='*80)

for det in rt_dets[:5]:
    x = det['x']
    y = det['y']
    row, col = map_detection_to_cell(det, h_lines, v_lines)
    
    print(f'\nText: "{det["text"]}"')
    print(f'  Position: X={x}, Y={y}')
    print(f'  Width: {det["width"]}px (WIDE because merged cells!)')
    print(f'  Mapped to: Row {row}, Column {col}')
    
    # Check which column X falls into
    for i in range(len(v_lines) - 1):
        if v_lines[i] <= x < v_lines[i+1]:
            print(f'  X={x} falls in Column {i} range [{v_lines[i]}, {v_lines[i+1]})')
            break
