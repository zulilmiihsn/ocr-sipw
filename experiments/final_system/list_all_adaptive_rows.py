import json

data = json.load(open('experiments/final_system/ADAPTIVE_V2_RESULTS.json', encoding='utf-8'))
rows = data['rows']

print(f"Total rows: {len(rows)}\n")
print("=== ALL ROWS ===\n")

for i, row in enumerate(rows):
    # Get Kode SLS from column 1 (using STRING key)
    kode_sls = row['cells'].get('1', {}).get('text_final', '')
    kode_sub = row['cells'].get('2', {}).get('text_final', '')
    rt_rw = row['cells'].get('3', {}).get('text_final', '')
    
    print(f"Scan Row {i}: Kode={kode_sls:6s} Sub={kode_sub:4s} RT/RW={rt_rw}")
