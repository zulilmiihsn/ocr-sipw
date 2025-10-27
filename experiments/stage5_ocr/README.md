# Stage 5: OCR per Cell

## Goal
Extract text dari setiap cell dengan akurasi tinggi.

## Experiments
- [ ] Test OCR engines
  - [ ] Tesseract (current primary)
  - [ ] PaddleOCR (current backup)
  - [ ] EasyOCR
  - [ ] Comparison results
- [ ] Test Tesseract PSM modes per cell type
  - [ ] PSM 6 (uniform block) - current
  - [ ] PSM 7 (single line)
  - [ ] PSM 8 (single word)
  - [ ] PSM 11 (sparse text)
- [ ] Test OCR config per column type
  - [ ] Numeric whitelist: 0-9,.
  - [ ] Text: full character set
  - [ ] Mixed: keep special chars
- [ ] Test dengan kualitas cell berbeda
  - [ ] Clear printed text
  - [ ] Handwriting
  - [ ] Blurry/small text
  - [ ] Dark/bright cells


