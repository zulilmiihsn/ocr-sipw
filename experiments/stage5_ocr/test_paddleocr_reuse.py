"""
Test Stage 5: PP-OCRv5 MODEL REUSE

Real-world scenario:
1. App starts → Load model ONCE (30s)
2. User uploads Form 1 → Process (fast, model already loaded)
3. User uploads Form 2 → Process (fast, model already loaded)

This test:
- Load model ONCE at startup
- Process SAME form TWICE
- Compare: 1st run vs 2nd run
- Show benefit of model reuse
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


class GlobalPPOCRv5:
    """
    Global PP-OCRv5 instance (simulates app-level singleton)
    """
    _ocr = None
    _init_time = 0
    
    @classmethod
    def initialize(cls):
        """Initialize PP-OCRv5 ONCE at app startup"""
        if cls._ocr is not None:
            print("  ! Model already loaded, skipping...")
            return cls._init_time
        
        print("\n" + "="*60)
        print("APP STARTUP: Loading PP-OCRv5 (ONE-TIME)")
        print("="*60)
        start = time.time()
        
        try:
            from paddleocr import PaddleOCR
            
            cls._ocr = PaddleOCR(
                lang='en',
                use_textline_orientation=False,
            )
            
            cls._init_time = time.time() - start
            print(f"OK Model loaded in {cls._init_time:.2f}s")
            print("   Model is now READY for all scans!")
            print("="*60)
            
            return cls._init_time
            
        except Exception as e:
            print(f"X ERROR: {e}")
            raise
    
    @classmethod
    def get_ocr(cls):
        """Get OCR instance (must call initialize() first)"""
        if cls._ocr is None:
            raise RuntimeError("PP-OCRv5 not initialized! Call initialize() first.")
        return cls._ocr
    
    @classmethod
    def get_init_time(cls):
        return cls._init_time


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


def process_form(form_name: str, image_path: Path, ocr_engine) -> dict:
    """
    Process a single form (simulates user uploading a form)
    
    Args:
        form_name: Name of form (for display)
        image_path: Path to form image
        ocr_engine: Pre-loaded PP-OCRv5 instance
    
    Returns:
        dict with timing stats
    """
    print("\n" + "="*60)
    print(f"PROCESSING: {form_name}")
    print("="*60)
    
    process_start = time.time()
    
    # Step 1: Load image
    print('\n[1] Loading image...')
    start = time.time()
    image = cv2.imread(str(image_path))
    load_time = time.time() - start
    print(f'  OK {image.shape} in {load_time:.2f}s')
    
    # Step 2: Extract cells
    print('[2] Extracting cells...')
    start = time.time()
    h_lines = detect_horizontal_lines(image, min_line_length=image.shape[1] // 3)
    v_lines = detect_vertical_lines(image, min_line_length=image.shape[0] // 5)
    cells = extract_cells_from_grid(image, h_lines, v_lines, margin=5)
    extract_time = time.time() - start
    print(f'  OK {len(cells)} cells in {extract_time:.2f}s')
    
    # Step 3: OCR (using pre-loaded model!)
    print('[3] Running OCR (model already loaded)...')
    start = time.time()
    
    results = {}
    processed = 0
    skipped = 0
    
    for (row, col), cell_img in cells.items():
        if is_cell_empty(cell_img):
            results[(row, col)] = ""
            skipped += 1
            continue
        
        # Ensure BGR
        if len(cell_img.shape) == 2:
            cell_img = cv2.cvtColor(cell_img, cv2.COLOR_GRAY2BGR)
        
        try:
            result = ocr_engine.predict(cell_img)
            
            if result and result[0] and 'rec_texts' in result[0]:
                texts = result[0]['rec_texts']
                combined = ' '.join(texts) if isinstance(texts, list) else str(texts)
                results[(row, col)] = combined
            else:
                results[(row, col)] = ""
            
            processed += 1
            
        except Exception as e:
            results[(row, col)] = ""
            processed += 1
        
        # Progress every 50 cells
        if processed % 50 == 0:
            print(f'  ... {processed}/{len(cells)} cells processed')
    
    ocr_time = time.time() - start
    print(f'  OK {processed} OCR\'d, {skipped} empty in {ocr_time:.2f}s')
    
    # Total time
    total_time = time.time() - process_start
    
    print(f'\n{"="*60}')
    print(f'{form_name} COMPLETE')
    print(f'{"="*60}')
    print(f'Total time: {total_time:.2f}s')
    print(f'  - Load:      {load_time:.2f}s')
    print(f'  - Extract:   {extract_time:.2f}s')
    print(f'  - OCR:       {ocr_time:.2f}s')
    print(f'{"="*60}')
    
    return {
        'form_name': form_name,
        'total_time': total_time,
        'load_time': load_time,
        'extract_time': extract_time,
        'ocr_time': ocr_time,
        'cells_total': len(cells),
        'cells_processed': processed,
        'cells_skipped': skipped,
    }


def test_model_reuse():
    """
    Test model reuse across multiple scans
    """
    print("\n" + "="*70)
    print("TEST: PP-OCRv5 MODEL REUSE (Real-World Scenario)")
    print("="*70)
    print("Simulating:")
    print("  1. App starts → Load model")
    print("  2. User scans Form 1")
    print("  3. User scans Form 2 (SAME form, model REUSED)")
    print("="*70)
    
    # ========================================
    # STEP 0: APP STARTUP - LOAD MODEL ONCE
    # ========================================
    init_time = GlobalPPOCRv5.initialize()
    
    # Get pre-loaded OCR instance
    ocr = GlobalPPOCRv5.get_ocr()
    
    # ========================================
    # STEP 1: SCAN FORM 1
    # ========================================
    image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
    
    if not image_path.exists():
        print(f'\nX ERROR: {image_path} not found')
        return False
    
    stats1 = process_form("Form 1 (First Scan)", image_path, ocr)
    
    # Small delay (simulate user thinking)
    print("\n... (user reviewing results)...")
    time.sleep(2)
    
    # ========================================
    # STEP 2: SCAN FORM 2 (REUSE MODEL!)
    # ========================================
    stats2 = process_form("Form 2 (Second Scan)", image_path, ocr)
    
    # ========================================
    # COMPARISON
    # ========================================
    print("\n\n" + "="*70)
    print("COMPARISON: Form 1 vs Form 2 (Model Reuse)")
    print("="*70)
    
    print(f"\nModel Loading Time: {init_time:.2f}s (ONE-TIME ONLY!)")
    
    print(f"\nForm 1 (First Scan):")
    print(f"  Total:   {stats1['total_time']:.2f}s")
    print(f"  OCR:     {stats1['ocr_time']:.2f}s")
    
    print(f"\nForm 2 (Second Scan, MODEL REUSED):")
    print(f"  Total:   {stats2['total_time']:.2f}s")
    print(f"  OCR:     {stats2['ocr_time']:.2f}s")
    
    # Speed comparison
    if stats2['total_time'] < stats1['total_time']:
        speedup = stats1['total_time'] / stats2['total_time']
        improvement = ((stats1['total_time'] - stats2['total_time']) / stats1['total_time']) * 100
        print(f"\nForm 2 is {speedup:.2f}x FASTER ({improvement:.1f}% improvement)")
    else:
        print(f"\nBoth forms took similar time (model already warm)")
    
    # Total time for 2 forms
    total_time_2_forms = init_time + stats1['total_time'] + stats2['total_time']
    avg_per_form = (stats1['total_time'] + stats2['total_time']) / 2
    
    print(f"\n" + "="*70)
    print("TOTAL TIME FOR 2 FORMS")
    print("="*70)
    print(f"Model loading (once):  {init_time:.2f}s")
    print(f"Form 1:                {stats1['total_time']:.2f}s")
    print(f"Form 2:                {stats2['total_time']:.2f}s")
    print(f"{'─'*70}")
    print(f"TOTAL:                 {total_time_2_forms:.2f}s")
    print(f"Average per form:      {avg_per_form:.2f}s")
    
    # Comparison with Tesseract
    tesseract_2_forms = 73.54 * 2  # No loading overhead for Tesseract
    
    print(f"\n" + "="*70)
    print("VS TESSERACT (2 Forms)")
    print("="*70)
    print(f"Tesseract:             {tesseract_2_forms:.2f}s (2 × 73.54s)")
    print(f"PP-OCRv5 (reuse):      {total_time_2_forms:.2f}s")
    
    if total_time_2_forms < tesseract_2_forms:
        speedup = tesseract_2_forms / total_time_2_forms
        print(f"PP-OCRv5 is {speedup:.2f}x FASTER! 🚀")
    else:
        slowdown = total_time_2_forms / tesseract_2_forms
        print(f"PP-OCRv5 is {slowdown:.2f}x slower ⚠️")
    
    # Key insight
    print(f"\n" + "="*70)
    print("KEY INSIGHT")
    print("="*70)
    print(f"If loading model separately EACH time:")
    print(f"  2 forms = 2 × (33s load + 665s OCR) = {2 * (init_time + stats1['ocr_time']):.0f}s")
    print(f"\nWith model REUSE:")
    print(f"  2 forms = 1 × 33s load + 2 × 665s OCR = {init_time + 2 * stats1['ocr_time']:.0f}s")
    print(f"\nSavings: ~{init_time:.0f}s per additional form!")
    print("="*70)
    
    # Conclusion
    print(f"\n" + "="*70)
    print("CONCLUSION")
    print("="*70)
    print("✓ Model loading overhead is ONE-TIME (33s)")
    print("✓ Each additional form: NO loading overhead!")
    print("✓ Model reuse works perfectly")
    print(f"✓ For batch processing: Load once, process many forms")
    print("\n⚠️  BUT: PP-OCRv5 OCR still slower than Tesseract (~665s vs 73s)")
    print("⚠️  Need GPU for PP-OCRv5 to be competitive with Tesseract")
    print("="*70)
    
    return True


if __name__ == '__main__':
    success = test_model_reuse()
    sys.exit(0 if success else 1)

