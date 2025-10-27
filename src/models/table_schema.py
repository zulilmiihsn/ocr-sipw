"""
Schema untuk tabel BLOK III REKAPITULASI MUATAN
Mapping kolom dan validasi
"""

# Header kolom untuk output CSV
COLUMN_HEADERS = [
    "No",
    "Kode Kab/Kota SLS",
    "Kode Kec",
    "Nama SLS/Non-SLS",
    "Perkiraan Jumlah Muatan KK",
    "BTT",
    "BTT Kosong",
    "BKU",
    "BBTT non Usaha",
    "Perkiraan Jumlah Muatan Usaha",
    "Total Muatan Ekonomi",
    "Nama Wilayah Konsentrasi Ekonomi",
    "Jumlah Shift Pada Wilayah Konsentrasi Ekonomi",
    "Jam Operasional",
    "Contact Person",
    "Muatan Dominan",
    "Apakah terdapat perubahan batas (hasil rekon ?)"
]

# Mapping tipe data per kolom untuk optimasi OCR
COLUMN_TYPES = {
    0: "numeric",  # No
    1: "numeric",  # Kode Kab/Kota SLS
    2: "numeric",  # Kode Kec
    3: "text",     # Nama SLS/Non-SLS
    4: "numeric",  # Perkiraan Jumlah Muatan KK
    5: "numeric",  # BTT
    6: "numeric",  # BTT Kosong
    7: "numeric",  # BKU
    8: "numeric",  # BBTT non Usaha
    9: "numeric",  # Perkiraan Jumlah Muatan Usaha
    10: "numeric", # Total Muatan Ekonomi
    11: "text",    # Nama Wilayah Konsentrasi Ekonomi
    12: "numeric", # Jumlah Shift
    13: "mixed",   # Jam Operasional (format: HH:MM-HH:MM)
    14: "mixed",   # Contact Person (bisa ada email/telepon)
    15: "numeric", # Muatan Dominan
    16: "numeric"  # Perubahan batas
}

# Karakter whitelist untuk optimasi OCR per kolom
# NOTE: Untuk numeric, kita tidak strict-whitelist karena perlu preserve commas/dots untuk desimal
COLUMN_WHITELISTS = {
    "numeric": "0123456789,.",  # Include comma and dot untuk desimal (3,1 atau 3.1)
    "text": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789/-",
    "mixed": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789@.-/:"
}

def get_column_type(column_index: int) -> str:
    """Get column type untuk optimasi OCR"""
    return COLUMN_TYPES.get(column_index, "mixed")

def get_column_whitelist(column_index: int) -> str:
    """Get whitelist karakter untuk kolom tertentu"""
    col_type = get_column_type(column_index)
    return COLUMN_WHITELISTS.get(col_type, "")

def get_column_name(column_index: int) -> str:
    """Get nama kolom untuk output"""
    if 0 <= column_index < len(COLUMN_HEADERS):
        return COLUMN_HEADERS[column_index]
    return f"Column_{column_index}"
