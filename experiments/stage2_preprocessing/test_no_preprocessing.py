"""
Test Stage 2: NO Preprocessing (Original Image)

Goal: Test if original image is already good enough

Strategy:
- Load original image
- NO grayscale conversion
- NO contrast enhancement
- NO denoising
- Just save as-is for next stages

Hypothesis: Original image quality might be sufficient!
"""

import sys
from pathlib import Path
import cv2

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_no_preprocessing():
    """Test with NO preprocessing - use original image"""
    
    print('='*60)
    print('STAGE 2: NO PREPROCESSING (Original Quality)')
    print('='*60)
    
    # Load original image
    print('\n[Load] Loading original image...')
    image_path = project_root / 'contoh gambar' / '1.png'
    
    if not image_path.exists():
        print(f'  ✗ ERROR: {image_path} not found')
        return False
    
    image = cv2.imread(str(image_path))
    print(f'  ✓ Original image loaded: {image.shape}')
    print(f'  ✓ Color mode: {"Color (RGB)" if len(image.shape) == 3 else "Grayscale"}')
    
    # Save directly without any processing
    print('\n[Save] Saving original image (no processing)...')
    results_dir = project_root / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    
    output_path = results_dir / 'stage2_no_preprocessing.jpg'
    cv2.imwrite(str(output_path), image)
    print(f'  ✓ Saved: {output_path.name}')
    
    # Image info
    print('\n[Info] Image information:')
    print(f'  Resolution: {image.shape[1]}×{image.shape[0]}')
    print(f'  Channels:   {image.shape[2] if len(image.shape) == 3 else 1}')
    print(f'  File size:  {output_path.stat().st_size // 1024} KB')
    
    print('\n' + '='*60)
    print('NO PREPROCESSING COMPLETE')
    print('='*60)
    print(f'Output: {output_path.name}')
    print('\nStrategy: Use original image quality')
    print('No color conversion, no enhancement, no filtering')
    print('\nNext: Run Stage 3 with original image')
    print('='*60)
    
    return True


if __name__ == '__main__':
    success = test_no_preprocessing()
    sys.exit(0 if success else 1)
