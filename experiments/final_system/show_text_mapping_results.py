"""Display TEXT_MAPPING_RESULTS.json in a formatted table"""

import sys
import json

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load results
with open('experiments/final_system/TEXT_MAPPING_RESULTS.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

metadata = data['metadata']
columns = data['columns']
table = data['table']

# Display header
print("=" * 150)
print("TEXT-BASED MAPPING RESULTS - BLOK III")
print("=" * 150)
print(f"Method: {metadata['method']}")
print(f"Time: {metadata['total_time']}")
print(f"Detections: {metadata['detections']} text regions")
print(f"Grid: {metadata['rows']} rows × {metadata['columns']} columns")
print("=" * 150)
print()

# Prepare column display (shorten names)
col_display = []
for col in columns:
    name = col['name']
    # Shorten long names
    if len(name) > 12:
        name = name[:10] + ".."
    col_display.append(name)

# Display table header
header_line = "No | " + " | ".join([f"{name:12s}" for name in col_display[:17]]) + " |"
print(header_line)
print("-" * len(header_line))

# Display data rows (skip first 4 header rows)
row_offset = 4
for i, row in enumerate(table[row_offset:], start=1):
    if i > 10:  # Show first 10 data rows
        break
    
    cells = row['cells']
    row_data = [f"{i:2d}"]
    
    for col_idx in range(min(17, len(columns))):
        cell = cells.get(str(col_idx), {})
        text = cell.get('text', '')
        text = text[:12]  # Truncate
        row_data.append(f"{text:12s}")
    
    print(" | ".join(row_data) + " |")

print("=" * 150)
print(f"Total rows displayed: 10")
print("=" * 150)

# Summary statistics
print()
print("=" * 80)
print("SUMMARY STATISTICS")
print("=" * 80)

data_rows = table[row_offset:]
for col_idx, col in enumerate(columns[:17]):
    filled = sum(1 for row in data_rows if row['cells'].get(str(col_idx), {}).get('text', '').strip() != '')
    total = len(data_rows)
    pct = (filled / total * 100) if total > 0 else 0
    col_name = col['name'][:30].ljust(30)
    print(f"{col_name}: {filled:3d}/{total:3d} cells filled ({pct:5.1f}%)")

print("=" * 80)
