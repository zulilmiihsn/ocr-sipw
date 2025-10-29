import json

data = json.load(open('experiments/final_system/ADAPTIVE_V2_RESULTS.json', encoding='utf-8'))

print(f"Total rows: {len(data['rows'])}\n")

print("First 5 rows:")
for i, row in enumerate(data['rows'][:5]):
    cells = row['cells']
    # Get sample text from column 1
    cell_1 = cells.get(1, {})
    text_final = cell_1.get('text_final', '')
    text = cell_1.get('text', '')
    
    print(f"\nRow {i}:")
    print(f"  Cell keys: {list(cells.keys())}")
    print(f"  Cell 1 text: '{text}'")
    print(f"  Cell 1 text_final: '{text_final}'")
    print(f"  Cell 1 full: {cell_1}")
