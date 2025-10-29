"""
Test: Full Document OCR with PaddleOCR

Strategy:
1. Load BLOK III table (full image)
2. Simple preprocessing (optional resize for better detection)
3. Run PaddleOCR FULL detection + recognition
4. Output ALL detected text with:
   - Bounding box coordinates
   - Text content
   - Confidence score
5. Visualize on image with boxes

This will show us EXACTLY what PaddleOCR sees!
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_full_document_ocr():
    """Run PaddleOCR on full document and output all detections"""
    
    print('='*80)
    print('FULL DOCUMENT OCR TEST - PaddleOCR PP-OCRv5')
    print('='*80)
    print('Purpose: See EXACTLY what PaddleOCR detects in the full table')
    print('='*80)
    
    # Load image
    print('\n[Step 1] Loading BLOK III table...')
    image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
    
    if not image_path.exists():
        print(f'  X ERROR: {image_path} not found')
        return False
    
    image = cv2.imread(str(image_path))
    print(f'  OK Image loaded: {image.shape}')
    
    # Simple preprocessing (optional - just for better detection)
    print('\n[Step 2] Simple preprocessing...')
    print('  (No over-processing - keeping it simple!)')
    
    # Just keep original or slight resize if too small
    h, w = image.shape[:2]
    if h < 1000:
        scale = 1000 / h
        new_w = int(w * scale)
        new_h = 1000
        image_processed = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        print(f'  - Upscaled to: {image_processed.shape}')
    else:
        image_processed = image.copy()
        print(f'  - Using original size: {image_processed.shape}')
    
    # Load PaddleOCR
    print('\n[Step 3] Loading PaddleOCR...')
    start = time.time()
    
    from paddleocr import PaddleOCR
    
    ocr = PaddleOCR(
        lang='en',
        use_textline_orientation=False
    )
    
    load_time = time.time() - start
    print(f'  OK Model loaded in {load_time:.2f}s')
    
    # Run OCR
    print('\n[Step 4] Running FULL OCR on entire table...')
    print('  (This will detect ALL text regions)')
    start = time.time()
    
    result = ocr.predict(image_processed)
    
    ocr_time = time.time() - start
    print(f'  OK OCR completed in {ocr_time:.2f}s')
    
    # Parse results
    print('\n[Step 5] Parsing results...')
    
    # Debug: check result structure
    print(f'  DEBUG: type(result) = {type(result)}')
    if result:
        print(f'  DEBUG: len(result) = {len(result)}')
        if len(result) > 0:
            print(f'  DEBUG: type(result[0]) = {type(result[0])}')
            print(f'  DEBUG: result[0] keys = {result[0].keys() if isinstance(result[0], dict) else "NOT A DICT"}')
    
    all_detections = []
    
    # Handle new API format (dictionary with 'dt_polys', 'rec_texts', 'rec_scores')
    if result and len(result) > 0 and isinstance(result[0], dict):
        dt_polys = result[0].get('dt_polys', [])
        rec_texts = result[0].get('rec_texts', [])
        rec_scores = result[0].get('rec_scores', [])
        
        print(f'  DEBUG: Found {len(dt_polys)} polygons, {len(rec_texts)} texts, {len(rec_scores)} scores')
        
        for idx, (bbox, text, confidence) in enumerate(zip(dt_polys, rec_texts, rec_scores)):
            # Calculate center and dimensions
            bbox_array = np.array(bbox)
            x_min = int(bbox_array[:, 0].min())
            y_min = int(bbox_array[:, 1].min())
            x_max = int(bbox_array[:, 0].max())
            y_max = int(bbox_array[:, 1].max())
            
            center_x = (x_min + x_max) // 2
            center_y = (y_min + y_max) // 2
            width = x_max - x_min
            height = y_max - y_min
            
            detection_info = {
                'id': idx + 1,
                'text': text,
                'confidence': float(confidence),
                'bbox': {
                    'top_left': [x_min, y_min],
                    'bottom_right': [x_max, y_max],
                    'center': [center_x, center_y],
                    'width': width,
                    'height': height
                },
                'bbox_coords': bbox.tolist() if isinstance(bbox, np.ndarray) else bbox
            }
            
            all_detections.append(detection_info)
    
    print(f'  OK Found {len(all_detections)} text regions!')
    
    # Save results
    print('\n[Step 6] Saving results...')
    
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    # Save JSON
    json_output = {
        'image_info': {
            'path': str(image_path),
            'original_size': [w, h],
            'processed_size': list(image_processed.shape[:2]),
            'total_detections': len(all_detections)
        },
        'timing': {
            'model_load': f'{load_time:.2f}s',
            'ocr_process': f'{ocr_time:.2f}s',
            'total': f'{load_time + ocr_time:.2f}s'
        },
        'detections': all_detections
    }
    
    json_path = results_dir / 'full_document_ocr_results.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)
    print(f'  OK JSON saved: {json_path.name}')
    
    # Save detailed text output
    txt_path = results_dir / 'full_document_ocr_detections.txt'
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('='*80 + '\n')
        f.write('FULL DOCUMENT OCR - ALL DETECTIONS\n')
        f.write('='*80 + '\n\n')
        f.write(f'Total detections: {len(all_detections)}\n')
        f.write(f'Image size: {image_processed.shape}\n\n')
        f.write('='*80 + '\n')
        f.write('DETECTION LIST (sorted by Y position)\n')
        f.write('='*80 + '\n\n')
        
        # Sort by Y position (top to bottom)
        sorted_detections = sorted(all_detections, key=lambda x: x['bbox']['center'][1])
        
        for det in sorted_detections:
            f.write(f"ID: {det['id']:3d}\n")
            f.write(f"Text: \"{det['text']}\"\n")
            f.write(f"Confidence: {det['confidence']:.1%}\n")
            f.write(f"Position: ({det['bbox']['center'][0]}, {det['bbox']['center'][1]})\n")
            f.write(f"Size: {det['bbox']['width']}x{det['bbox']['height']} px\n")
            f.write(f"BBox: ({det['bbox']['top_left'][0]}, {det['bbox']['top_left'][1]}) to ({det['bbox']['bottom_right'][0]}, {det['bbox']['bottom_right'][1]})\n")
            f.write('-'*80 + '\n\n')
    
    print(f'  OK Text list saved: {txt_path.name}')
    
    # Visualize - draw boxes on image
    print('\n[Step 7] Creating visualization...')
    
    vis_image = image_processed.copy()
    
    for det in all_detections:
        # Draw bounding box
        bbox_coords = det['bbox_coords']
        pts = np.array(bbox_coords, dtype=np.int32)
        
        # Color based on confidence
        conf = det['confidence']
        if conf >= 0.9:
            color = (0, 255, 0)  # Green - high confidence
        elif conf >= 0.7:
            color = (0, 255, 255)  # Yellow - medium
        else:
            color = (0, 0, 255)  # Red - low confidence
        
        # Draw polygon
        cv2.polylines(vis_image, [pts], True, color, 2)
        
        # Draw ID number
        x, y = det['bbox']['top_left']
        cv2.putText(vis_image, str(det['id']), (x, y-5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    vis_path = results_dir / 'full_document_ocr_visualization.jpg'
    cv2.imwrite(str(vis_path), vis_image)
    print(f'  OK Visualization saved: {vis_path.name}')
    
    # Print summary
    print('\n' + '='*80)
    print('SUMMARY')
    print('='*80)
    print(f'Total text regions detected: {len(all_detections)}')
    print(f'Processing time: {ocr_time:.2f}s')
    
    # Confidence distribution
    high_conf = sum(1 for d in all_detections if d['confidence'] >= 0.9)
    med_conf = sum(1 for d in all_detections if 0.7 <= d['confidence'] < 0.9)
    low_conf = sum(1 for d in all_detections if d['confidence'] < 0.7)
    
    print(f'\nConfidence distribution:')
    print(f'  High (≥90%): {high_conf}')
    print(f'  Medium (70-90%): {med_conf}')
    print(f'  Low (<70%): {low_conf}')
    
    # Sample detections
    print(f'\nSample detections (first 10):')
    for det in all_detections[:10]:
        print(f"  [{det['id']}] \"{det['text']}\" @ ({det['bbox']['center'][0]}, {det['bbox']['center'][1]}) - {det['confidence']:.1%}")
    
    print('\n' + '='*80)
    print('FILES CREATED:')
    print('='*80)
    print(f'1. {json_path.name} - Full JSON with all data')
    print(f'2. {txt_path.name} - Text list sorted by position')
    print(f'3. {vis_path.name} - Visual with bounding boxes')
    print('\nOpen these files to see exactly what PaddleOCR detected!')
    print('='*80)
    
    return True


if __name__ == '__main__':
    success = test_full_document_ocr()
    sys.exit(0 if success else 1)
