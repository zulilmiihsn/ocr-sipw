"""
Display Cell-by-Cell OCR Results in Table Format
"""

import json
import sys
from pathlib import Path

# Fix encoding
sys.stdout.reconfigure(encoding='utf-8')

# Load results
with open('experiments/final_system/CELL_BY_CELL_RESULTS.json', encoding='utf-8') as f:
    data = json.load(f)

print('='*150)
print('CELL-BY-CELL OCR RESULTS - BLOK III REKAPITULASI MUATAN')
print('='*150)
print(f"Method: {data['metadata']['method']}")
print(f"Time: {data['metadata']['total_time_seconds']}s")
print(f"Grid: {data['metadata']['grid_size']}")
print(f"Total Cells: {data['metadata']['total_cells']}")
print('='*150)

# Identify data rows (skip headers)
data_rows = [row for row in data['table'] if not row.get('is_header', False)]

print(f"\n✓ Found {len(data_rows)} data rows (excluding {len(data['table']) - len(data_rows)} header rows)")

# Print table header
print('\n' + '='*150)
header = "No | "
for col in range(17):
    if col == 0:
        header += "Col0 | "
    else:
        header += f"C{col:02d} | "
print(header)
print('-'*150)

# Print data rows
for idx, row in enumerate(data_rows[:10], 1):  # First 10 data rows
    row_line = f"{idx:2d} | "
    
    for cell in row['cells']:
        text = cell['text'][:4] if cell['text'] else ''  # Truncate to 4 chars
        conf = cell['confidence']
        
        # Color code by confidence
        if conf > 0.9:
            status = '✓'
        elif conf > 0.7:
            status = '~'
        else:
            status = ' '
        
        row_line += f"{text:4s} | "
    
    print(row_line)

print('='*150)

# Statistics
print('\n' + '='*100)
print('STATISTICS PER COLUMN')
print('='*100)

# Calculate stats per column
for col_idx in range(17):
    filled = 0
    total = 0
    avg_conf = 0.0
    
    for row in data_rows:
        if col_idx < len(row['cells']):
            total += 1
            cell = row['cells'][col_idx]
            if cell['text'] and not cell['is_empty']:
                filled += 1
                avg_conf += cell['confidence']
    
    if filled > 0:
        avg_conf /= filled
    
    fill_pct = (filled / total * 100) if total > 0 else 0
    
    print(f"Column {col_idx:2d}: {filled:2d}/{total:2d} filled ({fill_pct:5.1f}%) | Avg Confidence: {avg_conf:.1%}")

print('='*100)

# Overall statistics
total_cells = 0
filled_cells = 0
empty_cells = 0
avg_confidence = 0.0

for row in data_rows:
    for cell in row['cells']:
        total_cells += 1
        if cell['text'] and not cell['is_empty']:
            filled_cells += 1
            avg_confidence += cell['confidence']
        else:
            empty_cells += 1

if filled_cells > 0:
    avg_confidence /= filled_cells

print('\n' + '='*100)
print('OVERALL STATISTICS')
print('='*100)
print(f"Total Data Rows: {len(data_rows)}")
print(f"Total Cells: {total_cells}")
print(f"Filled Cells: {filled_cells} ({filled_cells/total_cells*100:.1f}%)")
print(f"Empty Cells: {empty_cells} ({empty_cells/total_cells*100:.1f}%)")
print(f"Average Confidence: {avg_confidence:.1%}")
print('='*100)

# Show sample cells with high confidence
print('\n' + '='*100)
print('SAMPLE HIGH-CONFIDENCE CELLS (Confidence > 95%)')
print('='*100)

high_conf_cells = []
for row in data_rows[:5]:
    for cell in row['cells']:
        if cell['confidence'] > 0.95 and cell['text']:
            high_conf_cells.append({
                'row': row['row'],
                'col': cell['col'],
                'text': cell['text'],
                'conf': cell['confidence']
            })

for i, cell in enumerate(high_conf_cells[:20], 1):
    print(f"{i:2d}. Row {cell['row']:2d}, Col {cell['col']:2d}: \"{cell['text']}\" ({cell['conf']:.1%})")

print('='*100)
