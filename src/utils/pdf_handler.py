"""
Utility untuk handling PDF input
"""

from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image
import numpy as np
import cv2

def pdf_to_images(pdf_path: str) -> list[Image.Image]:
    """
    Convert PDF ke list of PIL Images
    
    Args:
        pdf_path: Path ke PDF file
        
    Returns:
        List of PIL Images
    """
    try:
        images = convert_from_path(
            pdf_path,
            dpi=300,  # High resolution untuk OCR
            fmt='png'
        )
        return images
    except Exception as e:
        raise ValueError(f"Error converting PDF to images: {str(e)}")

def image_to_opencv_format(pil_image: Image.Image) -> np.ndarray:
    """
    Convert PIL Image ke OpenCV format (numpy array)
    
    Args:
        pil_image: PIL Image
        
    Returns:
        OpenCV image (BGR format)
    """
    # Convert PIL to RGB
    rgb_image = np.array(pil_image.convert('RGB'))
    # Convert RGB to BGR for OpenCV
    bgr_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
    return bgr_image

def opencv_to_pil(image: np.ndarray) -> Image.Image:
    """
    Convert OpenCV format ke PIL Image
    
    Args:
        image: OpenCV image (BGR format)
        
    Returns:
        PIL Image
    """
    # Convert BGR to RGB
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    # Convert to PIL
    pil_image = Image.fromarray(rgb_image)
    return pil_image

def load_image(file_path: str) -> np.ndarray:
    """
    Load image dari file (support PDF, JPG, PNG)
    
    Args:
        file_path: Path ke file
        
    Returns:
        OpenCV image (BGR format)
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Handle PDF
    if path.suffix.lower() == '.pdf':
        images = pdf_to_images(str(path))
        # Get first page
        pil_image = images[0]
        return image_to_opencv_format(pil_image)
    
    # Handle image files (JPG, PNG, etc.)
    else:
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Failed to load image: {file_path}")
        return image

