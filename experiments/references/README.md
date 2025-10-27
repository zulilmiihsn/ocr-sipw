# Reference Repositories & Models

Folder ini untuk menyimpan repository yang di-clone sebagai referensi atau untuk copy model OCR.

## Kategori Repositories

### Table Detection
- [ ] Repos untuk table detection dari scanned documents
- [ ] Line detection methods
- [ ] Template matching approaches

### OCR Engines
- [ ] Tesseract wrapper improvements
- [ ] PaddleOCR custom models
- [ ] EasyOCR implementations
- [ ] OCR-specific preprocessing techniques

### Handwriting Recognition
- [ ] HTR (Handwriting Text Recognition) models
- [ ] IAM-like datasets implementations
- [ ] Transfer learning approaches

### Document Understanding
- [ ] Document parsing pipelines
- [ ] Form extraction methods
- [ ] Layout analysis tools

### Preprocessing Techniques
- [ ] Advanced image preprocessing
- [ ] Denoising methods
- [ ] Skew correction algorithms

## Cara Menggunakan

1. Clone repository yang ingin digunakan:
```bash
git clone <repo_url> <folder_name>
```

2. Document findings di folder tersebut (buat notes.md)

3. Test methods dan compare dengan current implementation

4. Copy/adapt code yang useful ke main implementation

## Cloned Repositories

### ✅ RapidTableDetection (Table Detection)
**Location:** `table_detection/RapidTableDetection/`  
**Analysis:** See `table_detection/notes.md`

**Key findings:**
- Detect tabel dengan perspective correction (4 corner points)
- Handle rotation dan skewing
- Multiple model backends (YOLO11, Paddle)
- **Recommendation:** Very suitable untuk improve `stage3_table_detection`

### ✅ PaddleOCR (OCR Engine) 
**Location:** `ocr_engines/PaddleOCR/`  
**Analysis:** See `ocr_engines/PaddleOCR_notes.md`

**Key findings:**
- Better untuk handwriting recognition
- Support Bahasa Indonesia
- Already integrated sebagai backup engine
- **Recommendation:** Consider as primary untuk handwritten text

### ⚠️ DocumentAIExtractionPipeline (General Doc AI)
**Location:** `DocumentAIExtractionPipeline/`  
**Analysis:** See `DocumentAIExtractionPipeline/notes.md`

**Key findings:**
- General document extraction pipeline
- Less relevant untuk specific table OCR case
- **Recommendation:** Skip untuk now, focus ke table-specific solutions

## Useful Repositories to Consider (Future)

### Table Detection
- `table-transformer` - Microsoft's table detection
- `img2table` - Table detection and parsing
- `camelot-py` - PDF table extraction

### OCR
- `easyocr` - Alternative OCR engine
- `kraken` - End-to-end OCR/HTR engine
- `calamari` - OCR using neural networks

### Handwriting
- `TrOCR` - Transformer-based OCR
- `HTR models` - Various HTR implementations
