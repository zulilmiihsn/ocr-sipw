"""
Visualize Cell Mapping for Row 4

Show how cells are detected and extracted in row 4
"""

import sys
from pathlib import Path
import cv2
import numpy as np

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


def visualize_row4_cells():
    """Visualize cell mapping for row 4"""
    
    print('='*70)
    print('CELL MAPPING VISUALIZATION - ROW 4')
    print('='*70)
    
    # Load image
    print('\n[1] Loading table image...')
    image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
    
    if not image_path.exists():
        print(f'  X ERROR: {image_path} not found')
        return False
    
    image = cv2.imread(str(image_path))
    print(f'  OK Image: {image.shape}')
    
    # Extract cells
    print('\n[2] Extracting cells...')
    h_lines = detect_horizontal_lines(image, min_line_length=image.shape[1] // 3)
    v_lines = detect_vertical_lines(image, min_line_length=image.shape[0] // 5)
    cells = extract_cells_from_grid(image, h_lines, v_lines, margin=5)
    print(f'  OK {len(cells)} cells extracted')
    
    # Filter row 4 cells
    print('\n[3] Filtering row 4 cells...')
    row4_cells = {(row, col): img for (row, col), img in cells.items() if row == 4}
    print(f'  OK Found {len(row4_cells)} cells in row 4')
    
    # Create output directory
    results_dir = project_root / 'experiments' / 'results' / 'row4_cells'
    results_dir.mkdir(exist_ok=True)
    
    # Save individual cells
    print('\n[4] Saving individual cell images...')
    for (row, col), cell_img in sorted(row4_cells.items(), key=lambda x: x[0][1]):
        col_name = COLUMN_HEADERS[col] if col < len(COLUMN_HEADERS) else f'Col{col}'
        filename = f'row4_col{col:02d}_{col_name.replace(" ", "_")}.jpg'
        output_path = results_dir / filename
        
        cv2.imwrite(str(output_path), cell_img)
        h, w = cell_img.shape[:2]
        print(f'  ✓ Cell (4, {col:2d}) - {col_name:20s} - Size: {w}x{h}px - {filename}')
    
    # Create grid visualization
    print('\n[5] Creating grid visualization...')
    
    # Draw grid on original image
    vis_image = image.copy()
    
    # Draw all horizontal lines
    for y in h_lines:
        cv2.line(vis_image, (0, y), (vis_image.shape[1], y), (0, 255, 0), 2)
    
    # Draw all vertical lines
    for x in v_lines:
        cv2.line(vis_image, (x, 0), (x, vis_image.shape[0]), (255, 0, 0), 2)
    
    # Highlight row 4 with thicker red lines
    if len(h_lines) > 4:
        # Top border of row 4
        y_top = h_lines[4]
        cv2.line(vis_image, (0, y_top), (vis_image.shape[1], y_top), (0, 0, 255), 4)
        
        # Bottom border of row 4
        if len(h_lines) > 5:
            y_bottom = h_lines[5]
            cv2.line(vis_image, (0, y_bottom), (vis_image.shape[1], y_bottom), (0, 0, 255), 4)
            
            # Add text label
            cv2.putText(vis_image, 'ROW 4', (10, y_top + 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
    
    # Save grid visualization
    grid_path = results_dir / 'row4_grid_visualization.jpg'
    cv2.imwrite(str(grid_path), vis_image)
    print(f'  ✓ Grid visualization saved: {grid_path.name}')
    
    # Create cell montage (all cells in one image)
    print('\n[6] Creating cell montage...')
    
    # Get cells in order
    sorted_cells = sorted(row4_cells.items(), key=lambda x: x[0][1])
    
    if sorted_cells:
        # Calculate montage dimensions
        max_height = max(img.shape[0] for _, img in sorted_cells)
        total_width = sum(img.shape[1] for _, img in sorted_cells)
        
        # Create blank canvas
        montage = np.ones((max_height + 60, total_width, 3), dtype=np.uint8) * 255
        
        # Paste cells
        x_offset = 0
        for (row, col), cell_img in sorted_cells:
            h, w = cell_img.shape[:2]
            
            # Paste cell
            montage[30:30+h, x_offset:x_offset+w] = cell_img
            
            # Add column label
            col_name = COLUMN_HEADERS[col] if col < len(COLUMN_HEADERS) else f'C{col}'
            label = f'{col}'
            cv2.putText(montage, label, (x_offset + 5, 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            
            # Draw separator
            cv2.line(montage, (x_offset, 0), (x_offset, max_height + 60), (200, 200, 200), 1)
            
            x_offset += w
        
        montage_path = results_dir / 'row4_montage.jpg'
        cv2.imwrite(str(montage_path), montage)
        print(f'  ✓ Montage saved: {montage_path.name}')
    
    # Print cell mapping details
    print('\n[7] Cell Mapping Details for Row 4:')
    print('='*70)
    print(f'{"Col":<5} {"Column Name":<25} {"Width":<8} {"Height":<8} {"Pixels":<10}')
    print('-'*70)
    
    for (row, col), cell_img in sorted(row4_cells.items(), key=lambda x: x[0][1]):
        col_name = COLUMN_HEADERS[col] if col < len(COLUMN_HEADERS) else f'Column {col}'
        h, w = cell_img.shape[:2]
        pixels = h * w
        print(f'{col:<5} {col_name:<25} {w:<8} {h:<8} {pixels:<10,}')
    
    print('='*70)
    print(f'\nAll row 4 cells saved to: {results_dir}')
    print('Files created:')
    print(f'  - {len(row4_cells)} individual cell images')
    print(f'  - 1 grid visualization')
    print(f'  - 1 montage (all cells combined)')
    print('='*70)
    
    return True


if __name__ == '__main__':
    success = visualize_row4_cells()
    sys.exit(0 if success else 1)
