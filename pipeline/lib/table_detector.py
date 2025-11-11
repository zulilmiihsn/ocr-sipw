# BLOK III Table Detection (Ratio-based Detection)
# NOTE: Using ratio-based detection directly to avoid PaddleOCR thread-safety issues
# PaddleOCR is still used for OCR text extraction, but not for region detection

import cv2
import numpy as np
import os
from typing import Tuple, Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)

# Control verbosity (set to False for production)
VERBOSE = os.getenv('OCR_VERBOSE', 'false').lower() == 'true'


def _fallback_ratio_detection(image: np.ndarray, height: int, width: int) -> Optional[Tuple[int, int, int, int]]:
    # Ratio-based BLOK III detection (primary method)
    # Uses fixed proportional positioning based on typical document layout.
    # Robust for documents with consistent template but varying scales.
    # Args:
    #     image: Full document image
    #     height: Image height
    #     width: Image width
    # Returns:
    #     Tuple of (x, y, width, height) or None if invalid
    if VERBOSE:
        logger.debug(f"RATIO-BASED DETECTION: Document size: {width}x{height}px")
    
    # BLOK III typically located at 19%-90% of document height
    # These ratios are measured from actual BPS form samples with ±3% safety margin
    # Measured from sample: Top=21.9%, Bottom=89.0% → Added ±3% margin
    TOP_RATIO = 0.19      # BLOK III starts at ~19% from top (measured)
    BOTTOM_RATIO = 0.90   # BLOK III ends at ~90% from top (measured)
    
    blok3_y_start = int(height * TOP_RATIO)
    blok3_y_end = int(height * BOTTOM_RATIO)
    blok3_height = blok3_y_end - blok3_y_start
    
    # Apply margins (same as keyword detection)
    blok3_y_start = max(blok3_y_start - 10, 0)           # -10px margin
    blok3_y_end = min(blok3_y_end + 10, height)          # +10px margin
    blok3_height = blok3_y_end - blok3_y_start
    
    # Validation: BLOK III should be at least 20% of document height
    min_height = int(height * 0.2)
    if blok3_height < min_height:
        if VERBOSE:
            logger.warning(f"FALLBACK FAILED: Height too small ({blok3_height}px < {min_height}px)")
        return None
    
    if VERBOSE:
        logger.debug(
            f"RATIO-BASED SUCCESS: Top ratio: {TOP_RATIO*100:.0f}% → y={blok3_y_start}, "
            f"Bottom ratio: {BOTTOM_RATIO*100:.0f}% → y={blok3_y_end}, "
            f"Height: {blok3_height}px ({blok3_height/height*100:.1f}% of document)"
        )
    
    return (0, blok3_y_start, width, blok3_height)


def detect_table_region(image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    # Detect BLOK III region using ratio-based detection (reliable and fast)
    # PaddleOCR keyword detection disabled due to thread-safety issues:
    # Error: (PreconditionNotMet) trace_order size should be equal to dependency_count_
    # This occurs when PaddleOCR is called in certain contexts or from multiple threads
    # 
    # The ratio-based detection is more reliable and faster for consistent document templates
    # PaddleOCR is still used for OCR text extraction within the detected region
    #
    # Args:
    #     image: Full document image
    # Returns:
    #     Tuple of (x, y, width, height) or None if not found
    height, width = image.shape[:2]
    
    # Use ratio-based detection directly (more reliable and avoids PaddleOCR threading issues)
    logger.debug("Using ratio-based detection for BLOK III region (fast and reliable)")
    return _fallback_ratio_detection(image, height, width)


def crop_table(image: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
    # crop region tabel dari image
    # Args:
    #     image: Full image
    #     bbox: Bounding box (x, y, width, height)
    # Returns:
    #     Cropped image
    x, y, w, h = bbox
    return image[y:y+h, x:x+w]
