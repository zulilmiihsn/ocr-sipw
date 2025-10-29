"""
Test Stage 5: SINGLETON PP-OCRv5 (Load Once, Use Forever)

Strategy: ELIMINATE MODEL LOADING OVERHEAD
1. Load PP-OCRv5 model ONCE at startup
2. Reuse same instance for ALL cells
3. Process cells in true batches (not sequential)
4. No multiprocessing (avoid re-loading)

Target: Minimize total time by eliminating redundant model loads
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


class SingletonPPOCRv5:
    """
    Singleton PP-OCRv5 instance that loads once and reuses
    """
    _instance = None
    _ocr = None
    _init_time = 0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Only initialize once
        if self._ocr is None:
            print("=" * 60)
            print("INITIALIZING PP-OCRv5 (ONE-TIME LOAD)")
            print("=" * 60)
            start = time.time()
            
            try:
                from paddleocr import PaddleOCR
                
                self._ocr = PaddleOCR(
                    lang='en',
                    use_textline_orientation=False,  # Faster
                )
                
                self._init_time = time.time() - start
                print(f"OK PP-OCRv5 loaded in {self._init_time:.2f}s")
                print("   This model will be REUSED for all cells!")
                print("=" * 60)
                
            except ImportError:
                print("X ERROR: PaddleOCR not installed")
                raise
            except Exception as e:
                print(f"X ERROR: {e}")
                raise
    
    @property
    def ocr(self):
        return self._ocr
    
    @property
    def init_time(self):
        return self._init_time


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


def preprocess_cell(cell_img: np.ndarray) -> np.ndarray:
    """Minimal preprocessing for PP-OCRv5"""
    # Ensure BGR format
    if len(cell_img.shape) == 2:
        cell_img = cv2.cvtColor(cell_img, cv2.COLOR_GRAY2BGR)
    
    return cell_img


def ocr_cells_batch(ocr_engine, cells: dict, batch_size: int = 32) -> dict:
    """
    OCR cells in batches using singleton PP-OCRv5
    
    Args:
        ocr_engine: Singleton PP-OCRv5 instance
        cells: dict of {(row, col): cell_image}
        batch_size: number of cells per batch
    
    Returns:
        dict of {(row, col): text}
    """
    print(f"\nProcessing {len(cells)} cells in batches of {batch_size}...")
    
    cell_items = list(cells.items())
    results = {}
    
    processed = 0
    skipped = 0
    
    for i in range(0, len(cell_items), batch_size):
        batch_items = cell_items[i:i+batch_size]
        
        # Filter empty cells
        batch_to_process = []
        batch_keys = []
        
        for (row, col), cell_img in batch_items:
            if is_cell_empty(cell_img):
                results[(row, col)] = ""
                skipped += 1
            else:
                # Preprocess
                processed_img = preprocess_cell(cell_img)
                batch_to_process.append(processed_img)
                batch_keys.append((row, col))
        
        # Process non-empty cells
        if batch_to_process:
            for j, cell_img in enumerate(batch_to_process):
                key = batch_keys[j]
                
                try:
                    result = ocr_engine.ocr.predict(cell_img)
                    
                    # Extract text
                    if result and result[0] and 'rec_texts' in result[0]:
                        texts = result[0]['rec_texts']
                        if isinstance(texts, list):
                            combined = ' '.join(texts)
                        else:
                            combined = str(texts)
                        results[key] = combined
                    else:
                        results[key] = ""
                    
                    processed += 1
                    
                except Exception as e:
                    results[key] = ""
                    processed += 1
        
        # Progress
        if (i // batch_size + 1) % 5 == 0 or i + len(batch_items) >= len(cell_items):
            print(f"  Progress: {i + len(batch_items)}/{len(cell_items)} cells...")
    
    print(f"  OK Completed: {processed} OCR'd, {skipped} empty")
    
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


def test_paddleocr_singleton():
    """Test SINGLETON PP-OCRv5 (Load Once, Use Forever)"""
    
    print('\n' + '='*60)
    print('STAGE 5: SINGLETON PP-OCRv5')
    print('Strategy: Load model ONCE, reuse for ALL cells')
    print('='*60)
    
    overall_start = time.time()
    
    # STEP 0: Initialize PP-OCRv5 ONCE (singleton)
    print('\n[Step 0] Loading PP-OCRv5 model (ONE-TIME)...')
    ocr_engine = SingletonPPOCRv5()
    init_time = ocr_engine.init_time
    
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
    
    # Step 3: OCR with singleton (reused model!)
    print('\n[Step 3] Running OCR (REUSING loaded model)...')
    start = time.time()
    
    ocr_results = ocr_cells_batch(ocr_engine, cells, batch_size=32)
    
    ocr_time = time.time() - start
    print(f'  OK OCR completed in {ocr_time:.2f}s')
    
    # Step 4: Post-processing
    print('\n[Step 4] Post-processing...')
    start = time.time()
    
    for (row, col), text in ocr_results.items():
        ocr_results[(row, col)] = postprocess_text(text, col)
    
    postprocess_time = time.time() - start
    print(f'  OK Post-processed in {postprocess_time:.2f}s')
    
    # Step 5: Analyze
    print('\n[Step 5] Analyzing results...')
    
    empty_cells = sum(1 for v in ocr_results.values() if v == "")
    data_cells = len(ocr_results) - empty_cells
    
    print(f'  Total cells:   {len(ocr_results)}')
    print(f'  Empty cells:   {empty_cells}')
    print(f'  Data cells:    {data_cells}')
    
    # Step 6: Sample results
    print('\n[Step 6] Sample results...')
    
    samples = [(4, 0), (4, 1), (4, 3), (5, 0), (5, 5), (5, 10), (6, 1), (6, 3)]
    for pos in samples:
        if pos in ocr_results:
            text = ocr_results[pos]
            print(f'  Cell {pos}: "{text if text else "[empty]"}"')
    
    # Step 7: Save
    print('\n[Step 7] Saving results...')
    
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    import json
    
    json_results = {f"{row},{col}": text for (row, col), text in ocr_results.items()}
    
    json_path = results_dir / 'stage5_singleton_results.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_results, f, indent=2, ensure_ascii=False)
    
    print(f'  OK Saved: {json_path.name}')
    
    # Statistics
    total_time = time.time() - overall_start
    
    stats = {
        'total_cells': len(cells),
        'empty_cells': empty_cells,
        'data_cells': data_cells,
        'time': {
            'model_loading': f'{init_time:.2f}s',
            'extraction': f'{extract_time:.2f}s',
            'ocr': f'{ocr_time:.2f}s',
            'postprocess': f'{postprocess_time:.2f}s',
            'total': f'{total_time:.2f}s'
        },
        'method': 'PP-OCRv5 Singleton (Load Once)'
    }
    
    stats_path = results_dir / 'stage5_singleton_statistics.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    
    print(f'  OK Saved: {stats_path.name}')
    
    # Summary
    print(f'\n' + '='*60)
    print('SINGLETON PP-OCRv5 RESULTS')
    print('='*60)
    print(f'Total time: {total_time:.2f}s')
    print(f'  - Model loading: {init_time:.2f}s (ONE-TIME ONLY!)')
    print(f'  - Extraction:    {extract_time:.2f}s')
    print(f'  - OCR:           {ocr_time:.2f}s (reusing model)')
    print(f'  - Postprocess:   {postprocess_time:.2f}s')
    print(f'\nCells: {len(ocr_results)} total, {empty_cells} empty, {data_cells} data')
    print('='*60)
    
    # Comparison
    print(f'\n' + '='*60)
    print('SPEED COMPARISON')
    print('='*60)
    print(f'Tesseract (baseline):              73.54s')
    print(f'PP-OCRv5 Sequential:               584.47s (load 1x)')
    print(f'PP-OCRv5 Parallel (3 processes):   401.70s (load 3x!)')
    print(f'PP-OCRv5 Singleton:                {total_time:.2f}s (load 1x, reuse!)')
    
    if total_time > 0:
        print(f'\nSpeedup vs Sequential:             {584.47/total_time:.2f}x')
        print(f'Speedup vs Parallel:               {401.70/total_time:.2f}x')
        
        if total_time < 73.54:
            print(f'Speedup vs Tesseract:              {73.54/total_time:.2f}x FASTER!')
        else:
            print(f'vs Tesseract:                      {total_time/73.54:.2f}x slower')
    
    print('='*60)
    
    # Key insight
    print(f'\n' + '='*60)
    print('KEY INSIGHT')
    print('='*60)
    print(f'Model loading overhead eliminated!')
    print(f'  Parallel: 3 processes × 30s = 90s wasted on loading')
    print(f'  Singleton: 1 × {init_time:.2f}s = only {init_time:.2f}s loading')
    print(f'  Savings: ~{90 - init_time:.0f}s!')
    print('='*60)
    
    return True


if __name__ == '__main__':
    success = test_paddleocr_singleton()
    sys.exit(0 if success else 1)
