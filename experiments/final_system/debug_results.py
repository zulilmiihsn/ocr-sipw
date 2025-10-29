import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('experiments/final_system/FINAL_RESULTS.json', encoding='utf-8') as f:
    data = json.load(f)

print("="*80)
print(f"COLUMNS DETECTED: {len(data['columns'])} total")
print("="*80)
for col in data['columns']:
    print(f"  Col {col['index']:2d}: {col['name']}")

print("\n" + "="*80)
print("FIRST 5 DATA ROWS:")
print("="*80)

for row in data['data']:
    print(f"\nRow {row['row']}:")
    # Show first 8 columns
    for col_name, cell in list(row['cells'].items())[:8]:
        text = cell['text'][:40] if cell['text'] else ""
        print(f"  {col_name:30s}: \"{text}\"")
