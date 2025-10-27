"""
Test Stage 5: OCR per Cell with PaddleOCR

Strategy: Empty Detection + Batch PaddleOCR
- PaddleOCR: Better accuracy for Indonesian + mixed text
- Batch processing per cell
- Skip header rows (focus on data)

Expected: Better accuracy, ~10-15s processing time
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import from previous stages
from experiments.stage4_cell_segmentation.test_hybrid_segmentation import (
    detect_horizontal_lines,
    detect_vertical_lines,
    extract_cells_from_grid
)


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


def ocr_cells_with_paddleocr(cells: dict, skip_header_rows: int = 3) -> dict:
    """
    OCR cells using PaddleOCR for better accuracy
    
    Args:
        cells: Dict {(row, col): cell_image}
        skip_header_rows: Number of header rows to skip
        
    Returns:
        Dict {(row, col): text}
    """
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        print("  ✗ ERROR: PaddleOCR not installed")
        return {}
    
    print(f"  Initializing PaddleOCR...")
    start_init = time.time()
    
    # Initialize PaddleOCR
    ocr = PaddleOCR(
        lang='en'                  # English + numbers
    )
    
    init_time = time.time() - start_init
    print(f"  ✓ PaddleOCR initialized in {init_time:.2f}s")
    
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
        
        # OCR the cell
        try:
            result = ocr.predict(cell_img)
            
            # Extract text
            if result and result[0] and 'rec_texts' in result[0]:
                texts = result[0]['rec_texts']
                combined_text = ' '.join(texts)
                results[(row, col)] = combined_text
            else:
                results[(row, col)] = ""
            
            processed += 1
            
            # Progress indicator
            if processed % 20 == 0:
                print(f"    Processed: {processed} cells...")
                
        except Exception as e:
            print(f"    ⚠️  Error OCR cell {(row, col)}: {e}")
            results[(row, col)] = ""
    
    print(f"  ✓ Completed: {processed} cells OCR'd, {skipped} skipped")
    
    return results


def test_paddleocr_batch():
    """Test Stage 5 with PaddleOCR"""
    
    print('='*60)
    print('STAGE 5: PADDLEOCR BATCH (Better Accuracy)')
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
    
    # Step 3: OCR with PaddleOCR
    print('\n[Step 3] OCR with PaddleOCR (skip header rows)...')
    start = time.time()
    
    ocr_results = ocr_cells_with_paddleocr(cells, skip_header_rows=3)
    
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
        (4, 0), (4, 1), (4, 2),  # Row 4
        (5, 0), (5, 5), (5, 10), # Row 5
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
    
    json_path = results_dir / 'stage5_paddleocr_results.json'
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
        'method': 'PaddleOCR'
    }
    
    stats_path = results_dir / 'stage5_paddleocr_statistics.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    
    print(f'  ✓ Statistics saved: {stats_path.name}')
    
    # Total time
    total_time = time.time() - overall_start
    
    print(f'\n' + '='*60)
    print('PADDLEOCR BATCH RESULTS')
    print('='*60)
    print(f'Total time: {total_time:.2f}s')
    print(f'  - Cell extraction: {extract_time:.2f}s')
    print(f'  - PaddleOCR:       {ocr_time:.2f}s')
    print(f'\nResults:')
    print(f'  Total cells:   {len(ocr_results)}')
    print(f'  Header (skip): {header_cells}')
    print(f'  Empty:         {empty_cells}')
    print(f'  Data OCR:      {data_cells}')
    print(f'\nOutputs:')
    print(f'  Results: {json_path.name}')
    print(f'  Stats:   {stats_path.name}')
    print('='*60)
    
    return True


if __name__ == '__main__':
    success = test_paddleocr_batch()
    sys.exit(0 if success else 1)
