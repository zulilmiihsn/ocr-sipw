"""
Display FINAL OCR results in beautiful table format
"""

import json
import sys
from pathlib import Path

# Fix encoding
sys.stdout.reconfigure(encoding='utf-8')

# Load results
with open('experiments/final_system/FINAL_RESULTS.json', encoding='utf-8') as f:
    data = json.load(f)

# Simplified column mapping for display (CORRECTED!)
DISPLAY_COLUMNS = [
    ('Kode SLS/Non- SLS', 'Kode SLS', 8),
    ('Kode Sub- SLS', 'Sub', 4),
    ('Nama SLS/Non-SLS', 'RT/RW', 12),
    ('Perkiraan Jumlah Muatan', 'JML KK', 6),
    ('Bangunan Tinggal (BTT)', 'BTT', 4),
    ('Perkiraan Jumlah Muatan Bangunan Bangunan Tinggal Kosong (BTT Kosong)', 'Kosong', 6),  # FIXED NAME!
    ('Bangunan Usaha (BKU)', 'BKU', 4),
    ('Bangunan Tinggal (BBTT non Usaha)', 'BBTT', 4),
    ('Perkiraan Jumlah Muatan Usaha', 'JML Usaha', 8),  # ADDED!
    ('Total Muatan', 'Total', 5),
    ('Nama Wilayah Konsentrasi', 'Wilayah', 12),
    ('Jumlah Shift Pada Wilayah', 'Shift', 5),
    ('Operasional', 'Jam', 12),
    ('Contact Person', 'Contact', 15),
    ('Muatan', 'Dom', 3),
    ('Column 16', 'Ubah', 4),  # ADDED! (Kolom Perubahan)
]

print('='*150)
print('HASIL SCAN OCR - BLOK III REKAPITULASI MUATAN')
print('='*150)
print(f"Method: {data['metadata']['method']}")
print(f"Time: {data['metadata']['total_time_seconds']}s")
print(f"Detections: {data['metadata']['total_detections']} text regions")
print('='*150)

# Print header
header_line = "No | "
separator_line = "---|"
for _, display_name, width in DISPLAY_COLUMNS:
    header_line += f"{display_name:^{width}} | "
    separator_line += "-" * width + "-|-"

print("\n" + header_line)
print(separator_line)

# Print data rows (skip header rows, start from row 4)
ROW_OFFSET = 4
row_num = 1

for idx in range(ROW_OFFSET, len(data['data'])):
    row = data['data'][idx]
    cells = row['cells']
    
    # Skip if row is mostly empty
    filled_count = sum(1 for cell in cells.values() if cell['text'].strip())
    if filled_count < 3:
        continue
    
    # Build row
    row_line = f"{row_num:2d} | "
    
    for col_name, _, width in DISPLAY_COLUMNS:
        if col_name in cells:
            text = cells[col_name]['text']
            # Truncate if too long
            if len(text) > width:
                text = text[:width-2] + ".."
            row_line += f"{text:<{width}} | "
        else:
            row_line += " " * width + " | "
    
    print(row_line)
    row_num += 1

print("="*150)
print(f"Total rows displayed: {row_num - 1}")
print("="*150)

# Summary statistics
print("\n" + "="*80)
print("SUMMARY STATISTICS")
print("="*80)

# Count by column
for col_name, display_name, _ in DISPLAY_COLUMNS:
    filled = 0
    total = 0
    for idx in range(ROW_OFFSET, len(data['data'])):
        if col_name in data['data'][idx]['cells']:
            total += 1
            if data['data'][idx]['cells'][col_name]['text'].strip():
                filled += 1
    
    pct = (filled / total * 100) if total > 0 else 0
    print(f"{display_name:20s}: {filled:3d}/{total:3d} cells filled ({pct:5.1f}%)")

print("="*80)
