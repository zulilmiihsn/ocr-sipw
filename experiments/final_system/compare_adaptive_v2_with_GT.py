"""Compare ADAPTIVE_V2_RESULTS.json with Ground Truth"""

import sys
import json
from difflib import SequenceMatcher

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ground Truth
GROUND_TRUTH = {
    1: {"Kode_SLS": "0001", "Kode_Sub": "00", "RT_RW": "RT 001 RW 001", "JML_KK": "90", "BTT": "14", "BTT_Kosong": "15", "BKU": "21", "BBTT": "11", "JML_Usaha": "10", "Total": "75", "Wilayah": "Madong", "Shift": "5", "Jam": "8.00-12.00", "Contact": "0823456789/zul", "Dominan": "3", "Perubahan": "1"},
    2: {"Kode_SLS": "0002", "Kode_Sub": "00", "RT_RW": "RT 002 RW 002", "JML_KK": "23", "BTT": "23", "BTT_Kosong": "56", "BKU": "23", "BBTT": "8", "JML_Usaha": "9", "Total": "101", "Wilayah": "Eropa", "Shift": "12", "Jam": "10.00-16.00", "Contact": "12344512", "Dominan": "1", "Perubahan": "1"},
    3: {"Kode_SLS": "0003", "Kode_Sub": "00", "RT_RW": "RT 003 RW 001", "JML_KK": "121", "BTT": "32", "BTT_Kosong": "55", "BKU": "56", "BBTT": "78", "JML_Usaha": "99", "Total": "100", "Wilayah": "Barat", "Shift": "1", "Jam": "", "Contact": "", "Dominan": "", "Perubahan": ""},
    4: {"Kode_SLS": "0004", "Kode_Sub": "03", "RT_RW": "RT 004 RW 001", "JML_KK": "86", "BTT": "12", "BTT_Kosong": "11", "BKU": "2", "BBTT": "14", "JML_Usaha": "5", "Total": "76", "Wilayah": "Limapuluh", "Shift": "1", "Jam": "17.00", "Contact": "jauhari", "Dominan": "1", "Perubahan": "1"},
    5: {"Kode_SLS": "0004", "Kode_Sub": "02", "RT_RW": "RT 004 RW 001", "JML_KK": "8", "BTT": "14", "BTT_Kosong": "4", "BKU": "4", "BBTT": "4", "JML_Usaha": "10", "Total": "15", "Wilayah": "Limyu", "Shift": "1", "Jam": "12.00-10.00", "Contact": "jauhariya", "Dominan": "1", "Perubahan": "1"},
    6: {"Kode_SLS": "0004", "Kode_Sub": "01", "RT_RW": "RT 004 RW 001", "JML_KK": "64", "BTT": "77", "BTT_Kosong": "551", "BKU": "12", "BBTT": "14", "JML_Usaha": "9", "Total": "10", "Wilayah": "timtim", "Shift": "2", "Jam": "", "Contact": "", "Dominan": "1", "Perubahan": "1"},
    7: {"Kode_SLS": "0005", "Kode_Sub": "00", "RT_RW": "RT 005 RW 001", "JML_KK": "14", "BTT": "15", "BTT_Kosong": "16", "BKU": "17", "BBTT": "18", "JML_Usaha": "19", "Total": "10", "Wilayah": "jerman", "Shift": "2", "Jam": "8.00-21.00", "Contact": "surya", "Dominan": "1", "Perubahan": "1"},
    8: {"Kode_SLS": "0006", "Kode_Sub": "00", "RT_RW": "RT 012 RW 001", "JML_KK": "56", "BTT": "14", "BTT_Kosong": "7", "BKU": "21", "BBTT": "23", "JML_Usaha": "10", "Total": "75", "Wilayah": "Madong", "Shift": "5", "Jam": "8.00-12.00", "Contact": "0823456789/zul", "Dominan": "3", "Perubahan": "1"},
    9: {"Kode_SLS": "0007", "Kode_Sub": "00", "RT_RW": "RT 015 RW 001", "JML_KK": "8", "BTT": "21", "BTT_Kosong": "4", "BKU": "5", "BBTT": "11", "JML_Usaha": "10", "Total": "75", "Wilayah": "Madong", "Shift": "5", "Jam": "8.00-12.00", "Contact": "0823456789/zul", "Dominan": "3", "Perubahan": "1"},
    10: {"Kode_SLS": "0008", "Kode_Sub": "00", "RT_RW": "RT 016 RW 001", "JML_KK": "90", "BTT": "14", "BTT_Kosong": "15", "BKU": "21", "BBTT": "11", "JML_Usaha": "10", "Total": "75", "Wilayah": "Madong", "Shift": "5", "Jam": "8.00-12.00", "Contact": "0823456789/zul", "Dominan": "3", "Perubahan": "1"},
}

# Column mapping for Adaptive v2
COLUMN_MAPPING = {
    1: "Kode_SLS",
    2: "Kode_Sub",
    3: "RT_RW",
    4: "JML_KK",
    5: "BTT",
    6: "BTT_Kosong",
    7: "BKU",
    8: "BBTT",
    9: "JML_Usaha",
    10: "Total",
    11: "Wilayah",
    12: "Shift",
    13: "Jam",
    14: "Contact",
    15: "Dominan",
    16: "Perubahan"
}

def normalize_text(text):
    return text.strip().lower()

def similarity_ratio(text1, text2):
    return SequenceMatcher(None, normalize_text(text1), normalize_text(text2)).ratio()

def is_correct(detected, expected, threshold=0.85):
    if not expected and not detected:
        return True
    if not expected or not detected:
        return False
    return similarity_ratio(detected, expected) >= threshold

# Load results
with open('experiments/final_system/ADAPTIVE_V2_RESULTS.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

metadata = data['metadata']
columns = data['columns']
rows = data['rows']

# Calculate accuracy
total_cells = 0
correct_cells = 0
errors = []

print("=" * 100)
print("ADAPTIVE V2 vs GROUND TRUTH COMPARISON")
print("=" * 100)
print(f"Method: {metadata['method']}")
print(f"Time: {metadata['total_time']}")
print(f"Detections: {metadata['detections']}")
print(f"Columns: {metadata['columns']}")
print(f"Data rows: {metadata['data_rows']}")
print("=" * 100)
print()

# Compare each row
# GT row 1 = Scan row 0 (0-indexed)
for gt_row_idx in range(1, 11):
    scan_row_idx = gt_row_idx - 1  # GT row 1 = Scan row 0
    
    if scan_row_idx >= len(rows):
        print(f"⚠️  GT Row {gt_row_idx}: No scan data available")
        continue
    
    scan_row = rows[scan_row_idx]
    gt_data = GROUND_TRUTH[gt_row_idx]
    
    print(f"\n{'=' * 100}")
    print(f"GT ROW {gt_row_idx} = SCAN ROW {scan_row_idx}")
    print(f"{'=' * 100}")
    
    row_correct = 0
    row_total = 0
    
    for col_idx, field_name in COLUMN_MAPPING.items():
        expected = gt_data.get(field_name, "")
        # FIX: cells keys are strings, not integers!
        detected_cell = scan_row['cells'].get(str(col_idx), {})
        detected = detected_cell.get('text_final', '')
        
        sim = similarity_ratio(detected, expected) * 100
        correct = is_correct(detected, expected)
        
        row_total += 1
        total_cells += 1
        
        if correct:
            row_correct += 1
            correct_cells += 1
            status = "✓"
        else:
            status = "✗"
            errors.append({
                'row': gt_row_idx,
                'field': field_name,
                'expected': expected,
                'detected': detected,
                'similarity': sim
            })
        
        print(f"{status} {field_name:20s}: \"{detected:25s}\" vs \"{expected:25s}\" ({sim:.1f}%)")
    
    row_accuracy = (row_correct / row_total * 100) if row_total > 0 else 0
    print(f"\n→ Row {gt_row_idx} accuracy: {row_correct}/{row_total} = {row_accuracy:.1f}%")

# Overall statistics
overall_accuracy = (correct_cells / total_cells * 100) if total_cells > 0 else 0

print("\n" + "=" * 100)
print("OVERALL STATISTICS")
print("=" * 100)
print(f"Total cells compared: {total_cells}")
print(f"Correct cells: {correct_cells}")
print(f"Incorrect cells: {len(errors)}")
print()
print("=" * 100)
print(f"OVERALL ACCURACY: {overall_accuracy:.1f}%")
print("=" * 100)

# Top errors
if errors:
    print("\n" + "=" * 100)
    print(f"TOP 10 ERRORS (out of {len(errors)} total):")
    print("=" * 100)
    
    for i, error in enumerate(errors[:10], 1):
        print(f"\n{i}. GT Row {error['row']}, {error['field']}:")
        print(f"   Expected: \"{error['expected']}\"")
        print(f"   Detected: \"{error['detected']}\"")
        print(f"   Similarity: {error['similarity']:.1f}%")

print("\n" + "=" * 100)
print("CONCLUSION")
print("=" * 100)
print(f"✓ Adaptive v2 processed in {metadata['total_time']}")
print(f"✓ Detected {metadata['detections']} text regions")
print(f"✓ Learned {metadata['columns']} columns with vertical lines")
print(f"✓ Accuracy: {overall_accuracy:.1f}%")
print(f"✓ Using: Vertical lines for precise column boundaries")
print("=" * 100)
