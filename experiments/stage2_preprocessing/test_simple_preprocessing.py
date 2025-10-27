"""
Test Stage 2: Simple Preprocessing (Clarity-Focused)

Goal: Make text clear and HD without destroying data

Strategy:
1. Resize to HD if too small (upscale for clarity)
2. Slight contrast enhancement (make text pop)
3. Minimal noise reduction (preserve details)
4. NO aggressive binarization
5. NO heavy sharpening that creates artifacts

Expected: Clear, readable image that preserves all original data
"""

import sys
from pathlib import Path
import cv2
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def simple_preprocess(image: np.ndarray) -> np.ndarray:
    """
    Simple preprocessing focused on clarity
    
    Steps:
    1. Convert to grayscale
    2. Upscale if too small (for HD quality)
    3. Light contrast enhancement (CLAHE)
    4. Minimal denoising (preserve edges)
    
    NO: Heavy binarization, aggressive sharpening, morphology
    """
    
    # Step 1: Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    print(f"  Step 1: Grayscale - {gray.shape}")
    
    # Step 2: Upscale if resolution is low (for HD clarity)
    h, w = gray.shape
    target_height = 1500  # HD target
    
    if h < target_height:
        scale = target_height / h
        new_h = target_height
        new_w = int(w * scale)
        gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        print(f"  Step 2: Upscaled to HD - {gray.shape}")
    else:
        print(f"  Step 2: Already HD - {gray.shape}")
    
    # Step 3: Light contrast enhancement (CLAHE - adaptive)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    print(f"  Step 3: Contrast enhanced (CLAHE)")
    
    # Step 4: Minimal denoising (preserve edges & details)
    # Use bilateral filter - smooths while preserving edges
    denoised = cv2.bilateralFilter(enhanced, d=5, sigmaColor=50, sigmaSpace=50)
    print(f"  Step 4: Light denoising (bilateral)")
    
    return denoised


def test_simple_preprocessing():
    """Test simple preprocessing on sample image"""
    
    print('='*60)
    print('STAGE 2: SIMPLE PREPROCESSING (Clarity-Focused)')
    print('='*60)
    
    # Load original image from Stage 1
    print('\n[Load] Loading original image...')
    image_path = project_root / 'contoh gambar' / '1.png'
    
    if not image_path.exists():
        print(f'  ✗ ERROR: {image_path} not found')
        return False
    
    image = cv2.imread(str(image_path))
    print(f'  ✓ Original image loaded: {image.shape}')
    
    # Apply simple preprocessing
    print('\n[Process] Applying simple preprocessing...')
    processed = simple_preprocess(image)
    
    # Save result
    print('\n[Save] Saving result...')
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    output_path = results_dir / 'stage2_simple_preprocessing.jpg'
    cv2.imwrite(str(output_path), processed)
    print(f'  ✓ Saved: {output_path.name}')
    
    # Compare with original
    print('\n[Compare] Image comparison:')
    print(f'  Original:   {image.shape}')
    print(f'  Processed:  {processed.shape}')
    print(f'  File size:  {output_path.stat().st_size // 1024} KB')
    
    # Check contrast improvement
    orig_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    print(f'\n[Quality] Contrast analysis:')
    print(f'  Original contrast:   {orig_gray.std():.2f}')
    print(f'  Processed contrast:  {processed.std():.2f}')
    print(f'  Improvement:         {((processed.std() / orig_gray.std() - 1) * 100):.1f}%')
    
    print('\n' + '='*60)
    print('SIMPLE PREPROCESSING COMPLETE')
    print('='*60)
    print(f'Output: {output_path.name}')
    print('\nNext: Run Stage 3 with this preprocessed image')
    print('='*60)
    
    return True


if __name__ == '__main__':
    success = test_simple_preprocessing()
    sys.exit(0 if success else 1)
