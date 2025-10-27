"""
Extract individual cells dari tabel
"""

import cv2
import numpy as np
from typing import List, Tuple
from dataclasses import dataclass
from src.utils.config import NUM_ROWS, NUM_COLS, CELL_PADDING


@dataclass
class CellImage:
    """Data class untuk cell image"""
    row: int
    col: int
    image: np.ndarray
    x: int
    y: int
    width: int
    height: int


def detect_grid(image: np.ndarray) -> Tuple[List[int], List[int]]:
    """
    Detect grid lines untuk segmentasi cells
    
    Args:
        image: Table image (binary or grayscale)
        
    Returns:
        Tuple of (horizontal_lines, vertical_lines)
    """
    # Get image dimensions
    height, width = image.shape[:2]
    
    # Detect horizontal lines
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (width // NUM_COLS, 1))
    detected_horizontal = cv2.morphologyEx(image, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    
    # Detect vertical lines
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, height // NUM_ROWS))
    detected_vertical = cv2.morphologyEx(image, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
    
    # Get horizontal line positions
    horizontal_projection = cv2.reduce(detected_horizontal, 1, cv2.REDUCE_AVG)
    horizontal_lines = []
    for i, proj in enumerate(horizontal_projection):
        if proj[0] > 0:  # There's a line here
            horizontal_lines.append(i)
    
    # Get vertical line positions
    vertical_projection = cv2.reduce(detected_vertical, 0, cv2.REDUCE_AVG)
    vertical_lines = []
    for i, proj in enumerate(vertical_projection):
        if proj[0] > 0:  # There's a line here
            vertical_lines.append(i)
    
    # Clean up lines (remove duplicates and close lines)
    horizontal_lines = _clean_lines(horizontal_lines)
    vertical_lines = _clean_lines(vertical_lines)
    
    return horizontal_lines, vertical_lines


def _clean_lines(lines: List[int], min_gap: int = 5) -> List[int]:
    """
    Remove duplicate and close lines
    
    Args:
        lines: List of line positions
        min_gap: Minimum gap between lines
        
    Returns:
        Cleaned list of lines
    """
    if not lines:
        return lines
    
    # Sort lines
    sorted_lines = sorted(lines)
    cleaned = [sorted_lines[0]]
    
    for line in sorted_lines[1:]:
        if line - cleaned[-1] > min_gap:
            cleaned.append(line)
    
    return cleaned


def segment_cells(image: np.ndarray, num_rows: int = NUM_ROWS, num_cols: int = NUM_COLS) -> List[CellImage]:
    """
    Segment table into individual cells
    
    Args:
        image: Table image
        num_rows: Expected number of rows (including header)
        num_cols: Expected number of columns
        
    Returns:
        List of CellImage objects
    """
    height, width = image.shape[:2]
    
    # Get grid lines
    horizontal_lines, vertical_lines = detect_grid(image)
    
    # If we have grid lines, use them
    if len(horizontal_lines) >= num_rows + 1 and len(vertical_lines) >= num_cols + 1:
        return _segment_by_grid(image, horizontal_lines, vertical_lines, num_rows, num_cols)
    else:
        # Otherwise, use uniform grid
        return _segment_uniform(image, num_rows, num_cols)


def _segment_by_grid(image: np.ndarray, h_lines: List[int], v_lines: List[int], 
                      num_rows: int, num_cols: int) -> List[CellImage]:
    """
    Segment using detected grid lines
    """
    cells = []
    
    # Ensure we have enough lines
    if len(h_lines) < num_rows + 1:
        h_lines = _interpolate_lines(h_lines, image.shape[0], num_rows + 1)
    if len(v_lines) < num_cols + 1:
        v_lines = _interpolate_lines(v_lines, image.shape[1], num_cols + 1)
    
    for i in range(num_rows):
        for j in range(min(num_cols, len(v_lines) - 1)):
            # Cell boundaries
            y1 = h_lines[i]
            y2 = h_lines[i + 1] if i + 1 < len(h_lines) else image.shape[0]
            x1 = v_lines[j]
            x2 = v_lines[j + 1] if j + 1 < len(v_lines) else image.shape[1]
            
            # Add padding
            y1 = max(0, y1 - CELL_PADDING)
            y2 = min(image.shape[0], y2 + CELL_PADDING)
            x1 = max(0, x1 - CELL_PADDING)
            x2 = min(image.shape[1], x2 + CELL_PADDING)
            
            # Extract cell
            cell_img = image[y1:y2, x1:x2]
            
            cell = CellImage(
                row=i,
                col=j,
                image=cell_img,
                x=x1,
                y=y1,
                width=x2 - x1,
                height=y2 - y1
            )
            cells.append(cell)
    
    return cells


def _segment_uniform(image: np.ndarray, num_rows: int, num_cols: int) -> List[CellImage]:
    """
    Segment using uniform grid (fallback method)
    """
    cells = []
    height, width = image.shape[:2]
    
    row_height = height // num_rows
    col_width = width // num_cols
    
    for i in range(num_rows):
        for j in range(num_cols):
            y1 = i * row_height
            y2 = (i + 1) * row_height if i < num_rows - 1 else height
            x1 = j * col_width
            x2 = (j + 1) * col_width if j < num_cols - 1 else width
            
            # Add padding
            y1 = max(0, y1 - CELL_PADDING)
            y2 = min(height, y2 + CELL_PADDING)
            x1 = max(0, x1 - CELL_PADDING)
            x2 = min(width, x2 + CELL_PADDING)
            
            cell_img = image[y1:y2, x1:x2]
            
            cell = CellImage(
                row=i,
                col=j,
                image=cell_img,
                x=x1,
                y=y1,
                width=x2 - x1,
                height=y2 - y1
            )
            cells.append(cell)
    
    return cells


def _interpolate_lines(lines: List[int], max_dim: int, target_count: int) -> List[int]:
    """
    Interpolate missing lines to get target count
    """
    if not lines:
        # No lines detected, create uniform grid
        return [int(i * max_dim / target_count) for i in range(target_count)]
    
    if len(lines) >= target_count:
        return lines[:target_count]
    
    # Interpolate between existing lines
    result = []
    for i in range(target_count):
        pos = int(i * max_dim / target_count)
        result.append(pos)
    
    return result


def extract_cell_images(image: np.ndarray, num_rows: int = NUM_ROWS, num_cols: int = NUM_COLS) -> List[CellImage]:
    """
    Main function to extract cell images
    
    Args:
        image: Table image
        num_rows: Number of rows
        num_cols: Number of columns
        
    Returns:
        List of CellImage objects
    """
    return segment_cells(image, num_rows, num_cols)

