"""
Test Stage 4: Cell Segmentation with PaddleOCR PP-Structure

Production-ready table recognition from PaddlePaddle.
Accuracy: ~95-96%
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_paddleocr_table():
    """Test PaddleOCR PP-Structure for cell detection"""
    
    print('='*60)
    print('STAGE 4B: PADDLEOCR PP-STRUCTURE')
    print('='*60)
    
    overall_start = time.time()
    
    # Step 1: Install check
    print('\n[Step 1] Checking dependencies...')
    try:
        from paddleocr import PPStructureV3
        print('  ✓ PaddleOCR library available (v3)')
    except ImportError:
        print('  ✗ ERROR: paddleocr not installed')
        print('  → Install: pip install paddleocr')
        return False
    
    # Step 2: Initialize table engine
    print('\n[Step 2] Initializing PaddleOCR table engine...')
    start = time.time()
    
    try:
        table_engine = PPStructureV3(
            use_table_recognition=True  # Enable table recognition
        )
        
        load_time = time.time() - start
        print(f'  ✓ Engine initialized in {load_time:.2f}s')
        
    except Exception as e:
        print(f'  ✗ ERROR initializing engine: {e}')
        return False
    
    # Step 3: Load table image
    print('\n[Step 3] Loading table image...')
    image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
    
    if not image_path.exists():
        print(f'  ✗ ERROR: {image_path} not found')
        print('  → Run Stage 3 first!')
        return False
    
    image = cv2.imread(str(image_path))
    print(f'  ✓ Image loaded: {image.shape}')
    
    # Step 4: Detect table structure
    print('\n[Step 4] Detecting table structure with AI...')
    start = time.time()
    
    try:
        result = table_engine.predict(image)
        
        detect_time = time.time() - start
        print(f'  ✓ Detection completed in {detect_time:.2f}s')
        
    except Exception as e:
        print(f'  ✗ ERROR during detection: {e}')
        import traceback
        traceback.print_exc()
        return False
    
    # Step 5: Analyze results
    print('\n[Step 5] Analyzing detected structure...')
    
    print(f'  Results type: {type(result)}')
    print(f'  Number of elements: {len(result)}')
    
    # Parse results
    tables_found = 0
    cells_found = 0
    
    for i, element in enumerate(result):
        print(f'\n  Element {i}:')
        print(f'    Type: {element.get("type", "unknown")}')
        
        if 'bbox' in element:
            print(f'    BBox: {element["bbox"]}')
        
        if element.get('type') == 'table':
            tables_found += 1
            
            # Check for table structure
            if 'res' in element:
                table_data = element['res']
                print(f'    Table data keys: {table_data.keys() if isinstance(table_data, dict) else type(table_data)}')
                
                # Try to extract cells
                if isinstance(table_data, dict):
                    if 'html' in table_data:
                        print(f'    HTML length: {len(table_data["html"])}')
                    if 'cell_bbox' in table_data:
                        cells = table_data['cell_bbox']
                        cells_found = len(cells)
                        print(f'    Cells detected: {cells_found}')
    
    print(f'\n  Summary:')
    print(f'    Tables detected: {tables_found}')
    print(f'    Cells detected: {cells_found}')
    
    # Step 6: Visualize results
    print('\n[Step 6] Creating visualization...')
    
    vis_image = image.copy()
    
    for element in result:
        if 'bbox' in element:
            bbox = element['bbox']
            
            # Draw bbox
            x1, y1, x2, y2 = [int(v) for v in bbox]
            
            color = (0, 255, 0) if element.get('type') == 'table' else (255, 0, 0)
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), color, 2)
            
            # Add label
            label = element.get('type', 'unknown')
            cv2.putText(vis_image, label, (x1, y1-5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Draw cells if available
        if element.get('type') == 'table' and 'res' in element:
            table_data = element['res']
            
            if isinstance(table_data, dict) and 'cell_bbox' in table_data:
                cells = table_data['cell_bbox']
                
                for cell in cells:
                    # Cell format might vary, try different structures
                    try:
                        if isinstance(cell, (list, tuple)) and len(cell) >= 4:
                            x1, y1, x2, y2 = [int(v) for v in cell[:4]]
                            cv2.rectangle(vis_image, (x1, y1), (x2, y2), (0, 0, 255), 1)
                    except:
                        pass
    
    # Save visualization
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    vis_path = results_dir / 'stage4b_paddleocr_table.jpg'
    cv2.imwrite(str(vis_path), vis_image)
    print(f'  ✓ Visualization saved: {vis_path.name}')
    
    # Save detailed results
    import json
    
    # Convert result to JSON-serializable format
    try:
        result_json = []
        for element in result:
            elem_dict = {}
            for key, value in element.items():
                if isinstance(value, np.ndarray):
                    elem_dict[key] = value.tolist()
                elif key == 'img':
                    elem_dict[key] = f"<image {value.shape}>"
                else:
                    elem_dict[key] = str(value)
            result_json.append(elem_dict)
        
        json_path = results_dir / 'stage4b_paddleocr_details.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result_json, f, indent=2, ensure_ascii=False)
        print(f'  ✓ Details saved: {json_path.name}')
    except Exception as e:
        print(f'  ⚠️  Could not save JSON: {e}')
    
    # Total time
    total_time = time.time() - overall_start
    
    print(f'\n' + '='*60)
    print('PADDLEOCR PP-STRUCTURE RESULTS')
    print('='*60)
    print(f'Total time: {total_time:.2f}s')
    print(f'  - Engine init:   {load_time:.2f}s')
    print(f'  - Detection:     {detect_time:.2f}s')
    print(f'\nDetected:')
    print(f'  Tables: {tables_found}')
    print(f'  Cells: {cells_found}')
    print(f'\nOutputs:')
    print(f'  Visualization: {vis_path.name}')
    print(f'  Details: stage4b_paddleocr_details.json')
    print('='*60)
    
    return True


if __name__ == '__main__':
    success = test_paddleocr_table()
    sys.exit(0 if success else 1)
