# Testing Environment

## Purpose
Test optimizations independently before applying to main codebase.

## Structure
```
testing/
├── scripts/
│   └── test_optimizations.py    # Main test suite
├── results/
│   └── optimization_test_results.json  # Test results
└── README.md                     # This file
```

## How to Run

### Step 1: Prepare Test Image
Place a test image (PNG/JPG) in the project directory, or use an existing sample.

### Step 2: Run Test Suite
```bash
py testing/scripts/test_optimizations.py <path_to_test_image>
```

Example:
```bash
py testing/scripts/test_optimizations.py sample_blok3.png
```

### Step 3: Review Results
Check `testing/results/optimization_test_results.json` for detailed benchmark results.

## What is Tested

### 1. Resolution Scaling
- Downscales high-res images (>8MP → 6MP)
- Measures time and size reduction

### 2. Adaptive CLAHE
- Adjusts contrast enhancement based on image quality
- Measures processing time and contrast improvement

### 3. OCR Performance
- Compares baseline vs optimized OCR
- Measures speed improvement and detection count

### 4. Spatial Indexing
- Tests cell mapping efficiency
- Measures reduction in unnecessary calculations

## Safety Features
- ✅ Isolated testing (doesn't modify main code)
- ✅ Each optimization tested independently
- ✅ Benchmark comparisons (before/after)
- ✅ JSON results for analysis

## Expected Results
- **OCR Speedup:** 30-60% faster
- **Cell Mapping:** 70-90% fewer checks
- **Total Improvement:** ~50% faster overall

