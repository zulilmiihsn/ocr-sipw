"""
Test Stage 5: OCR per Cell with Optimized Tesseract

Strategy: Smart Preprocessing + Column-Specific OCR
- Per-cell preprocessing (sharpen, denoise, enhance)
- PSM mode per column type (single line vs block)
- Whitelist per column (digits, text, mixed)
- Skip header rows and empty cells

Expected: Fast (~5-10s) + Better accuracy than vanilla Tesseract
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np
import pytesseract

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
from src.models.table_schema import COLUMN_HEADERS, COLUMN_WHITELISTS


def is_cell_empty(cell_image: np.ndarray, threshold: float = 0.02) -> bool:
    """Quick check if cell is empty"""
    if cell_image.size == 0:
        return True
    
    if len(cell_image.shape) == 3:
        gray = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_image
    
    dark_pixels = np.sum(gray < 128)
    total_pixels = gray.size
    ratio = dark_pixels / total_pixels
    
    return ratio < threshold


def preprocess_cell_for_ocr(cell_image: np.ndarray) -> np.ndarray:
    """
    Preprocess cell image for better OCR accuracy
    
    Steps:
    1. Convert to grayscale
    2. Resize if too small
    3. Denoise
    4. Sharpen
    5. Adaptive threshold (binarize)
    """
    # Convert to grayscale
    if len(cell_image.shape) == 3:
        gray = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_image.copy()
    
    # Resize if too small (min height 40px for better OCR)
    h, w = gray.shape
    if h < 40:
        scale = 40 / h
        new_w = int(w * scale)
        new_h = 40
        gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    
    # Denoise
    denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
    
    # Sharpen
    kernel_sharpen = np.array([[-1, -1, -1],
                                [-1,  9, -1],
                                [-1, -1, -1]])
    sharpened = cv2.filter2D(denoised, -1, kernel_sharpen)
    
    # Adaptive threshold (binarize)
    binary = cv2.adaptiveThreshold(
        sharpened,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,  # Block size
        2    # C constant
    )
    
    return binary


def get_column_config(col_idx: int) -> dict:
    """
    Get OCR configuration for specific column
    
    Returns dict with:
    - psm: Page segmentation mode
    - whitelist: Character whitelist (if any)
    - lang: Language
    """
    # Default config
    config = {
        'psm': 6,  # Assume a single uniform block of text
        'whitelist': None,
        'lang': 'eng'
    }
    
    # Get column name
    if col_idx >= len(COLUMN_HEADERS):
        return config
    
    col_name = COLUMN_HEADERS[col_idx]
    
    # Get column type from whitelist
    col_type = None
    for dtype, whitelist in COLUMN_WHITELISTS.items():
        # Check if this column is numeric, text, or address
        if dtype == 'numeric' and any(x in col_name.lower() for x in ['no', 'kk', 'rt', 'rw', 'bangunan', 'usaha', 'jam']):
            col_type = 'numeric'
            config['whitelist'] = whitelist
            config['psm'] = 7  # Single text line
            break
        elif dtype == 'address' and any(x in col_name.lower() for x in ['alamat', 'wilayah', 'nama']):
            col_type = 'text'
            config['psm'] = 6  # Block of text
            break
    
    return config


def ocr_cell_optimized(cell_image: np.ndarray, col_idx: int) -> str:
    """
    OCR single cell with optimized preprocessing and config
    """
    # Preprocess
    processed = preprocess_cell_for_ocr(cell_image)
    
    # Get column-specific config
    config = get_column_config(col_idx)
    
    # Build Tesseract config string
    custom_config = f'--psm {config["psm"]} --oem 3'
    
    if config['whitelist']:
        # Escape whitelist for Tesseract
        whitelist_str = config['whitelist'].replace('\\', '\\\\')
        custom_config += f' -c tessedit_char_whitelist={whitelist_str}'
    
    # OCR
    try:
        text = pytesseract.image_to_string(
            processed,
            lang=config['lang'],
            config=custom_config
        ).strip()
        
        return text
    except Exception as e:
        return ""


def ocr_cells_optimized(cells: dict, skip_header_rows: int = 3) -> dict:
    """
    OCR all cells with optimized preprocessing
    
    Args:
        cells: Dict {(row, col): cell_image}
        skip_header_rows: Number of header rows to skip
        
    Returns:
        Dict {(row, col): text}
    """
    results = {}
    processed = 0
    skipped = 0
    
    print(f"  Processing cells (skip header rows 0-{skip_header_rows-1})...")
    
    for (row, col), cell_img in cells.items():
        # Skip header rows
        if row < skip_header_rows:
            results[(row, col)] = "[HEADER]"
            skipped += 1
            continue
        
        # Skip empty cells
        if is_cell_empty(cell_img):
            results[(row, col)] = ""
            skipped += 1
            continue
        
        # OCR with optimization
        text = ocr_cell_optimized(cell_img, col)
        results[(row, col)] = text
        processed += 1
        
        # Progress indicator
        if processed % 20 == 0:
            print(f"    Processed: {processed} cells...")
    
    print(f"  ✓ Completed: {processed} cells OCR'd, {skipped} skipped")
    
    return results


def test_optimized_tesseract():
    """Test Stage 5 with Optimized Tesseract"""
    
    print('='*60)
    print('STAGE 5: OPTIMIZED TESSERACT (Smart + Fast)')
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
    
    # Step 3: OCR with Optimized Tesseract
    print('\n[Step 3] OCR with Optimized Tesseract...')
    start = time.time()
    
    ocr_results = ocr_cells_optimized(cells, skip_header_rows=3)
    
    ocr_time = time.time() - start
    print(f'  ✓ OCR completed in {ocr_time:.2f}s')
    
    # Step 4: Analyze results
    print('\n[Step 4] Analyzing results...')
    
    header_cells = sum(1 for v in ocr_results.values() if v == "[HEADER]")
    empty_cells = sum(1 for v in ocr_results.values() if v == "")
    data_cells = len(ocr_results) - header_cells - empty_cells
    
    print(f'  Total cells:   {len(ocr_results)}')
    print(f'  Header cells:  {header_cells} (skipped)')
    print(f'  Empty cells:   {empty_cells}')
    print(f'  Data cells:    {data_cells}')
    
    # Step 5: Sample results
    print('\n[Step 5] Sample OCR results (data rows)...')
    
    # Show samples from different rows
    sample_positions = [
        (3, 0), (3, 1), (3, 2),  # Row 3
        (4, 0), (4, 1), (4, 2), (4, 3),  # Row 4
        (5, 0), (5, 5), (5, 10), (5, 11), # Row 5
    ]
    
    for pos in sample_positions:
        if pos in ocr_results:
            text = ocr_results[pos]
            if text == "[HEADER]":
                print(f'  Cell {pos}: [HEADER - skipped]')
            elif text == "":
                print(f'  Cell {pos}: [empty]')
            else:
                print(f'  Cell {pos}: "{text}"')
    
    # Step 6: Save results
    print('\n[Step 6] Saving results...')
    
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    import json
    
    # Convert to JSON
    json_results = {f"{row},{col}": text for (row, col), text in ocr_results.items()}
    
    json_path = results_dir / 'stage5_optimized_results.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_results, f, indent=2, ensure_ascii=False)
    
    print(f'  ✓ Results saved: {json_path.name}')
    
    # Save statistics
    stats = {
        'total_cells': len(cells),
        'header_cells': header_cells,
        'empty_cells': empty_cells,
        'data_cells': data_cells,
        'time': {
            'extraction': f'{extract_time:.2f}s',
            'ocr': f'{ocr_time:.2f}s',
            'total': f'{time.time() - overall_start:.2f}s'
        },
        'method': 'Optimized Tesseract'
    }
    
    stats_path = results_dir / 'stage5_optimized_statistics.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    
    print(f'  ✓ Statistics saved: {stats_path.name}')
    
    # Total time
    total_time = time.time() - overall_start
    
    print(f'\n' + '='*60)
    print('OPTIMIZED TESSERACT RESULTS')
    print('='*60)
    print(f'Total time: {total_time:.2f}s')
    print(f'  - Cell extraction: {extract_time:.2f}s')
    print(f'  - OCR:             {ocr_time:.2f}s')
    print(f'\nResults:')
    print(f'  Total cells:   {len(ocr_results)}')
    print(f'  Header (skip): {header_cells}')
    print(f'  Empty:         {empty_cells}')
    print(f'  Data OCR:      {data_cells}')
    print(f'\nOutputs:')
    print(f'  Results: {json_path.name}')
    print(f'  Stats:   {stats_path.name}')
    print('='*60)
    
    # Compare with previous methods
    print(f'\n' + '='*60)
    print('COMPARISON')
    print('='*60)
    print('Method                    | Time      | Data Cells')
    print('-'*60)
    print(f'Vanilla Tesseract         | ~2.57s    | ~30 cells')
    print(f'PaddleOCR                 | ~802.70s  | 122 cells')
    print(f'Optimized Tesseract       | {ocr_time:.2f}s     | {data_cells} cells')
    print('='*60)
    
    return True


if __name__ == '__main__':
    success = test_optimized_tesseract()
    sys.exit(0 if success else 1)

