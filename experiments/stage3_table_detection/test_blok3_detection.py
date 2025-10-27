"""
Test Stage 3: Ultra-Fast BLOK III Detection (OCR-Only)

Uses Tesseract OCR to find "BLOK III" text in top 30% of image,
then crops from that position to bottom. No heavy ML models needed!

Performance: ~6 seconds (8x faster than RapidTableDetection)
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.pdf_handler import load_image
from src.ocr.preprocessor import preprocess_image
from src.ocr.table_detector import detect_table_region, crop_table
import cv2


def test_stage3_ultrafast(image_path: str):
    """Test ultra-fast OCR-only BLOK III detection"""
    
    print('='*60)
    print('STAGE 3: ULTRA-FAST BLOK III DETECTION')
    print('='*60)
    
    overall_start = time.time()
    
    # Step 1: Load (NO preprocessing)
    print('\n[Step 1] Loading original image (no preprocessing)...')
    start = time.time()
    img = load_image(image_path)
    # Use original image without preprocessing
    processed = img
    preprocess_time = time.time() - start
    print(f'  ✓ Image: {processed.shape}')
    print(f'  ⏱ Time: {preprocess_time:.2f}s')
    
    # Step 2: Ultra-Fast OCR-Only Detection
    print('\n[Step 2] OCR-Only BLOK III Detection (Tesseract)...')
    start = time.time()
    bbox = detect_table_region(processed, use_rapid=False, rapid_detector=None)
    detect_time = time.time() - start
    
    if not bbox:
        print('  ✗ ERROR: BLOK III not detected')
        return False
    
    x, y, w, h = bbox
    print(f'  ✓ BLOK III bbox: ({x}, {y}, {w}, {h})')
    print(f'  ⏱ Time: {detect_time:.2f}s')
    
    # Step 3: Crop
    blok3_final = crop_table(processed, bbox)
    print(f'  ✓ Final size: {blok3_final.shape}')
    
    # Save outputs
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    output_path = results_dir / 'stage3_blok3_final.jpg'
    cv2.imwrite(str(output_path), blok3_final)
    print(f'  ✓ Saved: {output_path.name}')
    
    # Summary
    total_time = time.time() - overall_start
    
    print(f'\n' + '='*60)
    print('✅ STAGE 3 COMPLETED!')
    print('='*60)
    print(f'Total time: {total_time:.2f}s ⚡')
    print(f'  - Preprocessing: {preprocess_time:.2f}s')
    print(f'  - Detection:     {detect_time:.2f}s')
    print(f'\nOutput: {output_path.name} [{blok3_final.shape[1]}×{blok3_final.shape[0]}]')
    print('='*60)
    
    return True


if __name__ == '__main__':
    # Test with sample image
    image_path = 'contoh gambar/1.png'
    
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    
    success = test_stage3_ultrafast(image_path)
    sys.exit(0 if success else 1)

