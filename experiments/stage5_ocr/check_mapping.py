import json
from pathlib import Path

json_path = Path('experiments/results/stage5_smart_mapping_results.json')
with open(json_path, encoding='utf-8') as f:
    data = json.load(f)

print('Row-by-Row Analysis:')
print('='*80)

for row in data['table'][:12]:
    row_idx = row['row']
    filled = sum(1 for c in row['cells'] if c['text_final'])
    
    if filled > 0:
        print(f"\nRow {row_idx}: {filled} filled cells")
        for c in row['cells']:
            if c['text_final']:
                print(f"  Col {c['column']:2d} ({c['column_name'][:20]:20s}): \"{c['text_final']}\" (conf: {c['confidence']:.1%})")
