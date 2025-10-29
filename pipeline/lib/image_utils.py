"""
Image loading and basic operations
"""

import cv2
import numpy as np
from pathlib import Path


def load_image(image_path):
    """
    Load image from file (supports PNG, JPG, etc.)
    
    Args:
        image_path: Path to image file
        
    Returns:
        numpy.ndarray: Loaded image (BGR format)
        
    Raises:
        ValueError: If image cannot be loaded
    """
    path = Path(image_path)
    
    if not path.exists():
        raise ValueError(f"Image file not found: {image_path}")
    
    image = cv2.imread(str(path))
    
    if image is None:
        raise ValueError(f"Failed to load image: {image_path}")
    
    return image


def save_image(image, output_path):
    """
    Save image to file
    
    Args:
        image: numpy.ndarray image
        output_path: Path to save image
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image)
