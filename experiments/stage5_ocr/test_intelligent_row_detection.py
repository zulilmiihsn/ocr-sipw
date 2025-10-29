"""
Stage 5: INTELLIGENT ROW DETECTION + ULTIMATE OCR

Strategy:
1. Extract all cells from table
2. Quick OCR scan to classify rows (header vs data vs empty)
3. Identify data rows dynamically (not hardcoded!)
4. Perform high-accuracy OCR only on data rows
5. Map results with correct row indices

This approach is ROBUST and works regardless of:
- Header row count
- Table position
- Image quality variations
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
    """Fast OCR for classification (no preprocessing)"""
    try:
        text = pytesseract.image_to_string(cell_img, config='--psm 7 --oem 3').strip()
        return text
    except:
        return ""


def classify_row_type(row_cells: dict, row_idx: int) -> str:
    """
    Classify row as: header, data, or empty
    
    Returns: 'header', 'data', 'empty'
    """
    # Quick OCR on first few cells
    sample_texts = []
    
    for col_idx in range(min(5, len(row_cells))):
        if (row_idx, col_idx) in row_cells:
            cell_img = row_cells[(row_idx, col_idx)]
            text = quick_ocr(cell_img)
            sample_texts.append(text.lower())
    
    combined = ' '.join(sample_texts)
    
    # Check if empty
    if not combined.strip():
        return 'empty'
    
    # Header detection keywords
    header_keywords = [
        'kode', 'nama', 'jumlah', 'muatan', 'btt', 'bku', 'bbtt',
        'wilayah', 'shift', 'jam', 'operasional', 'contact', 'person',
        'telepon', 'email', 'dominan', 'perubahan', 'batas', 'perkiraan',
        'total', 'ekonomi', 'konsentrasi', 'sub', 'sls', 'non-sls',
        'tempat', 'tinggal', 'kosong', 'usaha', 'no'
    ]
    
    # Count header keywords
    keyword_count = sum(1 for keyword in header_keywords if keyword in combined)
    
    # If many keywords found → header
    if keyword_count >= 2:
        return 'header'
    
    # Check for data patterns
    # Data rows typically have: numbers, RT/RW, short text
    has_numbers = bool(re.search(r'\d', combined))
    has_rt_rw = bool(re.search(r'rt|rw', combined, re.IGNORECASE))
    
    # Pattern: starts with number (row number)
    starts_with_number = bool(re.match(r'^\d+', sample_texts[0] if sample_texts else ''))
    
    if has_numbers or has_rt_rw or starts_with_number:
        return 'data'
    
    # Default: check length
    # Headers usually have longer text
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


def enhance_cell_for_ocr(cell_img: np.ndarray, col_type: str) -> np.ndarray:
    """Advanced preprocessing tailored to column type"""
    if len(cell_img.shape) == 3:
        gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_img.copy()
    
    # Resize if too small
    h, w = gray.shape
    if h < 40:
        scale = 40 / h
        new_w = int(w * scale)
        gray = cv2.resize(gray, (new_w, 40), interpolation=cv2.INTER_CUBIC)
    
    # Denoise
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    
    # Column-specific preprocessing
    if col_type in ['pure_numeric', 'rt_rw', 'phone']:
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        kernel = np.ones((2,2), np.uint8)
        binary = cv2.dilate(binary, kernel, iterations=1)
        return binary
    
    elif col_type == 'time':
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 15, 2
        )
        return binary
    
    else:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        return binary


def get_column_type(col_idx: int) -> str:
    """Determine column type for optimization"""
    if col_idx >= len(COLUMN_HEADERS):
        return 'text'
    
    col_name = COLUMN_HEADERS[col_idx].lower()
    
    if col_idx == 0:
        return 'pure_numeric'  # No column
    elif col_idx in [1, 2]:
        return 'code'  # Kode columns
    elif 'rt' in col_name or 'rw' in col_name or col_idx == 3:
        return 'rt_rw'  # RT/RW format
    elif any(x in col_name for x in ['kk', 'bangunan', 'usaha', 'muatan', 'shift']):
        return 'pure_numeric'
    elif 'alamat' in col_name or 'wilayah' in col_name or 'nama' in col_name:
        return 'text'
    elif 'jam' in col_name:
        return 'time'
    elif 'telepon' in col_name or 'email' in col_name or 'contact' in col_name:
        return 'contact'
    else:
        return 'text'


def get_tesseract_config(col_type: str) -> str:
    """Get optimal Tesseract config for column type"""
    base_config = '--oem 3'
    
    if col_type == 'pure_numeric':
        return f'{base_config} --psm 7 -c tessedit_char_whitelist=0123456789'
    elif col_type == 'code':
        return f'{base_config} --psm 7 -c tessedit_char_whitelist=0123456789'
    elif col_type == 'rt_rw':
        return f'{base_config} --psm 7'
    elif col_type == 'contact':
        return f'{base_config} --psm 7'
    elif col_type == 'time':
        return f'{base_config} --psm 7 -c tessedit_char_whitelist=0123456789.: '
    else:
        return f'{base_config} --psm 7'


def ocr_with_confidence(cell_img: np.ndarray, col_type: str) -> tuple:
    """OCR with confidence check and retry"""
    enhanced = enhance_cell_for_ocr(cell_img, col_type)
    config = get_tesseract_config(col_type)
    
    data = pytesseract.image_to_data(
        enhanced, 
        config=config, 
        output_type=pytesseract.Output.DICT
    )
    
    texts = []
    confidences = []
    
    for i, conf in enumerate(data['conf']):
        if conf > 0:
            text = data['text'][i]
            if text.strip():
                texts.append(text)
                confidences.append(conf)
    
    if not texts:
        return "", 0.0
    
    combined_text = ' '.join(texts)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    
    # Retry with inverted image for low confidence numbers
    if avg_confidence < 60 and col_type in ['pure_numeric', 'code']:
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
            avg_confidence2 = sum(confidences2) / len(confidences2)
            if avg_confidence2 > avg_confidence:
                combined_text = ' '.join(texts2)
                avg_confidence = avg_confidence2
    
    return combined_text, avg_confidence


def postprocess_text(text: str, col_type: str) -> str:
    """Advanced post-processing with column-aware corrections"""
    if not text:
        return text
    
    text = ' '.join(text.split())
    
    if col_type in ['pure_numeric', 'code']:
        # Aggressive number corrections
        text = text.replace('O', '0').replace('o', '0')
        text = text.replace('I', '1').replace('l', '1').replace('|', '1')
        text = text.replace('Z', '2').replace('z', '2')
        text = text.replace('B', '8').replace('b', '8')
        text = text.replace('S', '5').replace('s', '5')
        text = re.sub(r'[^0-9]', '', text)
    
    elif col_type == 'rt_rw':
        text = text.upper()
        text = text.replace('RT0', 'RT ').replace('RW0', 'RW ')
        text = text.replace('O', '0').replace('I', '1').replace('l', '1')
        
        rt_match = re.search(r'RT\s*(\d+)', text)
        rw_match = re.search(r'RW\s*(\d+)', text)
        
        if rt_match and rw_match:
            rt_num = rt_match.group(1).zfill(3)
            rw_num = rw_match.group(1).zfill(3)
            text = f'RT {rt_num} RW {rw_num}'
        elif rt_match:
            rt_num = rt_match.group(1).zfill(3)
            text = f'RT {rt_num}'
    
    elif col_type == 'time':
        text = text.replace('O', '0').replace('o', '0').replace('I', '1').replace('l', '1')
        text = text.replace(':', '.').replace('-', '.')
        text = re.sub(r'[^0-9.]', '', text)
    
    elif col_type == 'contact':
        text = text.replace('O', '0').replace('o', '0').replace('I', '1').replace('l', '1')
    
    return text.strip()


def test_intelligent_row_detection():
    """Test intelligent row detection and classification"""
    
    print('='*70)
    print('STAGE 5: INTELLIGENT ROW DETECTION + ULTIMATE OCR')
    print('='*70)
    print('Strategy:')
    print('  1. Extract all cells')
    print('  2. Quick OCR to classify rows (header/data/empty)')
    print('  3. Identify data rows dynamically')
    print('  4. High-accuracy OCR only on data rows')
    print('  5. Map results with correct indices')
    print('='*70)
    
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
    
    # Get unique rows
    all_rows = sorted(set(row for row, col in cells.keys()))
    print(f'  OK {len(all_rows)} rows detected: {all_rows}')
    
    # Step 2: Classify rows
    print('\n[Step 2] Classifying rows (header vs data vs empty)...')
    start = time.time()
    
    row_classifications = {}
    
    for row_idx in all_rows:
        row_cells = {pos: img for pos, img in cells.items() if pos[0] == row_idx}
        classification = classify_row_type(row_cells, row_idx)
        row_classifications[row_idx] = classification
        
        symbol = '📋' if classification == 'header' else '📊' if classification == 'data' else '⚪'
        print(f'  {symbol} Row {row_idx:2d}: {classification.upper()}')
    
    classify_time = time.time() - start
    print(f'  OK Classification done in {classify_time:.2f}s')
    
    # Step 3: Filter data rows
    data_rows = [row for row, cls in row_classifications.items() if cls == 'data']
    header_rows = [row for row, cls in row_classifications.items() if cls == 'header']
    
    print(f'\n[Step 3] Row summary:')
    print(f'  Header rows: {header_rows}')
    print(f'  Data rows:   {data_rows}')
    print(f'  → {len(data_rows)} data rows to process')
    
    # Step 4: High-accuracy OCR on data rows only
    print(f'\n[Step 4] High-accuracy OCR on {len(data_rows)} data rows...')
    start = time.time()
    
    results = {}
    confidences = {}
    processed = 0
    skipped = 0
    
    for row_idx in data_rows:
        for col_idx in range(17):  # 17 columns
            if (row_idx, col_idx) not in cells:
                continue
            
            cell_img = cells[(row_idx, col_idx)]
            
            # Skip empty
            if is_cell_empty(cell_img):
                results[(row_idx, col_idx)] = ""
                confidences[(row_idx, col_idx)] = 100.0
                skipped += 1
                continue
            
            # Determine column type
            col_type = get_column_type(col_idx)
            
            # OCR with confidence
            text, confidence = ocr_with_confidence(cell_img, col_type)
            
            # Post-process
            text = postprocess_text(text, col_type)
            
            results[(row_idx, col_idx)] = text
            confidences[(row_idx, col_idx)] = confidence
            processed += 1
        
        print(f'  ... Row {row_idx} processed')
    
    ocr_time = time.time() - start
    print(f'  OK OCR completed in {ocr_time:.2f}s')
    print(f'     Processed: {processed}, Empty: {skipped}')
    
    # Step 5: Display results
    print(f'\n[Step 5] Data rows results:')
    print('='*70)
    
    for row_idx in data_rows[:10]:  # Show first 10 data rows
        print(f'\nRow {row_idx}:')
        row_data = []
        for col_idx in range(17):
            text = results.get((row_idx, col_idx), "")
            conf = confidences.get((row_idx, col_idx), 0)
            col_name = COLUMN_HEADERS[col_idx] if col_idx < len(COLUMN_HEADERS) else f'C{col_idx}'
            
            if text or conf > 0:
                status = "✓" if conf >= 70 else "⚠️" if conf >= 50 else "✗"
                print(f'  {status} [{col_idx:2d}] {col_name:20s}: "{text}" (conf: {conf:.0f}%)')
    
    # Step 6: Save results
    print(f'\n[Step 6] Saving results...')
    
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    import json
    
    # Save with row classification metadata
    output_data = {
        'row_classifications': {str(k): v for k, v in row_classifications.items()},
        'data_rows': data_rows,
        'header_rows': header_rows,
        'results': {f"{row},{col}": text for (row, col), text in results.items()},
        'confidences': {f"{row},{col}": conf for (row, col), conf in confidences.items()}
    }
    
    json_path = results_dir / 'stage5_intelligent_ocr_results.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f'  OK Saved: {json_path.name}')
    
    # Statistics
    total_time = time.time() - overall_start
    
    conf_values = [c for c in confidences.values() if c > 0]
    avg_conf = sum(conf_values) / len(conf_values) if conf_values else 0
    
    stats = {
        'total_rows': len(all_rows),
        'header_rows': len(header_rows),
        'data_rows': len(data_rows),
        'empty_cells': skipped,
        'data_cells': processed,
        'average_confidence': f'{avg_conf:.1f}%',
        'time': {
            'classification': f'{classify_time:.2f}s',
            'ocr': f'{ocr_time:.2f}s',
            'total': f'{total_time:.2f}s'
        }
    }
    
    stats_path = results_dir / 'stage5_intelligent_ocr_statistics.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    print(f'  OK Saved: {stats_path.name}')
    
    # Summary
    print(f'\n' + '='*70)
    print('INTELLIGENT OCR RESULTS')
    print('='*70)
    print(f'Total time: {total_time:.2f}s')
    print(f'  - Classification: {classify_time:.2f}s')
    print(f'  - OCR:            {ocr_time:.2f}s')
    print(f'\nRows: {len(all_rows)} total')
    print(f'  - Headers: {len(header_rows)}')
    print(f'  - Data:    {len(data_rows)}')
    print(f'\nCells: {processed} data, {skipped} empty')
    print(f'Average confidence: {avg_conf:.1f}%')
    print('='*70)
    
    return True


if __name__ == '__main__':
    success = test_intelligent_row_detection()
    sys.exit(0 if success else 1)
