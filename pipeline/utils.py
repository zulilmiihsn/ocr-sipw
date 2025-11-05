# utility functions untuk perhitungan di pipeline ocr
# menggabungkan logika yang duplikat supaya konsisten di semua tempat

from typing import List, Dict, Any, Optional
from config.settings import mapping_settings, table_settings


def calculate_header_y_max(
    header_groups: Optional[List[Dict[str, Any]]],
    sorted_h_lines: Optional[List[int]],
    ocr_results: Optional[List[Dict[str, Any]]],
    image_height: int
) -> int:
    # hitung posisi Y maksimum dari header dengan beberapa strategi fallback
    # fungsi ini punya beberapa cara untuk tentuin batas header:
    # 1. pakai H-lines di 30% bagian atas gambar (paling akurat)
    # 2. kalau H-lines gak ada, pakai header_groups dari hasil OCR
    # 3. kalau masih gak ada, pakai deteksi OCR langsung
    # 4. kalau semua gagal, pakai threshold default
    #
    # param:
    #   header_groups: grup header dari deteksi OCR (opsional)
    #   sorted_h_lines: posisi garis horizontal yang sudah diurutkan (opsional)
    #   ocr_results: hasil deteksi OCR (opsional, untuk fallback)
    #   image_height: tinggi gambar yang sudah di-crop
    #
    # return: posisi Y maksimum dari region header
    
    # strategi 1: pakai H-lines di 30% bagian atas (paling bisa diandalkan)
    if sorted_h_lines:
        header_candidates = [
            y for y in sorted_h_lines
            if y < image_height * mapping_settings.header_search_ratio
        ]
        
        if len(header_candidates) >= 1:
            # pakai garis terakhir di area header (garis pemisah)
            header_y_max = header_candidates[-1]
            return header_y_max
    
    # strategi 2: pakai header_groups dari deteksi OCR
    if header_groups and len(header_groups) > 0:
        header_y_max = max(g['y_center'] for g in header_groups) + table_settings.header_y_margin
        return header_y_max
    
    # strategi 3: fallback ke deteksi OCR langsung
    if ocr_results:
        header_y_max = 0
        for det in ocr_results:
            y_center = (det['y_min'] + det['y_max']) / 2
            if y_center < image_height * mapping_settings.header_search_ratio:
                header_y_max = max(header_y_max, det['y_max'])
        
        # tambahkan margin keamanan
        if header_y_max > 0:
            header_y_max += mapping_settings.header_margin_px
            return header_y_max
    
    # strategi 4: pakai threshold default
    return table_settings.header_y_threshold


def calculate_adaptive_tolerance(
    image_height: int,
    h_lines: Optional[List[int]] = None
) -> int:
    # hitung tolerance adaptif untuk matching baris
    # pakai perhitungan berdasarkan tinggi gambar untuk konsistensi
    # kalau h_lines tersedia, bisa juga pakai perhitungan berdasarkan tinggi baris
    #
    # param:
    #   image_height: tinggi gambar yang sudah di-crop
    #   h_lines: list garis horizontal (opsional, untuk perhitungan tinggi baris)
    #
    # return: nilai tolerance adaptif dalam pixel
    
    # metode utama: pakai tinggi gambar (konsisten dengan settings)
    tolerance_from_image = max(
        mapping_settings.adaptive_tolerance_min,
        int(image_height * mapping_settings.adaptive_tolerance_ratio)
    )
    
    # opsional: pakai tinggi baris kalau tersedia (bisa lebih akurat untuk kasus tertentu)
    if h_lines and len(h_lines) > 1:
        avg_row_height = (h_lines[-1] - h_lines[0]) / max(len(h_lines) - 1, 1)
        tolerance_from_row = max(8, int(avg_row_height * 0.25))
        
        # pakai nilai yang lebih kecil untuk matching yang lebih ketat (lebih konservatif)
        return min(tolerance_from_image, tolerance_from_row)
    
    return tolerance_from_image

