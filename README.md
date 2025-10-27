# OCR Form Scanner - Aplikasi Pengenalan Form Statistik

Aplikasi desktop berbasis Python untuk scanning dan ekstraksi data dari form statistik "DAFTAR REKAP SLS" menggunakan OCR (Optical Character Recognition).

## Fitur

- ✅ Support input PDF, JPG, PNG
- ✅ Deteksi otomatis posisi tabel BLOK III
- ✅ OCR untuk tulisan tangan dan teks cetak
- ✅ Preprocessing otomatis (deskew, denoise, enhance)
- ✅ UI untuk review dan edit hasil OCR
- ✅ Export ke CSV dengan encoding UTF-8
- ✅ Single .exe file - mudah didistribusi

## Installation

### Development

1. Clone repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Tesseract OCR:
   - Windows: Download dari https://github.com/UB-Mannheim/tesseract/wiki
   - Set path ke tesseract di environment variable

4. Run aplikasi:
```bash
python src/main.py
```

### Build Executable

```bash
pyinstaller build.spec
```

Output akan di `dist/OCR-Form-Scanner.exe`

## Usage

1. Jalankan aplikasi
2. Upload file PDF/JPG/PNG form statistik
3. Klik "Process" untuk mulai OCR
4. Review dan edit hasil di table view
5. Export ke CSV

## Struktur Project

```
lab-untuk-ocr/
├── src/
│   ├── main.py              # Entry point
│   ├── gui/                  # GUI components
│   ├── ocr/                  # OCR processing
│   ├── utils/                # Utilities
│   └── models/               # Data models
├── data/
│   ├── templates/            # Template files
│   └── output/               # Output directory
└── requirements.txt
```

## Requirements

- Python 3.10+
- Tesseract OCR
- PaddleOCR (optional, untuk handwriting)

## License

MIT

