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
    Convert PDF to list of images (one per page) using PyMuPDF
    
    Args:
        pdf_path: Path to PDF file
        dpi: Resolution for conversion (default 300 for good quality)
        
    Returns:
        List of images as numpy arrays (BGR format for OpenCV)
    """
    try:
        import fitz  # PyMuPDF
        import cv2
        
        print(f"📄 Converting PDF to images (DPI: {dpi})...")
        
        # Open PDF
        pdf_document = fitz.open(pdf_path)
        num_pages = len(pdf_document)
        
        print(f"  ✓ Detected {num_pages} page(s)")
        
        # Convert each page to image
        cv_images = []
        zoom = dpi / 72  # PDF default DPI is 72
        mat = fitz.Matrix(zoom, zoom)  # Zoom matrix
        
        for page_num in range(num_pages):
            # Get page
            page = pdf_document[page_num]
            
            # Render page to pixmap (image)
            pix = page.get_pixmap(matrix=mat)
            
            # Convert pixmap to numpy array (RGB)
            img_rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            
            # Convert RGB to BGR for OpenCV
            img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
            
            cv_images.append(img_bgr)
            print(f"  ✓ Page {page_num + 1}: {img_bgr.shape}")
        
        pdf_document.close()
        
        return cv_images
        
    except ImportError as e:
        raise ImportError(
            "PyMuPDF library not found.\n\n"
            "Install with: pip install PyMuPDF\n\n"
            "This is a pure Python library with no system dependencies!"
        ) from e
    except Exception as e:
        raise RuntimeError(f"Failed to convert PDF: {str(e)}") from e


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

