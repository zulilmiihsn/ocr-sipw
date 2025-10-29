"""Compare Adaptive v2 Results with Ground Truth"""

import json
from pathlib import Path
from difflib import SequenceMatcher

# Ground Truth
GROUND_TRUTH = {
    'row_1': {
        'No': '01',
        'Kode SLS': '0001',
        'Kode Sub': '00',
        'RT/RW': 'RT 001 RW 001',
        'Jumlah Muatan KK': '90',
        'BTT': '14',
        'BTT Kosong': '15',
        'BKU': '21',
        'BBTT non Usaha': '11',
        'Jumlah Muatan Usaha': '20',
        'Total Muatan': '75',
        'Nama Wilayah': 'Madong',
        'Jumlah Shift': '5',
        'Jam Operasional': '8.00-22.00',
        'Contact Person': '0823456789/zul',
        'Muatan Dominan': '3',
        'Perubahan': '1'
    },
    'row_2': {
        'No': '02',
        'Kode SLS': '0002',
        'Kode Sub': '00',
        'RT/RW': 'RT 002 RW 002',
        'Jumlah Muatan KK': '23',
        'BTT': '23',
        'BTT Kosong': '56',
        'BKU': '23',
        'BBTT non Usaha': '8',
        'Jumlah Muatan Usaha': '9',
        'Total Muatan': '101',
        'Nama Wilayah': 'Eropa',
        'Jumlah Shift': '12',
        'Jam Operasional': '10.00-16.00',
        'Contact Person': '12344512',
        'Muatan Dominan': '1',
        'Perubahan': '1'
    },
    'row_3': {
        'No': '03',
        'Kode SLS': '0003',
        'Kode Sub': '00',
        'RT/RW': 'RT 003 RW 001',
        'Jumlah Muatan KK': '121',
        'BTT': '32',
        'BTT Kosong': '55',
        'BKU': '56',
        'BBTT non Usaha': '78',
        'Jumlah Muatan Usaha': '99',
        'Total Muatan': '100',
        'Nama Wilayah': 'Barat',
        'Jumlah Shift': '1',
        'Jam Operasional': '',
        'Contact Person': '',
        'Muatan Dominan': '',
        'Perubahan': ''
    }
}

# Column mapping for v2 (17 columns based on vertical lines)
COLUMN_V2_MAPPING = {
    0: 'No',
    1: 'Kode SLS',
    2: 'Kode Sub',
    3: 'RT/RW',
    4: 'Jumlah Muatan KK',
    5: 'BTT',
    6: 'BTT Kosong',
    7: 'BKU',
    8: 'BBTT non Usaha',
    9: 'Jumlah Muatan Usaha',
    10: 'Total Muatan',
    11: 'Nama Wilayah',
    12: 'Jumlah Shift',
    13: 'Jam Operasional',
    14: 'Contact Person',
    15: 'Muatan Dominan',
    16: 'Perubahan'
}


def similarity_ratio(str1, str2):
    return SequenceMatcher(None, str1, str2).ratio()


def compare_cell(detected, expected):
    if not expected:
        is_correct = not detected or detected == ''
        return {
            'detected': detected,
            'expected': expected,
            'correct': is_correct,
            'similarity': 1.0 if is_correct else 0.0
        }
    
    if not detected:
        return {
            'detected': detected,
            'expected': expected,
            'correct': False,
            'similarity': 0.0
        }
    
    if detected == expected:
        return {
            'detected': detected,
            'expected': expected,
            'correct': True,
            'similarity': 1.0
        }
    
    sim = similarity_ratio(detected.lower(), expected.lower())
    is_correct = sim >= 0.9  # 90% threshold
    
    return {
        'detected': detected,
        'expected': expected,
        'correct': is_correct,
        'similarity': sim
    }


def analyze_v2_results():
    json_path = Path('experiments/results/stage5_adaptive_v2_results.json')
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    
    print('='*80)
    print('ADAPTIVE v2 ACCURACY ANALYSIS')
    print('='*80)
    print(f"Method: {data['metadata']['method']}")
    print(f"Total time: {data['metadata']['total_time']}")
    print(f"Grid size: {data['metadata']['grid_size']}")
    print('='*80)
    
    total_cells = 0
    correct_cells = 0
    total_similarity = 0.0
    
    # Compare rows 1, 2, 3
    for row_idx in [1, 2, 3]:
        gt_key = f'row_{row_idx}'
        ground_truth = GROUND_TRUTH.get(gt_key, {})
        
        result_row = data['rows'][row_idx]
        
        print(f'\n{"="*80}')
        print(f'ROW {row_idx} COMPARISON')
        print('='*80)
        
        for cell in result_row['cells']:
            col_idx = cell['column']
            col_name = COLUMN_V2_MAPPING.get(col_idx, f'Col{col_idx}')
            detected = cell['text_final'].strip()
            expected = ground_truth.get(col_name, '')
            
            comparison = compare_cell(detected, expected)
            
            total_cells += 1
            if comparison['correct']:
                correct_cells += 1
            total_similarity += comparison['similarity']
            
            status = '✓' if comparison['correct'] else '✗'
            print(f"{status} {col_name:20s}: \"{detected:20s}\" vs \"{expected:20s}\" - {comparison['similarity']:.1%}")
    
    # Overall stats
    print('\n' + '='*80)
    print('OVERALL STATISTICS')
    print('='*80)
    
    cell_accuracy = (correct_cells / total_cells * 100) if total_cells > 0 else 0
    avg_similarity = (total_similarity / total_cells * 100) if total_cells > 0 else 0
    
    print(f'Total cells analyzed: {total_cells}')
    print(f'Correct cells: {correct_cells}')
    print(f'Incorrect cells: {total_cells - correct_cells}')
    print(f'\n{"="*80}')
    print(f'CELL MAPPING ACCURACY: {cell_accuracy:.1f}%')
    print(f'TEXT SIMILARITY (Avg): {avg_similarity:.1f}%')
    print('='*80)
    
    print('\n' + '='*80)
    print('IMPROVEMENTS FROM v1:')
    print('='*80)
    print('v1: 76.9% accuracy (30/39 cells)')
    print(f'v2: {cell_accuracy:.1f}% accuracy ({correct_cells}/{total_cells} cells)')
    improvement = cell_accuracy - 76.9
    print(f'Improvement: {improvement:+.1f}%')
    print('='*80)


if __name__ == '__main__':
    analyze_v2_results()
