"""
Configuration settings untuk aplikasi
"""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = DATA_DIR / "templates"
OUTPUT_DIR = DATA_DIR / "output"

# Create directories if not exist
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# OCR Settings
TESSERACT_LANG = "eng"
TESSERACT_PSM_MODE = 6  # Assume uniform block

# Preprocessing settings
MAX_IMAGE_WIDTH = 3000  # Resize jika lebih besar
DESKEW_THRESHOLD = 0.5
BINARIZATION_BLOCK_SIZE = 11
BINARIZATION_C = 2

# Table detection settings
TABLE_DETECTION_METHOD = "auto"  # "auto" or "template"
MIN_TABLE_AREA = 0.1  # Minimum 10% dari total image
MAX_SKEW_ANGLE = 5  # Maximum rotation dalam degrees

# Cell extraction settings
NUM_ROWS = 10
NUM_COLS = 17
CELL_PADDING = 5  # Padding around cell content in pixels

# OCR confidence thresholds
HIGH_CONFIDENCE = 0.8
MEDIUM_CONFIDENCE = 0.5
LOW_CONFIDENCE = 0.0

# Performance settings
ENABLE_MULTITHREADING = True
MAX_WORKERS = 4

# Output settings
CSV_DELIMITER = ","
CSV_ENCODING = "utf-8"
CSV_QUOTING = "minimal"

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = BASE_DIR / "ocr_scanner.log"


