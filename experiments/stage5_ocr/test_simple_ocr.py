"""
Test Stage 5: Simple OCR (Minimal Preprocessing)

Strategy: KISS - Keep It Simple!
- Minimal preprocessing (just resize if needed)
- Use PSM 6 (block of text) for all
- Let Tesseract do its job
- Skip ONLY truly empty cells

Expected: Better balance of speed + accuracy
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
    """
    Minimal preprocessing - just grayscale and slight resize if needed
    """
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


def ocr_cells_simple(cells: dict) -> dict:
    """
    OCR all cells with minimal preprocessing
    
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
            
            results[(row, col)] = text
        except Exception as e:
            results[(row, col)] = ""
        
        processed += 1
        
        # Progress indicator
        if processed % 50 == 0:
            print(f"    Processed: {processed}/{len(cells)}...")
    
    print(f"  ✓ Completed: {processed} cells OCR'd, {skipped} empty")
    
    return results


def test_simple_ocr():
    """Test Stage 5 with Simple OCR"""
    
    print('='*60)
    print('STAGE 5: SIMPLE OCR (KISS Principle)')
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
    
    # Step 3: OCR with Simple method
    print('\n[Step 3] OCR with Simple method...')
    start = time.time()
    
    ocr_results = ocr_cells_simple(cells)
    
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
    print('\n[Step 5] Sample OCR results...')
    
    sample_positions = [
        (0, 0), (0, 1), (0, 2),  # Row 0
        (1, 0), (1, 1), (1, 2),  # Row 1
        (2, 0), (2, 1), (2, 2),  # Row 2
        (4, 0), (4, 1), (4, 2), (4, 3),  # Row 4 (data)
        (5, 0), (5, 1), (5, 5), (5, 10), # Row 5 (data)
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
    
    json_path = results_dir / 'stage5_simple_results.json'
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
        'method': 'Simple OCR (KISS)'
    }
    
    stats_path = results_dir / 'stage5_simple_statistics.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    
    print(f'  ✓ Statistics saved: {stats_path.name}')
    
    # Total time
    total_time = time.time() - overall_start
    
    print(f'\n' + '='*60)
    print('SIMPLE OCR RESULTS')
    print('='*60)
    print(f'Total time: {total_time:.2f}s')
    print(f'  - Cell extraction: {extract_time:.2f}s')
    print(f'  - OCR:             {ocr_time:.2f}s')
    print(f'\nResults:')
    print(f'  Total cells:   {len(ocr_results)}')
    print(f'  Empty:         {empty_cells}')
    print(f'  Data OCR:      {data_cells}')
    print(f'\nOutputs:')
    print(f'  Results: {json_path.name}')
    print(f'  Stats:   {stats_path.name}')
    print('='*60)
    
    return True


if __name__ == '__main__':
    success = test_simple_ocr()
    sys.exit(0 if success else 1)

