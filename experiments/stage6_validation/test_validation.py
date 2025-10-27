"""
Test Stage 6: Validation & Post-processing
Test cleaning, validation, dan empty cell detection
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.ocr.postprocessor import validate_cell_data, clean_ocr_text
from src.ocr.cell_validator import is_cell_empty
from src.models.table_schema import get_column_type, get_column_whitelist
import cv2
import numpy as np


def test_text_cleaning():
    """Test OCR text cleaning"""
    
    print("=" * 60)
    print("STAGE 6: TEXT CLEANING TEST")
    print("=" * 60)
    
    test_cases = [
        ("3,1", "Should preserve comma decimal"),
        ("  3.5  ", "Should trim whitespace"),
        ("JAKARTA", "Should preserve text"),
        ("08:00-16:00", "Should preserve time format"),
        ("l23", "Common OCR error (l → 1)"),
        ("O5", "Common OCR error (O → 0)"),
        ("", "Empty string"),
        ("   ", "Whitespace only"),
    ]
    
    print("\n📝 Testing text cleaning:\n")
    for text, description in test_cases:
        cleaned = clean_ocr_text(text, preserve_format=True)
        print(f"  {text:20} → {cleaned:20} | {description}")
    
    print("\n" + "=" * 60)


def test_column_validation():
    """Test validation per column type"""
    
    print("\n" + "=" * 60)
    print("STAGE 6: COLUMN VALIDATION TEST")
    print("=" * 60)
    
    # Test numeric columns (col 4, 5, 6, etc.)
    print("\n🔢 Testing NUMERIC validation (column 4):\n")
    numeric_tests = [
        "3,1",      # decimal with comma
        "3.5",      # decimal with dot
        "123",      # integer
        "abc",      # invalid
        "12.3x",    # partially invalid
        "",         # empty
    ]
    
    for text in numeric_tests:
        cleaned, is_valid = validate_cell_data(text, column_index=4)
        status = "✅" if is_valid else "❌"
        print(f"  {status} {text:15} → {cleaned:15} (valid: {is_valid})")
    
    # Test text columns (col 1, 2, 3)
    print("\n📝 Testing TEXT validation (column 1):\n")
    text_tests = [
        "JAKARTA",
        "Jakarta Barat",
        "123",      # numbers in text
        "Test-123", # mixed
        "",         # empty
    ]
    
    for text in text_tests:
        cleaned, is_valid = validate_cell_data(text, column_index=1)
        status = "✅" if is_valid else "❌"
        print(f"  {status} {text:15} → {cleaned:15} (valid: {is_valid})")
    
    # Test mixed columns (time - col 13)
    print("\n⏰ Testing MIXED validation (column 13 - time):\n")
    time_tests = [
        "08:00-16:00",  # correct format
        "8:00-16:00",   # missing leading zero
        "08:00",        # incomplete
        "invalid",      # invalid
        "",             # empty
    ]
    
    for text in time_tests:
        cleaned, is_valid = validate_cell_data(text, column_index=13)
        status = "✅" if is_valid else "❌"
        print(f"  {status} {text:20} → {cleaned:20} (valid: {is_valid})")
    
    print("\n" + "=" * 60)


def test_empty_cell_detection():
    """Test empty cell detection"""
    
    print("\n" + "=" * 60)
    print("STAGE 6: EMPTY CELL DETECTION TEST")
    print("=" * 60)
    
    print("\n🔍 Creating test cells...\n")
    
    # Create empty cell (white)
    empty_cell = np.ones((50, 100, 3), dtype=np.uint8) * 255
    
    # Create cell with text (simulate)
    text_cell = np.ones((50, 100, 3), dtype=np.uint8) * 255
    cv2.putText(text_cell, "123", (10, 35), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    
    # Create cell with light noise
    noisy_cell = np.ones((50, 100, 3), dtype=np.uint8) * 255
    noise = np.random.normal(0, 5, noisy_cell.shape).astype(np.uint8)
    noisy_cell = cv2.add(noisy_cell, noise)
    
    # Create cell with grid lines only
    grid_cell = np.ones((50, 100, 3), dtype=np.uint8) * 255
    cv2.line(grid_cell, (0, 0), (100, 0), (0, 0, 0), 1)  # top border
    cv2.line(grid_cell, (0, 49), (100, 49), (0, 0, 0), 1)  # bottom border
    
    # Test
    test_cells = [
        (empty_cell, "Empty cell (all white)", True),
        (text_cell, "Cell with text", False),
        (noisy_cell, "Cell with noise", True),
        (grid_cell, "Cell with grid only", True),
    ]
    
    results_dir = "experiments/results"
    os.makedirs(results_dir, exist_ok=True)
    
    for i, (cell, description, expected) in enumerate(test_cells):
        is_empty = is_cell_empty(cell)
        status = "✅" if is_empty == expected else "❌"
        
        print(f"  {status} {description:25} → Empty: {is_empty} (expected: {expected})")
        
        # Save test cell
        cv2.imwrite(f"{results_dir}/stage6_empty_test_{i}.jpg", cell)
    
    print(f"\n  💾 Saved test cells to: {results_dir}/")
    
    print("\n" + "=" * 60)
    print("Stage 6 testing completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_text_cleaning()
    test_column_validation()
    test_empty_cell_detection()


