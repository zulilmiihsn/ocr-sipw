"""
========================================
CELL-BY-CELL OCR PIPELINE
========================================

NEW APPROACH: OCR setiap cell secara terpisah untuk akurasi maksimal!

Stages:
1. Load Image
2. Detect BLOK III
3. Detect Grid (17 cols × rows)
4. Extract & OCR Each Cell
5. Direct Table Mapping
6. Export Results

Author: Lab OCR Team
Version: CELL-BY-CELL v1.0
Date: October 28, 2025
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np
import json

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import approved methods
from src.utils.pdf_handler import load_image
from src.ocr.table_detector import detect_table_region, crop_table


# ============================================================================
# STAGE 4: GRID DETECTION (Approved Method)
# ============================================================================

def detect_horizontal_lines(image):
    """Detect horizontal table lines"""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel_width = max(3, image.shape[1] // 3)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, 1))
    h_lines_img = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)
    contours, _ = cv2.findContours(h_lines_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    h_lines = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w > image.shape[1] * 0.5:
            h_lines.append(y)
    
    return sorted(set(h_lines))


def detect_vertical_lines(image):
    """Detect vertical table lines"""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel_height = max(3, image.shape[0] // 5)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kernel_height))
    v_lines_img = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)
    contours, _ = cv2.findContours(v_lines_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    v_lines = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if h > image.shape[0] * 0.3:
            v_lines.append(x)
    
    return sorted(set(v_lines))


# ============================================================================
# STAGE 5: CELL EXTRACTION & OCR
# ============================================================================

def extract_cell(image, row_start, row_end, col_start, col_end, margin=5):
    """Extract single cell from grid with margin to avoid borders"""
    # Add margin to avoid grid lines
    y1 = max(0, row_start + margin)
    y2 = min(image.shape[0], row_end - margin)
    x1 = max(0, col_start + margin)
    x2 = min(image.shape[1], col_end - margin)
    
    cell = image[y1:y2, x1:x2]
    return cell


def preprocess_cell(cell):
    """Smart preprocessing untuk single cell"""
    if cell is None or cell.size == 0:
        return None
    
    # Check if too small
    if cell.shape[0] < 10 or cell.shape[1] < 10:
        return None
    
    # Keep 3-channel
    if len(cell.shape) == 2:
        cell = cv2.cvtColor(cell, cv2.COLOR_GRAY2BGR)
    
    # Upscale 2x untuk OCR lebih baik
    cell = cv2.resize(cell, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    
    # Denoise
    cell = cv2.fastNlMeansDenoisingColored(cell, None, h=10, hColor=10, 
                                           templateWindowSize=7, searchWindowSize=21)
    
    # CLAHE (enhance contrast)
    lab = cv2.cvtColor(cell, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    l = clahe.apply(l)
    cell = cv2.merge([l, a, b])
    cell = cv2.cvtColor(cell, cv2.COLOR_LAB2BGR)
    
    # Sharpen
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    cell = cv2.filter2D(cell, -1, kernel)
    
    return cell


class PaddleOCREngine:
    """Singleton PaddleOCR instance"""
    _instance = None
    _ocr = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_ocr(self):
        if self._ocr is None:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                lang='en',
                use_textline_orientation=False
            )
        return self._ocr
    
    def ocr_cell(self, cell_img):
        """OCR single cell"""
        if cell_img is None or cell_img.size == 0:
            return {'text': '', 'confidence': 0.0, 'is_empty': True}
        
        try:
            ocr = self.get_ocr()
            result = ocr.predict(cell_img)
            
            # Parse results
            results_list = list(result)
            if results_list and len(results_list) > 0:
                ocr_result = results_list[0]
                
                # Extract texts
                if 'dt_polys' in ocr_result and 'rec_texts' in ocr_result:
                    texts = ocr_result['rec_texts']
                    scores = ocr_result['rec_scores']
                    
                    if texts:
                        combined_text = ' '.join(texts)
                        avg_conf = sum(scores) / len(scores) if scores else 0.0
                        
                        return {
                            'text': combined_text.strip(),
                            'confidence': float(avg_conf),
                            'is_empty': False
                        }
            
            return {'text': '', 'confidence': 0.0, 'is_empty': True}
        
        except Exception as e:
            print(f"  ⚠️ OCR Error: {e}")
            return {'text': '', 'confidence': 0.0, 'is_empty': True}


def ocr_all_cells(image, h_lines, v_lines, verbose=True):
    """OCR all cells in grid"""
    num_rows = len(h_lines) - 1
    num_cols = len(v_lines) - 1
    
    if verbose:
        print(f"  Grid: {num_rows} rows × {num_cols} columns = {num_rows * num_cols} cells")
    
    # Initialize OCR engine
    ocr_engine = PaddleOCREngine()
    
    # Initialize table
    table = []
    
    # Process each row
    for row in range(num_rows):
        if verbose and row % 2 == 0:
            print(f"  Processing row {row+1}/{num_rows}...", end='\r')
        
        row_data = {
            'row': row,
            'cells': []
        }
        
        # Process each cell in row
        for col in range(num_cols):
            # Extract cell
            cell_img = extract_cell(
                image,
                h_lines[row],
                h_lines[row + 1],
                v_lines[col],
                v_lines[col + 1]
            )
            
            # Preprocess cell
            cell_processed = preprocess_cell(cell_img)
            
            # OCR cell
            cell_result = ocr_engine.ocr_cell(cell_processed)
            
            row_data['cells'].append({
                'col': col,
                'text': cell_result['text'],
                'confidence': cell_result['confidence'],
                'is_empty': cell_result['is_empty']
            })
        
        table.append(row_data)
    
    if verbose:
        print(f"  ✓ Processed all {num_rows * num_cols} cells")
    
    return table


# ============================================================================
# STAGE 6: POST-PROCESSING
# ============================================================================

def identify_headers(table):
    """Identify header rows based on content"""
    header_keywords = ['kode', 'nama', 'jumlah', 'bangunan', 'wilayah', 'shift', 'muatan']
    
    for row_idx, row in enumerate(table):
        # Check if row contains many header keywords
        keyword_count = 0
        for cell in row['cells']:
            text_lower = cell['text'].lower()
            if any(kw in text_lower for kw in header_keywords):
                keyword_count += 1
        
        # If > 30% cells have keywords, mark as header
        if keyword_count > len(row['cells']) * 0.3:
            row['is_header'] = True
        else:
            row['is_header'] = False
    
    return table


def clean_text(text):
    """Clean OCR text"""
    if not text:
        return ''
    
    # Remove leading brackets
    if text.startswith('['):
        text = text[1:]
    
    # Clean whitespace
    text = ' '.join(text.split())
    
    return text.strip()


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def process_cell_by_cell(input_path, output_path=None, save_cells=False, verbose=True):
    """
    Complete pipeline dengan cell-by-cell OCR
    """
    start_time = time.time()
    
    if verbose:
        print('='*100)
        print('CELL-BY-CELL OCR PIPELINE v1.0')
        print('='*100)
    
    # ========== Stage 1: Load Image ==========
    if verbose:
        print('\n[Stage 1/6] Loading image...')
    
    image = load_image(str(input_path))
    if verbose:
        print(f'  ✓ Loaded: {image.shape}')
    
    # ========== Stage 2: Detect BLOK III ==========
    if verbose:
        print('\n[Stage 2/6] Detecting BLOK III...')
    
    stage2_start = time.time()
    bbox = detect_table_region(image, use_rapid=False, rapid_detector=None)
    
    if not bbox:
        raise ValueError("BLOK III not detected!")
    
    blok3_cropped = crop_table(image, bbox)
    stage2_time = time.time() - stage2_start
    
    if verbose:
        print(f'  ✓ BLOK III cropped: {blok3_cropped.shape}')
        print(f'  ⏱ Time: {stage2_time:.2f}s')
    
    # ========== Stage 3: Detect Grid ==========
    if verbose:
        print('\n[Stage 3/6] Detecting grid structure...')
    
    stage3_start = time.time()
    h_lines = detect_horizontal_lines(blok3_cropped)
    v_lines = detect_vertical_lines(blok3_cropped)
    stage3_time = time.time() - stage3_start
    
    if verbose:
        print(f'  ✓ Horizontal lines: {len(h_lines)}')
        print(f'  ✓ Vertical lines: {len(v_lines)}')
        print(f'  ⏱ Time: {stage3_time:.2f}s')
    
    # ========== Stage 4: OCR All Cells ==========
    if verbose:
        print('\n[Stage 4/6] OCR-ing each cell (this will take ~3 minutes)...')
    
    stage4_start = time.time()
    table = ocr_all_cells(blok3_cropped, h_lines, v_lines, verbose=verbose)
    stage4_time = time.time() - stage4_start
    
    if verbose:
        print(f'  ⏱ Time: {stage4_time:.2f}s')
    
    # ========== Stage 5: Post-processing ==========
    if verbose:
        print('\n[Stage 5/6] Post-processing...')
    
    table = identify_headers(table)
    
    # Clean text in all cells
    for row in table:
        for cell in row['cells']:
            cell['text'] = clean_text(cell['text'])
    
    if verbose:
        print('  ✓ Headers identified and text cleaned')
    
    # ========== Stage 6: Export Results ==========
    total_time = time.time() - start_time
    
    results = {
        'metadata': {
            'method': 'Cell-by-Cell OCR Pipeline v1.0',
            'input_file': str(input_path),
            'grid_size': f"{len(h_lines)-1} rows × {len(v_lines)-1} columns",
            'total_cells': (len(h_lines)-1) * (len(v_lines)-1),
            'total_time_seconds': round(total_time, 2),
            'stage_times': {
                'stage2_blok3_detect': round(stage2_time, 2),
                'stage3_grid_detect': round(stage3_time, 2),
                'stage4_cell_ocr': round(stage4_time, 2)
            }
        },
        'table': table
    }
    
    # Save results
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        if verbose:
            print(f'\n✓ Results saved to: {output_path}')
    
    if verbose:
        print(f'\n✓ PIPELINE COMPLETED in {total_time:.2f}s')
        print('='*100)
    
    return results


# ============================================================================
# CLI INTERFACE
# ============================================================================

if __name__ == '__main__':
    input_file = Path('contoh gambar/1.png')
    output_file = Path('experiments/final_system/CELL_BY_CELL_RESULTS.json')
    
    results = process_cell_by_cell(
        input_path=input_file,
        output_path=output_file,
        save_cells=False,
        verbose=True
    )
    
    # Print sample results
    print('\n' + '='*100)
    print('SAMPLE RESULTS (First 3 data rows, excluding headers)')
    print('='*100)
    
    data_rows = [row for row in results['table'] if not row.get('is_header', False)]
    
    for row in data_rows[:3]:
        print(f"\nRow {row['row']}:")
        for cell in row['cells'][:8]:  # First 8 cells
            print(f"  Col {cell['col']:2d}: \"{cell['text']:30s}\" (conf: {cell['confidence']:.1%})")
