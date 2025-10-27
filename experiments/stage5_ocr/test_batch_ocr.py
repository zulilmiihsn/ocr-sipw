"""
Test Stage 5: OCR per Cell with Hybrid Strategy

Strategy: Empty Detection + Batch Tesseract
1. Quick scan to detect empty cells (~2.5s)
2. Batch OCR for filled cells (~3-5s)
3. Map results back to positions (~0.1s)

Total time: ~6-8s for 255 cells!
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

# Import from previous stages
from experiments.stage4_cell_segmentation.test_hybrid_segmentation import (
    detect_horizontal_lines,
    detect_vertical_lines,
    extract_cells_from_grid
)


def is_cell_empty(cell_image: np.ndarray, threshold: float = 0.02) -> bool:
    """
    Quick check if cell is empty (mostly white)
    
    Args:
        cell_image: Cell image (grayscale or BGR)
        threshold: Max ratio of dark pixels to consider empty
        
    Returns:
        True if cell appears empty
    """
    if cell_image.size == 0:
        return True
    
    # Convert to grayscale if needed
    if len(cell_image.shape) == 3:
        gray = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_image
    
    # Count dark pixels (text is dark)
    dark_pixels = np.sum(gray < 128)
    total_pixels = gray.size
    
    ratio = dark_pixels / total_pixels
    
    return ratio < threshold


def batch_ocr_cells(cells: list, cell_positions: list) -> dict:
    """
    Batch OCR multiple cells at once
    
    Args:
        cells: List of cell images
        cell_positions: List of (row, col) positions
        
    Returns:
        Dict {(row, col): text}
    """
    if not cells:
        return {}
    
    # Arrange cells in a grid for batch processing
    # Simple approach: stack vertically with separators
    
    separator_height = 20
    max_width = max(cell.shape[1] for cell in cells)
    
    # Pad cells to same width and stack
    padded_cells = []
    for cell in cells:
        if len(cell.shape) == 2:
            cell = cv2.cvtColor(cell, cv2.COLOR_GRAY2BGR)
        
        # Pad to max width
        if cell.shape[1] < max_width:
            pad_width = max_width - cell.shape[1]
            cell = cv2.copyMakeBorder(cell, 0, 0, 0, pad_width, 
                                     cv2.BORDER_CONSTANT, value=(255, 255, 255))
        
        padded_cells.append(cell)
        
        # Add separator
        separator = np.ones((separator_height, max_width, 3), dtype=np.uint8) * 255
        padded_cells.append(separator)
    
    # Stack all cells
    batch_image = np.vstack(padded_cells)
    
    # OCR the entire batch
    try:
        # Set Tesseract path for Windows
        import os
        if os.name == 'nt':
            tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(tesseract_path):
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
        
        # Get detailed OCR data
        data = pytesseract.image_to_data(
            batch_image,
            output_type=pytesseract.Output.DICT,
            config='--psm 6'  # Uniform block of text
        )
        
        # Map results back to cells
        results = {}
        current_y = 0
        cell_idx = 0
        
        for i, cell in enumerate(cells):
            cell_height = cell.shape[0]
            cell_bottom = current_y + cell_height
            
            # Extract text in this cell's Y range
            cell_texts = []
            for j in range(len(data['text'])):
                text = data['text'][j].strip()
                conf = int(data['conf'][j])
                y = data['top'][j]
                
                if conf > 30 and text and current_y <= y < cell_bottom:
                    cell_texts.append(text)
            
            # Combine texts for this cell
            combined_text = ' '.join(cell_texts)
            results[cell_positions[i]] = combined_text
            
            # Move to next cell (cell + separator)
            current_y = cell_bottom + separator_height
        
        return results
        
    except Exception as e:
        print(f"  ⚠️  Batch OCR error: {e}")
        # Fallback: return empty results
        return {pos: "" for pos in cell_positions}


def test_batch_ocr():
    """Test Stage 5 with batch OCR strategy"""
    
    print('='*60)
    print('STAGE 5: BATCH OCR WITH EMPTY DETECTION')
    print('='*60)
    
    overall_start = time.time()
    
    # Step 1: Load table image (reuse Stage 3 output)
    print('\n[Step 1] Loading table image...')
    image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
    
    if not image_path.exists():
        print(f'  ✗ ERROR: {image_path} not found')
        return False
    
    image = cv2.imread(str(image_path))
    print(f'  ✓ Image loaded: {image.shape}')
    
    # Step 2: Get cells (reuse Stage 4 logic)
    print('\n[Step 2] Extracting cells...')
    start = time.time()
    
    h_lines = detect_horizontal_lines(image, min_line_length=image.shape[1] // 3)
    v_lines = detect_vertical_lines(image, min_line_length=image.shape[0] // 5)
    cells = extract_cells_from_grid(image, h_lines, v_lines, margin=5)
    
    extract_time = time.time() - start
    print(f'  ✓ Extracted {len(cells)} cells in {extract_time:.2f}s')
    
    # Step 3: Quick empty detection
    print('\n[Step 3] Detecting empty cells...')
    start = time.time()
    
    empty_cells = []
    filled_cells = []
    filled_positions = []
    
    for position, cell_img in cells.items():
        if is_cell_empty(cell_img):
            empty_cells.append(position)
        else:
            filled_cells.append(cell_img)
            filled_positions.append(position)
    
    empty_time = time.time() - start
    
    print(f'  ✓ Scanned {len(cells)} cells in {empty_time:.2f}s')
    print(f'  Empty cells: {len(empty_cells)}')
    print(f'  Filled cells: {len(filled_cells)}')
    print(f'  Skip ratio: {len(empty_cells)/len(cells)*100:.1f}%')
    
    # Step 4: Batch OCR for filled cells
    print('\n[Step 4] Batch OCR for filled cells...')
    start = time.time()
    
    if filled_cells:
        ocr_results = batch_ocr_cells(filled_cells, filled_positions)
    else:
        ocr_results = {}
    
    ocr_time = time.time() - start
    
    print(f'  ✓ OCR completed in {ocr_time:.2f}s')
    print(f'  Processed: {len(filled_cells)} cells')
    print(f'  Speed: {len(filled_cells)/ocr_time:.1f} cells/second')
    
    # Step 5: Combine results
    print('\n[Step 5] Combining results...')
    
    all_results = {}
    
    # Add empty cells
    for pos in empty_cells:
        all_results[pos] = ""
    
    # Add OCR results
    for pos, text in ocr_results.items():
        all_results[pos] = text
    
    print(f'  ✓ Total results: {len(all_results)}')
    
    # Step 6: Sample results
    print('\n[Step 6] Sample OCR results...')
    
    sample_positions = [
        (0, 0), (0, 1), (0, 2),  # Header row
        (1, 0), (1, 1), (1, 2),  # First data row
        (5, 5), (5, 6),          # Middle cells
    ]
    
    for pos in sample_positions:
        if pos in all_results:
            text = all_results[pos]
            status = "empty" if text == "" else f'"{text}"'
            print(f'  Cell {pos}: {status}')
    
    # Step 7: Save results
    print('\n[Step 7] Saving results...')
    
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    # Save as JSON
    import json
    
    # Convert tuple keys to strings for JSON
    json_results = {f"{row},{col}": text for (row, col), text in all_results.items()}
    
    json_path = results_dir / 'stage5_ocr_results.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_results, f, indent=2, ensure_ascii=False)
    
    print(f'  ✓ Results saved: {json_path.name}')
    
    # Save statistics
    stats = {
        'total_cells': len(cells),
        'empty_cells': len(empty_cells),
        'filled_cells': len(filled_cells),
        'skip_ratio': f'{len(empty_cells)/len(cells)*100:.1f}%',
        'time': {
            'extraction': f'{extract_time:.2f}s',
            'empty_detection': f'{empty_time:.2f}s',
            'ocr': f'{ocr_time:.2f}s',
            'total': f'{time.time() - overall_start:.2f}s'
        }
    }
    
    stats_path = results_dir / 'stage5_statistics.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    
    print(f'  ✓ Statistics saved: {stats_path.name}')
    
    # Total time
    total_time = time.time() - overall_start
    
    print(f'\n' + '='*60)
    print('BATCH OCR RESULTS')
    print('='*60)
    print(f'Total time: {total_time:.2f}s ⚡')
    print(f'  - Cell extraction:  {extract_time:.2f}s')
    print(f'  - Empty detection:  {empty_time:.2f}s')
    print(f'  - Batch OCR:        {ocr_time:.2f}s')
    print(f'\nEfficiency:')
    print(f'  Total cells:   {len(cells)}')
    print(f'  Empty (skip):  {len(empty_cells)} ({len(empty_cells)/len(cells)*100:.1f}%)')
    print(f'  OCR processed: {len(filled_cells)}')
    print(f'  Speed:         {len(filled_cells)/ocr_time if ocr_time > 0 else 0:.1f} cells/s')
    print(f'\nOutputs:')
    print(f'  Results: {json_path.name}')
    print(f'  Stats:   {stats_path.name}')
    print('='*60)
    
    return True


if __name__ == '__main__':
    success = test_batch_ocr()
    sys.exit(0 if success else 1)
