"""
OCR Engine wrapper untuk Tesseract dan PaddleOCR
"""

import cv2
import numpy as np
from typing import Tuple, Optional
import pytesseract
from dataclasses import dataclass

# Try to import PaddleOCR
try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
except ImportError:
    PADDLE_AVAILABLE = False


@dataclass
class OCRResult:
    """Result dari OCR"""
    text: str
    confidence: float
    engine: str


def ocr_cell(cell_image: np.ndarray, cell_type: str = "mixed") -> OCRResult:
    """
    Perform OCR pada single cell image
    
    Args:
        cell_image: Cell image (OpenCV format)
        cell_type: Type of cell ('numeric', 'text', 'mixed')
        
    Returns:
        OCRResult object
    """
    # Try Tesseract first (faster, generally good for printed text)
    result_tesseract = _ocr_tesseract(cell_image, cell_type)
    
    # If low confidence and PaddleOCR available, try it
    if result_tesseract.confidence < 0.6 and PADDLE_AVAILABLE:
        result_paddle = _ocr_paddle(cell_image, cell_type)
        
        # Use whichever has higher confidence
        if result_paddle.confidence > result_tesseract.confidence:
            return result_paddle
    
    return result_tesseract


def _ocr_tesseract(image: np.ndarray, cell_type: str) -> OCRResult:
    """
    OCR using Tesseract
    """
    # Configure based on cell type
    config = _get_tesseract_config(cell_type)
    
    # Try to get detailed data (text + confidence)
    try:
        data = pytesseract.image_to_data(
            image,
            config=config,
            output_type=pytesseract.Output.DICT
        )
        
        # Extract text and average confidence
        texts = []
        confidences = []
        
        for i, text in enumerate(data['text']):
            if text.strip():
                texts.append(text)
                conf = float(data['conf'][i]) if data['conf'][i] != -1 else 0
                confidences.append(conf)
        
        # Combine text
        combined_text = ' '.join(texts).strip()
        
        # Calculate average confidence
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        avg_confidence = avg_confidence / 100.0  # Convert to 0-1 scale
        
    except Exception as e:
        # Fallback to simple method
        combined_text = pytesseract.image_to_string(image, config=config).strip()
        avg_confidence = 0.5  # Default confidence
    
    return OCRResult(
        text=combined_text,
        confidence=avg_confidence,
        engine="tesseract"
    )


def _ocr_paddle(image: np.ndarray, cell_type: str) -> OCRResult:
    """
    OCR using PaddleOCR (better for handwriting)
    """
    if not PADDLE_AVAILABLE:
        return OCRResult(text="", confidence=0.0, engine="paddle")
    
    try:
        # Initialize PaddleOCR (lazy initialization)
        if not hasattr(_ocr_paddle, 'ocr'):
            _ocr_paddle.ocr = PaddleOCR(use_angle_cls=True, lang='en')
        
        result = _ocr_paddle.ocr(image, cls=True)
        
        if result and len(result) > 0 and result[0]:
            # Combine all detected text
            texts = []
            confidences = []
            
            for line in result[0]:
                if line and len(line) == 2:
                    text, info = line
                    conf = info[1] if len(info) > 1 else 0.5
                    texts.append(text)
                    confidences.append(conf)
            
            combined_text = ' '.join(texts).strip()
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return OCRResult(
                text=combined_text,
                confidence=avg_confidence,
                engine="paddle"
            )
        
        return OCRResult(text="", confidence=0.0, engine="paddle")
        
    except Exception as e:
        return OCRResult(text="", confidence=0.0, engine="paddle")


def _get_tesseract_config(cell_type: str) -> str:
    """
    Get Tesseract configuration based on cell type
    
    Args:
        cell_type: 'numeric', 'text', or 'mixed'
        
    Returns:
        Tesseract config string
    """
    base_config = "--psm 6 -c tessedit_char_whitelist="
    
    if cell_type == "numeric":
        return f"{base_config}0123456789 --oem 3"
    elif cell_type == "text":
        return f"--psm 6 --oem 3"
    else:  # mixed
        return "--psm 6 --oem 3"


def preprocess_cell_for_ocr(image: np.ndarray) -> np.ndarray:
    """
    Preprocess cell image untuk optimal OCR results
    
    Args:
        image: Cell image
        
    Returns:
        Preprocessed image
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Resize if too small
    height, width = gray.shape
    if width < 50 or height < 20:
        scale = max(50 / width, 20 / height) * 1.5
        new_width = int(width * scale)
        new_height = int(height * scale)
        gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
    
    # Apply morphology to clean up
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    gray = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    
    return gray

