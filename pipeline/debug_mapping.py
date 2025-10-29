"""
Debug script to check why cells are empty
"""
import json

# Load results
with open('ocr_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 80)
print("DEBUG: Cell Mapping Analysis")
print("=" * 80)

# Check metadata
meta = data['metadata']
print(f"\nMetadata:")
print(f"  Detections: {meta['detections']}")
print(f"  Columns: {meta['columns']}")
print(f"  Data Rows: {meta['data_rows']}")

# Check columns
columns = data['columns']
print(f"\nColumns ({len(columns)}):")
for col in columns[:5]:
    print(f"  {col['index']}: {col['name']} (x={col['x_left']}-{col['x_right']})")

# Check rows
rows = data['rows']
print(f"\nRows ({len(rows)}):")
for i, row in enumerate(rows[:3]):
    print(f"\n  Row {i}:")
    print(f"    Y range: {row['y_top']} - {row['y_bottom']}")
    
    # Count non-empty cells
    non_empty = sum(1 for cell in row['cells'].values() if cell['text'])
    print(f"    Non-empty cells: {non_empty}/{len(row['cells'])}")
    
    # Show first few cells
    for col_idx in range(min(5, len(row['cells']))):
        cell = row['cells'].get(str(col_idx), {})
        text = cell.get('text', '')
        conf = cell.get('confidence', 0.0)
        print(f"      Col {col_idx}: '{text}' (conf={conf:.2f})")

print("\n" + "=" * 80)
print("ISSUE DETECTED:")
print("  All cells are empty!")
print("  Possible causes:")
print("  1. header_y_max is too high (filtering out all detections)")
print("  2. Detection coordinates don't match line boundaries")
print("  3. Row/column mapping logic issue")
print("=" * 80)
