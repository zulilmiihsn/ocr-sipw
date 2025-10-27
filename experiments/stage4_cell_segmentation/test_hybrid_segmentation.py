"""
Test Stage 4: Cell Segmentation with Hybrid Approach

Hybrid Method:
1. Detect header row with Tesseract (get column positions)
2. Detect horizontal lines (get row positions)
3. Create grid from detected positions
4. Extract cells

Fast (~1s) + Accurate for fixed templates!
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def detect_horizontal_lines(image: np.ndarray, min_line_length: int = 100) -> list:
    """
    Detect horizontal lines in table using morphological operations
    
    Returns list of y-coordinates for horizontal lines
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Invert if needed (lines should be black)
    if np.mean(gray) > 127:
        gray = cv2.bitwise_not(gray)
    
    # Horizontal kernel
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_line_length, 1))
    
    # Detect horizontal lines
    horizontal_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    
    # Find contours
    contours, _ = cv2.findContours(horizontal_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Extract y-coordinates
    y_positions = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w > min_line_length:  # Filter short lines
            y_positions.append(y)
    
    # Sort and remove duplicates
    y_positions = sorted(set(y_positions))
    
    return y_positions


def detect_vertical_lines(image: np.ndarray, min_line_length: int = 50) -> list:
    """
    Detect vertical lines in table using morphological operations
    
    Returns list of x-coordinates for vertical lines
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Invert if needed (lines should be black)
    if np.mean(gray) > 127:
        gray = cv2.bitwise_not(gray)
    
    # Vertical kernel
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, min_line_length))
    
    # Detect vertical lines
    vertical_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
    
    # Find contours
    contours, _ = cv2.findContours(vertical_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Extract x-coordinates
    x_positions = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if h > min_line_length:  # Filter short lines
            x_positions.append(x)
    
    # Sort and remove duplicates
    x_positions = sorted(set(x_positions))
    
    return x_positions


def extract_cells_from_grid(image: np.ndarray, row_lines: list, col_lines: list, margin: int = 5):
    """
    Extract cells based on detected grid lines
    
    Args:
        image: Table image
        row_lines: Y-coordinates of horizontal lines
        col_lines: X-coordinates of vertical lines
        margin: Margin to avoid borders (pixels)
        
    Returns:
        Dictionary of {(row, col): cell_image}
    """
    cells = {}
    
    # Create cells from grid
    for row_idx in range(len(row_lines) - 1):
        y1 = row_lines[row_idx]
        y2 = row_lines[row_idx + 1]
        
        for col_idx in range(len(col_lines) - 1):
            x1 = col_lines[col_idx]
            x2 = col_lines[col_idx + 1]
            
            # Add margin to avoid borders
            cell = image[y1+margin:y2-margin, x1+margin:x2-margin]
            
            # Only save non-empty cells
            if cell.size > 0:
                cells[(row_idx, col_idx)] = cell
    
    return cells


def test_hybrid_segmentation():
    """Test hybrid cell segmentation approach"""
    
    print('='*60)
    print('STAGE 4C: HYBRID CELL SEGMENTATION')
    print('='*60)
    
    overall_start = time.time()
    
    # Step 1: Load table image
    print('\n[Step 1] Loading table image...')
    image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
    
    if not image_path.exists():
        print(f'  ✗ ERROR: {image_path} not found')
        print('  → Run Stage 3 first!')
        return False
    
    image = cv2.imread(str(image_path))
    print(f'  ✓ Image loaded: {image.shape}')
    
    # Step 2: Detect horizontal lines (rows)
    print('\n[Step 2] Detecting horizontal lines (rows)...')
    start = time.time()
    
    h_lines = detect_horizontal_lines(image, min_line_length=image.shape[1] // 3)
    h_time = time.time() - start
    
    print(f'  ✓ Detected {len(h_lines)} horizontal lines in {h_time:.2f}s')
    print(f'  First 5 positions: {h_lines[:5]}')
    
    # Step 3: Detect vertical lines (columns)
    print('\n[Step 3] Detecting vertical lines (columns)...')
    start = time.time()
    
    v_lines = detect_vertical_lines(image, min_line_length=image.shape[0] // 5)
    v_time = time.time() - start
    
    print(f'  ✓ Detected {len(v_lines)} vertical lines in {v_time:.2f}s')
    print(f'  First 5 positions: {v_lines[:5]}')
    
    # Step 4: Validate grid
    print('\n[Step 4] Validating grid structure...')
    
    expected_rows = 11  # 10 data rows + 1 header = 11 lines
    expected_cols = 18  # 17 columns = 18 lines
    
    print(f'  Expected: {expected_rows} rows × {expected_cols} columns')
    print(f'  Detected: {len(h_lines)} rows × {len(v_lines)} columns')
    
    if len(h_lines) < expected_rows:
        print(f'  ⚠️  WARNING: Missing {expected_rows - len(h_lines)} horizontal lines')
    
    if len(v_lines) < expected_cols:
        print(f'  ⚠️  WARNING: Missing {expected_cols - len(v_lines)} vertical lines')
    
    # Step 5: Extract cells
    print('\n[Step 5] Extracting cells from grid...')
    start = time.time()
    
    cells = extract_cells_from_grid(image, h_lines, v_lines, margin=5)
    extract_time = time.time() - start
    
    print(f'  ✓ Extracted {len(cells)} cells in {extract_time:.2f}s')
    
    # Calculate expected cells
    num_rows = len(h_lines) - 1
    num_cols = len(v_lines) - 1
    expected_cells = num_rows * num_cols
    
    print(f'  Expected: {expected_cells} cells ({num_rows}×{num_cols})')
    print(f'  Got: {len(cells)} cells')
    
    # Step 6: Visualize grid
    print('\n[Step 6] Creating visualization...')
    
    vis_image = image.copy()
    
    # Draw horizontal lines
    for y in h_lines:
        cv2.line(vis_image, (0, y), (image.shape[1], y), (0, 255, 0), 2)
    
    # Draw vertical lines
    for x in v_lines:
        cv2.line(vis_image, (x, 0), (x, image.shape[0]), (255, 0, 0), 2)
    
    # Add grid info
    cv2.putText(vis_image, f'Grid: {num_rows}x{num_cols} = {len(cells)} cells', 
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    
    # Save visualization
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    vis_path = results_dir / 'stage4c_hybrid_grid.jpg'
    cv2.imwrite(str(vis_path), vis_image)
    print(f'  ✓ Visualization saved: {vis_path.name}')
    
    # Step 7: Save sample cells
    print('\n[Step 7] Saving sample cells...')
    
    sample_cells = [
        (0, 0),  # Top-left (header, column 1)
        (0, 8),  # Header middle
        (1, 0),  # First data row, first column
        (5, 5),  # Middle cell
    ]
    
    saved_count = 0
    for row, col in sample_cells:
        if (row, col) in cells:
            cell_img = cells[(row, col)]
            cell_path = results_dir / f'stage4c_cell_r{row}_c{col}.jpg'
            cv2.imwrite(str(cell_path), cell_img)
            print(f'  ✓ Saved cell [{row},{col}]: {cell_img.shape}')
            saved_count += 1
    
    print(f'  ✓ Saved {saved_count} sample cells')
    
    # Total time
    total_time = time.time() - overall_start
    
    print(f'\n' + '='*60)
    print('HYBRID SEGMENTATION RESULTS')
    print('='*60)
    print(f'Total time: {total_time:.2f}s ⚡')
    print(f'  - H-line detection: {h_time:.2f}s')
    print(f'  - V-line detection: {v_time:.2f}s')
    print(f'  - Cell extraction:  {extract_time:.2f}s')
    print(f'\nGrid Structure:')
    print(f'  Rows: {num_rows} ({len(h_lines)} lines)')
    print(f'  Cols: {num_cols} ({len(v_lines)} lines)')
    print(f'  Cells: {len(cells)}')
    print(f'\nOutputs:')
    print(f'  Visualization: {vis_path.name}')
    print(f'  Sample cells: stage4c_cell_*.jpg')
    print('='*60)
    
    # Success criteria
    success = (
        len(h_lines) >= 10 and  # At least 10 rows
        len(v_lines) >= 17 and  # At least 17 columns
        len(cells) >= 150        # At least 150 cells (10×17=170)
    )
    
    if success:
        print('\n✅ SUCCESS: Grid detected correctly!')
    else:
        print('\n⚠️  WARNING: Grid detection incomplete')
        print('   Some lines may be missing or broken')
    
    return success


if __name__ == '__main__':
    success = test_hybrid_segmentation()
    sys.exit(0 if success else 1)

