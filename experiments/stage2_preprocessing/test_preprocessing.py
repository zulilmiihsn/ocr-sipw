"""
Test Stage 2: Preprocessing
Test individual steps dan full pipeline
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.ocr.preprocessor import (
    preprocess_image,
    resize_if_needed,
    deskew_image,
    enhance_contrast,
    denoise_image,
    binarize_image
)
from src.utils.pdf_handler import load_image
import cv2
import numpy as np


def test_preprocessing_steps():
    """Test setiap preprocessing step secara terpisah"""
    
    print("=" * 60)
    print("STAGE 2: PREPROCESSING TEST")
    print("=" * 60)
    
    # Load test image
    test_image_path = "data/templates/sample.jpg"
    
    if not os.path.exists(test_image_path):
        print(f"⚠️  Test image not found: {test_image_path}")
        print("Please provide a sample form image.")
        return
    
    image = load_image(test_image_path)
    print(f"\n📷 Loaded image: {image.shape}")
    
    results_dir = "experiments/results"
    os.makedirs(results_dir, exist_ok=True)
    
    # Save original
    cv2.imwrite(f"{results_dir}/stage2_0_original.jpg", image)
    print(f"  ✅ Saved: stage2_0_original.jpg")
    
    # Test individual steps
    steps = [
        ("1_resized", lambda img: resize_if_needed(img)),
        ("2_deskewed", lambda img: deskew_image(img)),
        ("3_enhanced", lambda img: enhance_contrast(img)),
        ("4_denoised", lambda img: denoise_image(img)),
        ("5_binarized", lambda img: binarize_image(img)),
    ]
    
    current_image = image.copy()
    
    for step_name, step_func in steps:
        print(f"\n🔄 Processing: {step_name}...")
        try:
            result = step_func(current_image)
            
            # Save result
            output_path = f"{results_dir}/stage2_{step_name}.jpg"
            cv2.imwrite(output_path, result)
            print(f"  ✅ Saved: {output_path}")
            
            # Update current image for next step
            current_image = result
            
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
    
    # Test full pipeline
    print(f"\n🔄 Processing: FULL PIPELINE...")
    try:
        full_result = preprocess_image(image, full_pipeline=True)
        output_path = f"{results_dir}/stage2_full_pipeline.jpg"
        cv2.imwrite(output_path, full_result)
        print(f"  ✅ Saved: {output_path}")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("Stage 2 testing completed!")
    print("Check experiments/results/ for output images")
    print("=" * 60)


def test_parameter_tuning():
    """Test berbagai parameter binarization"""
    
    print("\n" + "=" * 60)
    print("PARAMETER TUNING TEST")
    print("=" * 60)
    
    test_image_path = "data/templates/sample.jpg"
    
    if not os.path.exists(test_image_path):
        print(f"⚠️  Test image not found")
        return
    
    image = load_image(test_image_path)
    
    # Preprocess sampai sebelum binarization
    image = resize_if_needed(image)
    image = deskew_image(image)
    image = enhance_contrast(image)
    image = denoise_image(image)
    
    results_dir = "experiments/results"
    
    # Test different binarization parameters
    configs = [
        {"block_size": 7, "c": 1, "name": "optimized"},
        {"block_size": 11, "c": 2, "name": "soft"},
        {"block_size": 5, "c": 0, "name": "aggressive"},
    ]
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    for config in configs:
        print(f"\n🔧 Testing: {config['name']} (block={config['block_size']}, c={config['c']})")
        
        try:
            binary = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                config['block_size'],
                config['c']
            )
            binary = cv2.bitwise_not(binary)
            
            output_path = f"{results_dir}/stage2_binarize_{config['name']}.jpg"
            cv2.imwrite(output_path, binary)
            print(f"  ✅ Saved: {output_path}")
            
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("Parameter tuning completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_preprocessing_steps()
    test_parameter_tuning()


