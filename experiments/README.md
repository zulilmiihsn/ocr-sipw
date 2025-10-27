# OCR Experiments - Per Stage

Folder ini berisi eksperimen untuk mencari metode terbaik di setiap tahap OCR pipeline.

## Struktur Pipeline

```
Input → Stage 1 → Stage 2 → Stage 3 → Stage 4 → Stage 5 → Stage 6 → Stage 7 → Output
        Loading   Preproc   Detect    Segment   OCR      Validate  Export
```

## Folder Stage Experiments

### [Stage 1: Image Loading](stage1_image_loading/)
Handle input file (PDF/JPG/PNG) dan convert ke format untuk processing

### [Stage 2: Preprocessing](stage2_preprocessing/)
Optimize image quality: deskew, denoise, enhance, binarize

### [Stage 3: Table Detection](stage3_table_detection/)
Detect dan crop area tabel BLOK III

### [Stage 4: Cell Segmentation](stage4_cell_segmentation/)
Extract individual cells dari tabel

### [Stage 5: OCR](stage5_ocr/)
OCR per cell dengan berbagai engines

### [Stage 6: Validation](stage6_validation/)
Validate, clean, dan error correction

### [Stage 7: Export](stage7_export/)
Format dan export ke CSV

## Results Folder

Hasil comparison dari semua experiments disimpan di [results/](results/)

## Cara Menggunakan

1. Pilih stage yang ingin ditest
2. Lihat README di folder stage tersebut
3. Run experiment script atau create new one
4. Compare results dan dokumentasikan findings
5. Update main implementation dengan best method