"""
Debug Cell Mapping Issues
Analyzes why OCR detections are good but cell mapping is wrong

This script will:
1. Show OCR detections (Stage 3)
2. Show detected lines (horizontal & vertical)
3. Show column structure learning
4. Show cell mapping process with scoring
5. Identify mapping problems
"""

import cv2
import sys
import numpy as np
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipeline.lib.table_detector import detect_table_region, crop_table
from pipeline.ocr_engine import (
    run_full_document_ocr, detect_vertical_lines, detect_horizontal_lines,
    detect_header_rows, learn_column_structure
)


def visualize_lines(image, h_lines, v_lines, output_path):
    """Visualize detected horizontal and vertical lines"""
    vis_image = image.copy()
    
    # Draw horizontal lines (red)
    for y in h_lines:
        cv2.line(vis_image, (0, int(y)), (image.shape[1], int(y)), (0, 0, 255), 2)
        cv2.putText(vis_image, f"y={int(y)}", (10, int(y) - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
    
    # Draw vertical lines (blue)
    for x in v_lines:
        cv2.line(vis_image, (int(x), 0), (int(x), image.shape[0]), (255, 0, 0), 2)
        cv2.putText(vis_image, f"x={int(x)}", (int(x) + 5, 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
    
    cv2.imwrite(output_path, vis_image)
    print(f"✅ Lines visualization saved: {output_path}")


def visualize_columns(image, column_structure, output_path):
    """Visualize learned column structure"""
    vis_image = image.copy()
    
    # Draw column boundaries
    for idx, col in enumerate(column_structure):
        x_left = col['x_left']
        x_right = col['x_right']
        
        # Draw vertical lines for column boundaries
        cv2.line(vis_image, (x_left, 0), (x_left, image.shape[0]), (0, 255, 0), 2)
        cv2.line(vis_image, (x_right, 0), (x_right, image.shape[0]), (0, 255, 0), 2)
        
        # Draw column number
        x_center = (x_left + x_right) // 2
        cv2.putText(vis_image, f"Col {idx}", (x_center - 20, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Draw column name
        col_name = col.get('name', 'Unknown')
        cv2.putText(vis_image, col_name[:15], (x_center - 30, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    
    cv2.imwrite(output_path, vis_image)
    print(f"✅ Column structure visualization saved: {output_path}")


def analyze_cell_mapping(detections, h_lines, column_structure, image_height):
    """
    Analyze cell mapping process and identify issues
    
    Returns detailed analysis of mapping problems
    """
    print("\n" + "="*80)
    print("CELL MAPPING ANALYSIS")
    print("="*80)
    
    # Calculate adaptive tolerance
    if len(h_lines) > 1:
        avg_row_height = (h_lines[-1] - h_lines[0]) / max(len(h_lines) - 1, 1)
        adaptive_row_tolerance = max(8, int(avg_row_height * 0.25))
    else:
        adaptive_row_tolerance = 10
    
    print(f"\nAdaptive row tolerance: {adaptive_row_tolerance}px")
    print(f"Average row height: {avg_row_height:.1f}px" if len(h_lines) > 1 else "N/A")
    print(f"Horizontal lines: {len(h_lines)}")
    print(f"Columns: {len(column_structure)}")
    print(f"Total possible cells: {(len(h_lines)-1) * len(column_structure)}")
    
    # Find header end
    header_y_max = 0
    for det in detections:
        y_center = (det['y_min'] + det['y_max']) / 2
        if y_center < image_height * 0.25:
            header_y_max = max(header_y_max, det['y_max'])
    
    print(f"Header Y max: {header_y_max}")
    
    # Analyze each detection
    issues = {
        'no_row_match': [],
        'no_col_match': [],
        'low_score': [],
        'multiple_candidates': [],
        'mapped_successfully': []
    }
    
    # Helper functions (same as in main code)
    def calculate_iou(box1, box2):
        x1_min, y1_min, x1_max, y1_max = box1
        x2_min, y2_min, x2_max, y2_max = box2
        inter_x_min = max(x1_min, x2_min)
        inter_y_min = max(y1_min, y2_min)
        inter_x_max = min(x1_max, x2_max)
        inter_y_max = min(y1_max, y2_max)
        if inter_x_max < inter_x_min or inter_y_max < inter_y_min:
            return 0.0
        inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
        box1_area = (x1_max - x1_min) * (y1_max - y1_min)
        box2_area = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = box1_area + box2_area - inter_area
        return inter_area / union_area if union_area > 0 else 0.0
    
    def fuzzy_score(det, cell_box, confidence):
        det_box = (det['x_min'], det['y_min'], det['x_max'], det['y_max'])
        cell_x_min, cell_y_min, cell_x_max, cell_y_max = cell_box
        det_center_x = (det['x_min'] + det['x_max']) / 2
        det_center_y = (det['y_min'] + det['y_max']) / 2
        in_x = cell_x_min <= det_center_x < cell_x_max
        in_y = cell_y_min <= det_center_y < cell_y_max
        center_score = 1.0 if (in_x and in_y) else 0.0
        iou = calculate_iou(det_box, cell_box)
        cell_center_x = (cell_x_min + cell_x_max) / 2
        cell_center_y = (cell_y_min + cell_y_max) / 2
        distance = ((det_center_x - cell_center_x)**2 + (det_center_y - cell_center_y)**2)**0.5
        cell_width = cell_x_max - cell_x_min
        cell_height = cell_y_max - cell_y_min
        max_distance = ((cell_width/2)**2 + (cell_height/2)**2)**0.5
        distance_score = 1.0 - min(distance / max_distance, 1.0) if max_distance > 0 else 0.0
        conf_score = confidence
        total_score = (center_score * 0.50 + iou * 0.25 + distance_score * 0.15 + conf_score * 0.10)
        return total_score, center_score, iou, distance_score, conf_score
    
    # Spatial indexing (optimized)
    row_ranges = [(h_lines[i], h_lines[i+1], i) for i in range(len(h_lines)-1)]
    col_ranges = [(col['x_left'], col['x_right'], idx) for idx, col in enumerate(column_structure)]
    
    for det_idx, det in enumerate(detections):
        y_center = (det['y_min'] + det['y_max']) / 2
        x_center = (det['x_min'] + det['x_max']) / 2
        
        # Skip headers
        if y_center <= header_y_max:
            continue
        
        # Find candidate rows
        candidate_rows = []
        for y_min, y_max, idx in row_ranges:
            if y_min - adaptive_row_tolerance <= y_center <= y_max + adaptive_row_tolerance:
                candidate_rows.append(idx)
        
        # Find candidate columns
        candidate_cols = []
        for x_min, x_max, idx in col_ranges:
            if not (det['x_max'] < x_min or det['x_min'] > x_max):
                candidate_cols.append(idx)
        
        # Analyze mapping
        if not candidate_rows:
            issues['no_row_match'].append({
                'det_idx': det_idx,
                'text': det['text'],
                'y_center': y_center,
                'reason': f"No row match (y={y_center:.1f})"
            })
            continue
        
        if not candidate_cols:
            issues['no_col_match'].append({
                'det_idx': det_idx,
                'text': det['text'],
                'x_range': (det['x_min'], det['x_max']),
                'reason': f"No column match (x={x_center:.1f})"
            })
            continue
        
        # Find best cell
        best_score = 0.0
        best_row = -1
        best_col = -1
        all_scores = []
        
        for row_idx in candidate_rows:
            row_y_min = h_lines[row_idx]
            row_y_max = h_lines[row_idx + 1]
            
            for col_idx in candidate_cols:
                col_x_min = column_structure[col_idx]['x_left']
                col_x_max = column_structure[col_idx]['x_right']
                cell_box = (col_x_min, row_y_min, col_x_max, row_y_max)
                
                score, center_s, iou_s, dist_s, conf_s = fuzzy_score(det, cell_box, det['confidence'])
                all_scores.append({
                    'row': row_idx,
                    'col': col_idx,
                    'total': score,
                    'center': center_s,
                    'iou': iou_s,
                    'distance': dist_s,
                    'confidence': conf_s
                })
                
                if score > best_score and score > 0.4:
                    best_score = score
                    best_row = row_idx
                    best_col = col_idx
        
        if best_score < 0.4:
            issues['low_score'].append({
                'det_idx': det_idx,
                'text': det['text'],
                'best_score': best_score,
                'candidates': len(candidate_rows) * len(candidate_cols),
                'all_scores': all_scores
            })
        elif len(all_scores) > 1:
            issues['multiple_candidates'].append({
                'det_idx': det_idx,
                'text': det['text'],
                'best_score': best_score,
                'best_cell': (best_row, best_col),
                'num_candidates': len(all_scores),
                'all_scores': sorted(all_scores, key=lambda x: x['total'], reverse=True)[:3]
            })
            issues['mapped_successfully'].append({
                'det_idx': det_idx,
                'text': det['text'],
                'cell': (best_row, best_col),
                'score': best_score
            })
        else:
            issues['mapped_successfully'].append({
                'det_idx': det_idx,
                'text': det['text'],
                'cell': (best_row, best_col),
                'score': best_score
            })
    
    return issues, adaptive_row_tolerance


def print_issues_report(issues, output_path):
    """Print detailed issues report"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("CELL MAPPING ISSUES REPORT\n")
        f.write("="*80 + "\n\n")
        
        # Summary
        f.write("SUMMARY:\n")
        f.write(f"  Successfully mapped: {len(issues['mapped_successfully'])}\n")
        f.write(f"  No row match: {len(issues['no_row_match'])}\n")
        f.write(f"  No column match: {len(issues['no_col_match'])}\n")
        f.write(f"  Low score (<0.4): {len(issues['low_score'])}\n")
        f.write(f"  Multiple candidates: {len(issues['multiple_candidates'])}\n\n")
        
        # No row match
        if issues['no_row_match']:
            f.write("="*80 + "\n")
            f.write(f"ISSUE 1: NO ROW MATCH ({len(issues['no_row_match'])} detections)\n")
            f.write("="*80 + "\n\n")
            f.write("These detections couldn't find a matching row.\n")
            f.write("Possible causes: Y-position outside all row ranges + tolerance\n\n")
            for item in issues['no_row_match'][:10]:
                f.write(f"  Detection #{item['det_idx']}: '{item['text']}'\n")
                f.write(f"    Y-center: {item['y_center']:.1f}\n")
                f.write(f"    Reason: {item['reason']}\n\n")
        
        # No column match
        if issues['no_col_match']:
            f.write("="*80 + "\n")
            f.write(f"ISSUE 2: NO COLUMN MATCH ({len(issues['no_col_match'])} detections)\n")
            f.write("="*80 + "\n\n")
            f.write("These detections couldn't find a matching column.\n")
            f.write("Possible causes: X-position outside all column ranges\n\n")
            for item in issues['no_col_match'][:10]:
                f.write(f"  Detection #{item['det_idx']}: '{item['text']}'\n")
                f.write(f"    X-range: {item['x_range']}\n")
                f.write(f"    Reason: {item['reason']}\n\n")
        
        # Low score
        if issues['low_score']:
            f.write("="*80 + "\n")
            f.write(f"ISSUE 3: LOW SCORE (<0.4) ({len(issues['low_score'])} detections)\n")
            f.write("="*80 + "\n\n")
            f.write("These detections found candidates but all scores were too low.\n")
            f.write("Possible causes: Detection overlaps multiple cells, poor alignment\n\n")
            for item in issues['low_score'][:5]:
                f.write(f"  Detection #{item['det_idx']}: '{item['text']}'\n")
                f.write(f"    Best score: {item['best_score']:.3f}\n")
                f.write(f"    Candidates checked: {item['candidates']}\n")
                if item['all_scores']:
                    f.write(f"    Top candidate scores:\n")
                    for score_info in sorted(item['all_scores'], key=lambda x: x['total'], reverse=True)[:2]:
                        f.write(f"      Row {score_info['row']}, Col {score_info['col']}: ")
                        f.write(f"total={score_info['total']:.3f} ")
                        f.write(f"(center={score_info['center']:.2f}, iou={score_info['iou']:.2f}, ")
                        f.write(f"dist={score_info['distance']:.2f}, conf={score_info['confidence']:.2f})\n")
                f.write("\n")
        
        # Multiple candidates (good but worth noting)
        if issues['multiple_candidates']:
            f.write("="*80 + "\n")
            f.write(f"INFO: MULTIPLE CANDIDATES ({len(issues['multiple_candidates'])} detections)\n")
            f.write("="*80 + "\n\n")
            f.write("These detections had multiple cell candidates (successfully mapped to best one).\n\n")
            for item in issues['multiple_candidates'][:5]:
                f.write(f"  Detection #{item['det_idx']}: '{item['text']}'\n")
                f.write(f"    Mapped to: Row {item['best_cell'][0]}, Col {item['best_cell'][1]}\n")
                f.write(f"    Best score: {item['best_score']:.3f}\n")
                f.write(f"    Num candidates: {item['num_candidates']}\n")
                f.write(f"    Top 3 scores:\n")
                for score_info in item['all_scores']:
                    f.write(f"      Row {score_info['row']}, Col {score_info['col']}: {score_info['total']:.3f}\n")
                f.write("\n")
    
    print(f"✅ Issues report saved: {output_path}")


def main():
    """Main debug function"""
    
    # Test image path
    if len(sys.argv) > 1:
        test_image = sys.argv[1]
    else:
        test_image = "contoh gambar/2.png"
    
    if not Path(test_image).exists():
        print(f"❌ Image not found: {test_image}")
        return
    
    print("="*80)
    print("CELL MAPPING DEBUG ANALYSIS")
    print("="*80)
    print(f"\nTest Image: {test_image}\n")
    
    # Create output directory
    output_dir = Path("testing/results/debug")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load and process
    print("[1/7] Loading image...")
    image = cv2.imread(test_image)
    h, w = image.shape[:2]
    print(f"✅ Image loaded: {w}×{h}")
    
    print("\n[2/7] Detecting BLOK III...")
    bbox = detect_table_region(image)
    if bbox is None:
        print("❌ Failed to detect BLOK III")
        return
    cropped = crop_table(image, bbox)
    print(f"✅ BLOK III detected and cropped")
    
    print("\n[3/7] Running OCR...")
    detections = run_full_document_ocr(cropped)
    print(f"✅ OCR completed: {len(detections)} detections")
    
    print("\n[4/7] Detecting lines...")
    h_lines = detect_horizontal_lines(cropped)
    v_lines = detect_vertical_lines(cropped)
    print(f"✅ Lines detected: {len(h_lines)} horizontal, {len(v_lines)} vertical")
    
    # Visualize lines
    lines_output = str(output_dir / "debug_lines.png")
    visualize_lines(cropped, h_lines, v_lines, lines_output)
    
    print("\n[5/7] Learning column structure...")
    header_groups = detect_header_rows(detections)
    column_structure = learn_column_structure(header_groups, v_lines)
    print(f"✅ Columns learned: {len(column_structure)} columns")
    
    # Visualize columns
    cols_output = str(output_dir / "debug_columns.png")
    visualize_columns(cropped, column_structure, cols_output)
    
    print("\n[6/7] Analyzing cell mapping...")
    issues, tolerance = analyze_cell_mapping(detections, h_lines, column_structure, cropped.shape[0])
    
    print("\n[7/7] Generating issues report...")
    report_output = str(output_dir / "cell_mapping_issues.txt")
    print_issues_report(issues, report_output)
    
    # Summary
    print("\n" + "="*80)
    print("DEBUG ANALYSIS COMPLETE")
    print("="*80)
    print("\nGenerated Files:")
    print(f"  1. {lines_output}")
    print(f"     → Horizontal & vertical lines visualization")
    print(f"  2. {cols_output}")
    print(f"     → Column structure visualization")
    print(f"  3. {report_output}")
    print(f"     → Detailed cell mapping issues report")
    print("\nIssues Summary:")
    print(f"  ✅ Successfully mapped: {len(issues['mapped_successfully'])}")
    print(f"  ⚠️  No row match: {len(issues['no_row_match'])}")
    print(f"  ⚠️  No column match: {len(issues['no_col_match'])}")
    print(f"  ⚠️  Low score (<0.4): {len(issues['low_score'])}")
    print(f"  ℹ️  Multiple candidates: {len(issues['multiple_candidates'])}")
    
    # Calculate success rate
    total_data_detections = len(detections) - len([d for d in detections if (d['y_min'] + d['y_max']) / 2 < cropped.shape[0] * 0.25])
    success_rate = len(issues['mapped_successfully']) / total_data_detections * 100 if total_data_detections > 0 else 0
    print(f"\nMapping Success Rate: {success_rate:.1f}%")
    print()


if __name__ == "__main__":
    main()

