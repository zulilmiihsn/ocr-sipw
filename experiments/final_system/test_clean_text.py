import re

def clean_text(text, column_name):
    """Column-specific text cleaning"""
    original_text = text
    text = text.strip()
    
    # Remove brackets
    text = re.sub(r'^\[+', '', text)
    text = re.sub(r'\]+$', '', text)
    
    # Column-specific rules
    col_lower = column_name.lower()
    
    print(f"\n=== Cleaning: '{original_text}' for column: '{column_name}' ===")
    print(f"After strip and bracket removal: '{text}'")
    print(f"Column lower: '{col_lower}'")
    
    # Numeric columns: only digits and spaces
    if any(kw in col_lower for kw in ['kode', 'jumlah', 'shift', 'total', 'dominan', 'perubahan', 'no']):
        text = re.sub(r'[^0-9\s]', '', text)
        text = text.strip()
        print(f"  → Matched NUMERIC rule")
    
    # RT/RW: format as "RT XXX RW YYY"
    elif 'rt' in col_lower or 'rw' in col_lower:
        # Extract digits
        digits = re.findall(r'\d+', text)
        if len(digits) >= 2:
            text = f"RT {digits[0]} RW {digits[1]}"
        elif len(digits) == 1:
            text = f"RT {digits[0]} RW 001"
        print(f"  → Matched RT/RW rule")
    
    # Time: keep only time format
    elif 'jam' in col_lower or 'operasional' in col_lower:
        time_match = re.search(r'\d{1,2}\.\d{2}\s*-\s*\d{1,2}\.\d{2}', text)
        if time_match:
            text = time_match.group(0)
        else:
            # Keep original if no time format found
            pass
        print(f"  → Matched TIME rule")
    
    # For all other columns (Wilayah, Contact, Nama, etc.): keep as-is
    # (already cleaned of brackets above)
    else:
        print(f"  → No special rule matched, keeping as-is")
    
    print(f"Final result: '{text}'")
    
    return text

# Test cases
print("=" * 80)
print("TEST CLEAN_TEXT FUNCTION")
print("=" * 80)

# Test Wilayah column
test_cases = [
    ("Madong", "Nama Wilayah Konsentrasi Ekonomi {12}"),
    ("90", "Perkiraan Jumlah Muatan KK (Keluarga) (5"),
    ("001  001", "Nama SLS/Non-SLS (4}"),
    ("8.00-22.00", "Jam Operasional {14}"),
]

for text, col_name in test_cases:
    result = clean_text(text, col_name)
    print(f"\n{'='*80}")
