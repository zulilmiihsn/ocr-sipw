"""Application-wide constants."""

from typing import FrozenSet

# Column indices (0-indexed, matching OCR output)
COL_KODE_SLS = 1
COL_SUB_SLS = 2
COL_RT_RW = 3
COL_NUMERIC_RANGE = range(4, 11)  # Columns 4-10
COL_NAMA_WILAYAH = 11
COL_SHIFT = 12
COL_CONTACT_PERSON = 15
COL_MUATAN_DOMINAN = 16

# Numeric columns (for validation)
NUMERIC_COLS: FrozenSet[int] = frozenset([1, 2] + list(range(4, 11)) + [12, 15, 16])
MANDATORY_NUMERIC_COLS = [1, 2, 15]

# Table structure
EXPECTED_ROWS = 10
EXPECTED_COLS = 16

# File formats
SUPPORTED_IMAGE_FORMATS = ['.png', '.jpg', '.jpeg']
SUPPORTED_EXPORT_FORMATS = ['.xlsx', '.csv', '.json', '.html']

# UI constants
DEFAULT_MIN_COLUMN_WIDTHS = [
    70,   # Kode SLS/Non-SLS
    65,   # Kode Sub-SLS
    100,  # Nama SLS/Non-SLS
    80,   # Perkiraan Jumlah Muatan KK
    60,   # BTT
    70,   # BTT Kosong
    60,   # BKU
    90,   # Bangunan Bukan Tempat Tinggal
    75,   # Perkiraan Jumlah Muatan Usaha
    65,   # Total Muatan
    90,   # Nama Wilayah Konsentrasi
    75,   # Jumlah Shift
    75,   # Jam Operasional
    90,   # Contact - Telepon/Email
    75,   # Contact - Muatan Dominan
    65    # Perubahan batas (reko)
]

