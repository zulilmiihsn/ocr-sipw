import json
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
json_path = project_root / 'experiments' / 'results' / 'full_document_ocr_results.json'

with open(json_path, encoding='utf-8') as f:
    data = json.load(f)

detections = data['detections']

print('='*80)
print('ANALISIS FULL DOCUMENT OCR')
print('='*80)
print(f'Total detections: {len(detections)}')
print(f'Processing time: {data["timing"]["ocr_process"]}')

# Sort by Y position
sorted_dets = sorted(detections, key=lambda x: x['bbox']['center'][1])

print('\n' + '='*80)
print('TOP 30 DETECTIONS (header area, sorted by Y position):')
print('='*80)
print(f'{"No":<4} {"Position":<15} {"Size":<12} {"Conf":<7} {"Text"}')
print('-'*80)
for i, d in enumerate(sorted_dets[:30]):
    pos = f"({d['bbox']['center'][0]:4d}, {d['bbox']['center'][1]:4d})"
    size = f"{d['bbox']['width']:3d}x{d['bbox']['height']:2d}px"
    conf = f"{d['confidence']:.1%}"
    text = d['text'][:40]
    print(f'{i+1:<4} {pos:<15} {size:<12} {conf:<7} "{text}"')

print('\n' + '='*80)
print('DATA AREA DETECTIONS (Y > 200):')
print('='*80)
data_rows = [d for d in sorted_dets if d['bbox']['center'][1] > 200]
print(f'Found {len(data_rows)} detections in data area (below Y=200)')

print('\nFirst 30 data detections:')
print(f'{"No":<4} {"Position":<15} {"Size":<12} {"Conf":<7} {"Text"}')
print('-'*80)
for i, d in enumerate(data_rows[:30]):
    pos = f"({d['bbox']['center'][0]:4d}, {d['bbox']['center'][1]:4d})"
    size = f"{d['bbox']['width']:3d}x{d['bbox']['height']:2d}px"
    conf = f"{d['confidence']:.1%}"
    text = d['text'][:40]
    print(f'{i+1:<4} {pos:<15} {size:<12} {conf:<7} "{text}"')

print('\n' + '='*80)
print('COLUMN DETECTION ANALYSIS:')
print('='*80)
print('Grouping detections by X position (approximate columns)...')

# Group by X position (approximate column buckets)
x_buckets = {}
bucket_width = 100  # pixels

for d in data_rows:
    x = d['bbox']['center'][0]
    bucket = (x // bucket_width) * bucket_width
    if bucket not in x_buckets:
        x_buckets[bucket] = []
    x_buckets[bucket].append(d)

print(f'\nFound {len(x_buckets)} approximate columns:')
for bucket in sorted(x_buckets.keys()):
    texts = [d['text'][:20] for d in x_buckets[bucket][:5]]
    print(f'  X={bucket:4d}-{bucket+bucket_width:4d}: {len(x_buckets[bucket]):3d} items - Sample: {texts}')

print('\n' + '='*80)
