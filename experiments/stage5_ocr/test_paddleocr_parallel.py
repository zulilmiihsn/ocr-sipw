"""
Test Stage 5: PARALLEL PP-OCRv5

Strategy: EXTREME PARALLELIZATION
1. Split cells into chunks
2. Process each chunk in separate process (multiprocessing)
3. Each process loads its own PP-OCRv5 instance
4. Combine results

Target: Leverage ALL CPU cores for maximum speed
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np
from multiprocessing import Pool, cpu_count
import os

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import from previous stages
from experiments.stage4_cell_segmentation.test_hybrid_segmentation import (
    detect_horizontal_lines,
    detect_vertical_lines,
    extract_cells_from_grid
)


def is_cell_empty(cell_image: np.ndarray, threshold: float = 0.01) -> bool:
    """Quick empty check"""
    if cell_image.size == 0:
        return True
    
    if len(cell_image.shape) == 3:
        gray = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_image
    
    dark_pixels = np.sum(gray < 200)
    total_pixels = gray.size
    ratio = dark_pixels / total_pixels
    
    return ratio < threshold


def process_cell_batch(args):
    """
    Process a batch of cells in separate process
    This will be called by multiprocessing.Pool
    
    Args:
        args: tuple of (batch_items, process_id)
        batch_items: list of ((row, col), cell_image)
        process_id: for logging
    
    Returns:
        dict: {(row, col): text}
    """
    batch_items, process_id = args
    
    # Import PaddleOCR HERE (in worker process)
    try:
        from paddleocr import PaddleOCR
        
        # Initialize PP-OCRv5 in this process
        ocr = PaddleOCR(
            lang='en',
            use_textline_orientation=False,
        )
        
    except Exception as e:
        print(f"  [Process {process_id}] ERROR: {e}")
        return {}
    
    results = {}
    
    for (row, col), cell_img in batch_items:
        # Skip empty
        if is_cell_empty(cell_img):
            results[(row, col)] = ""
            continue
        
        try:
            # OCR
            result = ocr.predict(cell_img)
            
            # Extract text
            if result and result[0] and 'rec_texts' in result[0]:
                texts = result[0]['rec_texts']
                combined = ' '.join(texts) if isinstance(texts, list) else str(texts)
                results[(row, col)] = combined
            else:
                results[(row, col)] = ""
        
        except Exception as e:
            results[(row, col)] = ""
    
    print(f"  [Process {process_id}] Completed {len(results)} cells")
    
    return results


def postprocess_text(text: str, col_idx: int) -> str:
    """Post-process OCR text"""
    if not text:
        return text
    
    import re
    
    # Clean whitespace
    text = ' '.join(text.split())
    
    # Determine column type
    try:
        from src.models.table_schema import COLUMN_HEADERS
        
        if col_idx >= len(COLUMN_HEADERS):
            col_type = 'text'
        else:
            col_name = COLUMN_HEADERS[col_idx].lower()
            
            if any(x in col_name for x in ['no', 'kk', 'rt', 'rw', 'bangunan', 'usaha']):
                col_type = 'numeric'
            elif any(x in col_name for x in ['alamat', 'jam', 'telepon']):
                col_type = 'mixed'
            else:
                col_type = 'text'
    except:
        col_type = 'text'
    
    # Numeric columns: fix errors
    if col_type == 'numeric':
        text = text.replace('!', '1')
        text = text.replace('l', '1')
        text = text.replace('I', '1')
        text = text.replace('O', '0')
        text = text.replace('o', '0')
        text = re.sub(r'[^0-9,.\-\s]', '', text)
    
    # Mixed columns: selective fixing
    elif col_type == 'mixed':
        if 'RT' in text.upper() or 'RW' in text.upper():
            text = text.replace('!', '1')
            text = text.replace('O', '0')
    
    return text.strip()


def test_paddleocr_parallel():
    """Test PARALLEL PP-OCRv5"""
    
    print('='*60)
    print('STAGE 5: PARALLEL PP-OCRv5 (Multi-Process)')
    print('='*60)
    
    overall_start = time.time()
    
    # Check CPU cores
    n_cores = cpu_count()
    n_processes = max(1, n_cores - 1)  # Leave 1 core free
    print(f'\nCPU Cores: {n_cores}, Using: {n_processes} processes')
    
    # Step 1: Load table image
    print('\n[Step 1] Loading table image...')
    image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
    
    if not image_path.exists():
        print(f'  X ERROR: {image_path} not found')
        return False
    
    image = cv2.imread(str(image_path))
    print(f'  OK Image loaded: {image.shape}')
    
    # Step 2: Extract cells
    print('\n[Step 2] Extracting cells...')
    start = time.time()
    
    h_lines = detect_horizontal_lines(image, min_line_length=image.shape[1] // 3)
    v_lines = detect_vertical_lines(image, min_line_length=image.shape[0] // 5)
    cells = extract_cells_from_grid(image, h_lines, v_lines, margin=5)
    
    extract_time = time.time() - start
    print(f'  OK Extracted {len(cells)} cells in {extract_time:.2f}s')
    
    # Step 3: Split into batches for parallel processing
    print(f'\n[Step 3] Splitting {len(cells)} cells into {n_processes} batches...')
    
    cell_items = list(cells.items())
    batch_size = len(cell_items) // n_processes + 1
    
    batches = []
    for i in range(n_processes):
        start_idx = i * batch_size
        end_idx = min((i + 1) * batch_size, len(cell_items))
        batch = cell_items[start_idx:end_idx]
        if batch:
            batches.append((batch, i))
    
    print(f'  OK Created {len(batches)} batches')
    for i, (batch, pid) in enumerate(batches):
        print(f'    Batch {i}: {len(batch)} cells')
    
    # Step 4: Parallel OCR
    print(f'\n[Step 4] Running PARALLEL OCR ({n_processes} processes)...')
    start = time.time()
    
    # Use multiprocessing Pool
    with Pool(processes=n_processes) as pool:
        batch_results = pool.map(process_cell_batch, batches)
    
    ocr_time = time.time() - start
    print(f'  OK OCR completed in {ocr_time:.2f}s')
    
    # Step 5: Combine results
    print('\n[Step 5] Combining results...')
    
    ocr_results = {}
    for batch_result in batch_results:
        ocr_results.update(batch_result)
    
    print(f'  OK Combined {len(ocr_results)} results')
    
    # Step 6: Post-processing
    print('\n[Step 6] Post-processing...')
    start = time.time()
    
    for (row, col), text in ocr_results.items():
        ocr_results[(row, col)] = postprocess_text(text, col)
    
    postprocess_time = time.time() - start
    print(f'  OK Post-processed in {postprocess_time:.2f}s')
    
    # Step 7: Analyze
    print('\n[Step 7] Analyzing results...')
    
    empty_cells = sum(1 for v in ocr_results.values() if v == "")
    data_cells = len(ocr_results) - empty_cells
    
    print(f'  Total cells:   {len(ocr_results)}')
    print(f'  Empty cells:   {empty_cells}')
    print(f'  Data cells:    {data_cells}')
    
    # Step 8: Sample results
    print('\n[Step 8] Sample results...')
    
    samples = [(4, 0), (4, 1), (4, 3), (5, 0), (5, 5), (5, 10), (6, 1), (6, 3)]
    for pos in samples:
        if pos in ocr_results:
            text = ocr_results[pos]
            print(f'  Cell {pos}: "{text if text else "[empty]"}"')
    
    # Step 9: Save
    print('\n[Step 9] Saving results...')
    
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    import json
    
    json_results = {f"{row},{col}": text for (row, col), text in ocr_results.items()}
    
    json_path = results_dir / 'stage5_parallel_results.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_results, f, indent=2, ensure_ascii=False)
    
    print(f'  OK Saved: {json_path.name}')
    
    # Statistics
    total_time = time.time() - overall_start
    
    stats = {
        'total_cells': len(cells),
        'empty_cells': empty_cells,
        'data_cells': data_cells,
        'processes': n_processes,
        'time': {
            'extraction': f'{extract_time:.2f}s',
            'ocr': f'{ocr_time:.2f}s',
            'postprocess': f'{postprocess_time:.2f}s',
            'total': f'{total_time:.2f}s'
        },
        'method': f'PP-OCRv5 Parallel ({n_processes} processes)'
    }
    
    stats_path = results_dir / 'stage5_parallel_statistics.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    
    print(f'  OK Saved: {stats_path.name}')
    
    # Summary
    print(f'\n' + '='*60)
    print('PARALLEL PP-OCRv5 RESULTS')
    print('='*60)
    print(f'Total time: {total_time:.2f}s')
    print(f'  - Extraction:  {extract_time:.2f}s')
    print(f'  - OCR:         {ocr_time:.2f}s ({n_processes} parallel processes)')
    print(f'  - Postprocess: {postprocess_time:.2f}s')
    print(f'\nCells: {len(ocr_results)} total, {empty_cells} empty, {data_cells} data')
    print('='*60)
    
    # Comparison
    print(f'\n' + '='*60)
    print('SPEED COMPARISON')
    print('='*60)
    print(f'Tesseract (baseline):              73.54s (1 process)')
    print(f'PP-OCRv5 Sequential:               584.47s (SLOW!)')
    print(f'PP-OCRv5 Parallel ({n_processes} processes):   {ocr_time:.2f}s')
    if ocr_time > 0:
        print(f'Speedup vs Sequential:             {584.47/ocr_time:.1f}x')
        print(f'Speedup vs Tesseract:              {73.54/ocr_time:.1f}x')
    print('='*60)
    
    return True


if __name__ == '__main__':
    # Multiprocessing requires this on Windows
    from multiprocessing import freeze_support
    freeze_support()
    
    success = test_paddleocr_parallel()
    sys.exit(0 if success else 1)
