"""
Compare FINAL OCR results with ground truth
Accounts for row offset (data starts at scan row 4)
"""

import json
import sys
from pathlib import Path
from difflib import SequenceMatcher

# Fix encoding
sys.stdout.reconfigure(encoding='utf-8')

# Ground Truth
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

# Column mapping (scan col name -> GT key)
COLUMN_MAPPING = {
    'Kode SLS/Non- SLS': 'Kode_SLS',
    'Kode Sub- SLS': 'Kode_Sub',
    'Nama SLS/Non-SLS': 'RT_RW',
    'Perkiraan Jumlah Muatan': 'Jumlah_Muatan_KK',
    'Bangunan Tinggal (BTT)': 'BTT',
    'Perkiraan Jumlah Muatan Bangunan Bangunan Tinggal osong(BTT Kosong': 'BTT_Kosong',
    'Bangunan Usaha (BKU)': 'BKU',
    'Bangunan Tinggal (BBTT non Usaha)': 'BBTT',
    'Perkiraan Jumlah Muatan Usaha': 'Jumlah_Muatan_Usaha',
    'Total Muatan': 'Total_Muatan',
    'Nama Wilayah Konsentrasi': 'Nama_Wilayah',
    'Jumlah Shift Pada Wilayah': 'Jumlah_Shift',
    'Operasional': 'Jam_Operasional',
    'Contact Person': 'Contact',
    'Muatan': 'Muatan_Dominan',
}

def similarity_ratio(str1, str2):
    if not str1 and not str2:
        return 1.0
    if not str1 or not str2:
        return 0.0
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

def normalize_text(text):
    """Normalize text for comparison"""
    # Remove "RT" and "RW" prefixes for comparison
    text = text.replace('RT ', '').replace('RW ', '').replace('/', '')
    return ' '.join(text.split()).strip()

# Load results
with open('experiments/final_system/FINAL_RESULTS.json', encoding='utf-8') as f:
    data = json.load(f)

print('='*100)
print('FINAL OCR RESULTS vs GROUND TRUTH COMPARISON')
print('='*100)
print(f"Method: {data['metadata']['method']}")
print(f"Time: {data['metadata']['total_time_seconds']}s")
print(f"Grid: {data['metadata']['grid_size']}")
print(f"Total detections: {data['metadata']['total_detections']}")
print('='*100)

# Compare with offset (scan row 4 = GT row 1)
ROW_OFFSET = 4
total_cells = 0
correct_cells = 0
errors = []

print('\n' + '='*100)
print('ROW-BY-ROW COMPARISON (with offset adjustment)')
print('='*100)

for gt_idx, gt_row in enumerate(GROUND_TRUTH):
    scan_idx = gt_idx + ROW_OFFSET  # GT row 0 -> scan row 4
    
    if scan_idx >= len(data['data']):
        print(f'\n❌ GT Row {gt_idx+1}: Missing in scan (expected scan row {scan_idx})')
        continue
    
    scan_row = data['data'][scan_idx]
    
    print(f'\n{"="*100}')
    print(f'GT ROW {gt_idx+1} = SCAN ROW {scan_idx}')
    print('='*100)
    
    row_correct = 0
    row_total = 0
    
    # Compare each GT field
    for gt_key, gt_value in gt_row.items():
        # Find matching scan column
        scan_value = ''
        
        # Special handling for some fields
        if gt_key == 'No':
            # Column 0 is always empty, skip
            continue
        elif gt_key == 'Perubahan':
            # Not mapped yet, skip
            continue
        
        # Find in column mapping
        for scan_col, gt_col in COLUMN_MAPPING.items():
            if gt_col == gt_key:
                if scan_col in scan_row['cells']:
                    scan_value = scan_row['cells'][scan_col]['text']
                break
        
        # Compare
        row_total += 1
        total_cells += 1
        
        # Normalize for comparison
        scan_norm = normalize_text(scan_value)
        gt_norm = normalize_text(gt_value)
        
        sim = similarity_ratio(scan_norm, gt_norm)
        is_match = sim >= 0.85 or (not gt_value and not scan_value)
        
        if is_match:
            correct_cells += 1
            row_correct += 1
            status = '✓'
        else:
            status = '✗'
            errors.append({
                'gt_row': gt_idx + 1,
                'scan_row': scan_idx,
                'field': gt_key,
                'expected': gt_value,
                'detected': scan_value,
                'similarity': sim
            })
        
        print(f"{status} {gt_key:20s}: \"{scan_value:25s}\" vs \"{gt_value:25s}\" ({sim:.1%})")
    
    print(f'\n→ Row {gt_idx+1} accuracy: {row_correct}/{row_total} = {row_correct/row_total*100:.1f}%' if row_total > 0 else '')

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

# Top errors
if errors:
    print(f'\n{"="*100}')
    print(f'TOP 10 ERRORS (out of {len(errors)} total):')
    print('='*100)
    
    for i, err in enumerate(sorted(errors, key=lambda x: x['similarity'])[:10]):
        print(f"\n{i+1}. GT Row {err['gt_row']} (Scan Row {err['scan_row']}), {err['field']}:")
        print(f"   Expected: \"{err['expected']}\"")
        print(f"   Detected: \"{err['detected']}\"")
        print(f"   Similarity: {err['similarity']:.1%}")

print('\n' + '='*100)
print('CONCLUSION')
print('='*100)
print(f"✓ FINAL Pipeline processed in {data['metadata']['total_time_seconds']}s")
print(f"✓ Detected {data['metadata']['total_detections']} text regions")
print(f"✓ Accuracy: {accuracy:.1f}%")
print(f"✓ Using: Stage 3 (OCR+Border) + Stage 4 (Morphological) + Stage 5 (PaddleOCR PP-OCRv5)")
print('='*100)
