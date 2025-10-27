"""
Post-processing dan validasi hasil OCR
"""

import re
from typing import Dict, List, Tuple
from src.models import get_column_type, get_column_whitelist


def clean_ocr_text(text: str, preserve_format: bool = True) -> str:
    """
    Clean OCR result dari noise
    
    Args:
        text: Raw OCR text
        preserve_format: If True, preserve special characters (e.g., koma desimal)
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra whitespace (but preserve spaces)
    text = " ".join(text.split())
    
    # Fix common OCR errors (but be careful with context)
    # Only replace in specific contexts to avoid breaking valid data
    text = text.replace("|", "I")
    # Don't auto-replace 'l' to 'I' or 'O' to '0' globally - too risky for numbers
    # Let column-specific validation handle this
    
    return text


def validate_cell_data(text: str, column_index: int) -> Tuple[str, bool]:
    """
    Validate dan clean data per cell sesuai kolomnya
    NOTE: Preserves original format seperti koma desimal (3,1) dan karakter valid lainnya
    
    Args:
        text: OCR result text
        column_index: Index kolom
        
    Returns:
        Tuple of (cleaned_text, is_valid)
    """
    cleaned = clean_ocr_text(text, preserve_format=True)
    col_type = get_column_type(column_index)
    whitelist = get_column_whitelist(column_index)
    
    # Apply whitelist CAREFULLY - preserve commas and dots for decimal numbers
    if whitelist and col_type == "numeric":
        # For numeric, allow digits, commas, dots (for decimals)
        cleaned = ''.join(c for c in cleaned if c in whitelist or c in ',.')
    elif whitelist:
        cleaned = ''.join(c for c in cleaned if c in whitelist)
    
    # Additional validation per column type
    is_valid = True
    
    if col_type == "numeric":
        # Allow decimal numbers with comma or dot
        # Don't strip commas/dots - they're part of the number (e.g., 3,1)
        # Just ensure there's at least one digit
        has_digit = any(c.isdigit() for c in cleaned)
        is_valid = has_digit
        
    elif col_type == "mixed":
        # Check for time format if it's the time column (column 13)
        if column_index == 13:
            # Try to validate HH:MM-HH:MM format
            if ":" in cleaned:
                is_valid = re.match(r'\d{1,2}:\d{2}-\d{1,2}:\d{2}', cleaned) is not None
    
    return cleaned, is_valid


def process_cell_results(cell_results: Dict[Tuple[int, int], str]) -> Dict[str, List[str]]:
    """
    Convert cell results ke format tabel (row by row)
    
    Args:
        cell_results: Dict of {(row, col): text}
        
    Returns:
        Dict of {column_name: [values]}
    """
    from src.models import COLUMN_HEADERS
    
    # Get max row and col
    max_row = max(row for row, _ in cell_results.keys()) if cell_results else 0
    max_col = len(COLUMN_HEADERS)
    
    # Initialize output dict
    output = {col: [] for col in COLUMN_HEADERS}
    
    # Process row by row
    for row in range(max_row + 1):
        for col in range(max_col):
            key = (row, col)
            text = cell_results.get(key, "")
            
            # Validate
            validated_text, _ = validate_cell_data(text, col)
            
            # Add to output
            col_name = COLUMN_HEADERS[col]
            if row == 0:
                output[col_name].append(validated_text)
            else:
                # Extend if needed
                while len(output[col_name]) <= row:
                    output[col_name].append("")
                output[col_name][row] = validated_text
    
    return output


def calculate_confidence_stats(results: List[Tuple[str, float]]) -> Dict[str, any]:
    """
    Calculate confidence statistics
    
    Args:
        results: List of (text, confidence) tuples
        
    Returns:
        Dict with statistics
    """
    if not results:
        return {
            "avg_confidence": 0.0,
            "min_confidence": 0.0,
            "max_confidence": 0.0,
            "low_confidence_count": 0
        }
    
    confidences = [conf for _, conf in results]
    
    return {
        "avg_confidence": sum(confidences) / len(confidences),
        "min_confidence": min(confidences),
        "max_confidence": max(confidences),
        "low_confidence_count": sum(1 for c in confidences if c < 0.5)
    }
