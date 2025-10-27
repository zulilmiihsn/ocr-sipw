# Stage 6: Post-Processing & Validation

## Goal
Validate dan clean OCR results untuk akurasi final.

## Experiments
- [ ] Test empty cell detection
  - [ ] Pixel threshold method (current)
  - [ ] Contour-based detection
  - [ ] OCR confidence-based
  - [ ] Hybrid approach
- [ ] Test data validation per column
  - [ ] Numeric: preserve 3,1 format
  - [ ] Text: clean noise
  - [ ] Time: validate HH:MM-HH:MM
  - [ ] Mixed: preserve special chars
- [ ] Test error correction
  - [ ] Common OCR mistakes (O→0, l→1)
  - [ ] Context-based correction
  - [ ] Confidence-based filtering
- [ ] Test data cleaning
  - [ ] Strip whitespace
  - [ ] Remove noise chars
  - [ ] Normalize formats

