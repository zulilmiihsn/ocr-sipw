"""
BLOK III Table Detection (Parallel Dual-Direction Scan)
"""

import cv2
import numpy as np
import os
from typing import Tuple, Optional
from concurrent.futures import ThreadPoolExecutor

# Control verbosity (set to False for production)
VERBOSE = os.getenv('OCR_VERBOSE', 'false').lower() == 'true'


def _scan_top_for_rekapitulasi(image, search_region_top, width, search_height_top, pytesseract):
    """Helper function to scan TOP region for 'Rekapitulasi' (runs in parallel)"""
    import time
    start = time.time()
    
    data_top = pytesseract.image_to_data(
        search_region_top,
        output_type=pytesseract.Output.DICT,
        lang='eng+ind',
        config='--psm 6'
    )
    
    elapsed = time.time() - start
    
    # Find "Rekapitulasi" marker
    candidates_top = []
    
    for i in range(len(data_top['text'])):
        text = data_top['text'][i].strip()
        conf = int(data_top['conf'][i])
        
        if conf < 30 or not text:
            continue
        
        text_upper = text.upper()
        
        # Score keywords for upper boundary
        score = 0
        if 'REKAPITULASI' in text_upper:
            score = 100  # Perfect match
        elif 'BLOK' in text_upper and 'III' in text_upper:
            score = 90  # Very good
        elif 'MUATAN' in text_upper:
            score = 80  # Good
        
        if score > 0:
            y_title = data_top['top'][i]
            h_title = data_top['height'][i]
            candidates_top.append({
                'text': text,
                'score': score,
                'conf': conf,
                'y': y_title,
                'h': h_title
            })
    
    if not candidates_top:
        return None, elapsed
    
    # Pick best candidate for upper boundary
    best_top = sorted(candidates_top, key=lambda x: (x['score'], x['conf']), reverse=True)[0]
    
    # Find table border below "Rekapitulasi"
    y_search_start = best_top['y'] + best_top['h']
    y_search_end = min(y_search_start + 100, search_height_top)
    search_strip = search_region_top[y_search_start:y_search_end, :]
    
    # Find first row with significant horizontal content (table border)
    blok3_y_start = y_search_start
    for row_offset in range(search_strip.shape[0]):
        row = search_strip[row_offset, :]
        dark_pixels = np.sum(row < 128)
        if dark_pixels > width * 0.3:
            blok3_y_start = max(y_search_start + row_offset - 10, 0)  # -10px margin (shift up, capped at 0)
            break
    
    return {
        'best': best_top,
        'y_start': blok3_y_start,
        'elapsed': elapsed
    }, elapsed


def _scan_bottom_for_keterangan(image, search_region_bottom, width, height, search_height_bottom, pytesseract):
    """Helper function to scan BOTTOM region for 'Keterangan' (runs in parallel)"""
    import time
    start = time.time()
    
    data_bottom = pytesseract.image_to_data(
        search_region_bottom,
        output_type=pytesseract.Output.DICT,
        lang='eng+ind',
        config='--psm 6'
    )
    
    elapsed = time.time() - start
    
    # Find "Keterangan" marker
    candidates_bottom = []
    
    for i in range(len(data_bottom['text'])):
        text = data_bottom['text'][i].strip()
        conf = int(data_bottom['conf'][i])
        
        if conf < 30 or not text:
            continue
        
        text_upper = text.upper()
        
        # Score keywords for lower boundary
        score = 0
        if 'KETERANGAN' in text_upper:
            score = 100  # Perfect match
        elif 'KET' in text_upper:
            score = 80  # Good
        
        if score > 0:
            # Adjust Y coordinate (relative to full image)
            y_relative = data_bottom['top'][i]
            y_absolute = (height - search_height_bottom) + y_relative
            h_title = data_bottom['height'][i]
            
            candidates_bottom.append({
                'text': text,
                'score': score,
                'conf': conf,
                'y': y_absolute,
                'h': h_title
            })
    
    # Determine lower boundary
    blok3_y_end = height  # Default: sampai bawah
    best_bottom = None
    
    if candidates_bottom:
        # Pick best candidate for lower boundary
        best_bottom = sorted(candidates_bottom, key=lambda x: (x['score'], x['conf']), reverse=True)[0]
        
        # Find table border above "Keterangan"
        y_search_bottom_start = max(best_bottom['y'] - 100, height - search_height_bottom)
        y_search_bottom_end = best_bottom['y']
        
        if y_search_bottom_end > y_search_bottom_start:
            search_strip_bottom = image[y_search_bottom_start:y_search_bottom_end, :]
            
            # Find last row with significant horizontal content (table border)
            # Scan from bottom to top
            for row_offset in range(search_strip_bottom.shape[0] - 1, -1, -1):
                row = search_strip_bottom[row_offset, :]
                dark_pixels = np.sum(row < 128)
                if dark_pixels > width * 0.3:
                    blok3_y_end = min(y_search_bottom_start + row_offset + 10, height)  # +10px margin (capped at image bottom)
                    break
        else:
            blok3_y_end = min(best_bottom['y'] + 10, height)  # +10px margin (capped at image bottom)
    
    return {
        'best': best_bottom,
        'y_end': blok3_y_end,
        'elapsed': elapsed
    }, elapsed


def _fallback_ratio_detection(image: np.ndarray, height: int, width: int) -> Optional[Tuple[int, int, int, int]]:
    """
    Fallback: Ratio-based BLOK III detection
    
    Uses fixed proportional positioning based on typical document layout.
    Robust for documents with consistent template but varying scales.
    
    Args:
        image: Full document image
        height: Image height
        width: Image width
        
    Returns:
        Tuple of (x, y, width, height) or None if invalid
    """
    if VERBOSE:
        print(f"  📐 RATIO-BASED DETECTION:")
        print(f"    Document size: {width}x{height}px")
    
    # BLOK III typically located at 19%-90% of document height
    # These ratios are measured from actual BPS form samples with ±3% safety margin
    # Measured from sample: Top=21.9%, Bottom=89.0% → Added ±3% margin
    TOP_RATIO = 0.19      # BLOK III starts at ~19% from top (measured)
    BOTTOM_RATIO = 0.90   # BLOK III ends at ~90% from top (measured)
    
    blok3_y_start = int(height * TOP_RATIO)
    blok3_y_end = int(height * BOTTOM_RATIO)
    blok3_height = blok3_y_end - blok3_y_start
    
    # Apply margins (same as keyword detection)
    blok3_y_start = max(blok3_y_start - 10, 0)           # -10px margin
    blok3_y_end = min(blok3_y_end + 10, height)          # +10px margin
    blok3_height = blok3_y_end - blok3_y_start
    
    # Validation: BLOK III should be at least 20% of document height
    min_height = int(height * 0.2)
    if blok3_height < min_height:
        if VERBOSE:
            print(f"  ✗ FALLBACK FAILED: Height too small ({blok3_height}px < {min_height}px)")
        return None
    
    if VERBOSE:
        print(f"    Top ratio: {TOP_RATIO*100:.0f}% → y={blok3_y_start}")
        print(f"    Bottom ratio: {BOTTOM_RATIO*100:.0f}% → y={blok3_y_end}")
        print(f"    BLOK III height: {blok3_height}px ({blok3_height/height*100:.1f}% of document)")
        print(f"  ✓ FALLBACK SUCCESS: Using ratio-based boundaries")
    
    return (0, blok3_y_start, width, blok3_height)


def detect_table_region(image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect BLOK III region using parallel dual-direction OCR scan
    
    Args:
        image: Full document image
        
    Returns:
        Tuple of (x, y, width, height) or None if not found
    """
    height, width = image.shape[:2]
    
    try:
        import pytesseract
        import os
        if os.name == 'nt':  # Windows
            tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(tesseract_path):
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
    except ImportError:
        return None
    
    import time
    
    # Prepare regions for parallel scanning
    search_height_top = int(height * 0.3)
    search_height_bottom = int(height * 0.3)
    search_region_top = image[:search_height_top, :]
    search_region_bottom = image[height - search_height_bottom:, :]
    
    if VERBOSE:
        print(f"🔍 PARALLEL Dual-direction OCR scan:")
        print(f"  ⚡ Scanning TOP 30% ({search_height_top}px) for 'Rekapitulasi' [PARALLEL]")
        print(f"  ⚡ Scanning BOTTOM 30% ({search_height_bottom}px) for 'Keterangan' [PARALLEL]")
    
    start_total = time.time()
    
    try:
        # PARALLEL EXECUTION: TOP + BOTTOM simultaneously!
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_top = executor.submit(
                _scan_top_for_rekapitulasi,
                image, search_region_top, width, search_height_top, pytesseract
            )
            future_bottom = executor.submit(
                _scan_bottom_for_keterangan,
                image, search_region_bottom, width, height, search_height_bottom, pytesseract
            )
            
            result_top, elapsed_top = future_top.result()
            result_bottom, elapsed_bottom = future_bottom.result()
        
        elapsed_total = time.time() - start_total
        
        # Process results with FALLBACK
        if result_top is None:
            if VERBOSE:
                print(f"  ✗ 'Rekapitulasi' not found in top 30%")
                print(f"  🔄 FALLBACK: Using ratio-based detection...")
            return _fallback_ratio_detection(image, height, width)
        
        best_top = result_top['best']
        blok3_y_start = result_top['y_start']
        
        if VERBOSE:
            print(f"  ✓ TOP: Found '{best_top['text']}' at y={best_top['y']} (score={best_top['score']}, conf={best_top['conf']}%) in {elapsed_top:.2f}s")
            print(f"    → Upper boundary: y={blok3_y_start}")
        
        best_bottom = result_bottom['best']
        blok3_y_end = result_bottom['y_end']
        
        if VERBOSE:
            if best_bottom:
                print(f"  ✓ BOTTOM: Found '{best_bottom['text']}' at y={best_bottom['y']} (score={best_bottom['score']}, conf={best_bottom['conf']}%) in {elapsed_bottom:.2f}s")
                print(f"    → Lower boundary: y={blok3_y_end}")
            else:
                print(f"  ⚠ BOTTOM: 'Keterangan' not found, using image bottom in {elapsed_bottom:.2f}s")
                print(f"    → Lower boundary: y={blok3_y_end} (image bottom)")
        
        blok3_height = blok3_y_end - blok3_y_start
        
        if VERBOSE:
            # Calculate speedup
            sequential_time = elapsed_top + elapsed_bottom
            speedup = sequential_time / elapsed_total if elapsed_total > 0 else 1.0
            
            print(f"\n  ⚡ PARALLEL PERFORMANCE:")
            print(f"    Sequential time: {sequential_time:.2f}s")
            print(f"    Parallel time:   {elapsed_total:.2f}s")
            print(f"    Speedup:         {speedup:.2f}x faster!")
            
            print(f"\n  ✓ BLOK III region: y={blok3_y_start} to y={blok3_y_end} (height={blok3_height}px)")
        
        return (0, blok3_y_start, width, blok3_height)
        
    except Exception as e:
        if VERBOSE:
            print(f"  ✗ OCR scan failed: {e}")
        return None


def crop_table(image: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
    """
    Crop table region from image
    
    Args:
        image: Full image
        bbox: Bounding box (x, y, width, height)
        
    Returns:
        Cropped image
    """
    x, y, w, h = bbox
    return image[y:y+h, x:x+w]
