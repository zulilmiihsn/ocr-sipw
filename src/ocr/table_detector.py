"""
Deteksi posisi tabel BLOK III di form statistik
"""

import cv2
import numpy as np
from typing import Tuple, Optional
from .rapid_table_detector import RapidTableDetectorWrapper


def detect_blok3_with_ocr(
    image: np.ndarray
) -> Optional[Tuple[int, int, int, int]]:
    """
    FAST: Detect BLOK III region using Tesseract OCR only.
    Scans TOP 30% of image for "BLOK III" text.
    
    Args:
        image: Preprocessed full image
        
    Returns:
        Tuple of (x, y, width, height) bounding box for BLOK III region
        atau None jika tidak ditemukan
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
    
    # Search in TOP 30% only (BLOK III title always near top)
    search_height = int(height * 0.3)
    search_region = image[:search_height, :]
    
    print(f"🔍 Fast OCR scan for BLOK III in top 30% ({search_height}px)...")
    
    import time
    start = time.time()
    
    try:
        data = pytesseract.image_to_data(
            search_region,
            output_type=pytesseract.Output.DICT,
            lang='eng+ind',
            config='--psm 6'
        )
        
        elapsed = time.time() - start
        
        # Find BLOK III marker - look for best match (highest confidence + most complete)
        candidates = []
        
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            conf = int(data['conf'][i])
            
            if conf < 30 or not text:
                continue
            
            text_upper = text.upper()
            
            # Score keywords (higher = better match)
            score = 0
            if 'BLOK' in text_upper and 'III' in text_upper:
                score = 100  # Perfect match
            elif 'REKAPITULASI' in text_upper:
                score = 90  # Very good
            elif 'MUATAN' in text_upper:
                score = 80  # Good
            elif 'BLOK' in text_upper or 'III' in text_upper:
                score = 50  # Partial
            
            if score > 0:
                y_title = data['top'][i]
                h_title = data['height'][i]
                candidates.append({
                    'text': text,
                    'score': score,
                    'conf': conf,
                    'y': y_title,
                    'h': h_title
                })
        
        if not candidates:
            print(f"  ✗ BLOK III not found in top 30%")
            return None
        
        # Pick best candidate (highest score, then highest confidence)
        best = sorted(candidates, key=lambda x: (x['score'], x['conf']), reverse=True)[0]
        
        # Find table border below title
        # Strategy: Look for horizontal line (many dark pixels in a row)
        y_search_start = best['y'] + best['h']
        y_search_end = min(y_search_start + 100, search_height)
        search_strip = search_region[y_search_start:y_search_end, :]
        
        # Find first row with significant horizontal content (table border)
        blok3_y_start = y_search_start
        for row_offset in range(search_strip.shape[0]):
            row = search_strip[row_offset, :]
            dark_pixels = np.sum(row < 128)  # Count dark pixels
            if dark_pixels > width * 0.3:  # At least 30% of width is dark (line)
                blok3_y_start = y_search_start + row_offset
                break
        
        blok3_height = height - blok3_y_start
        
        print(f"  ✓ Found '{best['text']}' at y={best['y']} (score={best['score']}, conf={best['conf']}%) in {elapsed:.2f}s")
        print(f"  → Table border detected at y={blok3_y_start}")
        print(f"  → BLOK III region: y={blok3_y_start} to {height}")
        
        # Return bounding box for BLOK III region
        return (0, blok3_y_start, width, blok3_height)
        return None
        
    except Exception as e:
        print(f"  ✗ OCR scan failed: {e}")
        return None


def detect_table_region(
    image: np.ndarray, 
    use_rapid: bool = False,
    rapid_detector: RapidTableDetectorWrapper = None,
    blok3_bbox: Optional[Tuple[int, int, int, int]] = None
) -> Optional[Tuple[int, int, int, int]]:
    """
    Deteksi region tabel BLOK III.
    
    ULTRA-FAST MODE (default): Uses OCR-only detection (no RapidTable).
    Simply finds "BLOK III" text and crops from there to bottom.
    
    Args:
        image: Preprocessed image
        use_rapid: If True, use RapidTableDetection for refinement (slower)
        rapid_detector: RapidTableDetector instance (optional, for refinement)
        blok3_bbox: Pre-detected BLOK III bbox dari OCR (optional)
        
    Returns:
        Tuple of (x, y, width, height) bounding box tabel
        atau None jika tidak ditemukan
    """
    # FAST PATH: Use OCR-only detection (RECOMMENDED)
    if not use_rapid:
        if blok3_bbox:
            print(f"✓ Using OCR-detected BLOK III region (ultra-fast)")
            return blok3_bbox
        else:
            # Detect using OCR
            bbox = detect_blok3_with_ocr(image)
            if bbox:
                return bbox
            raise ValueError("BLOK III not detected with OCR.")
    
    # SLOW PATH: Use RapidTable for refinement (optional)
    if not rapid_detector:
        raise ValueError("RapidTableDetection required but not provided.")
    
    # OPTIMIZATION: If we already know BLOK III region from OCR, use it
    if blok3_bbox:
        x_b3, y_b3, w_b3, h_b3 = blok3_bbox
        search_region = image[y_b3:y_b3+h_b3, x_b3:x_b3+w_b3]
        print(f"🎯 RapidTable detecting in pre-scanned BLOK III region [{w_b3}×{h_b3}]...")
    else:
        search_region = image
        print(f"🎯 RapidTable detecting in full image...")
        x_b3, y_b3 = 0, 0
    
    result = rapid_detector.detect_and_crop_table(search_region, return_perspective_corrected=False)
    
    if result:
        metadata = result[1]
        box = metadata.get('box')
        if box is not None:
            xmin, ymin, xmax, ymax = box
            
            # Adjust coordinates if we searched in sub-region
            xmin += x_b3
            ymin += y_b3
            xmax += x_b3
            ymax += y_b3
            
            return (int(xmin), int(ymin), int(xmax-xmin), int(ymax-ymin))
    
    if rapid_detector.is_available():
        raise ValueError("RapidTableDetection available tapi gagal detect table. Periksa image quality.")
    
    raise ValueError("Table detection failed.")


def detect_table_by_lines(gray: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect table using horizontal and vertical lines
    """
    # Detect horizontal lines
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    detected_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    
    # Detect vertical lines
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    detected_lines_vert = cv2.morphologyEx(gray, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
    
    # Combine
    table_mask = detected_lines + detected_lines_vert
    
    # Find contours
    contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if len(contours) == 0:
        return None
    
    # Get largest contour
    largest_contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest_contour)
    
    # Filter by size (should be reasonably large)
    if w < 100 or h < 100:
        return None
    
    return (x, y, w, h)


def detect_table_by_contours(gray: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect table using contours
    """
    # Apply threshold
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    if len(contours) == 0:
        return None
    
    # Look for large rectangular contours
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        # Approximate contour to polygon
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        
        # If it has 4 corners, might be a table region
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Check if reasonably large
            height, width = gray.shape
            if w > width * 0.3 and h > height * 0.2:
                return (x, y, w, h)
    
    return None


def detect_table_by_text(gray: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect table by looking for "BLOK III" text
    Note: This is a simplified implementation. For production,
    use OCR engine like Tesseract to detect the text
    """
    # This is a placeholder - in production, use OCR to find "BLOK III"
    # For now, return None to use line-based detection
    return None


def find_blok3_in_table_old(table_image: np.ndarray) -> np.ndarray:
    """
    Find and extract BLOK III REKAPITULASI MUATAN from full table
    
    Uses TESSERACT OCR (lightweight, fast) for text detection.
    NO FALLBACK - will raise error if detection fails.
    
    Args:
        table_image: Full table image (might contain BLOK I, II, III, etc)
        
    Returns:
        BLOK III only image
        
    Raises:
        ValueError: If BLOK III cannot be detected
        ImportError: If Tesseract not installed
    """
    height, width = table_image.shape[:2]
    
    try:
        import pytesseract
        # Set Tesseract path for Windows
        import os
        if os.name == 'nt':  # Windows
            tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(tesseract_path):
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
    except ImportError:
        raise ImportError("Tesseract OCR required. Install: pip install pytesseract")
    
    # Search in top 70% of table for "BLOK III" title
    search_height = int(height * 0.7)
    search_region = table_image[:search_height, :]
    
    print(f"🔍 Scanning for BLOK III text with Tesseract ({height}x{width})...")
    
    # Use Tesseract to get text with bounding boxes
    # This is MUCH faster than PaddleOCR (2-5s vs 200s)
    import time
    start = time.time()
    
    try:
        # Get detailed data including positions
        data = pytesseract.image_to_data(
            search_region,
            output_type=pytesseract.Output.DICT,
            lang='eng+ind',  # English + Indonesian
            config='--psm 6'  # Assume uniform block of text
        )
        
        elapsed = time.time() - start
        print(f"  ⚡ Tesseract scan completed in {elapsed:.2f}s")
        
        # Find BLOK III marker
        blok3_start = None
        n_boxes = len(data['text'])
        
        print(f"  📄 Found {n_boxes} text regions, searching...")
        
        for i in range(n_boxes):
            text = data['text'][i].strip()
            conf = int(data['conf'][i])
            
            # Skip low confidence or empty
            if conf < 30 or not text:
                continue
            
            text_upper = text.upper()
            
            # Check for BLOK III markers
            if any(keyword in text_upper for keyword in ['BLOK', 'III', 'REKAPITULASI', 'MUATAN']):
                y = data['top'][i]
                h = data['height'][i]
                
                # FOUND! Stop immediately
                blok3_start = y + h + 30  # Start below the title
                print(f"  ✓ BLOK III marker found: '{text}' (conf: {conf}%)")
                print(f"    Position: y={y}")
                print(f"    Content starts at y={blok3_start}")
                break
        
        # NO FALLBACK - must detect
        if blok3_start is None:
            raise ValueError(
                f"Failed to detect BLOK III marker in table.\n"
                f"Searched {n_boxes} text regions.\n"
                f"Please check:\n"
                f"1. Does the table contain 'BLOK III' or 'REKAPITULASI' text?\n"
                f"2. Is the image quality sufficient?\n"
                f"3. Is Tesseract installed correctly?"
            )
        
        # Extract BLOK III
        blok3_image = table_image[blok3_start:, :]
        
        print(f"✓ BLOK III extracted: {blok3_image.shape}")
        print(f"  Reduction: {(1 - blok3_image.shape[0]/height)*100:.1f}% of table removed")
        
        return blok3_image
        
    except pytesseract.TesseractNotFoundError:
        raise ImportError(
            "Tesseract executable not found!\n"
            "Please install Tesseract OCR:\n"
            "- Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki\n"
            "- Linux: sudo apt-get install tesseract-ocr\n"
            "- Mac: brew install tesseract"
        )


def crop_table(image: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
    """
    Crop image to table region
    
    Args:
        image: Full image
        bbox: Bounding box (x, y, width, height)
        
    Returns:
        Cropped table image
    """
    x, y, w, h = bbox
    cropped = image[y:y+h, x:x+w]
    return cropped
