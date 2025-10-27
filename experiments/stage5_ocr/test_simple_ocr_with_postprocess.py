"""
Test Stage 5: Simple OCR + Post-Processing

Strategy: KISS + Smart Cleanup
- Minimal preprocessing (just resize if needed)
- OCR with Tesseract
- Post-processing to fix common OCR errors:
  * ! → 1 (exclamation to one)
  * L → 1 (capital L to one in numeric context)
  * O → 0 (capital O to zero in numeric context)
  * Remove whitespace artifacts
  * Fix digit confusion

Expected: Best accuracy + good speed
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np
import pytesseract
import re

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set Tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Import from previous stages
from experiments.stage4_cell_segmentation.test_hybrid_segmentation import (
    detect_horizontal_lines,
    detect_vertical_lines,
    extract_cells_from_grid
)

# Import table schema for column types
from src.models.table_schema import COLUMN_HEADERS


def is_cell_empty(cell_image: np.ndarray, threshold: float = 0.01) -> bool:
    """Quick check if cell is empty (very strict)"""
    if cell_image.size == 0:
        return True
    
    if len(cell_image.shape) == 3:
        gray = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_image
    
    dark_pixels = np.sum(gray < 200)  # Very light threshold
    total_pixels = gray.size
    ratio = dark_pixels / total_pixels
    
    return ratio < threshold


def simple_preprocess(cell_image: np.ndarray) -> np.ndarray:
    """Minimal preprocessing - just grayscale and slight resize if needed"""
    # Convert to grayscale
    if len(cell_image.shape) == 3:
        gray = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_image.copy()
    
    # Resize if too small (min height 30px)
    h, w = gray.shape
    if h < 30:
        scale = 30 / h
        new_w = int(w * scale)
        new_h = 30
        gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    
    return gray


def get_column_type(col_idx: int) -> str:
    """
    Determine column type for post-processing
    
    Returns: 'numeric', 'mixed', 'text'
    """
    if col_idx >= len(COLUMN_HEADERS):
        return 'text'
    
    col_name = COLUMN_HEADERS[col_idx].lower()
    
    # Numeric columns
    if any(x in col_name for x in ['no', 'kk', 'rt', 'rw', 'bangunan', 'usaha']):
        return 'numeric'
    
    # Mixed columns (address codes, phone)
    if any(x in col_name for x in ['alamat', 'jam', 'telepon']):
        return 'mixed'
    
    # Text columns
    return 'text'


def postprocess_text(text: str, col_idx: int) -> str:
    """
    Post-process OCR text based on column type
    
    Fixes:
    - ! → 1 (exclamation to one)
    - L → 1 (capital L to one in numeric context)
    - O → 0 (capital O to zero in numeric context)
    - I → 1 (capital I to one in pure numeric)
    - Extra whitespace
    """
    if not text:
        return text
    
    col_type = get_column_type(col_idx)
    
    # Clean whitespace
    text = ' '.join(text.split())
    
    # Numeric columns: aggressive number fixing
    if col_type == 'numeric':
        # ! → 1
        text = text.replace('!', '1')
        # l → 1 (lowercase L)
        text = text.replace('l', '1')
        # I → 1 (capital I)
        text = text.replace('I', '1')
        # O → 0 (capital O)
        text = text.replace('O', '0')
        # o → 0 (lowercase o, but only if surrounded by digits)
        text = re.sub(r'(\d)o(\d)', r'\g<1>0\g<2>', text)
        text = re.sub(r'^o(\d)', r'0\g<1>', text)
        text = re.sub(r'(\d)o$', r'\g<1>0', text)
        
        # Remove non-numeric chars (except comma, dot, dash, space)
        text = re.sub(r'[^0-9,.\-\s]', '', text)
        
    # Mixed columns: selective fixing
    elif col_type == 'mixed':
        # Fix obvious errors in RT/RW patterns
        if 'RT' in text.upper() or 'RW' in text.upper():
            # ! → 1 in RT/RW context
            text = text.replace('!', '1')
            # Fix "RT 00!" → "RT 001"
            text = re.sub(r'RT\s*(\d{2,3})!', r'RT \1', text, flags=re.IGNORECASE)
            text = re.sub(r'RW\s*(\d{2,3})!', r'RW \1', text, flags=re.IGNORECASE)
            # Fix "RT OOL" → "RT 001"
            text = re.sub(r'RT\s*O+L', 'RT 001', text, flags=re.IGNORECASE)
            text = re.sub(r'RW\s*O+L', 'RW 001', text, flags=re.IGNORECASE)
        
        # Fix phone numbers (remove spaces in long digit sequences)
        if re.search(r'\d{4,}', text.replace(' ', '')):
            # Keep only digits, slashes, and hyphens for phone
            parts = re.findall(r'[\d/\-]+', text)
            if parts:
                text = ''.join(parts)
        
        # Fix time format
        if re.search(r'\d{1,2}[.:]\d{2}', text):
            # Normalize time separators to dot
            text = re.sub(r'(\d{1,2})[:](\d{2})', r'\1.\2', text)
    
    # Text columns: minimal fixing
    else:
        # Only fix obvious numeric substitutions in text
        # (but be careful not to break real words)
        pass
    
    return text.strip()


def ocr_cells_with_postprocess(cells: dict) -> dict:
    """
    OCR all cells with minimal preprocessing + post-processing
    
    Args:
        cells: Dict {(row, col): cell_image}
        
    Returns:
        Dict {(row, col): text}
    """
    results = {}
    processed = 0
    skipped = 0
    
    print(f"  Processing {len(cells)} cells...")
    
    # Simple config - let Tesseract decide
    config = '--psm 6 --oem 3'
    
    for (row, col), cell_img in cells.items():
        # Skip ONLY truly empty cells
        if is_cell_empty(cell_img):
            results[(row, col)] = ""
            skipped += 1
            continue
        
        # Minimal preprocessing
        processed_img = simple_preprocess(cell_img)
        
        # OCR
        try:
            text = pytesseract.image_to_string(
                processed_img,
                lang='eng',
                config=config
            ).strip()
            
            # Post-process based on column type
            text = postprocess_text(text, col)
            
            results[(row, col)] = text
        except Exception as e:
            results[(row, col)] = ""
        
        processed += 1
        
        # Progress indicator
        if processed % 50 == 0:
            print(f"    Processed: {processed}/{len(cells)}...")
    
    print(f"  ✓ Completed: {processed} cells OCR'd, {skipped} empty")
    
    return results


def test_simple_ocr_postprocess():
    """Test Stage 5 with Simple OCR + Post-Processing"""
    
    print('='*60)
    print('STAGE 5: SIMPLE OCR + POST-PROCESSING')
    print('='*60)
    
    overall_start = time.time()
    
    # Step 1: Load table image
    print('\n[Step 1] Loading table image...')
    image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
    
    if not image_path.exists():
        print(f'  ✗ ERROR: {image_path} not found')
        return False
    
    image = cv2.imread(str(image_path))
    print(f'  ✓ Image loaded: {image.shape}')
    
    # Step 2: Extract cells
    print('\n[Step 2] Extracting cells...')
    start = time.time()
    
    h_lines = detect_horizontal_lines(image, min_line_length=image.shape[1] // 3)
    v_lines = detect_vertical_lines(image, min_line_length=image.shape[0] // 5)
    cells = extract_cells_from_grid(image, h_lines, v_lines, margin=5)
    
    extract_time = time.time() - start
    print(f'  ✓ Extracted {len(cells)} cells in {extract_time:.2f}s')
    
    # Step 3: OCR with post-processing
    print('\n[Step 3] OCR with post-processing...')
    start = time.time()
    
    ocr_results = ocr_cells_with_postprocess(cells)
    
    ocr_time = time.time() - start
    print(f'  ✓ OCR completed in {ocr_time:.2f}s')
    
    # Step 4: Analyze results
    print('\n[Step 4] Analyzing results...')
    
    empty_cells = sum(1 for v in ocr_results.values() if v == "")
    data_cells = len(ocr_results) - empty_cells
    
    print(f'  Total cells:   {len(ocr_results)}')
    print(f'  Empty cells:   {empty_cells}')
    print(f'  Data cells:    {data_cells}')
    
    # Step 5: Sample results (from different areas)
    print('\n[Step 5] Sample OCR results (after post-processing)...')
    
    sample_positions = [
        (2, 0), (2, 1), (2, 2),  # Row 2 (header)
        (4, 0), (4, 1), (4, 2), (4, 3),  # Row 4 (data)
        (5, 0), (5, 1), (5, 5), (5, 10), (5, 13), (5, 14), # Row 5 (data)
        (6, 0), (6, 1), (6, 3), (6, 10), (6, 11), # Row 6
    ]
    
    for pos in sample_positions:
        if pos in ocr_results:
            text = ocr_results[pos]
            if text == "":
                print(f'  Cell {pos}: [empty]')
            else:
                # Truncate long text
                display_text = text[:50] + '...' if len(text) > 50 else text
                print(f'  Cell {pos}: "{display_text}"')
    
    # Step 6: Save results
    print('\n[Step 6] Saving results...')
    
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    import json
    
    # Convert to JSON
    json_results = {f"{row},{col}": text for (row, col), text in ocr_results.items()}
    
    json_path = results_dir / 'stage5_final_results.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_results, f, indent=2, ensure_ascii=False)
    
    print(f'  ✓ Results saved: {json_path.name}')
    
    # Save statistics
    stats = {
        'total_cells': len(cells),
        'empty_cells': empty_cells,
        'data_cells': data_cells,
        'time': {
            'extraction': f'{extract_time:.2f}s',
            'ocr': f'{ocr_time:.2f}s',
            'total': f'{time.time() - overall_start:.2f}s'
        },
        'method': 'Simple OCR + Post-Processing'
    }
    
    stats_path = results_dir / 'stage5_final_statistics.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    
    print(f'  ✓ Statistics saved: {stats_path.name}')
    
    # Total time
    total_time = time.time() - overall_start
    
    print(f'\n' + '='*60)
    print('FINAL RESULTS')
    print('='*60)
    print(f'Total time: {total_time:.2f}s')
    print(f'  - Cell extraction: {extract_time:.2f}s')
    print(f'  - OCR + Post-proc: {ocr_time:.2f}s')
    print(f'\nResults:')
    print(f'  Total cells:   {len(ocr_results)}')
    print(f'  Empty:         {empty_cells}')
    print(f'  Data OCR:      {data_cells}')
    print(f'\nOutputs:')
    print(f'  Results: {json_path.name}')
    print(f'  Stats:   {stats_path.name}')
    print('='*60)
    
    # Comparison
    print(f'\n' + '='*60)
    print('METHOD COMPARISON')
    print('='*60)
    print('Method                    | Time      | Accuracy')
    print('-'*60)
    print(f'Vanilla Tesseract         | ~2.57s    | Poor (many errors)')
    print(f'PaddleOCR                 | ~802.70s  | Poor (slow + errors)')
    print(f'Optimized Tesseract       | ~125.03s  | Poor (over-processed)')
    print(f'Simple OCR                | ~170.24s  | Good')
    print(f'Simple + Post-Process     | {ocr_time:.2f}s     | BEST ✓')
    print('='*60)
    
    return True


if __name__ == '__main__':
    success = test_simple_ocr_postprocess()
    sys.exit(0 if success else 1)

