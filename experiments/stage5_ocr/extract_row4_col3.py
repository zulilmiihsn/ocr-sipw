"""
Extract Row 4, Column 3 cell
"""

import sys
from pathlib import Path
import cv2

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from experiments.stage4_cell_segmentation.test_hybrid_segmentation import (
    detect_horizontal_lines,
    detect_vertical_lines,
    extract_cells_from_grid
)

def extract_row4_col3():
    print('Extracting Row 4, Column 3...')
    
    # Load image
    image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
    image = cv2.imread(str(image_path))
    
    # Extract cells
    h_lines = detect_horizontal_lines(image, min_line_length=image.shape[1] // 3)
    v_lines = detect_vertical_lines(image, min_line_length=image.shape[0] // 5)
    cells = extract_cells_from_grid(image, h_lines, v_lines, margin=5)
    
    # Get row 4, col 3
    if (4, 3) in cells:
        cell_img = cells[(4, 3)]
        
        # Save with proper filename
        output_dir = project_root / 'experiments' / 'results' / 'row4_cells'
        output_dir.mkdir(exist_ok=True)
        
        output_path = output_dir / 'row4_col03_Nama_SLS_Non-SLS.jpg'
        cv2.imwrite(str(output_path), cell_img)
        
        h, w = cell_img.shape[:2]
        print(f'OK Saved: {output_path.name}')
        print(f'   Size: {w} x {h} pixels')
        print(f'   Full path: {output_path}')
        
        return True
    else:
        print('ERROR: Cell (4, 3) not found')
        return False

if __name__ == '__main__':
    success = extract_row4_col3()
    sys.exit(0 if success else 1)
