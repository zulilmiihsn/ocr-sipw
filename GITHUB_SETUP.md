# Panduan Upload Project ke GitHub

## Langkah 1: Persiapan

### 1.1 Install Git (jika belum)
- Download Git dari: https://git-scm.com/download/win
- Install dengan setting default

### 1.2 Konfigurasi Git (hanya sekali)
Buka PowerShell di folder project ini, kemudian jalankan:

```powershell
git config --global user.name "Nama Kamu"
git config --global user.email "email@kamu.com"
```

## Langkah 2: Inisialisasi Git Repository Lokal

Masih di PowerShell, jalankan perintah berikut satu per satu:

```powershell
# Inisialisasi git repository
git init

# Tambahkan semua file ke staging area
git add .

# Buat commit pertama
git commit -m "Initial commit: Lab OCR project with table detection and extraction"

# Ubah branch dari 'master' ke 'main' (standar GitHub sekarang)
git branch -M main
```

## Langkah 3: Buat Repository di GitHub

1. **Buka GitHub**: https://github.com
2. **Login** ke akun GitHub kamu (atau buat akun baru jika belum punya)
3. **Klik tombol "+" di kanan atas**, pilih **"New repository"**
4. **Isi form**:
   - **Repository name**: `lab-untuk-ocr` (atau nama lain yang kamu mau)
   - **Description**: `OCR Lab for table detection and data extraction`
   - **Public/Private**: Pilih sesuai kebutuhan
     - **Public**: Semua orang bisa lihat
     - **Private**: Hanya kamu yang bisa lihat
   - **JANGAN centang** "Add a README file" (karena kita sudah punya)
   - **JANGAN centang** "Add .gitignore" (karena kita sudah punya)
   - Klik **"Create repository"**

## Langkah 4: Hubungkan dengan GitHub

Setelah repository dibuat, GitHub akan menampilkan instruksi. Salin perintah yang mirip dengan ini:

```powershell
# Ganti USERNAME dengan username GitHub kamu
# Ganti REPOSITORY dengan nama repository yang kamu buat
git remote add origin https://github.com/USERNAME/REPOSITORY.git

# Push code ke GitHub
git push -u origin main
```

**Contoh** (ganti dengan data kamu):
```powershell
git remote add origin https://github.com/johndoe/lab-untuk-ocr.git
git push -u origin main
```

Kamu akan diminta login GitHub. Gunakan **Personal Access Token** (bukan password biasa).

## Langkah 5: Buat Personal Access Token (jika diminta)

Jika diminta autentikasi:

1. Buka: https://github.com/settings/tokens
2. Klik **"Generate new token"** → **"Generate new token (classic)"**
3. Beri nama: `Lab OCR Project`
4. Centang scope: **`repo`** (untuk akses full ke repository)
5. Klik **"Generate token"**
6. **COPY token** yang muncul (hanya muncul sekali!)
7. Gunakan token ini sebagai password saat `git push`

## Langkah 6: Verifikasi

Setelah push berhasil, buka browser ke:
```
https://github.com/USERNAME/REPOSITORY
```

Kamu akan lihat semua file project sudah ada di GitHub! 🎉

## Tips & Update Selanjutnya

### Setiap kali ada perubahan:

```powershell
# Lihat file yang berubah
git status

# Tambahkan perubahan
git add .

# Commit dengan pesan yang jelas
git commit -m "Deskripsi perubahan yang dibuat"

# Push ke GitHub
git push
```

### Contoh commit messages yang baik:
```powershell
git commit -m "Add new OCR engine comparison"
git commit -m "Fix cell segmentation bug"
git commit -m "Update README with usage instructions"
git commit -m "Improve preprocessing accuracy"
```

### Perintah Git yang berguna:

```powershell
# Lihat status file
git status

# Lihat history commit
git log --oneline

# Lihat perubahan yang belum di-commit
git diff

# Batalkan perubahan pada file tertentu
git checkout -- namafile.py

# Buat branch baru untuk experiment
git checkout -b experiment-new-feature

# Kembali ke branch main
git checkout main
```

## Troubleshooting

### Problem: File terlalu besar
```
remote: error: File x.exe is 100.00 MB; this exceeds GitHub's file size limit
```

**Solusi**: 
1. Tambahkan file tersebut ke `.gitignore`
2. Hapus dari git cache: `git rm --cached namafile.exe`
3. Commit dan push lagi

### Problem: Push ditolak
```
! [rejected] main -> main (fetch first)
```

**Solusi**:
```powershell
git pull origin main --rebase
git push origin main
```

### Problem: Lupa email/username
```powershell
git config --global user.name  # lihat username
git config --global user.email  # lihat email
```

## Struktur Project yang akan di-Upload

Berdasarkan `.gitignore`, yang **TIDAK** akan di-upload:
- ❌ `__pycache__/` folders
- ❌ `experiments/PaddleOCR/` (terlalu besar)
- ❌ `experiments/references/` (clone dari repo lain)
- ❌ `.exe` files (installer Tesseract)
- ❌ Virtual environment folders
- ❌ IDE settings

Yang **AKAN** di-upload:
- ✅ Source code (`src/`)
- ✅ Test scripts (`experiments/stage*`)
- ✅ Results dan dokumentasi
- ✅ `README.md`, `requirements.txt`
- ✅ Configuration files

## Estimasi Ukuran Upload

Project ini akan sekitar **50-100 MB** setelah filtering oleh `.gitignore`.
Waktu upload tergantung koneksi internet kamu.

## Need Help?

- GitHub Docs: https://docs.github.com/en/get-started
- Git Tutorial: https://www.atlassian.com/git/tutorials
- Atau tanya ke AI assistant! 😊

---

**Happy Coding!** 🚀

