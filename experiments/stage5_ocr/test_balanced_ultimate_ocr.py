"""
Stage 5: BALANCED ULTIMATE OCR

Strategy:
1. Intelligent row detection (skip headers)
2. Use PaddleOCR as PRIMARY engine (proven 51% accuracy)
3. TARGETED fixes for problematic columns:
   - RT/RW: Pattern extraction + aggressive cleaning
   - Time: Format normalization
   - Numbers: Digit-only validation
4. Smart post-processing based on actual errors
5. NO over-preprocessing - keep it simple!

Target: 70-85% accuracy (realistic!)
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


def is_cell_empty(cell_image: np.ndarray, threshold: float = 0.01) -> bool:
    """
    Enhanced empty detection - LESS AGGRESSIVE
    
    Lower threshold to avoid skipping cells with small text
    """
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


class PaddleOCREngine:
    """Singleton PaddleOCR engine"""
    _instance = None
    _ocr = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        if PaddleOCREngine._ocr is None:
            print('\n' + '='*70)
            print('LOADING PADDLEOCR (ONE-TIME)')
            print('='*70)
            start = time.time()
            
            from paddleocr import PaddleOCR
            
            PaddleOCREngine._ocr = PaddleOCR(
                lang='en',
                use_textline_orientation=False
            )
            
            load_time = time.time() - start
            print(f'OK Model loaded in {load_time:.2f}s')
            print('='*70 + '\n')
    
    def predict(self, image):
        """Perform OCR on image"""
        return PaddleOCREngine._ocr.predict(image)


def paddleocr_cell(cell_img: np.ndarray, ocr_engine) -> tuple:
    """
    Simple PaddleOCR - NO over-preprocessing
    
    Returns: (text, confidence)
    """
    # Ensure BGR format
    if len(cell_img.shape) == 2:
        cell_img = cv2.cvtColor(cell_img, cv2.COLOR_GRAY2BGR)
    
    try:
        result = ocr_engine.predict(cell_img)
        
        if result and 'rec_texts' in result[0]:
            texts = result[0]['rec_texts']
            scores = result[0]['rec_scores']
            
            if texts:
                combined_text = ' '.join(texts) if isinstance(texts, list) else str(texts)
                avg_conf = (sum(scores) / len(scores)) * 100 if scores else 0.0
                return combined_text, avg_conf
        
        return "", 0.0
        
    except Exception as e:
        return "", 0.0


def get_column_type(col_idx: int) -> str:
    """Determine column type for post-processing"""
    type_map = {
        0: 'number',        # No
        1: 'number',        # Kode
        2: 'number',        # Sub
        3: 'rtrw',          # Nama SLS (RT/RW) - CRITICAL!
        4: 'number',        # KK
        5: 'number',        # BTT
        6: 'number',        # BTT Kosong
        7: 'number',        # BKU
        8: 'number',        # BBTT
        9: 'number',        # Muatan Usaha
        10: 'number',       # Total
        11: 'text',         # Wilayah
        12: 'number',       # Shift
        13: 'time',         # Jam
        14: 'contact',      # Contact
        15: 'number',       # Muatan
        16: 'number',       # Perubahan
    }
    
    return type_map.get(col_idx, 'text')


def postprocess_balanced(text: str, col_type: str, col_idx: int) -> str:
    """
    BALANCED post-processing - targeted fixes based on actual errors
    """
    if not text:
        return text
    
    text = ' '.join(text.split())
    
    if col_type == 'number':
        # Clean numbers - AGGRESSIVE
        text = text.replace('O', '0').replace('o', '0')
        text = text.replace('I', '1').replace('l', '1').replace('|', '1')
        text = text.replace('Z', '2').replace('z', '2')
        text = text.replace('B', '8').replace('b', '8')
        text = text.replace('S', '5').replace('s', '5')
        text = text.replace('G', '6').replace('g', '6')
        text = text.replace('T', '7').replace('t', '7')
        
        # Extract only digits
        cleaned = re.sub(r'[^0-9]', '', text)
        
        # Validate based on column
        if col_idx == 0:  # No - should be 2 digits
            if len(cleaned) == 1:
                cleaned = '0' + cleaned
        elif col_idx == 1:  # Kode - should be 4 digits
            if len(cleaned) < 4:
                cleaned = cleaned.zfill(4)
        
        return cleaned
    
    elif col_type == 'rtrw':
        # RT/RW - THE MOST CRITICAL FIX!
        text = text.upper()
        
        # Fix common OCR errors
        text = text.replace('O', '0').replace('I', '1').replace('L', '1')
        text = text.replace('Z', '2').replace('S', '5').replace('B', '8')
        
        # Extract ALL numbers from text
        numbers = re.findall(r'\d+', text)
        
        # Strategy: Assume format "RT XXX RW XXX"
        # If we find numbers, use first for RT, second for RW (or same if only one)
        if len(numbers) >= 2:
            rt_num = numbers[0].zfill(3)
            rw_num = numbers[1].zfill(3)
            return f'RT {rt_num} RW {rw_num}'
        elif len(numbers) == 1:
            # Only one number found - likely RT
            num = numbers[0].zfill(3)
            # Check if text mentions both RT and RW
            if 'RT' in text and 'RW' in text:
                # Assume same number for both (common pattern)
                return f'RT {num} RW {num}'
            elif 'RT' in text:
                return f'RT {num}'
            elif 'RW' in text:
                return f'RW {num}'
            else:
                # Default to RT
                return f'RT {num}'
        else:
            # No numbers found - return cleaned text
            return text
    
    elif col_type == 'time':
        # Time format: X.XX-XX.XX or similar
        text = text.replace('O', '0').replace('o', '0')
        text = text.replace('I', '1').replace('l', '1')
        
        # Standardize separators
        text = text.replace(':', '.').replace(',', '.')
        
        # Extract time pattern: NN.NN-NN.NN or NN.NN
        time_match = re.search(r'(\d{1,2})[\.\:](\d{2})\s*[-~]\s*(\d{1,2})[\.\:](\d{2})', text)
        if time_match:
            h1, m1, h2, m2 = time_match.groups()
            return f'{h1}.{m1}-{h2}.{m2}'
        
        # Single time
        time_match = re.search(r'(\d{1,2})[\.\:](\d{2})', text)
        if time_match:
            h, m = time_match.groups()
            # If this looks like it should be a range, try to extract second part
            remaining = text[time_match.end():]
            second_match = re.search(r'(\d{1,2})[\.\:](\d{2})', remaining)
            if second_match:
                h2, m2 = second_match.groups()
                return f'{h}.{m}-{h2}.{m2}'
            return f'{h}.{m}'
        
        return text
    
    elif col_type == 'contact':
        # Contact - clean but preserve format
        text = text.replace('O', '0').replace('o', '0')
        text = text.replace('I', '1').replace('l', '1')
        
        # Fix common patterns
        # "823456789" should be "081.3456789"
        if text.startswith('8') and len(text) >= 9:
            # Likely missing "0"
            text = '0' + text
        
        # Add dots if missing (081.3456789 format)
        if re.match(r'^\d{11,}', text):
            # Insert dot after 3rd digit
            text = text[:3] + '.' + text[3:]
        
        return text
    
    elif col_type == 'text':
        # General text - just capitalize
        return text.strip()
    
    return text.strip()


def test_balanced_ultimate_ocr():
    """Test BALANCED Ultimate OCR"""
    
    print('='*80)
    print('STAGE 5: BALANCED ULTIMATE OCR')
    print('='*80)
    print('Strategy:')
    print('  ✓ PaddleOCR as primary engine (proven effective)')
    print('  ✓ Simple preprocessing - no over-processing!')
    print('  ✓ Targeted post-processing for RT/RW, time, numbers')
    print('  ✓ Smart validation based on column type')
    print('  ✓ Less aggressive empty detection')
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
    
    # Step 4: Load PaddleOCR
    print(f'\n[Step 4] Loading PaddleOCR...')
    paddle = PaddleOCREngine.get_instance()
    
    # Step 5: Balanced OCR
    print(f'\n[Step 5] Running Balanced OCR...')
    start = time.time()
    
    results = {}
    confidences = {}
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
            
            # Skip empty (less aggressive)
            if is_cell_empty(cell_img, threshold=0.01):
                results[(row_idx, col_idx)] = ""
                confidences[(row_idx, col_idx)] = 100.0
                skipped += 1
                row_skipped += 1
                continue
            
            # PaddleOCR
            text, confidence = paddleocr_cell(cell_img, paddle)
            
            # Post-process based on column type
            col_type = get_column_type(col_idx)
            text = postprocess_balanced(text, col_type, col_idx)
            
            results[(row_idx, col_idx)] = text
            confidences[(row_idx, col_idx)] = confidence
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
    print(f'  OK Balanced OCR completed in {ocr_time:.2f}s')
    print(f'     Processed: {processed}, Empty: {skipped}')
    
    # Step 6: Save results
    print(f'\n[Step 6] Saving results...')
    
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    import json
    
    output_data = {
        'row_classifications': {str(k): v for k, v in row_classifications.items()},
        'data_rows': data_rows,
        'header_rows': header_rows,
        'results': {f"{row},{col}": text for (row, col), text in results.items()},
        'confidences': {f"{row},{col}": conf for (row, col), conf in confidences.items()}
    }
    
    json_path = results_dir / 'stage5_balanced_ultimate_results.json'
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
        },
        'method': 'Balanced Ultimate OCR'
    }
    
    stats_path = results_dir / 'stage5_balanced_ultimate_statistics.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    print(f'  OK Saved: {stats_path.name}')
    
    # Summary
    print(f'\n' + '='*80)
    print('BALANCED ULTIMATE OCR RESULTS')
    print('='*80)
    print(f'Total time: {total_time:.2f}s ({total_time/60:.1f} minutes)')
    print(f'  - Classification: {classify_time:.2f}s')
    print(f'  - OCR: {ocr_time:.2f}s')
    print(f'\nRows: {len(all_rows)} total')
    print(f'  - Headers: {len(header_rows)} (skipped)')
    print(f'  - Data:    {len(data_rows)} (processed)')
    print(f'\nCells: {processed} OCR, {skipped} empty')
    print(f'Average confidence: {avg_conf:.1f}%')
    print('='*80)
    
    print(f'\nNow run comparison to see actual accuracy:')
    print(f'py experiments/stage5_ocr/compare_with_ground_truth.py')
    
    return True


if __name__ == '__main__':
    success = test_balanced_ultimate_ocr()
    sys.exit(0 if success else 1)
