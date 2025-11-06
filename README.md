# OCR SiPW - BLOK III Table Extraction System

Sistem OCR untuk mengekstrak data dari tabel **BLOK III** pada formulir statistik dengan akurasi tinggi menggunakan GUI berbasis PyQt5.

## 🚀 Quick Start

```bash
# Clone repository
git clone https://github.com/zulilmiihsn/ocr-sipw.git
cd ocr-sipw

# Install dependencies
pip install -r requirements.txt

# Run GUI application
python app.py
```

## ✨ Fitur Utama

### 🎨 GUI Application
- **Multi-file processing** - Proses beberapa file sekaligus
- **PDF support** - Mendukung file PDF multi-halaman
- **Progress tracking** - Progress bar real-time
- **Interactive table** - Tabel hasil yang dapat diedit
- **Auto-sort** - Otomatis mengurutkan berdasarkan Kode SLS & Sub-SLS
- **Multiple export** - Export ke Excel, CSV, JSON, atau HTML
- **Color-coded confidence** - Indikator warna untuk tingkat kepercayaan

### 🔍 OCR Engine
- Menggunakan **PaddleOCR PP-OCRv5** untuk akurasi tinggi
- Deteksi tabel BLOK III otomatis
- Segmentasi sel dengan deteksi garis vertikal/horizontal
- Post-processing untuk pembersihan data

## 📁 Struktur Proyek

```
ocr-sipw/
├── app.py                    # Entry point aplikasi GUI
├── config/                   # Konfigurasi aplikasi
│   ├── settings.py          # Settings aplikasi
│   └── constants.py         # Konstanta
├── gui/                      # Komponen GUI
│   ├── main_window.py       # Main window
│   ├── loading_screen.py    # Loading screen
│   └── workers/             # Background workers
├── pipeline/                 # OCR engine
│   ├── ocr_engine.py        # Core OCR engine
│   ├── table_processor.py   # Table processing
│   └── lib/                 # Utilities
├── utils/                   # Utility modules
├── examples/                # Sample images
└── requirements.txt         # Dependencies
```

## 🛠️ Teknologi

- **Python 3.8+**
- **PaddleOCR** - OCR engine (PP-OCRv5)
- **PyQt5** - GUI framework
- **OpenCV** - Image processing
- **NumPy** - Numerical operations

## 📋 Requirements

Install semua dependencies dengan:

```bash
pip install -r requirements.txt
```

## 📝 Penggunaan

1. Jalankan aplikasi dengan `python app.py`
2. Pilih file gambar atau PDF melalui tombol "Pilih File" atau drag & drop
3. Tunggu proses OCR selesai
4. Periksa dan edit hasil di tabel jika perlu
5. Export hasil ke format yang diinginkan (Excel, CSV, JSON, atau HTML)

## 👨‍💻 Author

**PKL FILKOM UB**
- GitHub: [@zulilmiihsn](https://github.com/zulilmiihsn)
- Repository: [ocr-sipw](https://github.com/zulilmiihsn/ocr-sipw)

## 📜 License

MIT License

---

Made with ❤️ by PKL FILKOM UB
