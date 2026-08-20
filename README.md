<div align="center">

# 🔍 OCR SIPW — Document AI & Intelligent Data Extraction

An automated Computer Vision & OCR pipeline engineered to extract, preprocess, and structure text from administrative and commercial document images.

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer_Vision-5C3EE8?style=flat-square&logo=opencv&logoColor=white)](https://opencv.org/)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

[Product Context](#-business--product-context) • [Pipeline Architecture](#-pipeline-architecture) • [Getting Started](#-getting-started)

</div>

---

## 💼 Business & Product Context

Manual document data entry is notoriously slow, costly, and error-prone. **OCR SIPW** was created to automate the intake and parsing of scanned physical forms, receipts, and administrative records—converting unsearchable raster images into machine-readable structured datasets with minimal human intervention.

---

## ⚡ Technical Pipeline

```mermaid
graph LR
    A["Raw Document Image"] --> B["CV Preprocessing<br/>(Denoise, Binarize, Deskew)"]
    B --> C["OCR Extraction Engine<br/>(Tesseract / Text Localization)"]
    C --> D["Post-Processing & Parsing"]
    D --> E["Structured JSON / Database Output"]
```

### ✨ Core Capabilities
- 📷 **Adaptive Image Enhancement**: Adaptive thresholding and morphological filtering to handle varied lighting, low scan contrast, and perspective skews.
- 🔤 **High-Fidelity Text Extraction**: Character and word recognition optimized for tabular and structured form formats.
- ⚙️ **Automated Export**: Direct pipeline for dumping extracted key-value pairs into structured text or JSON formats for downstream ERP/accounting integration.

---

## 🛠️ Installation & Usage

```bash
# Clone repository
git clone https://github.com/zulilmiihsn/ocr-sipw.git
cd ocr-sipw

# Setup environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run extraction pipeline
python main.py --input /path/to/document.jpg
```

---

<div align="center">
  Crafted by <a href="https://github.com/zulilmiihsn"><strong>Zul Ilmi Ihsan</strong></a> • AI Product Engineer
</div>
