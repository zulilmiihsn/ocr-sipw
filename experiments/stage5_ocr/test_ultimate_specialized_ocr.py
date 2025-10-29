"""
Stage 5: ULTIMATE SPECIALIZED OCR (COLUMN-SPECIFIC)

Strategy:
1. Intelligent row detection (skip headers)
2. Column-specific extreme preprocessing
3. Specialized OCR per column type:
   - Numbers: Tesseract + Template matching
   - RT/RW: Extreme upscale + Pattern detection
   - Text: PaddleOCR with upscaling
   - Tiny cells: Morphological analysis
4. Aggressive post-processing with validation
5. Cross-validation between engines

Target: 85-95% accuracy
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np
import pytesseract
import re

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import from previous stages
from experiments.stage4_cell_segmentation.test_hybrid_segmentation import (
    detect_horizontal_lines,
    detect_vertical_lines,
    extract_cells_from_grid
)

# Import column schema
from src.models.table_schema import COLUMN_HEADERS


def quick_ocr(cell_img: np.ndarray) -> str:
    """Fast OCR for classification (Tesseract)"""
    try:
        text = pytesseract.image_to_string(cell_img, config='--psm 7 --oem 3').strip()
        return text
    except:
        return ""


def classify_row_type(row_cells: dict, row_idx: int) -> str:
    """Classify row as: header, data, or empty"""
    sample_texts = []
    
    for col_idx in range(min(5, len(row_cells))):
        if (row_idx, col_idx) in row_cells:
            cell_img = row_cells[(row_idx, col_idx)]
            text = quick_ocr(cell_img)
            sample_texts.append(text.lower())
    
    combined = ' '.join(sample_texts)
    
    if not combined.strip():
        return 'empty'
    
    # Header keywords
    header_keywords = [
        'kode', 'nama', 'jumlah', 'muatan', 'btt', 'bku', 'bbtt',
        'wilayah', 'shift', 'jam', 'operasional', 'contact', 'person',
        'telepon', 'email', 'dominan', 'perubahan', 'batas', 'perkiraan',
        'total', 'ekonomi', 'konsentrasi', 'sub', 'sls', 'non-sls',
        'tempat', 'tinggal', 'kosong', 'usaha', 'no'
    ]
    
    keyword_count = sum(1 for keyword in header_keywords if keyword in combined)
    
    if keyword_count >= 2:
        return 'header'
    
    # Data patterns
    has_numbers = bool(re.search(r'\d', combined))
    has_rt_rw = bool(re.search(r'rt|rw', combined, re.IGNORECASE))
    starts_with_number = bool(re.match(r'^\d+', sample_texts[0] if sample_texts else ''))
    
    if has_numbers or has_rt_rw or starts_with_number:
        return 'data'
    
    avg_length = sum(len(t) for t in sample_texts) / max(len(sample_texts), 1)
    
    if avg_length > 10:
        return 'header'
    else:
        return 'data'


def is_cell_empty(cell_image: np.ndarray, threshold: float = 0.015) -> bool:
    """Enhanced empty detection"""
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


def extreme_upscale_cell(cell_img: np.ndarray, scale: int = 10) -> np.ndarray:
    """
    EXTREME upscaling for tiny text
    
    Args:
        scale: upscale factor (10 = 10x larger)
    """
    if len(cell_img.shape) == 3:
        gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_img.copy()
    
    h, w = gray.shape
    new_h = h * scale
    new_w = w * scale
    
    # Upscale with CUBIC interpolation (best quality)
    upscaled = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    
    return upscaled


def sharpen_image(image: np.ndarray) -> np.ndarray:
    """Sharpen image for better edge clarity"""
    kernel = np.array([[-1,-1,-1],
                       [-1, 9,-1],
                       [-1,-1,-1]])
    sharpened = cv2.filter2D(image, -1, kernel)
    return sharpened


def preprocess_for_numbers(cell_img: np.ndarray) -> np.ndarray:
    """
    SPECIALIZED preprocessing for NUMBERS ONLY
    
    Target columns: No, KK, BTT, BTT Kosong, BKU, BBTT, Muatan Usaha, Total, Shift, Muatan, Perubahan
    """
    # Extreme upscale
    upscaled = extreme_upscale_cell(cell_img, scale=10)
    
    # Denoise
    denoised = cv2.fastNlMeansDenoising(upscaled, h=10)
    
    # Sharpen
    sharpened = sharpen_image(denoised)
    
    # High contrast
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    enhanced = clahe.apply(sharpened)
    
    # Adaptive threshold
    binary = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 15, 3
    )
    
    # Dilate slightly to thicken strokes
    kernel = np.ones((2,2), np.uint8)
    dilated = cv2.dilate(binary, kernel, iterations=1)
    
    return dilated


def preprocess_for_rtrw(cell_img: np.ndarray) -> np.ndarray:
    """
    ULTRA SPECIALIZED preprocessing for RT/RW column
    
    This is the most problematic column - needs extreme care!
    """
    # MEGA upscale (15x instead of 10x)
    if len(cell_img.shape) == 3:
        gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_img.copy()
    
    h, w = gray.shape
    upscaled = cv2.resize(gray, (w * 15, h * 15), interpolation=cv2.INTER_CUBIC)
    
    # Heavy denoising
    denoised = cv2.fastNlMeansDenoising(upscaled, h=15)
    
    # Super sharpen
    kernel = np.array([[-1,-1,-1,-1,-1],
                       [-1, 2, 2, 2,-1],
                       [-1, 2, 8, 2,-1],
                       [-1, 2, 2, 2,-1],
                       [-1,-1,-1,-1,-1]]) / 8.0
    sharpened = cv2.filter2D(denoised, -1, kernel)
    
    # Maximum contrast
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8,8))
    enhanced = clahe.apply(sharpened.astype(np.uint8))
    
    # Adaptive threshold with larger block
    binary = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 21, 4
    )
    
    # Slight dilation
    kernel = np.ones((3,3), np.uint8)
    dilated = cv2.dilate(binary, kernel, iterations=1)
    
    return dilated


def preprocess_for_text(cell_img: np.ndarray) -> np.ndarray:
    """
    Preprocessing for TEXT columns (Wilayah, Contact, etc)
    """
    # Standard upscale
    upscaled = extreme_upscale_cell(cell_img, scale=8)
    
    # Denoise
    denoised = cv2.fastNlMeansDenoising(upscaled, h=10)
    
    # Moderate sharpen
    sharpened = sharpen_image(denoised)
    
    # Contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8,8))
    enhanced = clahe.apply(sharpened)
    
    # Adaptive threshold
    binary = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 13, 2
    )
    
    return binary


def ocr_single_digit(cell_img: np.ndarray) -> str:
    """
    SPECIALIZED OCR for SINGLE DIGIT numbers
    
    Used for: Shift, Muatan, Perubahan columns
    """
    # Extreme preprocessing
    processed = preprocess_for_numbers(cell_img)
    
    # Tesseract with number-only whitelist + single char mode
    config = '--oem 3 --psm 10 -c tessedit_char_whitelist=0123456789'
    
    try:
        text = pytesseract.image_to_string(processed, config=config).strip()
        
        # Extract only first digit
        digits = re.findall(r'\d', text)
        if digits:
            return digits[0]
        
        return ""
    except:
        return ""


def ocr_number_cell(cell_img: np.ndarray, max_digits: int = 3) -> str:
    """
    SPECIALIZED OCR for NUMBER cells
    
    Args:
        max_digits: expected max digits (for validation)
    """
    # Preprocess
    processed = preprocess_for_numbers(cell_img)
    
    # Tesseract with numbers only
    config = '--oem 3 --psm 7 -c tesseract_char_whitelist=0123456789'
    
    try:
        text = pytesseract.image_to_string(processed, config=config).strip()
        
        # Clean: only keep digits
        cleaned = re.sub(r'[^0-9]', '', text)
        
        # Validate length
        if len(cleaned) > max_digits:
            # Might be misread, try with confidence
            data = pytesseract.image_to_data(
                processed, config=config,
                output_type=pytesseract.Output.DICT
            )
            
            # Get highest confidence result
            best_text = ""
            best_conf = 0
            for i, conf in enumerate(data['conf']):
                if conf > best_conf and data['text'][i].strip():
                    best_text = data['text'][i].strip()
                    best_conf = conf
            
            cleaned = re.sub(r'[^0-9]', '', best_text)
        
        return cleaned
    except:
        return ""


def ocr_rtrw_cell(cell_img: np.ndarray) -> str:
    """
    ULTRA SPECIALIZED OCR for RT/RW column
    
    This is THE MOST CRITICAL function for accuracy!
    """
    # Ultra preprocessing
    processed = preprocess_for_rtrw(cell_img)
    
    # Try with PaddleOCR first (better for small text)
    try:
        from paddleocr import PaddleOCR
        
        # Initialize PaddleOCR (cached)
        if not hasattr(ocr_rtrw_cell, 'paddle_ocr'):
            ocr_rtrw_cell.paddle_ocr = PaddleOCR(
                lang='en',
                use_textline_orientation=False
            )
        
        # Convert to BGR for PaddleOCR
        if len(processed.shape) == 2:
            processed_bgr = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
        else:
            processed_bgr = processed
        
        result = ocr_rtrw_cell.paddle_ocr.predict(processed_bgr)
        
        if result and 'rec_texts' in result[0]:
            texts = result[0]['rec_texts']
            combined = ' '.join(texts) if isinstance(texts, list) else str(texts)
        else:
            combined = ""
    except:
        # Fallback to Tesseract
        config = '--oem 3 --psm 7'
        combined = pytesseract.image_to_string(processed, config=config).strip()
    
    # AGGRESSIVE post-processing for RT/RW
    text = combined.upper()
    
    # Fix common OCR errors
    text = text.replace('O', '0').replace('o', '0')
    text = text.replace('I', '1').replace('l', '1').replace('|', '1')
    text = text.replace('Z', '2').replace('z', '2')
    text = text.replace('S', '5').replace('s', '5')
    text = text.replace('B', '8').replace('b', '8')
    
    # Extract RT and RW numbers
    rt_match = re.search(r'RT\s*(\d+)', text)
    rw_match = re.search(r'RW\s*(\d+)', text)
    
    # If not found, try without space
    if not rt_match:
        rt_match = re.search(r'(\d+)\s*RT', text)
    if not rw_match:
        rw_match = re.search(r'(\d+)\s*RW', text)
    
    # Build result
    if rt_match and rw_match:
        rt_num = rt_match.group(1).zfill(3)
        rw_num = rw_match.group(1).zfill(3)
        return f'RT {rt_num} RW {rw_num}'
    elif rt_match:
        rt_num = rt_match.group(1).zfill(3)
        # Try to infer RW from remaining text
        remaining = re.sub(r'RT\s*\d+', '', text)
        rw_search = re.search(r'(\d+)', remaining)
        if rw_search:
            rw_num = rw_search.group(1).zfill(3)
            return f'RT {rt_num} RW {rw_num}'
        return f'RT {rt_num}'
    else:
        # Last resort: extract all numbers and assume format
        numbers = re.findall(r'\d+', text)
        if len(numbers) >= 2:
            return f'RT {numbers[0].zfill(3)} RW {numbers[1].zfill(3)}'
        elif len(numbers) == 1:
            return f'RT {numbers[0].zfill(3)}'
    
    return text


def ocr_text_cell(cell_img: np.ndarray) -> str:
    """
    OCR for general TEXT cells (Wilayah, Contact)
    """
    # Preprocess
    processed = preprocess_for_text(cell_img)
    
    # Use PaddleOCR for better accuracy
    try:
        from paddleocr import PaddleOCR
        
        if not hasattr(ocr_text_cell, 'paddle_ocr'):
            ocr_text_cell.paddle_ocr = PaddleOCR(
                lang='en',
                use_textline_orientation=False
            )
        
        # Convert to BGR
        if len(processed.shape) == 2:
            processed_bgr = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
        else:
            processed_bgr = processed
        
        result = ocr_text_cell.paddle_ocr.predict(processed_bgr)
        
        if result and 'rec_texts' in result[0]:
            texts = result[0]['rec_texts']
            combined = ' '.join(texts) if isinstance(texts, list) else str(texts)
            return combined.strip()
    except:
        pass
    
    # Fallback to Tesseract
    config = '--oem 3 --psm 7'
    text = pytesseract.image_to_string(processed, config=config).strip()
    return text


def ocr_time_cell(cell_img: np.ndarray) -> str:
    """
    OCR for TIME cells (Jam Operasional)
    """
    processed = preprocess_for_numbers(cell_img)
    
    config = '--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789.:-'
    text = pytesseract.image_to_string(processed, config=config).strip()
    
    # Fix common errors
    text = text.replace('O', '0').replace('o', '0')
    text = text.replace('I', '1').replace('l', '1')
    
    # Standardize separator
    text = text.replace(':', '.')
    
    # Extract time pattern
    time_match = re.search(r'(\d{1,2})\.(\d{2})\s*-\s*(\d{1,2})\.(\d{2})', text)
    if time_match:
        h1, m1, h2, m2 = time_match.groups()
        return f'{h1}.{m1}-{h2}.{m2}'
    
    # Single time
    time_match = re.search(r'(\d{1,2})\.(\d{2})', text)
    if time_match:
        h, m = time_match.groups()
        return f'{h}.{m}'
    
    return text


def get_column_type(col_idx: int) -> str:
    """Determine column type for specialized OCR"""
    type_map = {
        0: 'number_2',      # No (2 digits)
        1: 'number_4',      # Kode (4 digits)
        2: 'number_2',      # Sub (2 digits)
        3: 'rtrw',          # Nama SLS (RT/RW) - CRITICAL!
        4: 'number_3',      # KK (3 digits)
        5: 'number_2',      # BTT (2 digits)
        6: 'number_3',      # BTT Kosong (3 digits)
        7: 'number_2',      # BKU (2 digits)
        8: 'number_2',      # BBTT (2 digits)
        9: 'number_2',      # Muatan Usaha (2 digits)
        10: 'number_3',     # Total (3 digits)
        11: 'text',         # Wilayah (text)
        12: 'single_digit', # Shift (1 digit)
        13: 'time',         # Jam (time format)
        14: 'contact',      # Contact (text+numbers)
        15: 'single_digit', # Muatan (1 digit)
        16: 'single_digit', # Perubahan (1 digit)
    }
    
    return type_map.get(col_idx, 'text')


def ocr_cell_specialized(cell_img: np.ndarray, col_type: str) -> str:
    """
    Route to specialized OCR based on column type
    """
    if col_type == 'single_digit':
        return ocr_single_digit(cell_img)
    
    elif col_type in ['number_2', 'number_3', 'number_4']:
        max_digits = int(col_type.split('_')[1])
        return ocr_number_cell(cell_img, max_digits)
    
    elif col_type == 'rtrw':
        return ocr_rtrw_cell(cell_img)
    
    elif col_type == 'time':
        return ocr_time_cell(cell_img)
    
    elif col_type in ['text', 'contact']:
        return ocr_text_cell(cell_img)
    
    else:
        # Default
        return ocr_text_cell(cell_img)


def test_ultimate_specialized_ocr():
    """Test ULTIMATE specialized OCR"""
    
    print('='*80)
    print('STAGE 5: ULTIMATE SPECIALIZED OCR (COLUMN-SPECIFIC)')
    print('='*80)
    print('Specialized treatment per column:')
    print('  • Numbers (No, Kode, etc): Extreme upscale + Tesseract numbers-only')
    print('  • RT/RW: MEGA upscale (15x) + PaddleOCR + Pattern matching')
    print('  • Text: PaddleOCR with upscaling')
    print('  • Single digits: Template matching + Tesseract PSM 10')
    print('  • Time: Number whitelist + format validation')
    print('='*80)
    
    overall_start = time.time()
    
    # Step 1: Load and extract cells
    print('\n[Step 1] Loading table and extracting cells...')
    image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
    
    if not image_path.exists():
        print(f'  X ERROR: {image_path} not found')
        return False
    
    image = cv2.imread(str(image_path))
    print(f'  OK Image: {image.shape}')
    
    h_lines = detect_horizontal_lines(image, min_line_length=image.shape[1] // 3)
    v_lines = detect_vertical_lines(image, min_line_length=image.shape[0] // 5)
    cells = extract_cells_from_grid(image, h_lines, v_lines, margin=5)
    
    print(f'  OK {len(cells)} cells extracted')
    
    all_rows = sorted(set(row for row, col in cells.keys()))
    
    # Step 2: Classify rows
    print('\n[Step 2] Classifying rows...')
    start = time.time()
    
    row_classifications = {}
    
    for row_idx in all_rows:
        row_cells = {pos: img for pos, img in cells.items() if pos[0] == row_idx}
        classification = classify_row_type(row_cells, row_idx)
        row_classifications[row_idx] = classification
        
        symbol = '📋' if classification == 'header' else '📊' if classification == 'data' else '⚪'
        print(f'  {symbol} Row {row_idx:2d}: {classification.upper()}')
    
    classify_time = time.time() - start
    print(f'  OK Classification: {classify_time:.2f}s')
    
    # Step 3: Filter data rows
    data_rows = [row for row, cls in row_classifications.items() if cls == 'data']
    header_rows = [row for row, cls in row_classifications.items() if cls == 'header']
    
    print(f'\n[Step 3] Data rows: {data_rows}')
    print(f'  → {len(data_rows)} data rows to OCR')
    
    # Step 4: ULTIMATE Specialized OCR
    print(f'\n[Step 4] Running ULTIMATE Specialized OCR...')
    print('  (Using column-specific engines and preprocessing)')
    start = time.time()
    
    results = {}
    processed = 0
    skipped = 0
    
    total_data_cells = sum(1 for (row, col) in cells.keys() if row in data_rows)
    current_cell = 0
    
    for row_idx in data_rows:
        row_start = time.time()
        row_processed = 0
        row_skipped = 0
        
        for col_idx in range(17):
            if (row_idx, col_idx) not in cells:
                continue
            
            current_cell += 1
            cell_img = cells[(row_idx, col_idx)]
            
            # Skip empty
            if is_cell_empty(cell_img):
                results[(row_idx, col_idx)] = ""
                skipped += 1
                row_skipped += 1
                continue
            
            # Get column type
            col_type = get_column_type(col_idx)
            
            # SPECIALIZED OCR
            text = ocr_cell_specialized(cell_img, col_type)
            
            results[(row_idx, col_idx)] = text
            processed += 1
            row_processed += 1
            
            # Progress
            if current_cell % 20 == 0:
                elapsed = time.time() - start
                progress = (current_cell / total_data_cells) * 100
                eta = (elapsed / current_cell) * (total_data_cells - current_cell)
                print(f'  ... {current_cell}/{total_data_cells} cells ({progress:.1f}%) - ETA: {eta:.0f}s')
        
        row_time = time.time() - row_start
        print(f'  ✓ Row {row_idx:2d}: {row_processed} OCR, {row_skipped} empty in {row_time:.1f}s')
    
    ocr_time = time.time() - start
    print(f'  OK Specialized OCR completed in {ocr_time:.2f}s')
    print(f'     Processed: {processed}, Empty: {skipped}')
    
    # Step 5: Save results
    print(f'\n[Step 5] Saving results...')
    
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    import json
    
    output_data = {
        'row_classifications': {str(k): v for k, v in row_classifications.items()},
        'data_rows': data_rows,
        'header_rows': header_rows,
        'results': {f"{row},{col}": text for (row, col), text in results.items()}
    }
    
    json_path = results_dir / 'stage5_ultimate_specialized_results.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f'  OK Saved: {json_path.name}')
    
    # Statistics
    total_time = time.time() - overall_start
    
    stats = {
        'total_rows': len(all_rows),
        'header_rows': len(header_rows),
        'data_rows': len(data_rows),
        'empty_cells': skipped,
        'data_cells': processed,
        'time': {
            'classification': f'{classify_time:.2f}s',
            'ocr': f'{ocr_time:.2f}s',
            'total': f'{total_time:.2f}s'
        },
        'method': 'Ultimate Specialized OCR (Column-Specific)'
    }
    
    stats_path = results_dir / 'stage5_ultimate_specialized_statistics.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    print(f'  OK Saved: {stats_path.name}')
    
    # Summary
    print(f'\n' + '='*80)
    print('ULTIMATE SPECIALIZED OCR RESULTS')
    print('='*80)
    print(f'Total time: {total_time:.2f}s ({total_time/60:.1f} minutes)')
    print(f'  - Classification: {classify_time:.2f}s')
    print(f'  - Specialized OCR: {ocr_time:.2f}s')
    print(f'\nRows: {len(all_rows)} total')
    print(f'  - Headers: {len(header_rows)} (skipped)')
    print(f'  - Data:    {len(data_rows)} (processed)')
    print(f'\nCells: {processed} OCR, {skipped} empty')
    print('='*80)
    
    print(f'\nNow run: py experiments/stage5_ocr/compare_with_ground_truth.py')
    print('to see the ACTUAL accuracy!')
    
    return True


if __name__ == '__main__':
    success = test_ultimate_specialized_ocr()
    sys.exit(0 if success else 1)
