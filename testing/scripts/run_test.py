"""
Helper script to run optimization tests with automatic image detection
"""

import sys
from pathlib import Path

# Find test image
test_images = [
    "data/sample/sample_blok3.png",
    "sample_blok3.png",
    "test.png",
    "sample.png"
]

# Check if user provided image
if len(sys.argv) > 1:
    test_image = sys.argv[1]
    if not Path(test_image).exists():
        print(f"❌ Image not found: {test_image}")
        sys.exit(1)
else:
    # Try to find an image automatically
    test_image = None
    
    # Search in common locations
    search_patterns = ["*.png", "*.jpg", "*.jpeg"]
    for pattern in search_patterns:
        for img in Path(".").rglob(pattern):
            if "blok" in img.name.lower() or "sample" in img.name.lower() or "test" in img.name.lower():
                test_image = str(img)
                break
        if test_image:
            break
    
    if not test_image:
        print("❌ No test image found!")
        print("\nPlease run with:")
        print("  py testing/scripts/run_test.py <path_to_image>")
        print("\nOr place a test image (sample_blok3.png) in the project root.")
        sys.exit(1)

print(f"🎯 Using test image: {test_image}\n")

# Run the actual test
import subprocess
result = subprocess.run([sys.executable, "testing/scripts/test_optimizations.py", test_image])
sys.exit(result.returncode)

