"""
Utility untuk validasi dan deteksi cell kosong
"""

import cv2
import numpy as np


def is_cell_empty(cell_image: np.ndarray, threshold: float = 0.02) -> bool:
    """
    Deteksi apakah cell kosong atau tidak
    
    Args:
        cell_image: Cell image
        threshold: Threshold untuk percentage of white pixels
        
    Returns:
        True jika cell kosong, False jika ada content
    """
    # Convert to grayscale if needed
    if len(cell_image.shape) == 3:
        gray = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_image.copy()
    
    # Calculate percentage of dark pixels (content)
    # Assuming binary image: black text on white background
    total_pixels = gray.size
    dark_pixels = np.sum(gray < 128)  # Dark pixels
    
    dark_percentage = dark_pixels / total_pixels
    
    # If less than threshold% dark pixels, consider it empty
    return dark_percentage < threshold


def has_sufficient_content(cell_image: np.ndarray, min_text_height: int = 10) -> bool:
    """
    Check if cell has sufficient text content (not just noise/lines)
    
    Args:
        cell_image: Cell image
        min_text_height: Minimum height untuk consider as text
        
    Returns:
        True jika ada content yang berarti
    """
    # Convert to grayscale
    if len(cell_image.shape) == 3:
        gray = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_image.copy()
    
    # Find contours
    _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Check if any contour is large enough to be text
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if h >= min_text_height and w >= 5:  # Minimum size for text
            return True
    
    return False


def validate_cell_ocr_result(ocr_text: str, cell_image: np.ndarray) -> str:
    """
    Validate OCR result berdasarkan cell content
    
    Args:
        ocr_text: Raw OCR text
        cell_image: Original cell image
        
    Returns:
        Validated text
    """
    # Check if cell is actually empty
    if is_cell_empty(cell_image):
        return ""  # Return empty if no content
    
    # Check if OCR result is just noise
    if not ocr_text or len(ocr_text.strip()) == 0:
        # Double check with image analysis
        if not has_sufficient_content(cell_image):
            return ""
    
    return ocr_text


