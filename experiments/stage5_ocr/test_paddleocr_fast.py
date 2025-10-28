"""
Test Stage 5: Fast PP-OCRv5 with Batch Processing (Option 3: Hybrid)

Strategy:
- Keep text detection (for accuracy on complex cells)
- Use batch processing (for speed)
- Pre-process efficiently
- Target: 5-10 seconds for 238 cells with 85-95% accuracy

Expected: 7-15x faster than Tesseract, much better accuracy
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


class FastPPOCRv5:
    """Optimized PP-OCRv5 with batch processing"""
    
    def __init__(self):
        """Initialize PP-OCRv5 (one-time cost)"""
        print("  Initializing PP-OCRv5...")
        start = time.time()
        
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            print("  ✗ ERROR: PaddleOCR not installed")
            print("  Install with: pip install paddleocr")
            return None
        
        # Initialize with optimizations (updated API)
        self.ocr = PaddleOCR(
            lang='en',                              # English language
            use_textline_orientation=False,         # No rotation detection
            text_det_thresh=0.3,                    # Detection threshold
            text_det_box_thresh=0.5,                # Box threshold
            text_recognition_batch_size=16,         # Batch size for recognition
        )
        
        init_time = time.time() - start
        print(f"  ✓ PP-OCRv5 initialized in {init_time:.2f}s")
        self.init_time = init_time
    
    def preprocess_cells(self, cells):
        """Minimal preprocessing for cells"""
        processed = []
        
        for cell in cells:
            # Ensure BGR format (PaddleOCR expects BGR)
            if len(cell.shape) == 2:
                cell = cv2.cvtColor(cell, cv2.COLOR_GRAY2BGR)
            elif cell.shape[2] == 4:  # BGRA
                cell = cv2.cvtColor(cell, cv2.COLOR_BGRA2BGR)
            
            processed.append(cell)
        
        return processed
    
    def is_cell_empty(self, cell_image: np.ndarray, threshold: float = 0.01) -> bool:
        """Quick check if cell is empty"""
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
    
    def ocr_batch(self, cells, batch_size=16, skip_empty=True):
        """
        OCR cells in batches with detection
        
        Args:
            cells: Dict {(row, col): cell_image}
            batch_size: Number of cells to process together
            skip_empty: Skip obviously empty cells
            
        Returns:
            Dict {(row, col): text}
        """
        # Preprocess all cells
        cell_items = list(cells.items())
        
        results = {}
        processed = 0
        skipped = 0
        
        print(f"  Processing {len(cell_items)} cells in batches of {batch_size}...")
        
        for i in range(0, len(cell_items), batch_size):
            batch_items = cell_items[i:i+batch_size]
            batch_images = []
            batch_keys = []
            
            # Prepare batch
            for (row, col), cell_img in batch_items:
                # Skip empty cells
                if skip_empty and self.is_cell_empty(cell_img):
                    results[(row, col)] = ""
                    skipped += 1
                    continue
                
                # Preprocess
                if len(cell_img.shape) == 2:
                    cell_img = cv2.cvtColor(cell_img, cv2.COLOR_GRAY2BGR)
                
                batch_images.append(cell_img)
                batch_keys.append((row, col))
            
            # OCR batch
            if batch_images:
                for j, cell_img in enumerate(batch_images):
                    key = batch_keys[j]
                    
                    try:
                        # Predict (includes detection + recognition)
                        result = self.ocr.predict(cell_img)
                        
                        # Extract text from all detected regions
                        if result and result[0] and 'rec_texts' in result[0]:
                            texts = result[0]['rec_texts']
                            combined = ' '.join(texts)
                            results[key] = combined
                        else:
                            results[key] = ""
                        
                        processed += 1
                        
                    except Exception as e:
                        print(f"    ⚠️  Error OCR cell {key}: {e}")
                        results[key] = ""
            
            # Progress indicator
            if (i // batch_size + 1) % 5 == 0:
                print(f"    Progress: {i + len(batch_items)}/{len(cell_items)} cells...")
        
        print(f"  ✓ Completed: {processed} cells OCR'd, {skipped} empty")
        
        return results
    
    def postprocess_text(self, text: str, col_idx: int) -> str:
        """Post-process OCR text (same as before)"""
        if not text:
            return text
        
        import re
        
        # Clean whitespace
        text = ' '.join(text.split())
        
        # Determine column type
        col_type = self._get_column_type(col_idx)
        
        # Numeric columns: fix common errors
        if col_type == 'numeric':
            text = text.replace('!', '1')
            text = text.replace('l', '1')
            text = text.replace('I', '1')
            text = text.replace('O', '0')
            text = re.sub(r'[^0-9,.\-\s]', '', text)
        
        # Mixed columns: selective fixing
        elif col_type == 'mixed':
            if 'RT' in text.upper() or 'RW' in text.upper():
                text = text.replace('!', '1')
        
        return text.strip()
    
    def _get_column_type(self, col_idx: int) -> str:
        """Determine column type for post-processing"""
        try:
            from src.models.table_schema import COLUMN_HEADERS
            
            if col_idx >= len(COLUMN_HEADERS):
                return 'text'
            
            col_name = COLUMN_HEADERS[col_idx].lower()
            
            if any(x in col_name for x in ['no', 'kk', 'rt', 'rw', 'bangunan', 'usaha']):
                return 'numeric'
            elif any(x in col_name for x in ['alamat', 'jam', 'telepon']):
                return 'mixed'
            
            return 'text'
        except:
            return 'text'


def test_paddleocr_fast():
    """Test Stage 5 with optimized PP-OCRv5"""
    
    print('='*60)
    print('STAGE 5: FAST PP-OCRv5 (Hybrid with Batch Processing)')
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
    
    # Step 3: Initialize PP-OCRv5
    print('\n[Step 3] Initializing Fast PP-OCRv5...')
    start = time.time()
    
    ocr_engine = FastPPOCRv5()
    if ocr_engine.ocr is None:
        return False
    
    # Step 4: Batch OCR
    print('\n[Step 4] Running batch OCR...')
    start = time.time()
    
    ocr_results = ocr_engine.ocr_batch(cells, batch_size=16, skip_empty=True)
    
    ocr_time = time.time() - start
    print(f'  ✓ OCR completed in {ocr_time:.2f}s')
    
    # Step 5: Post-processing
    print('\n[Step 5] Post-processing results...')
    start = time.time()
    
    for (row, col), text in ocr_results.items():
        ocr_results[(row, col)] = ocr_engine.postprocess_text(text, col)
    
    postprocess_time = time.time() - start
    print(f'  ✓ Post-processing completed in {postprocess_time:.2f}s')
    
    # Step 6: Analyze results
    print('\n[Step 6] Analyzing results...')
    
    empty_cells = sum(1 for v in ocr_results.values() if v == "")
    data_cells = len(ocr_results) - empty_cells
    
    print(f'  Total cells:   {len(ocr_results)}')
    print(f'  Empty cells:   {empty_cells}')
    print(f'  Data cells:    {data_cells}')
    
    # Step 7: Sample results
    print('\n[Step 7] Sample OCR results...')
    
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
                display_text = text[:50] + '...' if len(text) > 50 else text
                print(f'  Cell {pos}: "{display_text}"')
    
    # Step 8: Save results
    print('\n[Step 8] Saving results...')
    
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    import json
    
    # Convert to JSON
    json_results = {f"{row},{col}": text for (row, col), text in ocr_results.items()}
    
    json_path = results_dir / 'stage5_paddleocr_fast_results.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_results, f, indent=2, ensure_ascii=False)
    
    print(f'  ✓ Results saved: {json_path.name}')
    
    # Save statistics
    stats = {
        'total_cells': len(cells),
        'empty_cells': empty_cells,
        'data_cells': data_cells,
        'time': {
            'initialization': f'{ocr_engine.init_time:.2f}s',
            'extraction': f'{extract_time:.2f}s',
            'ocr': f'{ocr_time:.2f}s',
            'postprocess': f'{postprocess_time:.2f}s',
            'total': f'{time.time() - overall_start:.2f}s'
        },
        'method': 'PP-OCRv5 Hybrid (Detection + Batch)'
    }
    
    stats_path = results_dir / 'stage5_paddleocr_fast_statistics.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    
    print(f'  ✓ Statistics saved: {stats_path.name}')
    
    # Total time
    total_time = time.time() - overall_start
    
    print(f'\n' + '='*60)
    print('FAST PP-OCRv5 RESULTS')
    print('='*60)
    print(f'Total time: {total_time:.2f}s')
    print(f'  - Initialization: {ocr_engine.init_time:.2f}s (one-time)')
    print(f'  - Cell extraction: {extract_time:.2f}s')
    print(f'  - OCR:             {ocr_time:.2f}s')
    print(f'  - Post-processing: {postprocess_time:.2f}s')
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
    print('COMPARISON WITH PREVIOUS METHODS')
    print('='*60)
    print('Method                          | Time      | Accuracy (Est.)')
    print('-'*60)
    print(f'Tesseract (simple)              | ~73.54s   | 70-80%')
    print(f'PP-OCRv5 Hybrid (this test)     | {ocr_time:.2f}s     | 85-95% (expected)')
    print(f'Speedup:                        | {73.54/ocr_time:.1f}x faster')
    print('='*60)
    
    return True


if __name__ == '__main__':
    success = test_paddleocr_fast()
    sys.exit(0 if success else 1)
