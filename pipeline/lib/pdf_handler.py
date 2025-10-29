"""
PDF Handler - Convert PDF to images for OCR processing
"""
import os
from pathlib import Path
from typing import List, Tuple
import numpy as np


def is_pdf(file_path: str) -> bool:
    """Check if file is a PDF"""
    return Path(file_path).suffix.lower() == '.pdf'


def pdf_to_images(pdf_path: str, dpi: int = 300) -> List[np.ndarray]:
    """
    Convert PDF to list of images (one per page)
    
    Args:
        pdf_path: Path to PDF file
        dpi: Resolution for conversion (default 300 for good quality)
        
    Returns:
        List of images as numpy arrays (BGR format for OpenCV)
    """
    try:
        from pdf2image import convert_from_path
        import cv2
        
        print(f"📄 Converting PDF to images (DPI: {dpi})...")
        
        # Convert PDF to PIL images
        pil_images = convert_from_path(pdf_path, dpi=dpi)
        
        print(f"  ✓ Extracted {len(pil_images)} page(s)")
        
        # Convert PIL images to OpenCV format (numpy BGR)
        cv_images = []
        for i, pil_img in enumerate(pil_images):
            # Convert PIL RGB to OpenCV BGR
            img_rgb = np.array(pil_img)
            img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
            cv_images.append(img_bgr)
            print(f"  ✓ Page {i+1}: {img_bgr.shape}")
        
        return cv_images
        
    except ImportError:
        raise ImportError(
            "pdf2image library not found. Install with: pip install pdf2image\n"
            "Also requires poppler: https://poppler.freedesktop.org/"
        )
    except Exception as e:
        raise RuntimeError(f"Failed to convert PDF: {str(e)}")


def load_document(file_path: str, dpi: int = 300) -> Tuple[List[np.ndarray], str]:
    """
    Load document (PDF or image) and return list of images
    
    Args:
        file_path: Path to PDF or image file
        dpi: Resolution for PDF conversion (ignored for images)
        
    Returns:
        Tuple of (list of images, file type 'pdf' or 'image')
    """
    import cv2
    
    if is_pdf(file_path):
        images = pdf_to_images(file_path, dpi=dpi)
        return images, 'pdf'
    else:
        # Single image file
        image = cv2.imread(file_path)
        if image is None:
            raise ValueError(f"Failed to load image: {file_path}")
        return [image], 'image'

