"""
OCR Diagnostic Tool - Visualize Bounding Boxes & Coordinates

This script will:
1. Run OCR on the image
2. Draw bounding boxes on the image
3. Show exact coordinates (x, y, width, height)
4. Color-code by row number (if detected)
5. Save detailed HTML report
"""

import cv2
import numpy as np
from pathlib import Path
import json
import time
from pipeline.lib.image_utils import load_image
from pipeline.lib.table_detector import detect_table_region, crop_table
from pipeline.ocr_engine import (
    run_full_document_ocr, detect_vertical_lines, detect_horizontal_lines,
    detect_header_rows
)
import re


def draw_boxes_with_labels(image, detections, output_path):
    """Draw bounding boxes with text labels and coordinates"""
    
    # Create a copy
    img_annotated = image.copy()
    
    # Define colors (BGR format)
    colors = {
        'header': (255, 0, 0),      # Blue
        'number': (0, 255, 0),      # Green
        'data': (0, 165, 255),      # Orange
        'unknown': (128, 128, 128)  # Gray
    }
    
    for idx, det in enumerate(detections):
        x_min = int(det['x_min'])
        y_min = int(det['y_min'])
        x_max = int(det['x_max'])
        y_max = int(det['y_max'])
        text = det['text']
        confidence = det['confidence']
        
        # Determine box type
        # Check if it's a number (1-10)
        text_clean = text.strip().replace('O', '0').replace('o', '0').replace('l', '1').replace('I', '1')
        if re.match(r'^[1-9]$|^10$', text_clean):
            box_type = 'number'
            label = f"#{text_clean}"
        elif y_min < image.shape[0] * 0.2:
            box_type = 'header'
            label = "HDR"
        else:
            box_type = 'data'
            label = f"{idx}"
        
        color = colors.get(box_type, colors['unknown'])
        
        # Draw bounding box
        cv2.rectangle(img_annotated, (x_min, y_min), (x_max, y_max), color, 2)
        
        # Draw filled background for text
        label_text = f"{label}: {text[:15]}"
        (text_width, text_height), baseline = cv2.getTextSize(
            label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1
        )
        
        # Background rectangle
        cv2.rectangle(
            img_annotated,
            (x_min, y_min - text_height - 4),
            (x_min + text_width + 4, y_min),
            color,
            -1
        )
        
        # Text
        cv2.putText(
            img_annotated,
            label_text,
            (x_min + 2, y_min - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (255, 255, 255),
            1,
            cv2.LINE_AA
        )
        
        # Draw center point
        center_x = (x_min + x_max) // 2
        center_y = (y_min + y_max) // 2
        cv2.circle(img_annotated, (center_x, center_y), 3, (0, 0, 255), -1)
    
    # Save
    cv2.imwrite(output_path, img_annotated)
    print(f"✅ Annotated image saved: {output_path}")
    
    return img_annotated


def generate_html_report(detections, row_numbers, image_path, output_html):
    """Generate detailed HTML report with all coordinates"""
    
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>OCR Diagnostic Report</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .stat-value {
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }
        .stat-label {
            color: #666;
            margin-top: 5px;
        }
        .image-container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            text-align: center;
        }
        .image-container img {
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
        }
        th {
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #f0f0f0;
        }
        tr:hover {
            background: #f8f9ff;
        }
        .bbox {
            font-family: 'Courier New', monospace;
            font-size: 11px;
            color: #666;
        }
        .text-cell {
            max-width: 300px;
            word-wrap: break-word;
        }
        .confidence {
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 600;
            display: inline-block;
        }
        .conf-high { background: #d4edda; color: #155724; }
        .conf-medium { background: #fff3cd; color: #856404; }
        .conf-low { background: #f8d7da; color: #721c24; }
        .row-number {
            background: #28a745;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
            display: inline-block;
        }
        .header-row {
            background: #007bff;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
            display: inline-block;
        }
        .legend {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .legend-item {
            display: inline-block;
            margin-right: 20px;
            margin-bottom: 10px;
        }
        .legend-box {
            display: inline-block;
            width: 20px;
            height: 20px;
            margin-right: 5px;
            vertical-align: middle;
            border: 2px solid;
        }
        .box-number { border-color: #28a745; background: #d4edda; }
        .box-header { border-color: #007bff; background: #cce5ff; }
        .box-data { border-color: #ffa500; background: #fff3cd; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 OCR Diagnostic Report</h1>
        <p>Detailed analysis of OCR detections with bounding box coordinates</p>
    </div>
"""
    
    # Statistics
    total_detections = len(detections)
    num_row_numbers = len(row_numbers)
    avg_confidence = sum(d['confidence'] for d in detections) / total_detections if total_detections > 0 else 0
    
    html += f"""
    <div class="stats">
        <div class="stat-card">
            <div class="stat-value">{total_detections}</div>
            <div class="stat-label">Total Detections</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{num_row_numbers}</div>
            <div class="stat-label">Row Numbers Detected</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{avg_confidence*100:.1f}%</div>
            <div class="stat-label">Avg Confidence</div>
        </div>
    </div>
    
    <div class="legend">
        <h3>🎨 Legend</h3>
        <div class="legend-item">
            <span class="legend-box box-number"></span>
            <strong>Green</strong> = Row Numbers (1-10)
        </div>
        <div class="legend-item">
            <span class="legend-box box-header"></span>
            <strong>Blue</strong> = Header Text
        </div>
        <div class="legend-item">
            <span class="legend-box box-data"></span>
            <strong>Orange</strong> = Data Text
        </div>
    </div>
    
    <div class="image-container">
        <h3>📷 Annotated Image</h3>
        <img src="{Path(image_path).name}" alt="Annotated OCR">
    </div>
    
    <h2>📋 Detection Details</h2>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Type</th>
                <th>Text</th>
                <th>Bounding Box (x, y, w, h)</th>
                <th>Center (x, y)</th>
                <th>Confidence</th>
            </tr>
        </thead>
        <tbody>
"""
    
    # Sort detections by Y position (top to bottom)
    sorted_dets = sorted(detections, key=lambda d: d['y_min'])
    
    for idx, det in enumerate(sorted_dets, 1):
        x_min = det['x_min']
        y_min = det['y_min']
        x_max = det['x_max']
        y_max = det['y_max']
        width = x_max - x_min
        height = y_max - y_min
        center_x = (x_min + x_max) / 2
        center_y = (y_min + y_max) / 2
        text = det['text']
        confidence = det['confidence']
        
        # Determine type
        text_clean = text.strip().replace('O', '0').replace('o', '0').replace('l', '1').replace('I', '1')
        if re.match(r'^[1-9]$|^10$', text_clean):
            det_type = f'<span class="row-number">Row #{text_clean}</span>'
        elif y_min < 200:  # Approximate header region
            det_type = '<span class="header-row">Header</span>'
        else:
            det_type = 'Data'
        
        # Confidence badge
        if confidence >= 0.8:
            conf_class = 'conf-high'
        elif confidence >= 0.5:
            conf_class = 'conf-medium'
        else:
            conf_class = 'conf-low'
        
        conf_badge = f'<span class="confidence {conf_class}">{confidence*100:.1f}%</span>'
        
        html += f"""
            <tr>
                <td><strong>{idx}</strong></td>
                <td>{det_type}</td>
                <td class="text-cell"><strong>{text}</strong></td>
                <td class="bbox">x:{x_min:.0f}, y:{y_min:.0f}, w:{width:.0f}, h:{height:.0f}</td>
                <td class="bbox">({center_x:.1f}, {center_y:.1f})</td>
                <td>{conf_badge}</td>
            </tr>
"""
    
    html += """
        </tbody>
    </table>
    
    <div style="margin-top: 30px; padding: 20px; background: white; border-radius: 8px; text-align: center;">
        <p style="color: #666;">Generated by Lab-untuk-OCR Diagnostic Tool</p>
    </div>
</body>
</html>
"""
    
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ HTML report saved: {output_html}")


def main():
    print("\n" + "="*80)
    print("🔬 OCR DIAGNOSTIC TOOL - Bounding Box Visualization")
    print("="*80 + "\n")
    
    # Input image path
    image_path = "contoh gambar/1.png"
    
    if not Path(image_path).exists():
        print(f"❌ Image not found: {image_path}")
        return
    
    print(f"📂 Loading image: {image_path}")
    
    # Create output directory
    output_dir = Path("diagnostic_output")
    output_dir.mkdir(exist_ok=True)
    
    start_time = time.time()
    
    # Step 1: Load and detect BLOK III
    print("\n[1/5] Loading image and detecting BLOK III region...")
    image = load_image(image_path)
    bbox = detect_table_region(image)
    
    if bbox is None:
        print("❌ Failed to detect BLOK III region")
        return
    
    cropped = crop_table(image, bbox)
    print(f"✅ BLOK III detected: {cropped.shape[1]}x{cropped.shape[0]} pixels")
    
    # Step 2: Run OCR
    print("\n[2/5] Running OCR scan (this may take ~70s)...")
    ocr_start = time.time()
    ocr_results = run_full_document_ocr(cropped)
    ocr_time = time.time() - ocr_start
    print(f"✅ OCR complete: {len(ocr_results)} detections in {ocr_time:.1f}s")
    
    # Step 3: Detect row numbers
    print("\n[3/5] Detecting row numbers (1-10)...")
    
    # Find leftmost column boundary
    vertical_lines = detect_vertical_lines(cropped)
    if len(vertical_lines) > 0:
        first_col_x_max = sorted(vertical_lines)[0] if len(vertical_lines) > 1 else cropped.shape[1] * 0.1
    else:
        first_col_x_max = cropped.shape[1] * 0.1
    
    # Find header end
    header_y_max = 0
    for det in ocr_results:
        y_center = (det['y_min'] + det['y_max']) / 2
        if y_center < cropped.shape[0] * 0.25:
            header_y_max = max(header_y_max, det['y_max'])
    
    # Extract row numbers
    row_number_detections = []
    for det in ocr_results:
        y_center = (det['y_min'] + det['y_max']) / 2
        x_center = (det['x_min'] + det['x_max']) / 2
        
        if y_center > header_y_max + 10 and x_center < first_col_x_max:
            text = det['text'].strip()
            text_clean = text.replace('O', '0').replace('o', '0').replace('l', '1').replace('I', '1')
            
            if re.match(r'^[1-9]$|^10$', text_clean):
                row_num = int(text_clean)
                row_number_detections.append({
                    'row_number': row_num,
                    'y_center': y_center,
                    'text_original': text,
                    'detection': det
                })
    
    row_number_detections = sorted(row_number_detections, key=lambda x: x['row_number'])
    print(f"✅ Row numbers detected: {[r['row_number'] for r in row_number_detections]}")
    
    # Step 4: Draw bounding boxes
    print("\n[4/5] Drawing bounding boxes...")
    annotated_image_path = output_dir / "ocr_bounding_boxes.png"
    draw_boxes_with_labels(cropped, ocr_results, str(annotated_image_path))
    
    # Step 5: Generate HTML report
    print("\n[5/5] Generating HTML report...")
    html_report_path = output_dir / "ocr_diagnostic_report.html"
    generate_html_report(
        ocr_results,
        row_number_detections,
        annotated_image_path,
        str(html_report_path)
    )
    
    # Save JSON data
    json_path = output_dir / "ocr_detections.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'total_detections': len(ocr_results),
            'row_numbers_detected': [r['row_number'] for r in row_number_detections],
            'detections': ocr_results,
            'row_number_details': row_number_detections,
            'processing_time': time.time() - start_time
        }, f, indent=2, ensure_ascii=False)
    
    print(f"✅ JSON data saved: {json_path}")
    
    total_time = time.time() - start_time
    
    print("\n" + "="*80)
    print("✅ DIAGNOSTIC COMPLETE!")
    print("="*80)
    print(f"\n📊 Summary:")
    print(f"  • Total detections: {len(ocr_results)}")
    print(f"  • Row numbers detected: {len(row_number_detections)}/10")
    print(f"  • Processing time: {total_time:.1f}s")
    print(f"\n📁 Output files:")
    print(f"  1. {annotated_image_path}")
    print(f"  2. {html_report_path}")
    print(f"  3. {json_path}")
    print(f"\n💡 Open the HTML report in your browser to see detailed analysis!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

