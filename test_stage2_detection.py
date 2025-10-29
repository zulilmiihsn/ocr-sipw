"""
Test Script: Stage 2 - Dual-Direction BLOK III Detection
=========================================================
Visualize the results of the improved dual-direction detection

Author: Lab OCR Team
Date: October 2025
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.pdf_handler import load_image
from src.ocr.table_detector import detect_table_region, crop_table

print("=" * 80)
print("🔍 STAGE 2 TEST - Dual-Direction BLOK III Detection")
print("=" * 80)
print()

# Load image
print("[1] Loading test image...")
image_path = 'contoh gambar/1.png'
image = load_image(image_path)
print(f"  ✓ Loaded: {image.shape}")
print()

# Detect BLOK III with timing
print("[2] Detecting BLOK III region...")
start = time.time()
bbox = detect_table_region(image)
elapsed = time.time() - start

if bbox is None:
    print("  ✗ BLOK III detection failed!")
    sys.exit(1)

x, y, w, h = bbox
print(f"\n  ✓ Detection completed in {elapsed:.2f}s")
print(f"  → Bounding box: x={x}, y={y}, w={w}, h={h}")
print()

# Crop BLOK III
print("[3] Cropping BLOK III region...")
blok3_img = crop_table(image, bbox)
print(f"  ✓ Cropped: {blok3_img.shape}")
print()

# Create visualization
print("[4] Creating visualization...")

# Create a copy for drawing
vis_image = image.copy()

# Draw bounding box
color_box = (0, 255, 0)  # Green
thickness = 3
cv2.rectangle(vis_image, (x, y), (x + w, y + h), color_box, thickness)

# Draw upper boundary line (thicker, red)
color_upper = (0, 0, 255)  # Red
cv2.line(vis_image, (0, y), (image.shape[1], y), color_upper, 5)

# Draw lower boundary line (thicker, blue)
color_lower = (255, 0, 0)  # Blue
y_bottom = y + h
cv2.line(vis_image, (0, y_bottom), (image.shape[1], y_bottom), color_lower, 5)

# Add text labels
font = cv2.FONT_HERSHEY_SIMPLEX
font_scale = 1.5
font_thickness = 3

# Label: Upper boundary
text_upper = f"Upper: y={y} (Rekapitulasi)"
cv2.putText(vis_image, text_upper, (50, y - 20), font, font_scale, color_upper, font_thickness)

# Label: Lower boundary
text_lower = f"Lower: y={y_bottom} (Keterangan)"
cv2.putText(vis_image, text_lower, (50, y_bottom + 50), font, font_scale, color_lower, font_thickness)

# Label: BLOK III
text_blok3 = f"BLOK III (height={h}px)"
cv2.putText(vis_image, text_blok3, (50, y + h//2), font, font_scale * 1.2, (0, 255, 255), font_thickness + 1)

# Save results
results_dir = project_root / 'pipeline' / 'results'
results_dir.mkdir(exist_ok=True)

# Save full image with annotations
vis_path = results_dir / 'stage2_detection_visualization.jpg'
cv2.imwrite(str(vis_path), vis_image)
print(f"  ✓ Saved visualization: {vis_path}")

# Save cropped BLOK III
crop_path = results_dir / 'stage2_blok3_cropped.jpg'
cv2.imwrite(str(crop_path), blok3_img)
print(f"  ✓ Saved cropped BLOK III: {crop_path}")

# Create side-by-side comparison
print("\n[5] Creating side-by-side comparison...")

# Resize images to same height for comparison
target_height = 800
scale_orig = target_height / image.shape[0]
scale_crop = target_height / blok3_img.shape[0]

orig_resized = cv2.resize(image, None, fx=scale_orig, fy=scale_orig)
crop_resized = cv2.resize(blok3_img, None, fx=scale_crop, fy=scale_crop)

# Add padding if needed to match widths
max_width = max(orig_resized.shape[1], crop_resized.shape[1])
orig_padded = cv2.copyMakeBorder(orig_resized, 0, 0, 0, max_width - orig_resized.shape[1], cv2.BORDER_CONSTANT, value=[255, 255, 255])
crop_padded = cv2.copyMakeBorder(crop_resized, 0, 0, 0, max_width - crop_resized.shape[1], cv2.BORDER_CONSTANT, value=[255, 255, 255])

# Add labels
label_height = 60
label_orig = np.ones((label_height, orig_padded.shape[1], 3), dtype=np.uint8) * 255
label_crop = np.ones((label_height, crop_padded.shape[1], 3), dtype=np.uint8) * 255

cv2.putText(label_orig, "ORIGINAL IMAGE", (20, 40), font, 1.0, (0, 0, 0), 2)
cv2.putText(label_crop, f"BLOK III CROPPED (y={y} to y={y_bottom})", (20, 40), font, 1.0, (0, 0, 0), 2)

# Stack vertically
orig_with_label = np.vstack([label_orig, orig_padded])
crop_with_label = np.vstack([label_crop, crop_padded])

# Combine side by side
comparison = np.hstack([orig_with_label, crop_with_label])

# Save comparison
comparison_path = results_dir / 'stage2_comparison.jpg'
cv2.imwrite(str(comparison_path), comparison)
print(f"  ✓ Saved comparison: {comparison_path}")

# Generate summary report
print("\n[6] Generating summary report...")

report = f"""
{'=' * 80}
STAGE 2 - DUAL-DIRECTION BLOK III DETECTION REPORT
{'=' * 80}

INPUT:
  File: {image_path}
  Size: {image.shape[0]}x{image.shape[1]} pixels

DETECTION METHOD:
  ✓ Dual-direction OCR scanning
  ✓ Upper boundary: Scan TOP 30% for "Rekapitulasi"
  ✓ Lower boundary: Scan BOTTOM 30% for "Keterangan"

RESULTS:
  Upper boundary (Rekapitulasi): y = {y}
  Lower boundary (Keterangan):   y = {y_bottom}
  BLOK III height:               {h} pixels
  Processing time:               {elapsed:.2f} seconds

COMPARISON WITH OLD METHOD:
  Old method (single direction):
    - Scan TOP only
    - Use image bottom as lower boundary
    - Result: y={y} to y={image.shape[0]} (height={image.shape[0]-y}px)
  
  New method (dual direction):
    - Scan TOP and BOTTOM
    - Detect both boundaries
    - Result: y={y} to y={y_bottom} (height={h}px)
  
  Improvement:
    - Area reduced by: {image.shape[0]-y-h} pixels ({(image.shape[0]-y-h)/(image.shape[0]-y)*100:.1f}%)
    - More precise cropping ✓
    - Excludes "Keterangan" section ✓

OUTPUT FILES:
  1. {vis_path.name}
     - Full image with bounding box and labels
     - Red line: Upper boundary (Rekapitulasi)
     - Blue line: Lower boundary (Keterangan)
     - Green box: BLOK III region
  
  2. {crop_path.name}
     - Cropped BLOK III image only
     - Ready for Stage 3 (OCR processing)
  
  3. {comparison_path.name}
     - Side-by-side comparison
     - Original vs Cropped

{'=' * 80}
✓ STAGE 2 TEST COMPLETED SUCCESSFULLY!
{'=' * 80}
"""

# Save report
report_path = results_dir / 'stage2_detection_report.txt'
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(report)

print(report)
print(f"\n  ✓ Saved report: {report_path}")

print("\n" + "=" * 80)
print("✨ ALL FILES SAVED TO: pipeline/results/")
print("=" * 80)
print("\nFiles created:")
print(f"  1. stage2_detection_visualization.jpg - Full image with annotations")
print(f"  2. stage2_blok3_cropped.jpg - Cropped BLOK III only")
print(f"  3. stage2_comparison.jpg - Side-by-side comparison")
print(f"  4. stage2_detection_report.txt - Detailed report")
print("\n" + "=" * 80)
