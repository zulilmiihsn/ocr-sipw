"""Application settings and configuration classes."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class OCRSettings:
    """OCR engine configuration."""
    lang: str = 'en'
    use_angle_cls: bool = False
    det_db_thresh: float = 0.3
    det_db_box_thresh: float = 0.5
    det_db_unclip_ratio: float = 1.6
    rec_batch_num: int = 16


@dataclass
class TableDetectionSettings:
    """Table detection configuration."""
    min_horizontal_line_ratio: int = 3
    min_vertical_line_ratio: int = 5
    header_y_threshold: int = 200
    header_y_tolerance: int = 20
    header_y_margin: int = 30
    header_keywords: Optional[List[str]] = None
    
    def __post_init__(self):
        """Initialize default header keywords if not provided."""
        if self.header_keywords is None:
            self.header_keywords = [
                'Kode', 'Nama', 'Jumlah', 'Perkiraan', 'Contact',
                'Apakah', 'Shift', 'Operasional', 'Wilayah', 'Muatan',
                'BTT', 'BKU', 'BBTT', 'Total'
            ]


@dataclass
class CellMappingSettings:
    """Cell mapping algorithm configuration."""
    # Adaptive tolerance
    adaptive_tolerance_ratio: float = 0.015  # 1.5% of image height
    adaptive_tolerance_min: int = 10
    
    # Header detection
    header_search_ratio: float = 0.30  # Top 30% of image
    header_margin_px: int = 20
    
    # Fuzzy matching threshold
    fuzzy_score_threshold: float = 0.12
    
    # Fuzzy score weights (for normal columns)
    center_weight_normal: float = 0.30
    iou_weight_normal: float = 0.40
    distance_weight_normal: float = 0.20
    confidence_weight: float = 0.10
    
    # Fuzzy score weights (for important columns 15-16)
    center_weight_important: float = 0.50
    iou_weight_important: float = 0.25
    distance_weight_important: float = 0.15
    
    # Rule prior weights
    rule_prior_max: float = 0.30  # Maximum rule prior bonus


@dataclass
class GUISettings:
    """GUI application settings."""
    window_min_width: int = 1280
    window_min_height: int = 800
    table_default_rows: int = 10
    table_default_cols: int = 16
    vertical_header_width: int = 40
    file_list_max_height: int = 120
    
    # Progress bar settings
    progress_init: int = 10
    progress_ocr_start: int = 30
    progress_structure_start: int = 70
    progress_column_start: int = 80
    progress_build_start: int = 90
    progress_complete: int = 100


@dataclass
class AppSettings:
    """Application-wide settings."""
    app_name: str = "OCR SiPW"
    app_version: str = "7.1"
    organization_name: str = "Lab OCR Team"
    
    # Cache settings
    ocr_cache_max: int = 16
    
    # Thread settings
    max_workers: int = 2  # For parallel table detection
    
    # Export settings
    default_export_format: str = "xlsx"


# Global settings instances (can be customized)
ocr_settings = OCRSettings()
table_settings = TableDetectionSettings()
mapping_settings = CellMappingSettings()
gui_settings = GUISettings()
app_settings = AppSettings()

