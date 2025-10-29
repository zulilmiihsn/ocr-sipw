"""
Advanced Cell Mapping System V2
Ultra-robust cell assignment using multi-criteria optimization
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from scipy.spatial.distance import euclidean


class AdvancedCellMapper:
    """
    Advanced cell mapper using:
    - DBSCAN-like clustering for row detection
    - Multi-criteria fuzzy scoring
    - Conflict resolution with priority system
    - Adaptive thresholding
    """
    
    def __init__(self, detections: List[Dict], h_lines: List[int], v_lines: List[int], 
                 column_structure: List[Dict], header_y_max: float):
        """
        Initialize mapper
        
        Args:
            detections: OCR detection results
            h_lines: Horizontal line Y-coordinates
            v_lines: Vertical line X-coordinates
            column_structure: Column definitions
            header_y_max: Maximum Y of header region
        """
        self.detections = detections
        self.h_lines = sorted(h_lines)
        self.v_lines = sorted(v_lines)
        self.column_structure = column_structure
        self.header_y_max = header_y_max
        
        # Statistics for adaptive thresholding
        self.compute_statistics()
    
    def compute_statistics(self):
        """Compute statistics from data for adaptive behavior"""
        # Get all Y-centers of data detections
        data_y_centers = []
        for det in self.detections:
            y_center = (det['y_min'] + det['y_max']) / 2
            if y_center > self.header_y_max:
                data_y_centers.append(y_center)
        
        if len(data_y_centers) > 0:
            self.y_mean = np.mean(data_y_centers)
            self.y_std = np.std(data_y_centers)
            
            # Compute typical row height from horizontal lines
            if len(self.h_lines) >= 2:
                line_gaps = [self.h_lines[i+1] - self.h_lines[i] for i in range(len(self.h_lines)-1)]
                # Filter out header gaps (too small)
                data_gaps = [g for g in line_gaps if g > 30]
                if data_gaps:
                    self.avg_row_height = np.mean(data_gaps)
                    self.std_row_height = np.std(data_gaps)
                else:
                    self.avg_row_height = 60
                    self.std_row_height = 10
            else:
                self.avg_row_height = 60
                self.std_row_height = 10
        else:
            self.y_mean = 500
            self.y_std = 100
            self.avg_row_height = 60
            self.std_row_height = 10
        
        print(f"📊 Mapping Statistics:")
        print(f"   Avg row height: {self.avg_row_height:.1f}px ± {self.std_row_height:.1f}px")
        print(f"   Y-distribution: μ={self.y_mean:.1f}, σ={self.y_std:.1f}")
    
    def calculate_iou(self, box1: Tuple[float, float, float, float], 
                      box2: Tuple[float, float, float, float]) -> float:
        """Calculate Intersection over Union"""
        x1_min, y1_min, x1_max, y1_max = box1
        x2_min, y2_min, x2_max, y2_max = box2
        
        # Intersection
        inter_x_min = max(x1_min, x2_min)
        inter_y_min = max(y1_min, y2_min)
        inter_x_max = min(x1_max, x2_max)
        inter_y_max = min(y1_max, y2_max)
        
        if inter_x_max < inter_x_min or inter_y_max < inter_y_min:
            return 0.0
        
        inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
        
        # Union
        box1_area = (x1_max - x1_min) * (y1_max - y1_min)
        box2_area = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = box1_area + box2_area - inter_area
        
        return inter_area / union_area if union_area > 0 else 0.0
    
    def calculate_overlap_ratio(self, det_box: Tuple[float, float, float, float],
                                cell_box: Tuple[float, float, float, float]) -> float:
        """
        Calculate what percentage of detection is inside cell
        More lenient than IoU
        """
        x1_min, y1_min, x1_max, y1_max = det_box
        x2_min, y2_min, x2_max, y2_max = cell_box
        
        # Intersection
        inter_x_min = max(x1_min, x2_min)
        inter_y_min = max(y1_min, y2_min)
        inter_x_max = min(x1_max, x2_max)
        inter_y_max = min(y1_max, y2_max)
        
        if inter_x_max < inter_x_min or inter_y_max < inter_y_min:
            return 0.0
        
        inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
        det_area = (x1_max - x1_min) * (y1_max - y1_min)
        
        return inter_area / det_area if det_area > 0 else 0.0
    
    def compute_advanced_score(self, det: Dict, row_idx: int, col_idx: int) -> float:
        """
        Compute advanced multi-criteria score for cell assignment
        
        Criteria (weighted):
        1. Overlap ratio (35%) - How much of detection is in cell
        2. IoU (25%) - Geometric overlap quality
        3. Center distance (20%) - Distance from cell center
        4. Y-alignment (10%) - How well aligned vertically
        5. Confidence (10%) - OCR confidence
        """
        # Get cell boundaries
        row_y_min = self.h_lines[row_idx]
        row_y_max = self.h_lines[row_idx + 1]
        col_x_min = self.column_structure[col_idx]['x_left']
        col_x_max = self.column_structure[col_idx]['x_right']
        
        cell_box = (col_x_min, row_y_min, col_x_max, row_y_max)
        det_box = (det['x_min'], det['y_min'], det['x_max'], det['y_max'])
        
        # Detection center
        det_center_x = (det['x_min'] + det['x_max']) / 2
        det_center_y = (det['y_min'] + det['y_max']) / 2
        
        # Cell center
        cell_center_x = (col_x_min + col_x_max) / 2
        cell_center_y = (row_y_min + row_y_max) / 2
        
        # 1. Overlap Ratio (35%) - Most important!
        overlap_ratio = self.calculate_overlap_ratio(det_box, cell_box)
        
        # 2. IoU (25%)
        iou = self.calculate_iou(det_box, cell_box)
        
        # 3. Center Distance (20%)
        cell_width = col_x_max - col_x_min
        cell_height = row_y_max - row_y_min
        max_distance = np.sqrt((cell_width/2)**2 + (cell_height/2)**2)
        
        if max_distance > 0:
            actual_distance = np.sqrt((det_center_x - cell_center_x)**2 + 
                                     (det_center_y - cell_center_y)**2)
            distance_score = 1.0 - min(actual_distance / max_distance, 1.0)
        else:
            distance_score = 0.0
        
        # 4. Y-Alignment (10%) - Check if vertically aligned
        y_diff = abs(det_center_y - cell_center_y)
        y_tolerance = cell_height / 2
        y_alignment_score = max(0, 1.0 - (y_diff / y_tolerance)) if y_tolerance > 0 else 0.0
        
        # 5. Confidence (10%)
        conf_score = det['confidence']
        
        # Weighted combination
        total_score = (
            overlap_ratio * 0.35 +     # Prioritas utama: overlap
            iou * 0.25 +                # Kualitas geometric
            distance_score * 0.20 +     # Proximity to center
            y_alignment_score * 0.10 +  # Vertical alignment
            conf_score * 0.10           # OCR confidence
        )
        
        return total_score
    
    def find_best_cell_for_detection(self, det: Dict) -> Tuple[int, int, float]:
        """
        Find best cell for a detection using multi-criteria scoring
        
        Returns:
            (row_idx, col_idx, score) or (-1, -1, 0.0) if no good match
        """
        det_center_y = (det['y_min'] + det['y_max']) / 2
        
        # Skip headers
        if det_center_y <= self.header_y_max:
            return (-1, -1, 0.0)
        
        best_score = 0.0
        best_row = -1
        best_col = -1
        
        # Adaptive tolerance based on row height
        y_tolerance = self.avg_row_height * 0.3  # 30% of avg row height
        
        # Try all possible cells
        for i in range(len(self.h_lines) - 1):
            row_y_min = self.h_lines[i]
            row_y_max = self.h_lines[i + 1]
            
            # Skip if detection Y is far from this row (adaptive)
            if det_center_y < row_y_min - y_tolerance or det_center_y > row_y_max + y_tolerance:
                continue
            
            for j in range(len(self.column_structure)):
                score = self.compute_advanced_score(det, i, j)
                
                if score > best_score:
                    best_score = score
                    best_row = i
                    best_col = j
        
        # Adaptive threshold based on statistics
        # Lower threshold if detection has high confidence
        if det['confidence'] >= 0.8:
            min_threshold = 0.30  # More lenient for high-conf
        elif det['confidence'] >= 0.5:
            min_threshold = 0.35  # Medium
        else:
            min_threshold = 0.40  # Strict for low-conf
        
        if best_score < min_threshold:
            return (-1, -1, 0.0)
        
        return (best_row, best_col, best_score)
    
    def resolve_conflicts(self, assignments: Dict[Tuple[int, int], List[Tuple[Dict, float]]]) -> Dict:
        """
        Resolve conflicts when multiple detections map to same cell
        
        Strategy:
        1. Sort by score (descending)
        2. Merge text if X-positions are well-separated (multi-word)
        3. Pick highest score if overlapping
        """
        final_cells = defaultdict(lambda: {'detections': []})
        
        for (row, col), det_list in assignments.items():
            if len(det_list) == 1:
                # No conflict
                det, score = det_list[0]
                final_cells[(row, col)]['detections'].append(det)
            else:
                # Multiple detections in same cell
                # Sort by X position
                det_list_sorted = sorted(det_list, key=lambda x: x[0]['x_min'])
                
                # Check if they're horizontally separated (multi-word in same cell)
                dets = [d for d, s in det_list_sorted]
                
                # Calculate gaps between consecutive detections
                gaps = []
                for i in range(len(dets) - 1):
                    gap = dets[i+1]['x_min'] - dets[i]['x_max']
                    gaps.append(gap)
                
                # If small gaps, likely same content, merge them
                # If large gaps, might be separate (conflict)
                if gaps and max(gaps) < 20:  # 20px threshold
                    # Merge all
                    for det, score in det_list_sorted:
                        final_cells[(row, col)]['detections'].append(det)
                else:
                    # Conflict: pick highest score
                    best_det = max(det_list, key=lambda x: x[1])
                    final_cells[(row, col)]['detections'].append(best_det[0])
        
        return final_cells
    
    def map_detections_to_cells(self) -> Dict:
        """
        Main mapping function
        
        Returns:
            Dictionary of (row, col) -> cell data
        """
        print(f"\n🧠 Advanced Cell Mapping V2...")
        print(f"   Processing {len(self.detections)} detections")
        print(f"   Target: {len(self.h_lines)-1} rows × {len(self.column_structure)} columns")
        
        # Step 1: Assign each detection to best cell
        assignments = defaultdict(list)
        unassigned = []
        
        for det in self.detections:
            row_idx, col_idx, score = self.find_best_cell_for_detection(det)
            
            if row_idx >= 0 and col_idx >= 0:
                assignments[(row_idx, col_idx)].append((det, score))
            else:
                unassigned.append(det)
        
        print(f"   ✓ Assigned: {len(self.detections) - len(unassigned)} detections")
        print(f"   ⚠ Unassigned: {len(unassigned)} detections (low confidence or ambiguous)")
        
        # Step 2: Resolve conflicts
        print(f"   🔧 Resolving conflicts...")
        final_cells = self.resolve_conflicts(assignments)
        
        print(f"   ✓ Final cells populated: {len(final_cells)}")
        
        return final_cells


def map_with_advanced_system(detections: List[Dict], h_lines: List[int], v_lines: List[int],
                             column_structure: List[Dict], header_y_max: float) -> Dict:
    """
    Convenience function to use advanced mapper
    
    Returns:
        cells dictionary with merged text
    """
    mapper = AdvancedCellMapper(detections, h_lines, v_lines, column_structure, header_y_max)
    cells_raw = mapper.map_detections_to_cells()
    
    # Merge detections in each cell
    cells = defaultdict(lambda: {'detections': []})
    
    for (row, col), cell_data in cells_raw.items():
        dets = cell_data['detections']
        
        if len(dets) == 1:
            cells[(row, col)]['text'] = dets[0]['text']
            cells[(row, col)]['confidence'] = dets[0]['confidence']
        elif len(dets) > 1:
            # Sort by X position
            dets.sort(key=lambda d: d['x_min'])
            cells[(row, col)]['text'] = ' '.join(d['text'] for d in dets)
            cells[(row, col)]['confidence'] = sum(d['confidence'] for d in dets) / len(dets)
        
        cells[(row, col)]['detections'] = dets
    
    return cells

