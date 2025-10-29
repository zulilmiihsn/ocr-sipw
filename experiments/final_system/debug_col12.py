import json

data = json.load(open('experiments/final_system/TEXT_MAPPING_RESULTS.json', encoding='utf-8'))

print("=== COLUMN 12 DEBUG ===\n")

col = data['columns'][12]
print(f"Column 12: {col['name']}")
print(f"X_center: {col['x_center']}")
print(f"Texts: {col['texts']}")

print("\n=== Sample data in column 12 (rows 4-10) ===")
for i, row in enumerate(data['table'][4:10], start=4):
    cell_data = row['cells'].get('12', {})
    text = cell_data.get('text', '')
    text_raw = cell_data.get('text_raw', '')
    conf = cell_data.get('confidence', 0.0)
    print(f"Row {i}: \"{text}\" (raw: \"{text_raw}\", conf: {conf:.1%})")

# Also check where "Madong", "Eropa", etc. are mapped
print("\n=== Searching for 'Madong' in all columns (row 4) ===")
row_4 = data['table'][4]
for col_idx, cell in row_4['cells'].items():
    if 'adong' in cell.get('text', '').lower() or 'madong' in cell.get('text_raw', '').lower():
        col_name = data['columns'][int(col_idx)]['name'] if int(col_idx) < len(data['columns']) else 'Unknown'
        print(f"  Column {col_idx} ({col_name}): \"{cell.get('text', '')}\" (raw: \"{cell.get('text_raw', '')}\")")
