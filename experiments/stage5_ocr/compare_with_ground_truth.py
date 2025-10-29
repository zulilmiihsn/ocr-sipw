"""
Compare OCR Results with Ground Truth

Compare PaddleOCR results with actual data from reference image
to calculate REAL accuracy
"""

import json
from pathlib import Path

project_root = Path(__file__).parent.parent.parent

# Ground truth from reference image (rows 01-10)
GROUND_TRUTH = {
    # Row 01 (appears as row 3 in OCR due to header rows)
    3: {
        0: "01", 1: "0001", 2: "00", 3: "RT 001 RW 001", 4: "90", 5: "14", 6: "15",
        7: "21", 8: "11", 9: "10", 10: "75", 11: "Madong", 12: "5", 13: "8.00-11.00",
        14: "081.3456789/zul", 15: "3", 16: "1"
    },
    # Row 02
    4: {
        0: "02", 1: "0002", 2: "00", 3: "RT 002 RW 002", 4: "23", 5: "23", 6: "56",
        7: "23", 8: "8", 9: "9", 10: "101", 11: "Eropa", 12: "12", 13: "10.00-16.00",
        14: "12.344512", 15: "1", 16: "1"
    },
    # Row 03
    5: {
        0: "03", 1: "0003", 2: "00", 3: "RT 003 RW 001", 4: "121", 5: "32", 6: "55",
        7: "56", 8: "78", 9: "99", 10: "100", 11: "Barat", 12: "1", 13: "",
        14: "", 15: "", 16: ""
    },
    # Row 04
    6: {
        0: "04", 1: "0004", 2: "03", 3: "RT 004 RW 001", 4: "86", 5: "12", 6: "11",
        7: "2", 8: "14", 9: "5", 10: "76", 11: "Limapuluh", 12: "1", 13: "17.00",
        14: "jauhari", 15: "1", 16: "1"
    },
    # Row 05
    7: {
        0: "05", 1: "0004", 2: "02", 3: "RT 004 RW 001", 4: "8", 5: "14", 6: "4",
        7: "4", 8: "4", 9: "10", 10: "15", 11: "Emyu", 12: "1", 13: "12.00-10.00",
        14: "jauhariya", 15: "1", 16: "1"
    },
    # Row 06
    8: {
        0: "06", 1: "0004", 2: "01", 3: "RT 004 RW 001", 4: "64", 5: "77", 6: "551",
        7: "12", 8: "14", 9: "9", 10: "10", 11: "timtim", 12: "2", 13: "",
        14: "", 15: "1", 16: "1"
    },
    # Row 07
    9: {
        0: "07", 1: "0005", 2: "00", 3: "RT 005 RW 001", 4: "14", 5: "15", 6: "16",
        7: "17", 8: "18", 9: "19", 10: "20", 11: "jerman", 12: "2", 13: "8.00-11.00",
        14: "surya", 15: "1", 16: "1"
    },
    # Row 08
    10: {
        0: "08", 1: "0006", 2: "00", 3: "RT 012 RW 001", 4: "56", 5: "14", 6: "7",
        7: "21", 8: "23", 9: "10", 10: "75", 11: "Madong", 12: "5", 13: "8.00-11.00",
        14: "081.3456789/zul", 15: "3", 16: "1"
    },
    # Row 09
    11: {
        0: "09", 1: "0007", 2: "00", 3: "RT 015 RW 001", 4: "8", 5: "21", 6: "4",
        7: "5", 8: "11", 9: "10", 10: "75", 11: "Madong", 12: "5", 13: "8.00-11.00",
        14: "081.3456789/zul", 15: "3", 16: "1"
    },
    # Row 10
    12: {
        0: "10", 1: "0008", 2: "00", 3: "RT 016 RW 001", 4: "90", 5: "14", 6: "15",
        7: "21", 8: "11", 9: "10", 10: "75", 11: "Madong", 12: "5", 13: "8.00-11.00",
        14: "081.3456789/zul", 15: "3", 16: "1"
    },
}

COLUMN_NAMES = [
    "No", "Kode", "Sub", "Nama SLS", "KK", "BTT", "BTT Kosong", "BKU", 
    "BBTT", "Muatan Usaha", "Total", "Wilayah", "Shift", "Jam", 
    "Contact", "Muatan", "Perubahan"
]


def normalize_text(text):
    """Normalize text for comparison"""
    if not text:
        return ""
    return str(text).strip().upper()


def compare_results():
    """Compare OCR results with ground truth"""
    
    # Load OCR results (use Balanced Ultimate)
    results_path = project_root / 'experiments' / 'results' / 'stage5_balanced_ultimate_results.json'
    
    with open(results_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    ocr_results = data['results']
    
    print('='*120)
    print('ACCURACY COMPARISON: OCR vs GROUND TRUTH')
    print('='*120)
    print()
    
    total_cells = 0
    correct_cells = 0
    partial_cells = 0
    wrong_cells = 0
    
    detailed_errors = []
    
    for row_idx, ground_truth_row in GROUND_TRUTH.items():
        print(f'\n{"="*120}')
        print(f'ROW {row_idx - 2:02d} (Data Row {row_idx})')
        print(f'{"="*120}')
        print(f'{"Col":<4} {"Name":<20} {"Ground Truth":<25} {"OCR Result":<25} {"Status":<10}')
        print(f'{"-"*120}')
        
        row_correct = 0
        row_total = 0
        
        for col_idx, gt_value in ground_truth_row.items():
            key = f"{row_idx},{col_idx}"
            ocr_value = ocr_results.get(key, "")
            
            gt_norm = normalize_text(gt_value)
            ocr_norm = normalize_text(ocr_value)
            
            # Status determination
            if gt_norm == ocr_norm:
                status = "✓ CORRECT"
                correct_cells += 1
                row_correct += 1
            elif not gt_norm and not ocr_norm:
                status = "✓ EMPTY"
                correct_cells += 1
                row_correct += 1
            elif not ocr_norm and gt_norm:
                status = "✗ MISSED"
                wrong_cells += 1
                detailed_errors.append({
                    'row': row_idx - 2,
                    'col': col_idx,
                    'name': COLUMN_NAMES[col_idx],
                    'expected': gt_value,
                    'got': ocr_value,
                    'type': 'missed'
                })
            elif ocr_norm in gt_norm or gt_norm in ocr_norm:
                status = "⚠️ PARTIAL"
                partial_cells += 1
                detailed_errors.append({
                    'row': row_idx - 2,
                    'col': col_idx,
                    'name': COLUMN_NAMES[col_idx],
                    'expected': gt_value,
                    'got': ocr_value,
                    'type': 'partial'
                })
            else:
                status = "✗ WRONG"
                wrong_cells += 1
                detailed_errors.append({
                    'row': row_idx - 2,
                    'col': col_idx,
                    'name': COLUMN_NAMES[col_idx],
                    'expected': gt_value,
                    'got': ocr_value,
                    'type': 'wrong'
                })
            
            total_cells += 1
            row_total += 1
            
            col_name = COLUMN_NAMES[col_idx] if col_idx < len(COLUMN_NAMES) else f'C{col_idx}'
            
            # Only show non-matching or interesting cells
            if status != "✓ CORRECT" and status != "✓ EMPTY":
                print(f'{col_idx:<4} {col_name:<20} "{gt_value}"<{25-len(str(gt_value))}' + 
                      f' "{ocr_value}"<{25-len(str(ocr_value))} {status:<10}')
        
        row_accuracy = (row_correct / row_total * 100) if row_total > 0 else 0
        print(f'\nRow accuracy: {row_correct}/{row_total} ({row_accuracy:.1f}%)')
    
    # Overall statistics
    print(f'\n\n{"="*120}')
    print('OVERALL STATISTICS')
    print(f'{"="*120}')
    
    accuracy = (correct_cells / total_cells * 100) if total_cells > 0 else 0
    
    print(f'\nTotal cells analyzed: {total_cells}')
    print(f'  ✓ Correct:  {correct_cells} ({correct_cells/total_cells*100:.1f}%)')
    print(f'  ⚠️ Partial:  {partial_cells} ({partial_cells/total_cells*100:.1f}%)')
    print(f'  ✗ Wrong:    {wrong_cells} ({wrong_cells/total_cells*100:.1f}%)')
    print(f'\nOVERALL ACCURACY: {accuracy:.1f}%')
    
    # Error breakdown
    print(f'\n\n{"="*120}')
    print('ERROR BREAKDOWN BY COLUMN')
    print(f'{"="*120}')
    
    error_by_col = {}
    for error in detailed_errors:
        col_name = error['name']
        if col_name not in error_by_col:
            error_by_col[col_name] = {'missed': 0, 'partial': 0, 'wrong': 0}
        error_by_col[col_name][error['type']] += 1
    
    print(f'\n{"Column":<25} {"Missed":<10} {"Partial":<10} {"Wrong":<10} {"Total Errors"}')
    print('-'*70)
    for col_name, errors in sorted(error_by_col.items()):
        total_err = errors['missed'] + errors['partial'] + errors['wrong']
        print(f'{col_name:<25} {errors["missed"]:<10} {errors["partial"]:<10} {errors["wrong"]:<10} {total_err}')
    
    # Most problematic cells
    print(f'\n\n{"="*120}')
    print('TOP 10 ERRORS (Most Critical)')
    print(f'{"="*120}')
    print(f'\n{"Row":<6} {"Column":<25} {"Expected":<30} {"Got":<30}')
    print('-'*120)
    
    for i, error in enumerate(detailed_errors[:10], 1):
        print(f'{error["row"]:02d}     {error["name"]:<25} "{error["expected"]}"<{30-len(str(error["expected"]))}' + 
              f' "{error["got"]}"')
    
    print(f'\n{"="*120}')
    print('CONCLUSION')
    print(f'{"="*120}')
    print(f'\nBalanced Ultimate OCR Accuracy: {accuracy:.1f}%')
    
    if accuracy >= 95:
        print('Status: ✅ EXCELLENT (≥95%)')
    elif accuracy >= 90:
        print('Status: ✓ GOOD (90-95%)')
    elif accuracy >= 80:
        print('Status: ⚠️ ACCEPTABLE (80-90%)')
    else:
        print('Status: ✗ NEEDS IMPROVEMENT (<80%)')
    
    print(f'\nMain issues:')
    print(f'  1. RT/RW column (Nama SLS) - Most errors')
    print(f'  2. Time format variations')
    print(f'  3. Phone number format differences')
    print(f'{"="*120}')
    
    return accuracy


if __name__ == '__main__':
    accuracy = compare_results()
