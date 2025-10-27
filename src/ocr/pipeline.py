"""
Main OCR pipeline untuk processing form
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, List
from PIL import Image

from src.ocr.preprocessor import preprocess_image
from src.ocr.table_detector import detect_table_region, crop_table
from src.ocr.rapid_table_detector import RapidTableDetectorWrapper
from src.ocr.cell_extractor import extract_cell_images, CellImage
from src.ocr.ocr_engine import ocr_cell, preprocess_cell_for_ocr, OCRResult
from src.ocr.postprocessor import clean_ocr_text, validate_cell_data
from src.ocr.cell_validator import is_cell_empty, validate_cell_ocr_result
from src.utils.pdf_handler import pdf_to_images, image_to_opencv_format, opencv_to_pil
from src.utils.config import NUM_ROWS, NUM_COLS
from src.models import get_column_type, get_column_name


class OCRPipeline:
    """Main OCR pipeline untuk processing form statistik"""
    
    def __init__(self, use_rapid_detection: bool = False):
        """
        Initialize OCR Pipeline
        
        Args:
            use_rapid_detection: If True, use RapidTableDetection for perspective 
                                correction (slower but handles rotated images).
                                If False (default), use ultra-fast OCR-only detection.
        """
        self.processed_image = None
        self.table_image = None
        self.cells = []
        self.results = {}
        
        # Initialize RapidTableDetection ONLY if explicitly requested
        self.rapid_detector = None
        if use_rapid_detection:
            try:
                self.rapid_detector = RapidTableDetectorWrapper(use_cuda=False)
                print("✓ RapidTableDetection enabled (slower, perspective correction)")
            except Exception as e:
                print(f"⚠ RapidTableDetection not available: {e}")
                print("  Falling back to ultra-fast OCR-only detection")
                self.rapid_detector = None
        else:
            print("✓ Ultra-fast OCR-only detection mode")
        
    def process_file(self, file_path: str) -> Dict[Tuple[int, int], str]:
        """
        Main processing function
        
        Args:
            file_path: Path ke form file (PDF/JPG/PNG)
            
        Returns:
            Dict of {(row, col): text} - hasil OCR
        """
        # Step 1: Load image
        image = self._load_image(file_path)
        
        # Step 2: Preprocessing
        self.processed_image = preprocess_image(image, full_pipeline=True)
        
        # Step 3: Detect table (ultra-fast OCR-only by default)
        bbox = detect_table_region(
            self.processed_image,
            use_rapid=self.rapid_detector is not None,
            rapid_detector=self.rapid_detector
        )
        
        if bbox is None:
            raise ValueError("Tidak bisa mendeteksi tabel BLOK III")
        
        self.table_image = crop_table(self.processed_image, bbox)
        
        # Step 4: Extract cells
        self.cells = extract_cell_images(self.table_image, NUM_ROWS, NUM_COLS)
        
        # Step 5: OCR per cell
        self.results = {}
        for cell in self.cells:
            text, confidence = self._ocr_cell(cell)
            
            # Skip header row (row 0)
            if cell.row > 0:
                self.results[(cell.row, cell.col)] = text
        
        return self.results
    
    def _load_image(self, file_path: str) -> np.ndarray:
        """Load image dari file atau PDF"""
        path = Path(file_path)
        
        if path.suffix.lower() == '.pdf':
            # Convert PDF ke images
            images = pdf_to_images(str(file_path))
            if not images:
                raise ValueError("PDF kosong atau tidak bisa dibaca")
            
            # Use first page
            pil_image = images[0]
            image = image_to_opencv_format(pil_image)
            
        elif path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']:
            image = cv2.imread(str(file_path))
            if image is None:
                raise ValueError(f"Cannot load image: {file_path}")
        
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
        
        return image
    
    def _ocr_cell(self, cell: CellImage) -> Tuple[str, float]:
        """Perform OCR on single cell"""
        
        # IMPORTANT: Check if cell is empty FIRST
        if is_cell_empty(cell.image):
            return "", 1.0  # Return empty with high confidence
        
        # Preprocess cell
        cell_img = preprocess_cell_for_ocr(cell.image)
        
        # Get column type
        col_type = get_column_type(cell.col)
        
        # Perform OCR
        result = ocr_cell(cell_img, cell_type=col_type)
        
        # Validate result dengan original cell image
        validated_text = validate_cell_ocr_result(result.text, cell.image)
        
        # Post-process dan clean
        cleaned_text, _ = validate_cell_data(validated_text, cell.col)
        
        return cleaned_text, result.confidence
    
    def get_preview_image(self) -> Image.Image:
        """Get preview image untuk GUI"""
        if self.processed_image is not None:
            return opencv_to_pil(self.processed_image)
        return None
    
    def get_table_preview_image(self) -> Image.Image:
        """Get preview table image"""
        if self.table_image is not None:
            return opencv_to_pil(self.table_image)
        return None
    
    def get_results_structured(self) -> List[Dict[str, str]]:
        """
        Get results dalam format list of dictionaries (ready untuk CSV export)
        
        Returns:
            List of dicts, each dict is a row
        """
        from src.models import COLUMN_HEADERS
        
        # Find max row
        max_row = max(row for row, _ in self.results.keys()) if self.results else 0
        
        structured_results = []
        
        for row in range(1, max_row + 1):  # Skip header (row 0)
            row_data = {}
            
            for col in range(len(COLUMN_HEADERS)):
                col_name = get_column_name(col)
                text = self.results.get((row, col), "")
                row_data[col_name] = text
            
            structured_results.append(row_data)
        
        return structured_results
