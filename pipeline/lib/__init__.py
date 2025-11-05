# library utility pipeline untuk deteksi tabel dan pemrosesan gambar

from .table_detector import detect_table_region, crop_table

__all__ = [
    'detect_table_region',
    'crop_table',
]
