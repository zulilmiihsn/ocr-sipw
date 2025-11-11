# OCR SiPW - BLOK III Table Extraction System

Sistem OCR untuk mengekstrak data dari tabel **BLOK III** pada formulir statistik dengan akurasi tinggi menggunakan GUI berbasis PyQt5.

## 🚀 Quick Start

**Langkah cepat:**
```bash
# 1. Clone atau download project
git clone https://github.com/zulilmiihsn/ocr-sipw.git
cd ocr-sipw

# 2. Buat virtual environment (disarankan)
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Test setup
python test_setup.py

# 5. Jalankan aplikasi
python app.py
```

### Persyaratan Sistem
- **Python 3.8+** (disarankan 3.9 atau 3.10) - [Download Python](https://www.python.org/downloads/)
- **RAM:** Minimal 4GB (disarankan 8GB)
- **Storage:** Minimal 2GB ruang kosong (total ~0.5-0.7 GB untuk dependencies + models)
- **Internet:** Diperlukan untuk download dependencies (~400-600 MB) dan model OCR (~10-15 MB) - **hanya sekali**

### 📥 Yang Perlu Didownload
**Manual:**
- Python installer (~25-30 MB) - [Download](https://www.python.org/downloads/)
- Project files (~5-10 MB) - Clone dari GitHub atau download ZIP

**Otomatis (saat install):**
- Python packages (~400-600 MB) - Terdownload saat `pip install -r requirements.txt`
- PaddleOCR models (~10-15 MB) - Terdownload saat pertama kali menjalankan aplikasi

**Total:** ~440-655 MB (sekitar 0.5-0.7 GB)

### Opsi Instalasi Lain
- **Menggunakan ZIP file:** Download ZIP dari GitHub, extract, lalu ikuti langkah 2-5 di atas
- **Tanpa virtual environment:** Langsung jalankan `pip install -r requirements.txt` (tidak disarankan)

### ⚠️ Catatan Penting
- **Setelah install requirements.txt:** Aplikasi sudah bisa langsung digunakan, tidak ada setup tambahan
- **Pure PaddleOCR:** Semua deteksi menggunakan PaddleOCR saja (tidak perlu Tesseract OCR atau dependency tambahan)
- **Pertama kali run:** Perlu koneksi internet untuk download PaddleOCR models (~10-15 MB, 1-5 menit)
- **Setelah models terdownload:** Aplikasi bisa digunakan offline, loading lebih cepat
- **Tingkat keberhasilan:** 85-90% langsung jalan dengan Python 3.9/3.10
- **Potensi masalah:** Windows mungkin perlu Visual C++ Build Tools (20-30% kasus)
- **Kunci sukses:** Install semua dependencies dengan `pip install -r requirements.txt` (versi fleksibel, support NumPy 2.x)

## 🔧 Troubleshooting

Jika aplikasi tidak muncul atau ada error:

1. **Test setup terlebih dahulu:**
   ```bash
   python test_setup.py
   ```

2. **Pastikan semua dependencies terinstall:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Masalah umum:**
   - **Python tidak dikenali:** Pastikan Python sudah terinstall dan ditambahkan ke PATH
   - **Error saat install:** Cek koneksi internet, upgrade pip dengan `python -m pip install --upgrade pip`
   - **Aplikasi tidak muncul:** Cek error message di terminal, pastikan PyQt5 terinstall
   - **Model OCR tidak load:** Pastikan koneksi internet aktif (untuk download model pertama kali)

4. **Butuh bantuan lebih lanjut?**
   - Cek [Issues di GitHub](https://github.com/zulilmiihsn/ocr-sipw/issues)
   - Buat issue baru jika masalah belum teratasi

## ✨ Fitur Utama

### 🎨 GUI Application
- **Multi-file processing** - Proses beberapa file gambar sekaligus
- **Progress tracking** - Progress bar real-time
- **Interactive table** - Tabel hasil yang dapat diedit
- **Auto-sort** - Otomatis mengurutkan berdasarkan Kode SLS & Sub-SLS
- **Multiple export** - Export ke Excel, CSV, JSON, atau HTML
- **Color-coded confidence** - Indikator warna untuk tingkat kepercayaan

### 🔍 OCR Engine
- Menggunakan **PaddleOCR PP-OCRv5** untuk akurasi tinggi (pure PaddleOCR, tidak ada dependency tambahan)
- Deteksi tabel BLOK III otomatis (keyword-based dengan PaddleOCR, atau ratio-based fallback)
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
2. Pilih file gambar (PNG, JPG, JPEG) melalui tombol "Pilih File" atau drag & drop
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
