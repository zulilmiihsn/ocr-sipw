"""
Test Stage 4: Cell Segmentation
Test grid detection dan cell extraction
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.ocr.cell_extractor import extract_cell_images
from src.utils.pdf_handler import load_image
from src.ocr.preprocessor import preprocess_image
from src.ocr.table_detector import detect_table_region, crop_table
from src.ocr.rapid_table_detector import RapidTableDetectorWrapper
import cv2
import numpy as np


def test_cell_segmentation():
    """Test cell extraction dari table"""
    
    print("=" * 60)
    print("STAGE 4: CELL SEGMENTATION TEST")
    print("=" * 60)
    
    # Load dan preprocess image
    test_image_path = "data/templates/sample.jpg"
    
    if not os.path.exists(test_image_path):
        print(f"⚠️  Test image not found: {test_image_path}")
        return
    
    print(f"\n📷 Loading image...")
    image = load_image(test_image_path)
    
    print(f"🔄 Preprocessing...")
    processed = preprocess_image(image, full_pipeline=True)
    
    # Detect table (need Stage 3)
    print(f"🔄 Detecting table region...")
    try:
        rapid_detector = RapidTableDetectorWrapper(use_cuda=False)
        bbox = detect_table_region(processed, use_rapid=True, rapid_detector=rapid_detector)
        
        if bbox is None:
            print(f"❌ Table detection failed")
            return
        
        table_image = crop_table(processed, bbox)
        print(f"  ✅ Table detected: {table_image.shape}")
        
        # Save table image
        results_dir = "experiments/results"
        os.makedirs(results_dir, exist_ok=True)
        cv2.imwrite(f"{results_dir}/stage4_table_detected.jpg", table_image)
        
    except Exception as e:
        print(f"❌ Table detection error: {e}")
        print(f"⚠️  Using full image as table (fallback)")
        table_image = processed
    
    # Extract cells
    print(f"\n🔄 Extracting cells...")
    try:
        cells = extract_cell_images(table_image)
        
        print(f"  ✅ Extracted {len(cells)} cells")
        
        # Validate grid structure
        rows = len(set([c.row for c in cells]))
        cols = len(set([c.col for c in cells]))
        print(f"  📊 Grid structure: {rows} × {cols}")
        
        if rows == 10 and cols == 17:
            print(f"  ✅ Grid structure CORRECT (expected 10×17)")
        else:
            print(f"  ⚠️  Grid structure MISMATCH (expected 10×17)")
        
        # Save sample cells
        results_dir = "experiments/results"
        sample_cells = cells[:20]  # first 20 cells
        
        print(f"\n💾 Saving sample cells...")
        for i, cell in enumerate(sample_cells):
            output_path = f"{results_dir}/stage4_cell_r{cell.row}_c{cell.col}.jpg"
            cv2.imwrite(output_path, cell.image)
        
        print(f"  ✅ Saved {len(sample_cells)} sample cells")
        
        # Visualize grid
        print(f"\n🎨 Creating grid visualization...")
        vis_image = cv2.cvtColor(table_image, cv2.COLOR_GRAY2BGR) if len(table_image.shape) == 2 else table_image.copy()
        
        for cell in cells:
            # Draw rectangle
            x, y, w, h = cell.x, cell.y, cell.width, cell.height
            cv2.rectangle(vis_image, (x, y), (x+w, y+h), (0, 255, 0), 1)
            
            # Draw cell index
            text = f"({cell.row},{cell.col})"
            cv2.putText(vis_image, text, (x+5, y+15), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 0, 0), 1)
        
        cv2.imwrite(f"{results_dir}/stage4_grid_visualization.jpg", vis_image)
        print(f"  ✅ Saved: stage4_grid_visualization.jpg")
        
    except Exception as e:
        print(f"❌ Cell extraction error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Stage 4 testing completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_cell_segmentation()


