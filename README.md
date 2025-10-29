# 🎯 Lab OCR - BLOK III Table Extraction System

<div align="center">

![Accuracy](https://img.shields.io/badge/Accuracy-95.0%25-brightgreen?style=for-the-badge)
![Version](https://img.shields.io/badge/Version-2.0-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.8+-yellow?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Production%20Ready-success?style=for-the-badge)

**High-accuracy OCR system for extracting BLOK III table data from statistical forms**

[Quick Start](#-quick-start) • [Features](#-features) • [Documentation](#-documentation) • [Performance](#-performance)

</div>

---

## 📋 Overview

Lab OCR adalah sistem OCR (Optical Character Recognition) yang dirancang khusus untuk mengekstrak data dari tabel **BLOK III** pada formulir statistik dengan akurasi tinggi.

### 🎯 Key Achievements
- ✅ **95.0% Overall Accuracy** (152/160 cells correct)
- ✅ **4 Rows with 100% Accuracy** (Perfect!)
- ✅ **Exactly 10 Data Rows** detected (fixed template)
- ✅ **17 Columns** detected automatically
- ✅ **Production-Ready** with beautiful HTML visualization

---

## 🚀 Quick Start

### 1️⃣ Installation

```bash
# Clone repository
git clone https://github.com/zulilmiihsn/lab-ocr.git
cd lab-ocr

# Install dependencies
pip install -r requirements.txt
```

### 2️⃣ Run the System

```bash
# Navigate to final system
cd experiments/final_system

# Run the main pipeline
python RUN_ADAPTIVE_V2_SMART_ROWS.py

# View results in browser
# Open: visualize_results.html
```

### 3️⃣ View Results

The system generates:
- ✅ `ADAPTIVE_V2_SMART_RESULTS.json` - Structured data
- ✅ `visualize_results.html` - Beautiful visualization
- ✅ `results_data.js` - JavaScript data for web display

---

## ✨ Features

### 🔍 Intelligent Detection
- **Smart Row Detection**: Forces exactly 10 equal-spaced data rows
- **Adaptive Column Learning**: Learns column structure from document headers
- **Vertical Line Precision**: Uses morphological detection for column boundaries

### 🎨 Beautiful Visualization
- Color-coded accuracy (Green = ✅ Correct, Red = ❌ Incorrect)
- Row-by-row accuracy breakdown
- Confidence scores for each cell
- Ground truth comparison

### ⚡ High Performance
- **Processing Time**: ~81 seconds per document
- **Batch Processing**: Supports multiple documents
- **No Fallbacks Needed**: Single-pass accuracy

---

## 📊 Performance

### Accuracy Breakdown

| Metric | Value |
|--------|-------|
| **Overall Accuracy** | **95.0%** |
| Correct Cells | 152 / 160 |
| Perfect Rows (100%) | 4 rows |
| High Accuracy Rows (93.8%) | 5 rows |
| Good Accuracy Rows (81.2%) | 1 row |
| Rows Detected | **10** (exact!) |
| Columns Detected | **17** (complete!) |

### Method Comparison

| Method | Accuracy | Rows | Speed |
|--------|----------|------|-------|
| Text-Based Mapping | 63.1% | 13 | 165s |
| Adaptive v2 (basic) | 70.0% | 12 | 81s |
| **Adaptive v2.1 (Smart)** | **95.0%** ✅ | **10** ✅ | **81s** ✅ |

---

## 📁 Project Structure

```
lab-untuk-ocr/
├── 📂 src/                          # Core library
│   ├── ocr/                         # OCR modules
│   ├── utils/                       # Utility functions
│   └── models/                      # Data models
│
├── 📂 experiments/
│   ├── stage1_image_loading/        # ✅ Approved: PDF/Image loading
│   ├── stage2_preprocessing/        # ✅ Approved: No preprocessing
│   ├── stage3_table_detection/      # ✅ Approved: OCR + Border detection
│   ├── stage4_cell_segmentation/    # ✅ Approved: Morphological lines
│   ├── stage5_ocr/                  # ✅ Final OCR methods
│   ├── results/                     # Final results only
│   └── final_system/                # 🎯 PRODUCTION-READY v2.1
│       ├── RUN_ADAPTIVE_V2_SMART_ROWS.py   # Main pipeline
│       ├── visualize_results.html          # Visualization
│       ├── adaptive_ocr_pipeline.py        # Core library
│       └── README.md                       # Detailed docs
│
├── 📂 contoh gambar/                # Sample images
├── 📂 data/                         # Data directory
├── 📄 requirements.txt              # Python dependencies
└── 📄 README.md                     # This file
```

---

## 🛠️ Technical Details

### Pipeline Stages

1. **Stage 1: Image Loading**
   - Load PDF/Image files
   - Format: PNG, JPG, PDF
   - Method: `pdf2image` + OpenCV

2. **Stage 2: Preprocessing**
   - Strategy: **No preprocessing** (preserve original quality)
   - Reason: Over-processing degrades accuracy

3. **Stage 3: Table Detection**
   - Method: **OCR + Border Detection**
   - Speed: ~3 seconds
   - Accuracy: 100% BLOK III detection

4. **Stage 4: Cell Segmentation**
   - Method: **Morphological Line Detection**
   - Detection: 17 vertical + 11 horizontal lines
   - Grid: 10 rows × 17 columns

5. **Stage 5: OCR + Mapping**
   - Engine: **PaddleOCR PP-OCRv5**
   - Method: **Adaptive v2.1 - Smart Row Detection**
   - Features:
     - Full document scan (245 text regions)
     - Vertical lines for column boundaries
     - Equal spacing for 10 data rows
     - Column-specific post-processing

### Technologies Used

- **Python 3.8+**
- **PaddleOCR** - OCR engine (PP-OCRv5)
- **OpenCV** - Image processing
- **NumPy** - Numerical operations
- **Tesseract** - Table boundary detection (helper)

---

## 📖 Documentation

Detailed documentation available in:

- 📘 **[experiments/final_system/README.md](experiments/final_system/README.md)** - Full system documentation
- 📗 **[experiments/final_system/SUMMARY.md](experiments/final_system/SUMMARY.md)** - Executive summary
- 📙 **[experiments/final_system/QUICK_START.md](experiments/final_system/QUICK_START.md)** - Quick start guide
- 📕 **[experiments/PIPELINE_STAGES.md](experiments/PIPELINE_STAGES.md)** - Pipeline overview

Each stage has its own documentation:
- `experiments/stage1_image_loading/README.md`
- `experiments/stage2_preprocessing/README.md`
- `experiments/stage3_table_detection/STAGE3_APPROVED.md`
- `experiments/stage4_cell_segmentation/STAGE4_APPROVED.md`
- `experiments/stage5_ocr/OCR_MODELS_INFO.md`

---

## 🎨 Visualization

The system includes a beautiful HTML visualization:

![Visualization Preview](https://via.placeholder.com/800x400/667eea/ffffff?text=95.0%25+Accuracy+Visualization)

**Features:**
- 🟢 Green cells = Correct detection
- 🔴 Red cells = Incorrect detection
- ⚪ Gray cells = Empty (both)
- 📊 Row-by-row accuracy breakdown
- 🎯 Confidence scores per cell
- 📈 Summary statistics

---

## 🧪 Testing

To test with your own images:

1. Place image in `contoh gambar/` folder
2. Edit `RUN_ADAPTIVE_V2_SMART_ROWS.py`:
   ```python
   image = load_image('contoh gambar/YOUR_IMAGE.png')
   ```
3. Run the pipeline:
   ```bash
   python RUN_ADAPTIVE_V2_SMART_ROWS.py
   ```

---

## 🔧 Configuration

Key configuration in `experiments/final_system/requirements.txt`:

```txt
paddleocr>=3.0.0       # OCR engine
opencv-python>=4.8.0   # Image processing
numpy>=1.24.0          # Numerical ops
```

---

## 📝 Version History

### v2.0 - Smart Row Detection (Current) 🎯
- ✅ 95.0% accuracy achieved
- ✅ Smart row detection (exactly 10 rows)
- ✅ Adaptive column learning
- ✅ HTML visualization
- ✅ Production-ready

### v1.1 - Adaptive Mapping
- 📈 94.1% accuracy
- 🔍 Vertical line column detection
- 🧹 Bracket artifact removal

### v1.0 - Initial Release
- 🚀 Basic pipeline
- 📊 70% accuracy
- 🔬 Experimental methods

---

## 👨‍💻 Author

**Lab OCR Team**
- GitHub: [@zulilmiihsn](https://github.com/zulilmiihsn)
- Repository: [lab-ocr](https://github.com/zulilmiihsn/lab-ocr)

---

## 📜 License

This project is licensed under the MIT License.

---

## 🙏 Acknowledgments

- **PaddleOCR** - Excellent OCR engine
- **OpenCV** - Powerful image processing
- **Tesseract** - Table boundary helper

---

<div align="center">

**⭐ If you find this project helpful, please give it a star! ⭐**

Made with ❤️ by Lab OCR Team

</div>


