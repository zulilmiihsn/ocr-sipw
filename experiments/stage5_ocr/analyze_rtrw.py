import json
from pathlib import Path

json_path = Path('experiments/results/full_document_ocr_results.json')
with open(json_path, encoding='utf-8') as f:
    data = json.load(f)

print('='*80)
print('RT/RW DETECTION ANALYSIS')
print('='*80)

# Find all RT/RW detections
rt_dets = [det for det in data['detections'] if 'RT' in det['text'] and 'RW' in det['text']]

print(f'\nFound {len(rt_dets)} RT/RW detections:\n')
print(f'{"Text":<25} {"X Position":<12} {"Y Position":<12} {"Width":<8}')
print('-'*80)

for det in rt_dets:
    text = det['text'][:24]
    x = det['bbox']['center'][0]
    y = det['bbox']['center'][1]
    w = det['bbox']['width']
    print(f'{text:<25} {x:<12} {y:<12} {w:<8}')

# Analyze column positions from all detections
print('\n' + '='*80)
print('COLUMN X-POSITION RANGES (from vertical lines)')
print('='*80)

# Load smart mapping results to see column boundaries
smart_path = Path('experiments/results/stage5_smart_mapping_results.json')
if smart_path.exists():
    print('\n(We need to analyze vertical line positions...)')
    print('RT/RW should be in Column 3 (Nama SLS/Non-SLS)')
    print(f'\nRT/RW X-positions: {[det["bbox"]["center"][0] for det in rt_dets[:5]]}')
    print('These should map to column 3!')
