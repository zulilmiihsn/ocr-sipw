# 🔄 Code Duplication Issues Found

**Date:** 2025  
**Issue:** "Lah disini kan udah dilakukan ini, kenapa disini lagi?"

---

## 🚨 Critical Duplications

### 1. ❌ **`header_y_max` Calculation - DUPLIKAT dengan LOGIKA BERBEDA!**

**Location 1:** `pipeline/ocr_engine.py` line 458-461
```python
# ❌ SIMPLE calculation
header_y_max = (
    max(g['y_center'] for g in header_groups) + table_settings.header_y_margin 
    if header_groups else table_settings.header_y_threshold
)
```

**Location 2:** `gui/workers/ocr_worker.py` line 356-396
```python
# ❌ COMPLEX calculation dengan fallback
def _calculate_header_y_max(self, header_groups, sorted_h_lines, ocr_results, image_height):
    # Use H-lines in top 30% of image
    header_candidates = [
        y for y in sorted_h_lines
        if y < image_height * mapping_settings.header_search_ratio
    ]
    
    if len(header_candidates) >= 1:
        header_y_max = header_candidates[-1]
    else:
        # Fallback: use OCR-based detection
        header_y_max = 0
        for det in ocr_results:
            y_center = (det['y_min'] + det['y_max']) / 2
            if y_center < image_height * 0.25:
                header_y_max = max(header_y_max, det['y_max'])
        
        if header_y_max > 0:
            header_y_max += mapping_settings.header_margin_px
    
    return header_y_max
```

**Problem:**
- ❌ **2 implementasi berbeda** untuk hal yang sama!
- ❌ Yang satu simple (pakai `header_groups`), yang satu kompleks (pakai H-lines + fallback)
- ❌ Bisa hasil berbeda untuk gambar yang sama!

**Recommendation:**
- ✅ **Pilih salah satu** (yang kompleks lebih robust)
- ✅ **Pindahkan ke utility function** di `pipeline/ocr_engine.py` atau `utils/`
- ✅ **Gunakan di semua tempat**

---

### 2. ❌ **`adaptive_tolerance` Calculation - DUPLIKAT dengan LOGIKA BERBEDA!**

**Location 1:** `pipeline/table_processor.py` line 106-120
```python
# ❌ Berdasarkan ROW HEIGHT
def _calculate_adaptive_tolerance(self, image_height: int, h_lines: List[int]) -> int:
    if len(h_lines) > 1:
        avg_row_height = (h_lines[-1] - h_lines[0]) / max(len(h_lines) - 1, 1)
        adaptive_row_tolerance = max(8, int(avg_row_height * 0.25))
    else:
        adaptive_row_tolerance = 10
    return adaptive_row_tolerance
```

**Location 2:** `gui/workers/ocr_worker.py` line 275-279
```python
# ❌ Berdasarkan IMAGE HEIGHT
adaptive_tolerance = max(
    mapping_settings.adaptive_tolerance_min,
    int(image_height * mapping_settings.adaptive_tolerance_ratio)
)
```

**Problem:**
- ❌ **2 formula berbeda** untuk hal yang sama!
- ❌ Satu pakai `row_height * 0.25`, satu pakai `image_height * 0.015`
- ❌ Bisa hasil berbeda!

**Recommendation:**
- ✅ **Pilih salah satu formula** (yang mana lebih akurat?)
- ✅ **Pindahkan ke utility function**
- ✅ **Gunakan konsisten**

---

### 3. ⚠️ **Row Filtering Logic - DUPLIKAT (Minor)**

**Location 1:** `pipeline/ocr_engine.py` line 471
```python
y_center = (h_lines[row_idx] + h_lines[row_idx + 1]) // 2
if y_center <= header_y_max:
    continue
```

**Location 2:** `pipeline/table_processor.py` line 560
```python
y_center = (h_lines[row_idx] + h_lines[row_idx + 1]) / 2
if y_center <= header_y_max:
    continue
```

**Location 3:** `gui/workers/ocr_worker.py` line 290
```python
y_center = (det['y_min'] + det['y_max']) / 2
if y_center > header_y_max + 10:
    data_y_centers.append(y_center)
```

**Problem:**
- ⚠️ **3 tempat** melakukan filtering yang sama
- ⚠️ Logic sedikit berbeda (satu pakai `+ 10`, yang lain tidak)

**Recommendation:**
- ✅ **Standardize** ke satu logic
- ✅ **Extract** ke helper function jika perlu

---

### 4. ✅ **`validate_and_correct_by_template` - OK (Dipanggil dari tempat berbeda)**

**Location 1:** `pipeline/ocr_engine.py` line 495
```python
# Dalam process_table (CLI mode)
cell['text_final'] = validate_and_correct_by_template(cell['text'], col_idx)
```

**Location 2:** `pipeline/table_processor.py` line 568
```python
# Dalam _build_table_data (GUI mode)
text_final = validate_and_correct_by_template(text, col_idx)
```

**Status:** ✅ **OK** - Dipanggil dari pipeline berbeda (CLI vs GUI), ini expected behavior.

---

## 📊 Summary

| Issue | Severity | Locations | Status |
|-------|----------|-----------|--------|
| `header_y_max` calculation | 🚨 **CRITICAL** | 2 places, different logic | ❌ Needs fix |
| `adaptive_tolerance` calculation | 🚨 **CRITICAL** | 2 places, different logic | ❌ Needs fix |
| Row filtering logic | ⚠️ **MINOR** | 3 places, similar logic | ⚠️ Can improve |
| `validate_and_correct_by_template` | ✅ **OK** | 2 places, expected | ✅ OK |

---

## 🎯 Recommended Fixes

### Priority 1: Fix `header_y_max` Duplication

**Option A:** Use complex version (more robust)
```python
# pipeline/utils/header_utils.py (NEW FILE)
def calculate_header_y_max(header_groups, sorted_h_lines, ocr_results, image_height):
    """Calculate header Y maximum with fallback mechanisms."""
    # ... complex logic from ocr_worker.py
    pass
```

**Option B:** Use simple version (if header_groups always available)
```python
# pipeline/ocr_engine.py
def calculate_header_y_max(header_groups, table_settings):
    """Calculate header Y maximum from header groups."""
    if header_groups:
        return max(g['y_center'] for g in header_groups) + table_settings.header_y_margin
    return table_settings.header_y_threshold
```

### Priority 2: Fix `adaptive_tolerance` Duplication

**Decision needed:** Which formula is better?
- Formula A: `row_height * 0.25` (from row structure)
- Formula B: `image_height * 0.015` (from image size)

**Recommendation:** Use Formula B (from settings) for consistency, unless Formula A is proven better.

---

## ✅ Action Items

1. [ ] **Decide** which `header_y_max` logic to use
2. [ ] **Extract** to utility function
3. [ ] **Replace** all usages
4. [ ] **Decide** which `adaptive_tolerance` formula to use
5. [ ] **Extract** to utility function
6. [ ] **Replace** all usages
7. [ ] **Standardize** row filtering logic

---

## 💡 Why This Matters

**Impact:**
- ❌ **Inconsistent results** - Same image bisa hasil berbeda
- ❌ **Maintenance nightmare** - Fix bug di satu tempat, lupa di tempat lain
- ❌ **Confusion** - Developer bingung mana yang benar

**After Fix:**
- ✅ **Single source of truth** - Satu implementasi untuk semua
- ✅ **Consistent results** - Same image always same result
- ✅ **Easier maintenance** - Fix sekali, semua tempat ter-update

