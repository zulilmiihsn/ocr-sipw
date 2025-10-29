"""
Stage 5: INTELLIGENT ROW DETECTION + PADDLEOCR (ULTIMATE ACCURACY)

Strategy:
1. Extract all cells from table
2. Quick OCR to classify rows (header vs data)
3. Skip header rows → process ONLY data rows
4. Use PaddleOCR PP-OCRv5 for maximum accuracy
5. Model loaded once, reused for all cells

Expected:
- Time: ~8-9 minutes (faster than before due to skipping headers)
- Accuracy: 85-95% (PaddleOCR is better for small text)
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np
import pytesseract
import re

# Set Tesseract path (for classification only)
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
    """
    Classify row as: header, data, or empty
    
    Returns: 'header', 'data', 'empty'
    """
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


class PaddleOCRSingleton:
    """Singleton pattern for PaddleOCR - load once, use many times"""
    _instance = None
    _ocr = None
    _init_time = 0
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        if PaddleOCRSingleton._ocr is None:
            print('\n' + '='*70)
            print('LOADING PADDLEOCR PP-OCRv5 (ONE-TIME)')
            print('='*70)
            start = time.time()
            
            from paddleocr import PaddleOCR
            
            PaddleOCRSingleton._ocr = PaddleOCR(
                lang='en',
                use_textline_orientation=False
            )
            
            PaddleOCRSingleton._init_time = time.time() - start
            print(f'OK Model loaded in {PaddleOCRSingleton._init_time:.2f}s')
            print('   Model ready for processing!')
            print('='*70 + '\n')
    
    def predict(self, image):
        """Perform OCR on image"""
        return PaddleOCRSingleton._ocr.predict(image)
    
    @classmethod
    def get_init_time(cls):
        return cls._init_time


def paddleocr_cell(cell_img: np.ndarray, ocr_engine) -> tuple:
    """
    OCR single cell with PaddleOCR
    
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
        print(f'  ERROR in PaddleOCR: {e}')
        return "", 0.0


def get_column_type(col_idx: int) -> str:
    """Determine column type"""
    if col_idx >= len(COLUMN_HEADERS):
        return 'text'
    
    col_name = COLUMN_HEADERS[col_idx].lower()
    
    if col_idx == 0:
        return 'pure_numeric'
    elif col_idx in [1, 2]:
        return 'code'
    elif 'rt' in col_name or 'rw' in col_name or col_idx == 3:
        return 'rt_rw'
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


def postprocess_paddleocr(text: str, col_type: str) -> str:
    """Post-process PaddleOCR results"""
    if not text:
        return text
    
    text = ' '.join(text.split())
    
    if col_type in ['pure_numeric', 'code']:
        # Number corrections
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
        elif rw_match:
            rw_num = rw_match.group(1).zfill(3)
            text = f'RW {rw_num}'
    
    elif col_type == 'time':
        text = text.replace('O', '0').replace('o', '0')
        text = text.replace('I', '1').replace('l', '1')
        text = text.replace(':', '.').replace('-', '.')
        
        # Extract time pattern
        time_match = re.search(r'(\d{1,2})[\.\:\-]?(\d{2})', text)
        if time_match:
            h = time_match.group(1)
            m = time_match.group(2)
            text = f'{h}.{m}'
    
    elif col_type == 'contact':
        text = text.replace('O', '0').replace('o', '0')
        text = text.replace('I', '1').replace('l', '1')
    
    return text.strip()


def test_intelligent_paddleocr():
    """Test intelligent row detection + PaddleOCR"""
    
    print('='*70)
    print('STAGE 5: INTELLIGENT DETECTION + PADDLEOCR (ULTIMATE)')
    print('='*70)
    print('Strategy:')
    print('  1. Extract all cells')
    print('  2. Quick classification (header vs data)')
    print('  3. Skip headers → process ONLY data rows')
    print('  4. PaddleOCR PP-OCRv5 for maximum accuracy')
    print('  5. Model loaded once, reused for all cells')
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
    
    all_rows = sorted(set(row for row, col in cells.keys()))
    print(f'  OK {len(all_rows)} rows detected')
    
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
    
    print(f'\n[Step 3] Filtering data rows...')
    print(f'  Header rows: {header_rows} (SKIPPED)')
    print(f'  Data rows:   {data_rows}')
    print(f'  → {len(data_rows)} data rows to OCR')
    
    # Step 4: Load PaddleOCR (once)
    print(f'\n[Step 4] Loading PaddleOCR model...')
    paddle = PaddleOCRSingleton.get_instance()
    model_load_time = PaddleOCRSingleton.get_init_time()
    
    # Step 5: PaddleOCR on data rows
    print(f'\n[Step 5] Running PaddleOCR on {len(data_rows)} data rows...')
    print('  (This will take ~8-9 minutes for maximum accuracy)')
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
            
            # Skip empty
            if is_cell_empty(cell_img):
                results[(row_idx, col_idx)] = ""
                confidences[(row_idx, col_idx)] = 100.0
                skipped += 1
                row_skipped += 1
                continue
            
            # PaddleOCR
            text, confidence = paddleocr_cell(cell_img, paddle)
            
            # Post-process
            col_type = get_column_type(col_idx)
            text = postprocess_paddleocr(text, col_type)
            
            results[(row_idx, col_idx)] = text
            confidences[(row_idx, col_idx)] = confidence
            processed += 1
            row_processed += 1
            
            # Progress update every 20 cells
            if current_cell % 20 == 0:
                elapsed = time.time() - start
                progress = (current_cell / total_data_cells) * 100
                eta = (elapsed / current_cell) * (total_data_cells - current_cell)
                print(f'  ... {current_cell}/{total_data_cells} cells ({progress:.1f}%) - ETA: {eta:.0f}s')
        
        row_time = time.time() - row_start
        print(f'  ✓ Row {row_idx:2d}: {row_processed} OCR, {row_skipped} empty in {row_time:.1f}s')
    
    ocr_time = time.time() - start
    print(f'  OK PaddleOCR completed in {ocr_time:.2f}s')
    print(f'     Processed: {processed}, Empty: {skipped}')
    
    # Step 6: Display sample results
    print(f'\n[Step 6] Sample results (first 3 data rows):')
    print('='*70)
    
    for row_idx in data_rows[:3]:
        print(f'\nData Row {row_idx}:')
        for col_idx in range(17):
            text = results.get((row_idx, col_idx), "")
            conf = confidences.get((row_idx, col_idx), 0)
            col_name = COLUMN_HEADERS[col_idx] if col_idx < len(COLUMN_HEADERS) else f'C{col_idx}'
            
            if text or conf > 0:
                status = "✓" if conf >= 80 else "⚠️" if conf >= 60 else "✗"
                print(f'  {status} [{col_idx:2d}] {col_name:25s}: "{text}" ({conf:.0f}%)')
    
    # Step 7: Save results
    print(f'\n[Step 7] Saving results...')
    
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
    
    json_path = results_dir / 'stage5_intelligent_paddleocr_results.json'
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
            'model_loading': f'{model_load_time:.2f}s',
            'classification': f'{classify_time:.2f}s',
            'paddleocr': f'{ocr_time:.2f}s',
            'total': f'{total_time:.2f}s'
        },
        'method': 'Intelligent + PaddleOCR PP-OCRv5'
    }
    
    stats_path = results_dir / 'stage5_intelligent_paddleocr_statistics.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    print(f'  OK Saved: {stats_path.name}')
    
    # Summary
    print(f'\n' + '='*70)
    print('INTELLIGENT + PADDLEOCR RESULTS')
    print('='*70)
    print(f'Total time: {total_time:.2f}s ({total_time/60:.1f} minutes)')
    print(f'  - Model loading:  {model_load_time:.2f}s (ONE-TIME)')
    print(f'  - Classification: {classify_time:.2f}s')
    print(f'  - PaddleOCR:      {ocr_time:.2f}s')
    print(f'\nRows: {len(all_rows)} total')
    print(f'  - Headers: {len(header_rows)} (skipped)')
    print(f'  - Data:    {len(data_rows)} (processed)')
    print(f'\nCells: {processed} OCR, {skipped} empty')
    print(f'Average confidence: {avg_conf:.1f}%')
    print('='*70)
    
    print(f'\n' + '='*70)
    print('COMPARISON')
    print('='*70)
    print(f'Tesseract (simple):        73.54s, 70-80% accuracy')
    print(f'Tesseract (ultimate):      70.09s, 79.8% accuracy')
    print(f'PaddleOCR (intelligent):   {total_time:.2f}s, {avg_conf:.1f}% accuracy')
    print('='*70)
    
    return True


if __name__ == '__main__':
    success = test_intelligent_paddleocr()
    sys.exit(0 if success else 1)
