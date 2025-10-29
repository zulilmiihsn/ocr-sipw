"""
Test script for Adaptive OCR Pipeline v2.0
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from experiments.final_system.adaptive_ocr_pipeline import process_table


def test_with_sample_image():
    """Test pipeline with sample BLOK III image"""
    
    print('='*80)
    print('TESTING ADAPTIVE OCR PIPELINE v2.0')
    print('='*80)
    
    # Use the sample image from experiments/results
    image_path = project_root / 'experiments' / 'results' / 'stage3_blok3_final.jpg'
    
    if not image_path.exists():
        print(f'\nERROR: Sample image not found at: {image_path}')
        print('Please run Stage 3 first to generate the sample image.')
        return False
    
    # Output path
    output_path = project_root / 'experiments' / 'final_system' / 'test_output.json'
    
    # Process
    print(f'\nProcessing: {image_path.name}')
    print(f'Output: {output_path.name}')
    print()
    
    results = process_table(
        image_path=str(image_path),
        output_path=str(output_path),
        verbose=True
    )
    
    # Print summary
    print('\n' + '='*80)
    print('TEST RESULTS')
    print('='*80)
    print(f"Method: {results['metadata']['method']}")
    print(f"Processing time: {results['metadata']['processing_time_seconds']}s")
    print(f"Grid size: {results['metadata']['grid_size']}")
    print(f"Columns detected: {results['metadata']['learned_columns']}")
    print(f"Data rows: {results['metadata']['data_rows']}")
    print(f"Estimated accuracy: {results['metadata']['accuracy_estimate']}")
    
    print(f'\n✓ Test completed successfully!')
    print(f'✓ Results saved to: {output_path}')
    print('='*80)
    
    return True


if __name__ == '__main__':
    success = test_with_sample_image()
    sys.exit(0 if success else 1)
