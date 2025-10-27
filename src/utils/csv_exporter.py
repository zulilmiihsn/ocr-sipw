"""
Utility untuk export data ke CSV
"""

import csv
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from src.utils.config import OUTPUT_DIR, CSV_DELIMITER, CSV_ENCODING, CSV_QUOTING
from src.models import COLUMN_HEADERS
import csv as csv_module

def export_to_csv(
    data: List[Dict[str, str]], 
    filename: str = None,
    output_dir: Path = None
) -> Path:
    """
    Export data ke CSV file
    
    Args:
        data: List of dictionaries dengan data (row-by-row)
        filename: Nama file output (optional)
        output_dir: Directory untuk menyimpan file
        
    Returns:
        Path ke file CSV yang dibuat
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR
    
    # Generate filename jika tidak diberikan
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ocr_result_{timestamp}.csv"
    
    output_path = output_dir / filename
    
    # Prepare CSV writer dengan quoting
    quoting = csv_module.QUOTE_MINIMAL
    
    # Write CSV
    with open(output_path, 'w', newline='', encoding=CSV_ENCODING) as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=COLUMN_HEADERS,
            delimiter=CSV_DELIMITER,
            quoting=quoting,
            escapechar='\\'
        )
        
        # Write header
        writer.writeheader()
        
        # Write data rows
        for row in data:
            # Ensure all columns are present
            clean_row = {}
            for col in COLUMN_HEADERS:
                clean_row[col] = row.get(col, "")
            writer.writerow(clean_row)
    
    return output_path


