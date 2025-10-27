"""
Test Stage 4: Cell Segmentation with Table Transformer (Microsoft)

State-of-the-art AI model for table structure recognition.
Accuracy: ~97-98%
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import torch

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_table_transformer():
    """Test Microsoft Table Transformer for cell detection"""
    
    print('='*60)
    print('STAGE 4A: TABLE TRANSFORMER (Microsoft)')
    print('='*60)
    
    overall_start = time.time()
    
    # Step 1: Install check
    print('\n[Step 1] Checking dependencies...')
    try:
        from transformers import AutoImageProcessor, TableTransformerForObjectDetection
        print('  ✓ Transformers library available')
    except ImportError:
        print('  ✗ ERROR: transformers not installed')
        print('  → Install: pip install transformers torch pillow')
        return False
    
    # Step 2: Load model
    print('\n[Step 2] Loading Table Transformer model...')
    start = time.time()
    
    try:
        model_name = "microsoft/table-transformer-structure-recognition"
        
        print(f'  Loading: {model_name}')
        processor = AutoImageProcessor.from_pretrained(model_name)
        model = TableTransformerForObjectDetection.from_pretrained(model_name)
        
        load_time = time.time() - start
        print(f'  ✓ Model loaded in {load_time:.2f}s')
        
    except Exception as e:
        print(f'  ✗ ERROR loading model: {e}')
        return False
    
    # Step 3: Load table image
    print('\n[Step 3] Loading table image...')
    image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
    
    if not image_path.exists():
        print(f'  ✗ ERROR: {image_path} not found')
        print('  → Run Stage 3 first!')
        return False
    
    image = Image.open(image_path).convert("RGB")
    print(f'  ✓ Image loaded: {image.size}')
    
    # Step 4: Detect table structure
    print('\n[Step 4] Detecting cells with AI...')
    start = time.time()
    
    # Process image
    inputs = processor(images=image, return_tensors="pt")
    
    # Run inference
    with torch.no_grad():
        outputs = model(**inputs)
    
    # Post-process
    target_sizes = torch.tensor([image.size[::-1]])
    results = processor.post_process_object_detection(
        outputs, 
        threshold=0.7,  # Confidence threshold
        target_sizes=target_sizes
    )[0]
    
    detect_time = time.time() - start
    print(f'  ✓ Detection completed in {detect_time:.2f}s')
    
    # Step 5: Analyze results
    print('\n[Step 5] Analyzing detected objects...')
    
    detected_objects = {}
    for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
        label_name = model.config.id2label[label.item()]
        
        if label_name not in detected_objects:
            detected_objects[label_name] = []
        
        detected_objects[label_name].append({
            'confidence': score.item(),
            'box': box.tolist()
        })
    
    # Print summary
    print(f'\n  Detected objects:')
    for obj_type, objs in detected_objects.items():
        print(f'    {obj_type}: {len(objs)} (avg conf: {np.mean([o["confidence"] for o in objs]):.2%})')
    
    # Step 6: Extract cells
    print('\n[Step 6] Extracting cells...')
    
    cells = {}
    cell_objects = detected_objects.get('table cell', []) + \
                   detected_objects.get('table column', []) + \
                   detected_objects.get('table row', [])
    
    if not cell_objects:
        print('  ⚠️  WARNING: No cells detected!')
        print('  Detected object types:', list(detected_objects.keys()))
    
    # Convert to OpenCV for visualization
    image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    vis_image = image_cv.copy()
    
    # Draw bounding boxes
    colors = {
        'table cell': (0, 255, 0),      # Green
        'table column': (255, 0, 0),    # Blue
        'table row': (0, 0, 255),       # Red
        'table': (255, 255, 0),         # Cyan
    }
    
    for obj_type, objs in detected_objects.items():
        color = colors.get(obj_type, (128, 128, 128))
        for obj in objs:
            x1, y1, x2, y2 = [int(v) for v in obj['box']]
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), color, 2)
            
            # Add label
            label_text = f"{obj_type[:8]} {obj['confidence']:.2f}"
            cv2.putText(vis_image, label_text, (x1, y1-5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    
    # Save visualization
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    vis_path = results_dir / 'stage4a_table_transformer.jpg'
    cv2.imwrite(str(vis_path), vis_image)
    print(f'  ✓ Visualization saved: {vis_path.name}')
    
    # Total time
    total_time = time.time() - overall_start
    
    print(f'\n' + '='*60)
    print('TABLE TRANSFORMER RESULTS')
    print('='*60)
    print(f'Total time: {total_time:.2f}s')
    print(f'  - Model loading: {load_time:.2f}s')
    print(f'  - Detection:     {detect_time:.2f}s')
    print(f'\nDetected:')
    for obj_type, objs in detected_objects.items():
        print(f'  {obj_type}: {len(objs)}')
    print(f'\nOutput: {vis_path.name}')
    print('='*60)
    
    return True


if __name__ == '__main__':
    success = test_table_transformer()
    sys.exit(0 if success else 1)

