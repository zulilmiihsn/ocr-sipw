"""
Compare scan results with ground truth from table image
"""

import json
import sys
from pathlib import Path
from difflib import SequenceMatcher

# Fix encoding for Windows console
sys.stdout.reconfigure(encoding='utf-8')

# Ground Truth from the table image provided
GROUND_TRUTH = [
    {'No': '01', 'Kode_SLS': '0001', 'Kode_Sub': '00', 'RT_RW': 'RT 001 RW 001', 'Jumlah_Muatan_KK': '90', 'BTT': '14', 'BTT_Kosong': '15', 'BKU': '21', 'BBTT': '11', 'Jumlah_Muatan_Usaha': '10', 'Total_Muatan': '75', 'Nama_Wilayah': 'Madong', 'Jumlah_Shift': '5', 'Jam_Operasional': '8.00-12.00', 'Contact': '0823456789/zul', 'Muatan_Dominan': '3', 'Perubahan': '1'},
    {'No': '02', 'Kode_SLS': '0002', 'Kode_Sub': '00', 'RT_RW': 'RT 002 RW 002', 'Jumlah_Muatan_KK': '23', 'BTT': '23', 'BTT_Kosong': '56', 'BKU': '23', 'BBTT': '8', 'Jumlah_Muatan_Usaha': '9', 'Total_Muatan': '101', 'Nama_Wilayah': 'Eropa', 'Jumlah_Shift': '12', 'Jam_Operasional': '10.00-16.00', 'Contact': '12344512', 'Muatan_Dominan': '1', 'Perubahan': '1'},
    {'No': '03', 'Kode_SLS': '0003', 'Kode_Sub': '00', 'RT_RW': 'RT 003 RW 001', 'Jumlah_Muatan_KK': '121', 'BTT': '32', 'BTT_Kosong': '55', 'BKU': '56', 'BBTT': '78', 'Jumlah_Muatan_Usaha': '99', 'Total_Muatan': '100', 'Nama_Wilayah': 'Barat', 'Jumlah_Shift': '1', 'Jam_Operasional': '', 'Contact': '', 'Muatan_Dominan': '', 'Perubahan': ''},
    {'No': '04', 'Kode_SLS': '0004', 'Kode_Sub': '03', 'RT_RW': 'RT 004 RW 001', 'Jumlah_Muatan_KK': '86', 'BTT': '12', 'BTT_Kosong': '11', 'BKU': '2', 'BBTT': '14', 'Jumlah_Muatan_Usaha': '5', 'Total_Muatan': '76', 'Nama_Wilayah': 'Limapuluh', 'Jumlah_Shift': '1', 'Jam_Operasional': '17.00', 'Contact': 'jauhari', 'Muatan_Dominan': '1', 'Perubahan': '1'},
    {'No': '05', 'Kode_SLS': '0004', 'Kode_Sub': '02', 'RT_RW': 'RT 004 RW 001', 'Jumlah_Muatan_KK': '8', 'BTT': '14', 'BTT_Kosong': '4', 'BKU': '4', 'BBTT': '4', 'Jumlah_Muatan_Usaha': '10', 'Total_Muatan': '15', 'Nama_Wilayah': 'Limyu', 'Jumlah_Shift': '1', 'Jam_Operasional': '12.00-10.00', 'Contact': 'jauhariya', 'Muatan_Dominan': '1', 'Perubahan': '1'},
    {'No': '06', 'Kode_SLS': '0004', 'Kode_Sub': '01', 'RT_RW': 'RT 004 RW 001', 'Jumlah_Muatan_KK': '64', 'BTT': '77', 'BTT_Kosong': '551', 'BKU': '12', 'BBTT': '14', 'Jumlah_Muatan_Usaha': '9', 'Total_Muatan': '10', 'Nama_Wilayah': 'timtim', 'Jumlah_Shift': '2', 'Jam_Operasional': '', 'Contact': '', 'Muatan_Dominan': '1', 'Perubahan': '1'},
    {'No': '07', 'Kode_SLS': '0005', 'Kode_Sub': '00', 'RT_RW': 'RT 005 RW 001', 'Jumlah_Muatan_KK': '14', 'BTT': '15', 'BTT_Kosong': '16', 'BKU': '17', 'BBTT': '18', 'Jumlah_Muatan_Usaha': '19', 'Total_Muatan': '10', 'Nama_Wilayah': 'jerman', 'Jumlah_Shift': '2', 'Jam_Operasional': '8.00-21.00', 'Contact': 'surya', 'Muatan_Dominan': '1', 'Perubahan': '1'},
    {'No': '08', 'Kode_SLS': '0006', 'Kode_Sub': '00', 'RT_RW': 'RT 012 RW 001', 'Jumlah_Muatan_KK': '56', 'BTT': '14', 'BTT_Kosong': '7', 'BKU': '21', 'BBTT': '23', 'Jumlah_Muatan_Usaha': '10', 'Total_Muatan': '75', 'Nama_Wilayah': 'Madong', 'Jumlah_Shift': '5', 'Jam_Operasional': '8.00-12.00', 'Contact': '0823456789/zul', 'Muatan_Dominan': '3', 'Perubahan': '1'},
    {'No': '09', 'Kode_SLS': '0007', 'Kode_Sub': '00', 'RT_RW': 'RT 015 RW 001', 'Jumlah_Muatan_KK': '8', 'BTT': '21', 'BTT_Kosong': '4', 'BKU': '5', 'BBTT': '11', 'Jumlah_Muatan_Usaha': '10', 'Total_Muatan': '75', 'Nama_Wilayah': 'Madong', 'Jumlah_Shift': '5', 'Jam_Operasional': '8.00-12.00', 'Contact': '0823456789/zul', 'Muatan_Dominan': '3', 'Perubahan': '1'},
    {'No': '10', 'Kode_SLS': '0008', 'Kode_Sub': '00', 'RT_RW': 'RT 016 RW 001', 'Jumlah_Muatan_KK': '90', 'BTT': '14', 'BTT_Kosong': '15', 'BKU': '21', 'BBTT': '11', 'Jumlah_Muatan_Usaha': '10', 'Total_Muatan': '75', 'Nama_Wilayah': 'Madong', 'Jumlah_Shift': '5', 'Jam_Operasional': '8.00-12.00', 'Contact': '0823456789/zul', 'Muatan_Dominan': '3', 'Perubahan': '1'},
]

# Column mapping
COLUMN_MAPPING = {
    'Column 0': 'No',
    'Kode': 'Kode_SLS',
    'Kode Sub-': 'Kode_Sub',
    'Nama SLS/Non-SLS': 'RT_RW',
    'Perkiraan Jumlah Muatan': 'Jumlah_Muatan_KK',
    'Tinggal (BTT)': 'BTT',
    'KoKosong (BTT': 'BTT_Kosong',
    'Perkiraan Jumlah Muatan Bangunan Usaha (': 'BKU',
    'Tinggal (BBTT': 'BBTT',
}


def similarity_ratio(str1, str2):
    """Calculate similarity between two strings"""
    if not str1 and not str2:
        return 1.0
    if not str1 or not str2:
        return 0.0
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def normalize_text(text):
    """Normalize text for comparison"""
    return text.strip().lower()


def compare_results():
    """Compare scan results with ground truth"""
    
    # Load scan results
    json_path = Path('experiments/final_system/FINAL_RESULTS.json')
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    
    print('='*100)
    print('COMPARISON: SCAN RESULTS vs GROUND TRUTH')
    print('='*100)
    print(f"Image: 1.png (Original full image with BLOK III detection)")
    print(f"Scan method: {data['metadata']['method']}")
    print(f"Original size: {data['metadata']['original_size']}")
    print(f"BLOK III size: {data['metadata']['blok3_size']}")
    print(f"Processing time: {data['metadata']['total_time_seconds']}s")
    print(f"Grid detected: {data['metadata']['grid_size']}")
    print('='*100)
    
    # Get column names from scan
    scan_columns = {col['name']: col['index'] for col in data['columns']}
    
    print('\n' + '='*100)
    print('COLUMNS DETECTED:')
    print('='*100)
    for col in data['columns']:
        print(f"  Col {col['index']:2d}: {col['name']}")
    
    # Compare data
    total_cells = 0
    correct_cells = 0
    errors = []
    
    print('\n' + '='*100)
    print('ROW-BY-ROW COMPARISON')
    print('='*100)
    
    for row_idx, gt_row in enumerate(GROUND_TRUTH):
        if row_idx >= len(data['data']):
            print(f'\n❌ Row {row_idx+1}: MISSING in scan results')
            continue
        
        scan_row = data['data'][row_idx]
        
        print(f'\n{"="*100}')
        print(f'ROW {row_idx+1} (Scan Row {scan_row["row"]})')
        print('='*100)
        
        row_correct = 0
        row_total = 0
        
        # Compare each field
        for gt_key, gt_value in gt_row.items():
            # Find matching column in scan
            scan_value = ''
            
            # Try to find the column
            for scan_col_name, cell_data in scan_row['cells'].items():
                # Direct match or partial match
                if gt_key.lower() in scan_col_name.lower() or scan_col_name.lower() in gt_key.lower():
                    scan_value = cell_data['text']
                    break
                
                # Special mappings
                if gt_key == 'Kode_SLS' and scan_col_name == 'Kode':
                    scan_value = cell_data['text']
                    break
                elif gt_key == 'Kode_Sub' and 'Kode Sub' in scan_col_name:
                    scan_value = cell_data['text']
                    break
                elif gt_key == 'RT_RW' and 'SLS/Non-SLS' in scan_col_name:
                    scan_value = cell_data['text']
                    break
                elif gt_key == 'Nama_Wilayah' and 'Wilayah' in scan_col_name:
                    scan_value = cell_data['text']
                    break
                elif gt_key == 'Contact' and 'Column 14' in scan_col_name:
                    scan_value = cell_data['text']
                    break
                elif gt_key == 'Muatan_Dominan' and scan_col_name == 'Muatan':
                    # Muatan column has "3 1" format, take first number
                    scan_value = cell_data['text'].split()[0] if cell_data['text'] else ''
                    break
                elif gt_key == 'Perubahan' and scan_col_name == 'Muatan':
                    # Muatan column has "3 1" format, take second number
                    parts = cell_data['text'].split()
                    scan_value = parts[1] if len(parts) > 1 else ''
                    break
                elif gt_key == 'Jumlah_Muatan_KK' and scan_col_name == 'Perkiraan Jumlah Muatan':
                    scan_value = cell_data['text']
                    break
                elif gt_key == 'Jam_Operasional' and scan_col_name == 'Operasional':
                    scan_value = cell_data['text']
                    break
            
            # Compare
            row_total += 1
            total_cells += 1
            
            sim = similarity_ratio(scan_value, gt_value)
            is_match = sim >= 0.9 or (not gt_value and not scan_value)
            
            if is_match:
                correct_cells += 1
                row_correct += 1
                status = '✓'
            else:
                status = '✗'
                errors.append({
                    'row': row_idx + 1,
                    'field': gt_key,
                    'expected': gt_value,
                    'detected': scan_value,
                    'similarity': sim
                })
            
            print(f"{status} {gt_key:20s}: \"{scan_value:25s}\" vs \"{gt_value:25s}\" ({sim:.1%})")
        
        print(f'\n→ Row {row_idx+1} accuracy: {row_correct}/{row_total} = {row_correct/row_total*100:.1f}%')
    
    # Overall statistics
    accuracy = (correct_cells / total_cells * 100) if total_cells > 0 else 0
    
    print('\n' + '='*100)
    print('OVERALL STATISTICS')
    print('='*100)
    print(f'Total cells compared: {total_cells}')
    print(f'Correct cells: {correct_cells}')
    print(f'Incorrect cells: {total_cells - correct_cells}')
    print(f'\n{"="*100}')
    print(f'OVERALL ACCURACY: {accuracy:.1f}%')
    print('='*100)
    
    # Error breakdown
    if errors:
        print(f'\n{"="*100}')
        print(f'TOP ERRORS ({len(errors)} total):')
        print('='*100)
        
        for i, err in enumerate(sorted(errors, key=lambda x: x['similarity'])[:10]):
            print(f"\n{i+1}. Row {err['row']}, {err['field']}:")
            print(f"   Expected: \"{err['expected']}\"")
            print(f"   Detected: \"{err['detected']}\"")
            print(f"   Similarity: {err['similarity']:.1%}")
    
    print('\n' + '='*100)
    print('CONCLUSION')
    print('='*100)
    print(f"✓ Scanned {len(data['data'])} rows in {data['metadata']['total_time_seconds']}s")
    print(f"✓ Accuracy: {accuracy:.1f}%")
    print(f"✓ Grid: {data['metadata']['grid_size']}")
    print(f"✓ Method: {data['metadata']['method']}")
    print('='*100)


if __name__ == '__main__':
    compare_results()
