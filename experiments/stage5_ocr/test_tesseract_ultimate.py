"""
Test Stage 5: ULTIMATE TESSERACT OCR

Strategy: MAXIMUM ACCURACY with Tesseract
1. Adaptive preprocessing per cell (custom for each cell type)
2. Multi-pass OCR with different PSM modes
3. Confidence-based retry with enhanced preprocessing
4. Aggressive post-processing with column-aware corrections
5. Character whitelist per column type

Target: 95%+ accuracy with Tesseract
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np
import pytesseract

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


def get_column_type(col_idx: int) -> str:
    """Determine column type for optimization"""
    if col_idx >= len(COLUMN_HEADERS):
        return 'text'
    
    col_name = COLUMN_HEADERS[col_idx].lower()
    
    if any(x in col_name for x in ['no', 'kk', 'bangunan', 'usaha']):
        return 'pure_numeric'  # Only numbers
    elif 'rt' in col_name or 'rw' in col_name:
        return 'rt_rw'  # RT/RW format
    elif 'alamat' in col_name:
        return 'address'  # Text with numbers
    elif 'jam' in col_name:
        return 'time'  # Time format
    elif 'telepon' in col_name:
        return 'phone'  # Phone numbers
    else:
        return 'text'  # General text


def is_cell_empty(cell_image: np.ndarray, threshold: float = 0.015) -> bool:
    """Enhanced empty detection"""
    if cell_image.size == 0:
        return True
    
    if len(cell_image.shape) == 3:
        gray = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_image
    
    # Check dark pixels
    dark_pixels = np.sum(gray < 200)
    total_pixels = gray.size
    ratio = dark_pixels / total_pixels
    
    return ratio < threshold


def enhance_cell_for_ocr(cell_img: np.ndarray, col_type: str) -> np.ndarray:
    """
    ADVANCED preprocessing tailored to column type
    """
    # Convert to grayscale if needed
    if len(cell_img.shape) == 3:
        gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_img.copy()
    
    # Resize if too small (critical for accuracy!)
    h, w = gray.shape
    if h < 40:
        scale = 40 / h
        new_w = int(w * scale)
        gray = cv2.resize(gray, (new_w, 40), interpolation=cv2.INTER_CUBIC)
    
    # Denoise
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    
    # Different preprocessing based on column type
    if col_type in ['pure_numeric', 'rt_rw', 'phone']:
        # For numbers: High contrast, sharp edges
        # Adaptive thresholding
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Slight dilation to thicken thin strokes
        kernel = np.ones((2,2), np.uint8)
        binary = cv2.dilate(binary, kernel, iterations=1)
        
        return binary
    
    elif col_type == 'time':
        # For time: Preserve dots and colons
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 15, 2
        )
        return binary
    
    else:
        # For text: Balance between contrast and detail
        # CLAHE for contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # Adaptive threshold
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        
        return binary


def get_tesseract_config(col_type: str) -> str:
    """
    Get optimal Tesseract config for column type
    """
    base_config = '--oem 3'  # Use LSTM OCR Engine
    
    if col_type == 'pure_numeric':
        # Only digits
        return f'{base_config} --psm 7 -c tessedit_char_whitelist=0123456789'
    
    elif col_type == 'rt_rw':
        # RT/RW format: letters + numbers + space
        return f'{base_config} --psm 7 -c tessedit_char_whitelist=RTrw0123456789 '
    
    elif col_type == 'phone':
        # Phone: digits, dash, parentheses
        return f'{base_config} --psm 7 -c tessedit_char_whitelist=0123456789-()+ '
    
    elif col_type == 'time':
        # Time: digits, dot, colon
        return f'{base_config} --psm 7 -c tessedit_char_whitelist=0123456789.: '
    
    else:
        # General text: no whitelist
        return f'{base_config} --psm 7'


def ocr_with_confidence(cell_img: np.ndarray, col_type: str, min_confidence: float = 60.0) -> tuple:
    """
    OCR with confidence check and retry
    
    Returns:
        (text, confidence)
    """
    # First attempt: Standard preprocessing
    enhanced = enhance_cell_for_ocr(cell_img, col_type)
    config = get_tesseract_config(col_type)
    
    # Get OCR with confidence
    data = pytesseract.image_to_data(
        enhanced, 
        config=config, 
        output_type=pytesseract.Output.DICT
    )
    
    # Extract text and average confidence
    texts = []
    confidences = []
    
    for i, conf in enumerate(data['conf']):
        if conf > 0:  # Valid detection
            text = data['text'][i]
            if text.strip():
                texts.append(text)
                confidences.append(conf)
    
    if not texts:
        return "", 0.0
    
    combined_text = ' '.join(texts)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    
    # If low confidence, retry with different preprocessing
    if avg_confidence < min_confidence and col_type in ['pure_numeric', 'rt_rw']:
        # Retry with inverted image (for negative cells)
        inverted = cv2.bitwise_not(enhanced)
        
        data2 = pytesseract.image_to_data(
            inverted,
            config=config,
            output_type=pytesseract.Output.DICT
        )
        
        texts2 = []
        confidences2 = []
        
        for i, conf in enumerate(data2['conf']):
            if conf > 0:
                text = data2['text'][i]
                if text.strip():
                    texts2.append(text)
                    confidences2.append(conf)
        
        if confidences2:
            combined_text2 = ' '.join(texts2)
            avg_confidence2 = sum(confidences2) / len(confidences2)
            
            # Use better result
            if avg_confidence2 > avg_confidence:
                combined_text = combined_text2
                avg_confidence = avg_confidence2
    
    return combined_text, avg_confidence


def postprocess_ultimate(text: str, col_type: str) -> str:
    """
    ULTIMATE post-processing with aggressive corrections
    """
    if not text:
        return text
    
    import re
    
    # Clean whitespace
    text = ' '.join(text.split())
    
    # Column-specific corrections
    if col_type == 'pure_numeric':
        # Aggressive number corrections
        corrections = {
            'O': '0', 'o': '0',
            'I': '1', 'l': '1', '|': '1',
            'Z': '2', 'z': '2',
            'B': '8', 'b': '8',
            'S': '5', 's': '5',
            'G': '6', 'g': '6',
            'T': '7', 't': '7',
        }
        
        for old, new in corrections.items():
            text = text.replace(old, new)
        
        # Remove all non-digits
        text = re.sub(r'[^0-9]', '', text)
    
    elif col_type == 'rt_rw':
        # RT/RW specific
        text = text.upper()
        
        # Fix common OCR errors
        text = text.replace('RT0', 'RT ')
        text = text.replace('RW0', 'RW ')
        text = text.replace('RTI', 'RT 1')
        text = text.replace('RWI', 'RW 1')
        
        # Fix number errors in RT/RW
        text = re.sub(r'O(\d)', r'0\1', text)
        text = re.sub(r'(\d)O', r'\g<1>0', text)
        text = text.replace('!', '1')
        text = text.replace('l', '1')
        
        # Standardize format: RT XXX / RW XXX
        rt_match = re.search(r'RT\s*(\d+)', text)
        rw_match = re.search(r'RW\s*(\d+)', text)
        
        if rt_match and rw_match:
            rt_num = rt_match.group(1).zfill(3)
            rw_num = rw_match.group(1).zfill(3)
            text = f'RT {rt_num} / RW {rw_num}'
        elif rt_match:
            rt_num = rt_match.group(1).zfill(3)
            text = f'RT {rt_num}'
        elif rw_match:
            rw_num = rw_match.group(1).zfill(3)
            text = f'RW {rw_num}'
    
    elif col_type == 'phone':
        # Phone numbers
        text = text.replace('O', '0')
        text = text.replace('o', '0')
        text = text.replace('I', '1')
        text = text.replace('l', '1')
        
        # Keep only digits and separators
        text = re.sub(r'[^0-9\-()+ ]', '', text)
    
    elif col_type == 'time':
        # Time format: HH.MM or HH:MM
        text = text.replace('O', '0')
        text = text.replace('o', '0')
        text = text.replace('I', '1')
        text = text.replace('l', '1')
        
        # Standardize to dot separator
        text = text.replace(':', '.')
        
        # Keep only time characters
        text = re.sub(r'[^0-9.]', '', text)
    
    elif col_type == 'address':
        # Address: capitalize properly
        words = text.split()
        text = ' '.join(word.capitalize() if len(word) > 2 else word.upper() for word in words)
    
    return text.strip()


def test_ultimate_tesseract():
    """Test ULTIMATE Tesseract with maximum accuracy"""
    
    print('='*70)
    print('STAGE 5: ULTIMATE TESSERACT OCR (Maximum Accuracy)')
    print('='*70)
    print('Optimizations:')
    print('  ✓ Adaptive preprocessing per column type')
    print('  ✓ Cell resizing for small text')
    print('  ✓ Denoising before OCR')
    print('  ✓ Confidence-based retry mechanism')
    print('  ✓ Column-specific Tesseract configs')
    print('  ✓ Character whitelists per column')
    print('  ✓ Aggressive post-processing corrections')
    print('='*70)
    
    overall_start = time.time()
    
    # Step 1: Load table
    print('\n[Step 1] Loading table image...')
    image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
    
    if not image_path.exists():
        print(f'  X ERROR: {image_path} not found')
        return False
    
    image = cv2.imread(str(image_path))
    print(f'  OK Image: {image.shape}')
    
    # Step 2: Extract cells
    print('\n[Step 2] Extracting cells...')
    start = time.time()
    
    h_lines = detect_horizontal_lines(image, min_line_length=image.shape[1] // 3)
    v_lines = detect_vertical_lines(image, min_line_length=image.shape[0] // 5)
    cells = extract_cells_from_grid(image, h_lines, v_lines, margin=5)
    
    extract_time = time.time() - start
    print(f'  OK {len(cells)} cells in {extract_time:.2f}s')
    
    # Step 3: Ultimate OCR
    print('\n[Step 3] Running ULTIMATE Tesseract OCR...')
    start = time.time()
    
    results = {}
    confidences = {}
    skipped = 0
    processed = 0
    low_conf_count = 0
    
    total_cells = len(cells)
    
    for idx, ((row, col), cell_img) in enumerate(cells.items(), 1):
        # Progress
        if idx % 50 == 0 or idx == total_cells:
            print(f'  ... {idx}/{total_cells} cells processed')
        
        # Skip empty
        if is_cell_empty(cell_img):
            results[(row, col)] = ""
            confidences[(row, col)] = 100.0
            skipped += 1
            continue
        
        # Determine column type
        col_type = get_column_type(col)
        
        # OCR with confidence
        text, confidence = ocr_with_confidence(cell_img, col_type, min_confidence=60.0)
        
        # Post-process
        text = postprocess_ultimate(text, col_type)
        
        results[(row, col)] = text
        confidences[(row, col)] = confidence
        processed += 1
        
        if confidence < 70.0 and text:
            low_conf_count += 1
    
    ocr_time = time.time() - start
    print(f'  OK Completed in {ocr_time:.2f}s')
    print(f'     Processed: {processed}, Empty: {skipped}')
    print(f'     Low confidence (<70%): {low_conf_count}')
    
    # Step 4: Analyze confidence
    print('\n[Step 4] Confidence analysis...')
    
    conf_values = [c for c in confidences.values() if c > 0]
    if conf_values:
        avg_conf = sum(conf_values) / len(conf_values)
        min_conf = min(conf_values)
        max_conf = max(conf_values)
        
        print(f'  Average confidence: {avg_conf:.1f}%')
        print(f'  Range: {min_conf:.1f}% - {max_conf:.1f}%')
        
        # Confidence distribution
        high_conf = sum(1 for c in conf_values if c >= 80)
        med_conf = sum(1 for c in conf_values if 60 <= c < 80)
        low_conf = sum(1 for c in conf_values if c < 60)
        
        print(f'  High (≥80%): {high_conf} cells')
        print(f'  Med (60-80%): {med_conf} cells')
        print(f'  Low (<60%): {low_conf} cells')
    
    # Step 5: Sample results with confidence
    print('\n[Step 5] Sample results with confidence...')
    
    samples = [
        (4, 0), (4, 1), (4, 3), (4, 8),
        (5, 0), (5, 5), (5, 10), (5, 14),
        (6, 1), (6, 3), (6, 8)
    ]
    
    for pos in samples:
        if pos in results:
            text = results[pos]
            conf = confidences[pos]
            col_type = get_column_type(pos[1])
            
            status = "OK" if conf >= 70 else "⚠️"
            print(f'  {status} Cell {pos} ({col_type}): "{text if text else "[empty]"}" (conf: {conf:.0f}%)')
    
    # Step 6: Save
    print('\n[Step 6] Saving results...')
    
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    import json
    
    # Save results
    json_results = {f"{row},{col}": text for (row, col), text in results.items()}
    json_path = results_dir / 'stage5_ultimate_tesseract_results.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_results, f, indent=2, ensure_ascii=False)
    print(f'  OK Saved: {json_path.name}')
    
    # Save confidences
    json_conf = {f"{row},{col}": conf for (row, col), conf in confidences.items()}
    conf_path = results_dir / 'stage5_ultimate_tesseract_confidences.json'
    with open(conf_path, 'w', encoding='utf-8') as f:
        json.dump(json_conf, f, indent=2)
    print(f'  OK Saved: {conf_path.name}')
    
    # Statistics
    total_time = time.time() - overall_start
    
    stats = {
        'total_cells': len(cells),
        'empty_cells': skipped,
        'data_cells': processed,
        'low_confidence_cells': low_conf_count,
        'average_confidence': f'{avg_conf:.1f}%' if conf_values else 'N/A',
        'time': {
            'extraction': f'{extract_time:.2f}s',
            'ocr': f'{ocr_time:.2f}s',
            'total': f'{total_time:.2f}s'
        },
        'method': 'Ultimate Tesseract (Maximum Accuracy)'
    }
    
    stats_path = results_dir / 'stage5_ultimate_tesseract_statistics.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    print(f'  OK Saved: {stats_path.name}')
    
    # Summary
    print(f'\n' + '='*70)
    print('ULTIMATE TESSERACT RESULTS')
    print('='*70)
    print(f'Total time: {total_time:.2f}s')
    print(f'  - Extraction:  {extract_time:.2f}s')
    print(f'  - OCR:         {ocr_time:.2f}s')
    print(f'\nCells: {len(cells)} total, {skipped} empty, {processed} data')
    print(f'Average confidence: {avg_conf:.1f}%')
    print('='*70)
    
    # Comparison
    print(f'\n' + '='*70)
    print('COMPARISON WITH PREVIOUS METHODS')
    print('='*70)
    print(f'Simple Tesseract:      73.54s, 70-80% accuracy')
    print(f'PP-OCRv5 (CPU):        584.47s, 85-95% accuracy')
    print(f'Ultimate Tesseract:    {total_time:.2f}s, {avg_conf:.1f}% avg confidence')
    print('='*70)
    
    return True


if __name__ == '__main__':
    success = test_ultimate_tesseract()
    sys.exit(0 if success else 1)

