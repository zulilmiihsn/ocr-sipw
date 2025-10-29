#!/usr/bin/env python3
"""
Measure actual BLOK III position ratios from sample document
"""

import cv2
from pipeline.lib.image_utils import load_image
from pipeline.lib.table_detector import detect_table_region

# Load sample image
image_path = "contoh gambar/1.png"
image = load_image(image_path)
height, width = image.shape[:2]

print(f"\n{'='*80}")
print(f"📏 MEASURING BLOK III POSITION RATIOS")
print(f"{'='*80}\n")
print(f"Document dimensions: {width}x{height}px")

# Run detection
bbox = detect_table_region(image)

if bbox:
    x, y_start, w, h = bbox
    y_end = y_start + h
    
    print(f"\n{'='*80}")
    print(f"📊 ACTUAL MEASUREMENTS:")
    print(f"{'='*80}\n")
    print(f"BLOK III Y-start: {y_start}px")
    print(f"BLOK III Y-end:   {y_end}px")
    print(f"BLOK III height:  {h}px")
    
    # Calculate ratios
    top_ratio = y_start / height
    bottom_ratio = y_end / height
    height_ratio = h / height
    
    print(f"\n{'='*80}")
    print(f"📐 CALCULATED RATIOS:")
    print(f"{'='*80}\n")
    print(f"Top boundary:    {top_ratio:.3f} ({top_ratio*100:.1f}%)")
    print(f"Bottom boundary: {bottom_ratio:.3f} ({bottom_ratio*100:.1f}%)")
    print(f"BLOK III height: {height_ratio:.3f} ({height_ratio*100:.1f}%)")
    
    print(f"\n{'='*80}")
    print(f"💡 RECOMMENDED FALLBACK RATIOS:")
    print(f"{'='*80}\n")
    
    # Add some margin for safety
    recommended_top = max(top_ratio - 0.03, 0.10)  # -3% safety margin
    recommended_bottom = min(bottom_ratio + 0.03, 0.90)  # +3% safety margin
    
    print(f"TOP_RATIO = {recommended_top:.2f}  # {recommended_top*100:.0f}% from top")
    print(f"BOTTOM_RATIO = {recommended_bottom:.2f}  # {recommended_bottom*100:.0f}% from top")
    print(f"\n(Added ±3% safety margin)")
    
    print(f"\n{'='*80}\n")
else:
    print("❌ BLOK III detection failed!")

