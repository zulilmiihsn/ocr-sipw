import json

data = json.load(open('experiments/final_system/ADAPTIVE_V2_RESULTS.json', encoding='utf-8'))
rows = data['rows']

print(f"Total rows: {len(rows)}\n")

print("=== SCAN ROW 1 (should be GT ROW 1) ===")
row1 = rows[1]
print(f"Row index: {row1.get('row_index', 'N/A')}")
print(f"Y range: {row1.get('y_top', 'N/A')} - {row1.get('y_bottom', 'N/A')}")
print(f"\nCells:")

for col_idx in [1, 2, 3, 4]:  # Check first 4 columns
    cell = row1['cells'].get(str(col_idx), {})
    print(f"\nColumn {col_idx}:")
    print(f"  text: '{cell.get('text', '')}'")
    print(f"  text_final: '{cell.get('text_final', '')}'")
    print(f"  confidence: {cell.get('confidence', 0.0):.1%}")
    print(f"  full cell: {cell}")
