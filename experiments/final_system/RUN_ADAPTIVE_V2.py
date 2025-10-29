"""
RUN ADAPTIVE V2 PIPELINE
========================
Complete pipeline:
1. Load image (1.png)
2. Detect & Crop BLOK III (Stage 3 approved method)
3. Run Adaptive v2 OCR (94.1% accuracy method)
4. Compare with Ground Truth
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np
import json
import re
from collections import defaultdict

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.pdf_handler import load_image
from src.ocr.table_detector import detect_table_region, crop_table

print("=" * 100)
print("ADAPTIVE V2 PIPELINE - FULL TEST")
print("=" * 100)
print()

total_start = time.time()

# Stage 1: Load
print("[Stage 1] Loading 1.png...")
t1 = time.time()
image = load_image('contoh gambar/1.png')
print(f"  ✓ Loaded: {image.shape}")
print(f"  ⏱ Time: {time.time() - t1:.2f}s")

# Stage 2: Detect BLOK III
print("\n[Stage 2] Detecting BLOK III...")
t2 = time.time()
bbox = detect_table_region(image)
blok3_img = crop_table(image, bbox)
print(f"  ✓ Cropped: {blok3_img.shape}")
print(f"  ⏱ Time: {time.time() - t2:.2f}s")

# Save cropped image
output_path = project_root / 'experiments' / 'final_system' / 'blok3_cropped_for_adaptive_v2.jpg'
cv2.imwrite(str(output_path), blok3_img)
print(f"  ✓ Saved: {output_path}")

# Stage 3: Run Adaptive v2 OCR
print("\n[Stage 3] Running Adaptive v2 OCR...")
print("  (This will take ~3 minutes with PaddleOCR)")
t3 = time.time()

# Import adaptive v2 functions
sys.path.insert(0, str(project_root / 'experiments' / 'stage5_ocr'))
from test_adaptive_mapping_v2 import (
    run_full_document_ocr,
    detect_horizontal_lines,
    detect_vertical_lines,
    detect_header_rows,
    learn_column_names_from_lines,
    map_to_table,
    post_process_text
)

# Run OCR
detections = run_full_document_ocr(blok3_img)
print(f"  ✓ Detected {len(detections)} text regions")

# Detect lines
h_lines = detect_horizontal_lines(blok3_img)
v_lines = detect_vertical_lines(blok3_img)
print(f"  ✓ H-lines: {len(h_lines)}, V-lines: {len(v_lines)}")

# FIX: Use horizontal lines to determine header boundary
# Header ends at the 4th or 5th horizontal line (after column number row)
if len(h_lines) >= 5:
    header_y_max = h_lines[4]  # After column numbers row
elif len(h_lines) >= 4:
    header_y_max = h_lines[3]
else:
    header_y_max = h_lines[2] if len(h_lines) >= 3 else 200

print(f"  ✓ Header area ends at Y={header_y_max} (using h_lines[4])")

# Detect header rows for column name learning
header_groups = detect_header_rows(detections, y_threshold=header_y_max)
print(f"  ✓ Header groups: {len(header_groups)}")

# Learn columns from vertical lines
columns = learn_column_names_from_lines(header_groups, v_lines)
print(f"  ✓ Learned {len(columns)} columns")

# Map to table
rows = map_to_table(detections, columns, h_lines, v_lines, header_y_max)
print(f"  ✓ Built table: {len(rows)} data rows")

# Apply post-processing
for row in rows:
    for col_idx, cell in row['cells'].items():
        col_name = columns[col_idx]['name'] if col_idx < len(columns) else ''
        cell['text_final'] = post_process_text(cell['text'], col_name)

print(f"  ⏱ Time: {time.time() - t3:.2f}s")

# Save results
results = {
    'metadata': {
        'method': 'Adaptive v2 (94.1% accuracy)',
        'input': 'contoh gambar/1.png',
        'total_time': f"{time.time() - total_start:.2f}s",
        'detections': len(detections),
        'columns': len(columns),
        'data_rows': len(rows)
    },
    'columns': columns,
    'rows': rows
}

results_path = project_root / 'experiments' / 'final_system' / 'ADAPTIVE_V2_RESULTS.json'
with open(results_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n✓ Results saved to: {results_path}")
print(f"\n✓ PIPELINE COMPLETED in {time.time() - total_start:.2f}s")
print("=" * 100)

# Show sample
print("\n" + "=" * 100)
print("SAMPLE RESULTS (First 3 data rows)")
print("=" * 100)

for i, row in enumerate(rows[:3], start=1):
    print(f"\nRow {i}:")
    for col_idx in range(min(5, len(columns))):
        if col_idx in row['cells']:
            cell = row['cells'][col_idx]
            col_name = columns[col_idx]['name'][:25].ljust(25)
            text = cell.get('text_final', '')[:20].ljust(20)
            conf = cell.get('confidence', 0.0)
            print(f"  {col_name}: \"{text}\" (conf: {conf:.1%})")

print("\n" + "=" * 100)
print("Now run: py experiments/final_system/compare_adaptive_v2_with_GT.py")
print("=" * 100)
