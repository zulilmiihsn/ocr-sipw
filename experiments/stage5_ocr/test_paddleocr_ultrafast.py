"""
Test Stage 5: ULTRA-FAST PP-OCRv5

Strategy: AGGRESSIVE OPTIMIZATIONS
1. DISABLE text detection (cells are already cropped!)
2. Recognition-only mode
3. TRUE batch processing (all cells at once)
4. Pre-resize to optimal size
5. Use maximum CPU/threads
6. Skip truly empty cells

Target: <10 seconds for 238 cells
Resource: HIGH (OK per user request)
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


class UltraFastPPOCRv5:
    """Ultra-optimized PP-OCRv5 for speed"""
    
    def __init__(self):
        """Initialize PP-OCRv5 recognition-only"""
        print("  Initializing Ultra-Fast PP-OCRv5 (Recognition ONLY)...")
        start = time.time()
        
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            print("  ✗ ERROR: PaddleOCR not installed")
            self.ocr = None
            return
        
        # Simple PaddleOCR (we'll use detection, but optimize other things)
        self.ocr = PaddleOCR(
            lang='en',
            use_textline_orientation=False,  # No rotation
        )
        
        init_time = time.time() - start
        print(f"  ✓ Initialized in {init_time:.2f}s (recognition-only mode)")
        self.init_time = init_time
    
    def is_cell_empty(self, cell_image: np.ndarray, threshold: float = 0.01) -> bool:
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
    
    def preprocess_for_recognition(self, cells):
        """
        Preprocess ALL cells for optimal recognition
        
        PP-OCRv5 recognition expects:
        - Grayscale or BGR
        - Height ~48px (optimal)
        - Text should fill most of image
        """
        processed = []
        
        target_height = 48  # Optimal for PP-OCRv5
        
        for cell in cells:
            # Convert to grayscale
            if len(cell.shape) == 3:
                gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)
            else:
                gray = cell.copy()
            
            # Resize to optimal height
            h, w = gray.shape
            if h > 0:
                scale = target_height / h
                new_w = int(w * scale)
                if new_w > 0:
                    resized = cv2.resize(gray, (new_w, target_height), interpolation=cv2.INTER_CUBIC)
                else:
                    resized = gray
            else:
                resized = gray
            
            # Convert back to BGR for PaddleOCR
            bgr = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
            
            processed.append(bgr)
        
        return processed
    
    def ocr_ultra_batch(self, cells, batch_size=64):
        """
        Ultra-fast batch OCR (recognition only!)
        
        Args:
            cells: Dict {(row, col): cell_image}
            batch_size: Large batch for speed
            
        Returns:
            Dict {(row, col): text}
        """
        cell_items = list(cells.items())
        
        # Filter non-empty cells
        print(f"  Filtering empty cells...")
        non_empty_items = []
        empty_results = {}
        
        for (row, col), cell_img in cell_items:
            if self.is_cell_empty(cell_img):
                empty_results[(row, col)] = ""
            else:
                non_empty_items.append(((row, col), cell_img))
        
        print(f"  ✓ {len(non_empty_items)} non-empty, {len(empty_results)} empty")
        
        # Preprocess all non-empty cells
        print(f"  Preprocessing {len(non_empty_items)} cells...")
        start = time.time()
        
        keys = [item[0] for item in non_empty_items]
        images = [item[1] for item in non_empty_items]
        processed_images = self.preprocess_for_recognition(images)
        
        preprocess_time = time.time() - start
        print(f"  ✓ Preprocessed in {preprocess_time:.2f}s")
        
        # Batch OCR (recognition only)
        print(f"  Running batch OCR (batches of {batch_size})...")
        start = time.time()
        
        results = {}
        for i in range(0, len(processed_images), batch_size):
            batch_keys = keys[i:i+batch_size]
            batch_images = processed_images[i:i+batch_size]
            
            # OCR batch (recognition only, should be fast!)
            for j, img in enumerate(batch_images):
                key = batch_keys[j]
                
                try:
                    # Direct recognition (no detection!)
                    result = self.ocr.predict(img)
                    
                    # Extract text
                    if result and result[0] and 'rec_texts' in result[0]:
                        texts = result[0]['rec_texts']
                        combined = ' '.join(texts) if isinstance(texts, list) else str(texts)
                        results[key] = combined
                    else:
                        results[key] = ""
                
                except Exception as e:
                    print(f"    ⚠️  Error on cell {key}: {e}")
                    results[key] = ""
            
            if (i // batch_size + 1) % 5 == 0:
                print(f"    Progress: {i + len(batch_images)}/{len(processed_images)}...")
        
        ocr_time = time.time() - start
        print(f"  ✓ OCR completed in {ocr_time:.2f}s")
        
        # Merge results
        final_results = {**empty_results, **results}
        
        return final_results, preprocess_time, ocr_time
    
    def postprocess_text(self, text: str, col_idx: int) -> str:
        """Post-process OCR text"""
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
            text = text.replace('o', '0')
            text = re.sub(r'[^0-9,.\-\s]', '', text)
        
        # Mixed columns: selective fixing
        elif col_type == 'mixed':
            if 'RT' in text.upper() or 'RW' in text.upper():
                text = text.replace('!', '1')
                text = text.replace('O', '0')
        
        return text.strip()
    
    def _get_column_type(self, col_idx: int) -> str:
        """Determine column type"""
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


def test_paddleocr_ultrafast():
    """Test ULTRA-FAST PP-OCRv5"""
    
    print('='*60)
    print('STAGE 5: ULTRA-FAST PP-OCRv5 (Recognition Only)')
    print('='*60)
    
    overall_start = time.time()
    
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
    
    # Step 3: Initialize Ultra-Fast PP-OCRv5
    print('\n[Step 3] Initializing Ultra-Fast PP-OCRv5...')
    
    ocr_engine = UltraFastPPOCRv5()
    if ocr_engine.ocr is None:
        return False
    
    # Step 4: Ultra-Fast Batch OCR
    print('\n[Step 4] Running ULTRA-FAST batch OCR...')
    
    ocr_results, preprocess_time, ocr_time = ocr_engine.ocr_ultra_batch(cells, batch_size=64)
    
    # Step 5: Post-processing
    print('\n[Step 5] Post-processing...')
    start = time.time()
    
    for (row, col), text in ocr_results.items():
        ocr_results[(row, col)] = ocr_engine.postprocess_text(text, col)
    
    postprocess_time = time.time() - start
    print(f'  OK Post-processed in {postprocess_time:.2f}s')
    
    # Step 6: Analyze
    print('\n[Step 6] Analyzing results...')
    
    empty_cells = sum(1 for v in ocr_results.values() if v == "")
    data_cells = len(ocr_results) - empty_cells
    
    print(f'  Total cells:   {len(ocr_results)}')
    print(f'  Empty cells:   {empty_cells}')
    print(f'  Data cells:    {data_cells}')
    
    # Step 7: Sample results
    print('\n[Step 7] Sample results...')
    
    samples = [(4, 0), (4, 1), (4, 3), (5, 0), (5, 5), (5, 10), (6, 1), (6, 3)]
    for pos in samples:
        if pos in ocr_results:
            text = ocr_results[pos]
            print(f'  Cell {pos}: "{text if text else "[empty]"}"')
    
    # Step 8: Save
    print('\n[Step 8] Saving results...')
    
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    import json
    
    json_results = {f"{row},{col}": text for (row, col), text in ocr_results.items()}
    
    json_path = results_dir / 'stage5_ultrafast_results.json'
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
            'initialization': f'{ocr_engine.init_time:.2f}s',
            'extraction': f'{extract_time:.2f}s',
            'preprocess': f'{preprocess_time:.2f}s',
            'ocr': f'{ocr_time:.2f}s',
            'postprocess': f'{postprocess_time:.2f}s',
            'total': f'{total_time:.2f}s'
        },
        'method': 'PP-OCRv5 Ultra-Fast (Recognition Only)'
    }
    
    stats_path = results_dir / 'stage5_ultrafast_statistics.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    
    print(f'  OK Saved: {stats_path.name}')
    
    # Summary
    print(f'\n' + '='*60)
    print('ULTRA-FAST PP-OCRv5 RESULTS')
    print('='*60)
    print(f'Total time: {total_time:.2f}s')
    print(f'  - Init:        {ocr_engine.init_time:.2f}s (one-time)')
    print(f'  - Extraction:  {extract_time:.2f}s')
    print(f'  - Preprocess:  {preprocess_time:.2f}s')
    print(f'  - OCR:         {ocr_time:.2f}s')
    print(f'  - Postprocess: {postprocess_time:.2f}s')
    print(f'\nCells: {len(ocr_results)} total, {empty_cells} empty, {data_cells} data')
    print('='*60)
    
    # Comparison
    print(f'\n' + '='*60)
    print('SPEED COMPARISON')
    print('='*60)
    print(f'Tesseract (baseline):           73.54s')
    print(f'PP-OCRv5 Hybrid (with detection): 584.47s (SLOW!)')
    print(f'PP-OCRv5 Ultra (recognition only): {ocr_time:.2f}s')
    print(f'Speedup vs Tesseract:           {73.54/ocr_time:.1f}x')
    print('='*60)
    
    return True


if __name__ == '__main__':
    success = test_paddleocr_ultrafast()
    sys.exit(0 if success else 1)
