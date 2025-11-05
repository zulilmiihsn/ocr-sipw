"""
Visualization Script for Stage 2 & 3 Detection
Shows:
- Stage 2: BLOK III region detection
- Stage 3: OCR text detection with bounding boxes and positions
"""

import cv2
import sys
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipeline.lib.table_detector import detect_table_region, crop_table
from pipeline.ocr_engine import run_full_document_ocr


def visualize_stage2(image, bbox, output_path):
    """
    Visualize Stage 2: BLOK III Detection
    
    Args:
        image: Original image
        bbox: Bounding box (x1, y1, x2, y2)
        output_path: Path to save visualization
    """
    vis_image = image.copy()
    
    if bbox:
        x1, y1, x2, y2 = bbox
        
        # Draw bounding box (thick green rectangle)
        cv2.rectangle(vis_image, (x1, y1), (x2, y2), (0, 255, 0), 3)
        
        # Add label
        label = "BLOK III Region"
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        cv2.rectangle(vis_image, (x1, y1 - label_size[1] - 10), 
                     (x1 + label_size[0] + 10, y1), (0, 255, 0), -1)
        cv2.putText(vis_image, label, (x1 + 5, y1 - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
        
        # Add coordinates text
        coord_text = f"({x1}, {y1}) -> ({x2}, {y2})"
        cv2.putText(vis_image, coord_text, (x1, y2 + 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Add size text
        width = x2 - x1
        height = y2 - y1
        size_text = f"Size: {width}×{height}"
        cv2.putText(vis_image, size_text, (x1, y2 + 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
    # Save result
    cv2.imwrite(output_path, vis_image)
    print(f"✅ Stage 2 visualization saved: {output_path}")
    
    return vis_image


def visualize_stage3(image, detections, output_path):
    """
    Visualize Stage 3: OCR Text Detection
    
    Args:
        image: Cropped BLOK III image
        detections: List of OCR detections
        output_path: Path to save visualization
    """
    vis_image = image.copy()
    
    # Color palette for different confidence levels
    def get_color(confidence):
        """Get color based on confidence (red=low, yellow=medium, green=high)"""
        if confidence < 0.7:
            return (0, 0, 255)  # Red (low confidence)
        elif confidence < 0.85:
            return (0, 165, 255)  # Orange (medium)
        else:
            return (0, 255, 0)  # Green (high confidence)
    
    # Draw each detection
    for idx, det in enumerate(detections):
        x_min = det['x_min']
        y_min = det['y_min']
        x_max = det['x_max']
        y_max = det['y_max']
        text = det['text']
        confidence = det['confidence']
        
        # Get color based on confidence
        color = get_color(confidence)
        
        # Draw bounding box
        cv2.rectangle(vis_image, (x_min, y_min), (x_max, y_max), color, 2)
        
        # Draw detection number
        cv2.putText(vis_image, f"#{idx+1}", (x_min, y_min - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        
        # Draw center point
        center_x = (x_min + x_max) // 2
        center_y = (y_min + y_max) // 2
        cv2.circle(vis_image, (center_x, center_y), 3, (255, 0, 255), -1)
    
    # Save result
    cv2.imwrite(output_path, vis_image)
    print(f"✅ Stage 3 visualization saved: {output_path}")
    
    return vis_image


def create_detailed_report(detections, output_path):
    """
    Create detailed text report of all detections
    
    Args:
        detections: List of OCR detections
        output_path: Path to save text report
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("STAGE 3: OCR TEXT DETECTION REPORT\n")
        f.write("="*80 + "\n\n")
        
        f.write(f"Total Detections: {len(detections)}\n\n")
        
        # Statistics
        confidences = [d['confidence'] for d in detections]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        min_conf = min(confidences) if confidences else 0
        max_conf = max(confidences) if confidences else 0
        
        f.write(f"Confidence Statistics:\n")
        f.write(f"  Average: {avg_conf:.2%}\n")
        f.write(f"  Minimum: {min_conf:.2%}\n")
        f.write(f"  Maximum: {max_conf:.2%}\n\n")
        
        f.write("="*80 + "\n")
        f.write("DETAILED DETECTIONS\n")
        f.write("="*80 + "\n\n")
        
        # Sort by Y position (top to bottom), then X (left to right)
        sorted_dets = sorted(detections, key=lambda d: (d['y_min'], d['x_min']))
        
        for idx, det in enumerate(sorted_dets):
            f.write(f"Detection #{idx+1}\n")
            f.write(f"  Text:       '{det['text']}'\n")
            f.write(f"  Confidence: {det['confidence']:.2%}\n")
            f.write(f"  Position:   ({det['x_min']}, {det['y_min']}) → ({det['x_max']}, {det['y_max']})\n")
            f.write(f"  Center:     ({det['x']}, {det['y']})\n")
            f.write(f"  Size:       {det['width']}×{det['height']}\n")
            f.write("\n")
    
    print(f"✅ Detailed report saved: {output_path}")


def main():
    """Main visualization function"""
    
    # Test image path
    if len(sys.argv) > 1:
        test_image = sys.argv[1]
    else:
        test_image = "examples/2.png"
    
    if not Path(test_image).exists():
        print(f"❌ Image not found: {test_image}")
        print("\nUsage:")
        print(f"  py testing/scripts/visualize_detection.py <image_path>")
        return
    
    print("="*80)
    print("VISUALIZATION: STAGE 2 & 3 DETECTION")
    print("="*80)
    print(f"\nTest Image: {test_image}\n")
    
    # Create output directory
    output_dir = Path("testing/results/visualizations")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load image
    print("[1/5] Loading image...")
    image = cv2.imread(test_image)
    if image is None:
        print(f"❌ Failed to load image: {test_image}")
        return
    
    h, w = image.shape[:2]
    print(f"✅ Image loaded: {w}×{h} ({w*h/1_000_000:.1f}MP)")
    
    # ========================================================================
    # STAGE 2: BLOK III Detection
    # ========================================================================
    print("\n[2/5] Stage 2: Detecting BLOK III region...")
    bbox = detect_table_region(image)
    
    if bbox is None:
        print("❌ Failed to detect BLOK III region")
        return
    
    x1, y1, x2, y2 = bbox
    blok_width = x2 - x1
    blok_height = y2 - y1
    print(f"✅ BLOK III detected:")
    print(f"   Position: ({x1}, {y1}) → ({x2}, {y2})")
    print(f"   Size: {blok_width}×{blok_height}")
    
    # Visualize Stage 2
    stage2_output = str(output_dir / "stage2_blok3_detection.png")
    visualize_stage2(image, bbox, stage2_output)
    
    # Crop BLOK III
    cropped = crop_table(image, bbox)
    
    # Save cropped image
    cropped_output = str(output_dir / "stage2_cropped_blok3.png")
    cv2.imwrite(cropped_output, cropped)
    print(f"✅ Cropped BLOK III saved: {cropped_output}")
    
    # ========================================================================
    # STAGE 3: OCR Text Detection
    # ========================================================================
    print("\n[3/5] Stage 3: Running OCR detection...")
    detections = run_full_document_ocr(cropped)
    
    print(f"✅ OCR completed: {len(detections)} text detections")
    
    # Statistics
    confidences = [d['confidence'] for d in detections]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0
    high_conf = sum(1 for c in confidences if c >= 0.85)
    med_conf = sum(1 for c in confidences if 0.7 <= c < 0.85)
    low_conf = sum(1 for c in confidences if c < 0.7)
    
    print(f"   Average confidence: {avg_conf:.2%}")
    print(f"   High confidence (≥85%): {high_conf}")
    print(f"   Medium confidence (70-85%): {med_conf}")
    print(f"   Low confidence (<70%): {low_conf}")
    
    # Visualize Stage 3
    print("\n[4/5] Creating visualizations...")
    stage3_output = str(output_dir / "stage3_ocr_detections.png")
    visualize_stage3(cropped, detections, stage3_output)
    
    # Create detailed report
    print("\n[5/5] Creating detailed report...")
    report_output = str(output_dir / "stage3_detection_report.txt")
    create_detailed_report(detections, report_output)
    
    # Summary
    print("\n" + "="*80)
    print("VISUALIZATION COMPLETE")
    print("="*80)
    print("\nGenerated Files:")
    print(f"  1. {stage2_output}")
    print(f"     → Stage 2: BLOK III detection with bounding box")
    print(f"  2. {cropped_output}")
    print(f"     → Cropped BLOK III region")
    print(f"  3. {stage3_output}")
    print(f"     → Stage 3: OCR text detections with bounding boxes")
    print(f"  4. {report_output}")
    print(f"     → Detailed text report of all detections")
    print("\nColor Legend (Stage 3):")
    print("  🟢 Green:  High confidence (≥85%)")
    print("  🟠 Orange: Medium confidence (70-85%)")
    print("  🔴 Red:    Low confidence (<70%)")
    print()


if __name__ == "__main__":
    main()

