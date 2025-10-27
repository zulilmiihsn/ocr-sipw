# Quick Git Commands Reference 🚀

## Setup Awal (Sekali Saja)

```powershell
# Konfigurasi Git
git config --global user.name "Nama Kamu"
git config --global user.email "email@example.com"

# Inisialisasi repository
git init
git add .
git commit -m "Initial commit"
git branch -M main

# Hubungkan ke GitHub (ganti URL dengan punya kamu)
git remote add origin https://github.com/USERNAME/REPO.git
git push -u origin main
```

## Daily Workflow ⚡

```powershell
# 1. Cek perubahan
git status

# 2. Tambahkan perubahan
git add .

# 3. Commit dengan pesan
git commit -m "Deskripsi perubahan"

# 4. Push ke GitHub
git push
```

## Useful Commands 🛠️

```powershell
# Lihat history
git log --oneline

# Lihat perubahan yang belum di-commit
git diff

# Batalkan perubahan
git checkout -- filename

# Pull update dari GitHub
git pull

# Lihat remote URL
git remote -v

# Lihat branch
git branch -a

# Buat branch baru
git checkout -b nama-branch
```

## Emergency Commands 🚨

```powershell
# Hapus file dari git tapi tetap di disk
git rm --cached filename

# Undo commit terakhir (keep changes)
git reset --soft HEAD~1

# Undo commit terakhir (discard changes) ⚠️ HATI-HATI!
git reset --hard HEAD~1

# Force pull (overwrite local) ⚠️ HATI-HATI!
git fetch origin
git reset --hard origin/main
```

## Common Issues & Fixes 🔧

### File terlalu besar
```powershell
# Tambah ke .gitignore
echo "large-file.exe" >> .gitignore
git rm --cached large-file.exe
git commit -m "Remove large file"
git push
```

### Push rejected
```powershell
git pull --rebase
git push
```

### Forgot last commit message
```powershell
git log -1
```

## Best Practices ✨

- ✅ Commit often dengan pesan yang jelas
- ✅ Pull sebelum Push jika kerja dalam tim
- ✅ Gunakan branch untuk fitur baru
- ✅ Review `git status` sebelum commit
- ❌ Jangan commit file besar (>50MB)
- ❌ Jangan commit secrets/passwords
- ❌ Jangan force push ke branch utama

## Commit Message Examples 💬

```
✅ Good:
- "Add PaddleOCR integration"
- "Fix cell segmentation alignment bug"
- "Update requirements.txt with new dependencies"
- "Refactor preprocessing pipeline"

❌ Bad:
- "update"
- "fix"
- "changes"
- "asdf"
```

---

**Pro Tip**: Simpan file ini sebagai referensi cepat! 📌

