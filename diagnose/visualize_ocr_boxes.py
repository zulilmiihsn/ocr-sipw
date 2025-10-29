"""
OCR Bounding Box Diagnostic Tool
Visualizes all OCR detections with accurate coordinates and metadata
"""

import sys
import cv2
import numpy as np
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.lib.image_utils import load_image
from pipeline.lib.table_detector import detect_table_region, crop_table
from pipeline.ocr_engine import run_full_document_ocr, detect_horizontal_lines, detect_vertical_lines


def draw_ocr_boxes(image, ocr_results, output_path="diagnose/ocr_boxes_visual.jpg"):
    """
    Draw all OCR bounding boxes on image with detailed annotations
    
    Args:
        image: Image to draw on
        ocr_results: List of OCR detections
        output_path: Output file path
    """
    # Create copy for drawing
    visual = image.copy()
    height, width = visual.shape[:2]
    
    # Color coding by confidence
    def get_color(conf):
        if conf >= 0.8:
            return (0, 255, 0)    # Green - High confidence
        elif conf >= 0.5:
            return (0, 255, 255)  # Yellow - Medium confidence
        else:
            return (0, 0, 255)    # Red - Low confidence
    
    # Draw each detection
    for idx, det in enumerate(ocr_results):
        x_min = int(det['x_min'])
        y_min = int(det['y_min'])
        x_max = int(det['x_max'])
        y_max = int(det['y_max'])
        
        text = det['text']
        conf = det['confidence']
        color = get_color(conf)
        
        # Draw bounding box
        cv2.rectangle(visual, (x_min, y_min), (x_max, y_max), color, 2)
        
        # Draw center point
        center_x = (x_min + x_max) // 2
        center_y = (y_min + y_max) // 2
        cv2.circle(visual, (center_x, center_y), 5, color, -1)
        
        # Draw index number
        label = f"#{idx}"
        cv2.putText(visual, label, (x_min, y_min - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    
    # Save
    cv2.imwrite(output_path, visual)
    print(f"✅ Visual saved: {output_path}")
    
    return visual


def save_ocr_metadata(ocr_results, h_lines, v_lines, output_path="diagnose/ocr_metadata.json"):
    """
    Save detailed OCR metadata to JSON
    
    Args:
        ocr_results: List of OCR detections
        h_lines: List of horizontal line Y-coordinates
        v_lines: List of vertical line X-coordinates
        output_path: Output JSON file path
    """
    metadata = {
        "total_detections": len(ocr_results),
        "horizontal_lines": {
            "count": len(h_lines),
            "positions": sorted(h_lines)
        },
        "vertical_lines": {
            "count": len(v_lines),
            "positions": sorted(v_lines)
        },
        "detections": []
    }
    
    # Add each detection with full details
    for idx, det in enumerate(ocr_results):
        center_x = (det['x_min'] + det['x_max']) / 2
        center_y = (det['y_min'] + det['y_max']) / 2
        width = det['x_max'] - det['x_min']
        height = det['y_max'] - det['y_min']
        
        detection_data = {
            "index": idx,
            "text": det['text'],
            "confidence": round(det['confidence'], 4),
            "bbox": {
                "x_min": int(det['x_min']),
                "y_min": int(det['y_min']),
                "x_max": int(det['x_max']),
                "y_max": int(det['y_max']),
                "width": int(width),
                "height": int(height)
            },
            "center": {
                "x": round(center_x, 2),
                "y": round(center_y, 2)
            }
        }
        
        metadata["detections"].append(detection_data)
    
    # Save JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Metadata saved: {output_path}")
    
    return metadata


def generate_html_report(image_path, metadata, output_path="diagnose/ocr_report.html"):
    """
    Generate interactive HTML report
    
    Args:
        image_path: Path to visual image
        metadata: OCR metadata dict
        output_path: Output HTML file path
    """
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>OCR Diagnostic Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        h1 {{
            margin: 0 0 10px 0;
            font-size: 32px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-label {{
            color: #666;
            font-size: 14px;
            margin-bottom: 5px;
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }}
        .image-container {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .image-container img {{
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .table-container {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            position: sticky;
            top: 0;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #eee;
        }}
        tr:hover {{
            background: #f9f9f9;
        }}
        .conf-high {{ color: #10b981; font-weight: bold; }}
        .conf-med {{ color: #f59e0b; font-weight: bold; }}
        .conf-low {{ color: #ef4444; font-weight: bold; }}
        .coord {{ font-family: 'Courier New', monospace; color: #666; }}
        .legend {{
            display: flex;
            gap: 20px;
            margin: 20px 0;
            padding: 15px;
            background: #f9fafb;
            border-radius: 8px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .legend-box {{
            width: 20px;
            height: 20px;
            border-radius: 4px;
        }}
        .legend-high {{ background: #10b981; }}
        .legend-med {{ background: #f59e0b; }}
        .legend-low {{ background: #ef4444; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 OCR Diagnostic Report</h1>
        <p>Detailed analysis of OCR detections with bounding boxes and coordinates</p>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <div class="stat-label">Total Detections</div>
            <div class="stat-value">{metadata['total_detections']}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Horizontal Lines</div>
            <div class="stat-value">{metadata['horizontal_lines']['count']}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Vertical Lines</div>
            <div class="stat-value">{metadata['vertical_lines']['count']}</div>
        </div>
    </div>
    
    <div class="legend">
        <div class="legend-item">
            <div class="legend-box legend-high"></div>
            <span>High Confidence (≥80%)</span>
        </div>
        <div class="legend-item">
            <div class="legend-box legend-med"></div>
            <span>Medium Confidence (50-79%)</span>
        </div>
        <div class="legend-item">
            <div class="legend-box legend-low"></div>
            <span>Low Confidence (&lt;50%)</span>
        </div>
    </div>
    
    <div class="image-container">
        <h2>📊 Visual Annotation</h2>
        <img src="{Path(image_path).name}" alt="OCR Bounding Boxes">
    </div>
    
    <div class="table-container">
        <h2>📋 Detection Details</h2>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Text</th>
                    <th>Confidence</th>
                    <th>Bounding Box (x_min, y_min, x_max, y_max)</th>
                    <th>Size (W × H)</th>
                    <th>Center (X, Y)</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # Add rows
    for det in metadata['detections']:
        conf = det['confidence']
        if conf >= 0.8:
            conf_class = 'conf-high'
        elif conf >= 0.5:
            conf_class = 'conf-med'
        else:
            conf_class = 'conf-low'
        
        bbox = det['bbox']
        center = det['center']
        
        html += f"""
                <tr>
                    <td><strong>#{det['index']}</strong></td>
                    <td>{det['text']}</td>
                    <td class="{conf_class}">{conf*100:.1f}%</td>
                    <td class="coord">({bbox['x_min']}, {bbox['y_min']}, {bbox['x_max']}, {bbox['y_max']})</td>
                    <td class="coord">{bbox['width']} × {bbox['height']}px</td>
                    <td class="coord">({center['x']:.1f}, {center['y']:.1f})</td>
                </tr>
"""
    
    html += """
            </tbody>
        </table>
    </div>
    
    <div class="table-container" style="margin-top: 20px;">
        <h2>📏 Line Positions</h2>
        <h3>Horizontal Lines (Y-coordinates)</h3>
        <p class="coord">"""
    
    html += ", ".join([f"y={y}" for y in metadata['horizontal_lines']['positions']])
    
    html += """</p>
        <h3>Vertical Lines (X-coordinates)</h3>
        <p class="coord">"""
    
    html += ", ".join([f"x={x}" for x in metadata['vertical_lines']['positions']])
    
    html += """</p>
    </div>
</body>
</html>"""
    
    # Save
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ HTML report saved: {output_path}")


def main():
    """Main diagnostic pipeline"""
    print("=" * 80)
    print("🔍 OCR DIAGNOSTIC TOOL - BOUNDING BOX ANALYZER")
    print("=" * 80)
    print()
    
    # Input image
    image_path = "contoh gambar/1.png"
    print(f"📁 Loading image: {image_path}")
    image = load_image(image_path)
    print(f"   Image size: {image.shape[1]}x{image.shape[0]}px")
    print()
    
    # Stage 1: Detect BLOK III
    print("🔍 Stage 1: Detecting BLOK III region...")
    bbox = detect_table_region(image)
    if bbox is None:
        print("❌ Failed to detect BLOK III region!")
        return
    
    cropped = crop_table(image, bbox)
    print(f"   BLOK III size: {cropped.shape[1]}x{cropped.shape[0]}px")
    print()
    
    # Stage 2: Run OCR
    print("🔍 Stage 2: Running full OCR scan...")
    print("   ⏳ This will take ~70 seconds...")
    ocr_results = run_full_document_ocr(cropped)
    print(f"   ✅ Detected {len(ocr_results)} text regions")
    print()
    
    # Stage 3: Detect lines
    print("🔍 Stage 3: Detecting table lines...")
    h_lines = detect_horizontal_lines(cropped)
    v_lines = detect_vertical_lines(cropped)
    print(f"   ✅ Horizontal lines: {len(h_lines)}")
    print(f"   ✅ Vertical lines: {len(v_lines)}")
    print()
    
    # Stage 4: Generate visualizations
    print("🎨 Stage 4: Generating visualizations...")
    visual = draw_ocr_boxes(cropped, ocr_results)
    print()
    
    # Stage 5: Save metadata
    print("💾 Stage 5: Saving metadata...")
    metadata = save_ocr_metadata(ocr_results, h_lines, v_lines)
    print()
    
    # Stage 6: Generate HTML report
    print("📄 Stage 6: Generating HTML report...")
    generate_html_report("ocr_boxes_visual.jpg", metadata)
    print()
    
    # Summary
    print("=" * 80)
    print("✅ DIAGNOSTIC COMPLETE!")
    print("=" * 80)
    print()
    print("📂 Output files:")
    print("   1. diagnose/ocr_boxes_visual.jpg   - Annotated image with bounding boxes")
    print("   2. diagnose/ocr_metadata.json      - Detailed JSON metadata")
    print("   3. diagnose/ocr_report.html        - Interactive HTML report")
    print()
    print("🌐 Open the HTML report in your browser for interactive viewing!")
    print()


if __name__ == "__main__":
    main()

