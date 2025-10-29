import json

d = json.load(open('experiments/final_system/ADAPTIVE_V2_SMART_RESULTS.json', encoding='utf-8'))

print(f"Total rows: {len(d['rows'])}")
print(f"Strategy: {d['metadata']['strategy']}")
print(f"\nFirst 3 rows:")

for i in range(min(3, len(d['rows']))):
    row = d['rows'][i]
    kode = row['cells'].get('1', {}).get('text_final', '')
    print(f"  Row {i}: Kode={kode}")
