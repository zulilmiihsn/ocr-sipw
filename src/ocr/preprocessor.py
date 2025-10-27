"""
Image preprocessing untuk optimasi OCR
"""

import cv2
import numpy as np
from PIL import Image
from typing import Tuple, Union
from src.utils.config import (
    MAX_IMAGE_WIDTH,
    DESKEW_THRESHOLD,
    BINARIZATION_BLOCK_SIZE,
    BINARIZATION_C
)


def load_image(image_path: str) -> np.ndarray:
    """
    Load image file ke OpenCV format
    
    Args:
        image_path: Path ke image file
        
    Returns:
        OpenCV image (BGR format)
    """
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Cannot load image: {image_path}")
    return image


def resize_image(image: np.ndarray, max_width: int = MAX_IMAGE_WIDTH) -> np.ndarray:
    """
    Resize image jika terlalu besar (untuk performance)
    
    Args:
        image: OpenCV image
        max_width: Maximum width untuk resize
        
    Returns:
        Resized image
    """
    height, width = image.shape[:2]
    
    if width > max_width:
        scale = max_width / width
        new_width = max_width
        new_height = int(height * scale)
        image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    
    return image


def deskew_image(image: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Auto-rotate image jika miring
    
    Args:
        image: OpenCV image
        
    Returns:
        Tuple of (rotated_image, rotation_angle)
    """
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Detect lines using Hough Transform
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi/180, 200)
    
    if lines is None or len(lines) == 0:
        return image, 0.0
    
    # Calculate average angle
    angles = []
    for line in lines[:20]:  # Use first 20 lines
        rho, theta = line[0]
        angle = np.degrees(theta - np.pi/2)
        angles.append(angle)
    
    median_angle = np.median(angles)
    
    # Only rotate if significant skew
    if abs(median_angle) < DESKEW_THRESHOLD:
        return image, 0.0
    
    # Rotate image
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), 
                            flags=cv2.INTER_CUBIC,
                            borderMode=cv2.BORDER_REPLICATE)
    
    return rotated, median_angle


def enhance_image(image: np.ndarray) -> np.ndarray:
    """
    Enhance contrast dan brightness untuk OCR
    
    Args:
        image: OpenCV image
        
    Returns:
        Enhanced image
    """
    # Convert to LAB color space
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    
    # Merge channels
    enhanced_lab = cv2.merge([l, a, b])
    enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
    
    return enhanced


def denoise_image(image: np.ndarray) -> np.ndarray:
    """
    Remove noise dari image
    
    Args:
        image: OpenCV image
        
    Returns:
        Denoised image
    """
    # Apply bilateral filter (preserves edges)
    denoised = cv2.bilateralFilter(image, 9, 75, 75)
    return denoised


def binarize_image(image: np.ndarray) -> np.ndarray:
    """
    Convert image ke binary (black & white) untuk OCR optimal
    NOTE: Optimized untuk preserve thin lines dan prevent data loss
    
    Args:
        image: OpenCV image
        
    Returns:
        Binary image
    """
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply adaptive threshold with careful parameters
    # Use smaller block size untuk better preserve thin details
    block_size = max(3, BINARIZATION_BLOCK_SIZE - 4)
    c_value = max(1, BINARIZATION_C - 1)
    
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        c_value
    )
    
    # Invert jika perlu (text should be black)
    # Most OCR engines expect white background with black text
    binary = cv2.bitwise_not(binary)
    
    return binary


def preprocess_image(image: Union[str, np.ndarray], 
                     full_pipeline: bool = True) -> np.ndarray:
    """
    Complete preprocessing pipeline
    
    Args:
        image: Image path or OpenCV image
        full_pipeline: Run full preprocessing steps
        
    Returns:
        Preprocessed image
    """
    # Load if path provided
    if isinstance(image, str):
        img = load_image(image)
    else:
        img = image.copy()
    
    if not full_pipeline:
        return img
    
    # Step 1: Resize if needed
    img = resize_image(img)
    
    # Step 2: Deskew
    img, _ = deskew_image(img)
    
    # Step 3: Enhance
    img = enhance_image(img)
    
    # Step 4: Denoise
    img = denoise_image(img)
    
    # Step 5: Binarize
    img = binarize_image(img)
    
    return img
