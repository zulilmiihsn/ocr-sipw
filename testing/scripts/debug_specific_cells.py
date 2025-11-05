"""
Deep Debug: Specific Cell Mapping Issues
Focus on why "0011" and "Muatan Dominan" not mapped correctly
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


def find_detection_by_text(detections, search_text):
    """Find all detections containing search text"""
    results = []
    for idx, det in enumerate(detections):
        if search_text.lower() in det['text'].lower():
            results.append({
                'index': idx,
                'text': det['text'],
                'confidence': det['confidence'],
                'position': (det['x_min'], det['y_min'], det['x_max'], det['y_max']),
                'center': (det['x'], det['y'])
            })
    return results


def analyze_specific_detection(det, h_lines, column_structure, adaptive_tolerance, header_y_max):
    """Analyze why a specific detection is not mapped"""
    
    y_center = (det['y_min'] + det['y_max']) / 2
    x_center = (det['x_min'] + det['x_max']) / 2
    
    print(f"\n{'='*80}")
    print(f"ANALYZING DETECTION: '{det['text']}'")
    print(f"{'='*80}")
    print(f"  Position: ({det['x_min']}, {det['y_min']}) → ({det['x_max']}, {det['y_max']})")
    print(f"  Center: ({x_center:.1f}, {y_center:.1f})")
    print(f"  Confidence: {det['confidence']:.2%}")
    print(f"  Size: {det['width']}×{det['height']}")
    
    # Check if in header region
    if y_center <= header_y_max:
        print(f"\n⚠️  SKIPPED: Detection in HEADER region")
        print(f"  Y-center ({y_center:.1f}) <= Header max ({header_y_max:.1f})")
        return
    
    print(f"\n✅ Detection in DATA region (below header)")
    
    # Find candidate rows
    print(f"\n--- ROW MATCHING ---")
    print(f"Adaptive row tolerance: {adaptive_tolerance}px")
    
    row_ranges = [(h_lines[i], h_lines[i+1], i) for i in range(len(h_lines)-1)]
    candidate_rows = []
    
    for y_min, y_max, idx in row_ranges:
        if y_min - adaptive_tolerance <= y_center <= y_max + adaptive_tolerance:
            candidate_rows.append(idx)
            print(f"  ✅ Row {idx}: y_range=({y_min:.1f}, {y_max:.1f}), y_center={y_center:.1f}")
        else:
            # Show why it doesn't match
            if y_center < y_min - adaptive_tolerance:
                diff = (y_min - adaptive_tolerance) - y_center
                if diff < 20:  # Show close misses
                    print(f"  ❌ Row {idx}: Too HIGH by {diff:.1f}px")
            elif y_center > y_max + adaptive_tolerance:
                diff = y_center - (y_max + adaptive_tolerance)
                if diff < 20:
                    print(f"  ❌ Row {idx}: Too LOW by {diff:.1f}px")
    
    if not candidate_rows:
        print(f"\n❌ PROBLEM: No matching rows!")
        return
    
    # Find candidate columns
    print(f"\n--- COLUMN MATCHING ---")
    
    col_ranges = [(col['x_left'], col['x_right'], idx, col.get('name', 'Unknown')) 
                  for idx, col in enumerate(column_structure)]
    candidate_cols = []
    
    for x_min, x_max, idx, name in col_ranges:
        # Check if detection overlaps with column
        overlap = not (det['x_max'] < x_min or det['x_min'] > x_max)
        
        if overlap:
            candidate_cols.append(idx)
            print(f"  ✅ Col {idx} ({name[:20]}): x_range=({x_min:.1f}, {x_max:.1f}), det_x=({det['x_min']:.1f}, {det['x_max']:.1f})")
        else:
            # Show why it doesn't match
            if det['x_max'] < x_min:
                diff = x_min - det['x_max']
                if diff < 50:
                    print(f"  ❌ Col {idx} ({name[:20]}): Detection TOO LEFT by {diff:.1f}px")
            elif det['x_min'] > x_max:
                diff = det['x_min'] - x_max
                if diff < 50:
                    print(f"  ❌ Col {idx} ({name[:20]}): Detection TOO RIGHT by {diff:.1f}px")
    
    if not candidate_cols:
        print(f"\n❌ PROBLEM: No matching columns!")
        print(f"  Detection X-range: ({det['x_min']:.1f}, {det['x_max']:.1f})")
        print(f"  Detection width: {det['width']}px")
        return
    
    # Calculate scores for all candidates
    print(f"\n--- FUZZY SCORING ---")
    print(f"Candidates: {len(candidate_rows)} rows × {len(candidate_cols)} cols = {len(candidate_rows)*len(candidate_cols)}")
    
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
    
    all_scores = []
    
    for row_idx in candidate_rows:
        row_y_min = h_lines[row_idx]
        row_y_max = h_lines[row_idx + 1]
        
        for col_idx in candidate_cols:
            col_x_min = column_structure[col_idx]['x_left']
            col_x_max = column_structure[col_idx]['x_right']
            col_name = column_structure[col_idx].get('name', 'Unknown')
            
            cell_box = (col_x_min, row_y_min, col_x_max, row_y_max)
            det_box = (det['x_min'], det['y_min'], det['x_max'], det['y_max'])
            
            # Calculate components
            det_center_x = (det['x_min'] + det['x_max']) / 2
            det_center_y = (det['y_min'] + det['y_max']) / 2
            
            in_x = col_x_min <= det_center_x < col_x_max
            in_y = row_y_min <= det_center_y < row_y_max
            center_score = 1.0 if (in_x and in_y) else 0.0
            
            iou = calculate_iou(det_box, cell_box)
            
            cell_center_x = (col_x_min + col_x_max) / 2
            cell_center_y = (row_y_min + row_y_max) / 2
            distance = ((det_center_x - cell_center_x)**2 + (det_center_y - cell_center_y)**2)**0.5
            cell_width = col_x_max - col_x_min
            cell_height = row_y_max - row_y_min
            max_distance = ((cell_width/2)**2 + (cell_height/2)**2)**0.5
            distance_score = 1.0 - min(distance / max_distance, 1.0) if max_distance > 0 else 0.0
            
            # NEW weights
            total_score = (center_score * 0.30 + iou * 0.40 + distance_score * 0.20 + det['confidence'] * 0.10)
            
            all_scores.append({
                'row': row_idx,
                'col': col_idx,
                'col_name': col_name,
                'total': total_score,
                'center': center_score,
                'iou': iou,
                'distance': distance_score,
                'conf': det['confidence'],
                'in_x': in_x,
                'in_y': in_y
            })
    
    # Sort by score
    all_scores.sort(key=lambda x: x['total'], reverse=True)
    
    print(f"\nTop 5 candidate cells:")
    for i, score in enumerate(all_scores[:5]):
        status = "✅ MAPPED" if i == 0 and score['total'] > 0.12 else "❌ REJECTED"
        print(f"\n  {i+1}. Row {score['row']}, Col {score['col']} ({score['col_name'][:20]})")
        print(f"     Total: {score['total']:.3f} {status}")
        print(f"     - Center: {score['center']:.2f} (in_x={score['in_x']}, in_y={score['in_y']})")
        print(f"     - IoU:    {score['iou']:.2f}")
        print(f"     - Dist:   {score['distance']:.2f}")
        print(f"     - Conf:   {score['conf']:.2f}")
    
    if all_scores[0]['total'] <= 0.12:
        print(f"\n❌ PROBLEM: Best score {all_scores[0]['total']:.3f} <= threshold 0.12")
        print(f"   This detection will NOT be mapped!")


def main():
    """Main debug function"""
    
    test_image = "examples/2.png"
    
    if not Path(test_image).exists():
        print(f"❌ Image not found: {test_image}")
        return
    
    print("="*80)
    print("SPECIFIC CELL MAPPING DEBUG")
    print("="*80)
    print(f"\nTest Image: {test_image}\n")
    
    # Load and process
    print("[1/5] Loading and detecting BLOK III...")
    image = cv2.imread(test_image)
    bbox = detect_table_region(image)
    cropped = crop_table(image, bbox)
    print(f"✅ BLOK III cropped")
    
    print("\n[2/5] Running OCR...")
    detections = run_full_document_ocr(cropped)
    print(f"✅ OCR completed: {len(detections)} detections")
    
    print("\n[3/5] Detecting structure...")
    h_lines = detect_horizontal_lines(cropped)
    v_lines = detect_vertical_lines(cropped)
    header_groups = detect_header_rows(detections)
    column_structure = learn_column_structure(header_groups, v_lines)
    print(f"✅ Structure: {len(h_lines)} H-lines, {len(column_structure)} columns")
    
    # Calculate header max
    header_y_max = 0
    for det in detections:
        y_center = (det['y_min'] + det['y_max']) / 2
        if y_center < cropped.shape[0] * 0.25:
            header_y_max = max(header_y_max, det['y_max'])
    
    adaptive_tolerance = max(8, int(((h_lines[-1] - h_lines[0]) / max(len(h_lines) - 1, 1)) * 0.25))
    
    print("\n[4/5] Searching for specific detections...")
    
    # Search for "0011" (Kode SLS yang hilang)
    print("\n" + "="*80)
    print("ISSUE 1: Kode SLS '0011' tidak termapping")
    print("="*80)
    
    results_0011 = find_detection_by_text(detections, "0011")
    if results_0011:
        print(f"\nFound {len(results_0011)} detection(s) containing '0011':")
        for r in results_0011:
            print(f"  #{r['index']}: '{r['text']}' (conf={r['confidence']:.2%})")
            print(f"     Position: {r['position']}, Center: {r['center']}")
        
        # Analyze first match
        det_0011 = detections[results_0011[0]['index']]
        analyze_specific_detection(det_0011, h_lines, column_structure, adaptive_tolerance, header_y_max)
    else:
        print("\n❌ No detection found containing '0011'!")
        print("   Possible OCR misread or not detected at all")
    
    # Search for Muatan Dominan column (should be numbers)
    print("\n\n" + "="*80)
    print("ISSUE 2: Muatan Dominan column kosong")
    print("="*80)
    
    # Find Muatan Dominan column index
    muatan_col_idx = -1
    for idx, col in enumerate(column_structure):
        if 'muatan' in col.get('name', '').lower() and 'dominan' in col.get('name', '').lower():
            muatan_col_idx = idx
            print(f"\nMuatan Dominan column found: Col {idx}")
            print(f"  Name: {col.get('name')}")
            print(f"  X-range: ({col['x_left']:.1f}, {col['x_right']:.1f})")
            print(f"  Width: {col['x_right'] - col['x_left']:.1f}px")
            break
    
    if muatan_col_idx >= 0:
        # Find all detections in this X-range
        col = column_structure[muatan_col_idx]
        candidates = []
        
        for idx, det in enumerate(detections):
            y_center = (det['y_min'] + det['y_max']) / 2
            if y_center > header_y_max:  # Data region only
                # Check X overlap
                if not (det['x_max'] < col['x_left'] or det['x_min'] > col['x_right']):
                    candidates.append({
                        'index': idx,
                        'text': det['text'],
                        'confidence': det['confidence'],
                        'x_center': (det['x_min'] + det['x_max']) / 2,
                        'y_center': y_center
                    })
        
        print(f"\nFound {len(candidates)} detection(s) in Muatan Dominan X-range:")
        for c in candidates[:10]:  # Show first 10
            print(f"  #{c['index']}: '{c['text']}' at x={c['x_center']:.1f}, y={c['y_center']:.1f}")
        
        if candidates:
            print(f"\n✅ OCR detected {len(candidates)} items in this column!")
            print(f"   Analyzing why they're not mapped...")
            
            # Analyze first few
            for c in candidates[:3]:
                det = detections[c['index']]
                analyze_specific_detection(det, h_lines, column_structure, adaptive_tolerance, header_y_max)
        else:
            print(f"\n❌ No detections found in Muatan Dominan X-range!")
    
    print("\n" + "="*80)
    print("DEBUGGING COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()

