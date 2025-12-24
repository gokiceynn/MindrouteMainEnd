# 🚀 GitHub'a Push Yapma Rehberi

## 📋 Adım Adım Talimatlar

### 1️⃣ Git Repository'yi Başlat (Eğer henüz başlatılmadıysa)

```bash
# Proje kök dizinine git
cd C:\Users\silae\OneDrive\Masaüstü\mindroute-main

# Git repository'yi başlat
git init

# Varsayılan branch'i master yerine main yap (GitHub'ın yeni standardı)
git branch -M main
```

### 2️⃣ Dosyaları Stage'e Ekle

```bash
# Tüm değişiklikleri ekle
git add .

# Veya belirli dosyaları eklemek istersen:
# git add app/
# git add mindroute-web/
# git add .gitignore
```

### 3️⃣ İlk Commit'i Yap

```bash
git commit -m "Initial commit: MindRoute project with emotion analysis and place recommendations"
```

### 4️⃣ GitHub Repository'yi Remote Olarak Ekle

```bash
# GitHub'da oluşturduğunuz repository URL'ini kullanın
# Örnek: https://github.com/KULLANICIADI/mindroute.git
git remote add origin https://github.com/KULLANICIADI/mindroute.git

# Remote'un doğru eklendiğini kontrol et
git remote -v
```

### 5️⃣ GitHub'a Push Et

```bash
# İlk push (main branch'e)
git push -u origin main
```

**Not:** İlk push'ta GitHub kullanıcı adı ve şifre/token isteyebilir. Eğer 2FA (Two-Factor Authentication) aktifse, Personal Access Token kullanmanız gerekir.

---

## 🔐 GitHub Authentication (Token Kullanımı)

### Personal Access Token Oluşturma:

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. "Generate new token (classic)" tıklayın
3. Token'a bir isim verin (örn: "mindroute-push")
4. Süre seçin (örn: 90 days veya no expiration)
5. **Scopes:** `repo` seçeneğini işaretleyin
6. "Generate token" tıklayın
7. **Token'ı kopyalayın** (bir daha gösterilmeyecek!)

### Token ile Push:

```bash
# Username: GitHub kullanıcı adınız
# Password: Oluşturduğunuz Personal Access Token
git push -u origin main
```

---

## 📝 Sonraki Push'lar İçin

Değişiklik yaptıktan sonra:

```bash
# 1. Değişiklikleri kontrol et
git status

# 2. Değişiklikleri ekle
git add .

# 3. Commit yap
git commit -m "Açıklayıcı commit mesajı"

# 4. Push et
git push
```

---

## 🛠️ Yararlı Git Komutları

```bash
# Değişiklikleri göster
git status

# Commit geçmişini göster
git log --oneline

# Son commit'i geri al (dosyalar değişmeden)
git reset --soft HEAD~1

# Remote repository bilgisi
git remote -v

# Branch'leri göster
git branch

# Yeni branch oluştur
git checkout -b yeni-ozellik

# Branch değiştir
git checkout main
```

---

## ⚠️ Önemli Notlar

1. **`.env` dosyaları `.gitignore`'da olmalı** - API key'leriniz GitHub'a yüklenmemeli!
2. **`node_modules/` ve `__pycache__/`** otomatik ignore edilir
3. **Büyük dosyalar** (video, model dosyaları) `.gitignore`'da
4. **İlk push'tan önce** `.env` dosyasının ignore edildiğinden emin olun

---

## 🐛 Sorun Giderme

### "remote origin already exists" hatası:
```bash
git remote remove origin
git remote add origin https://github.com/KULLANICIADI/mindroute.git
```

### "Authentication failed" hatası:
- Personal Access Token kullanın (şifre değil)
- Token'ın `repo` scope'una sahip olduğundan emin olun

### "Updates were rejected" hatası:
```bash
# Önce remote'daki değişiklikleri çek
git pull origin main --rebase

# Sonra tekrar push et
git push
```

---

## ✅ Başarı Kontrolü

Push başarılı olduktan sonra:
1. GitHub repository sayfasını açın
2. Dosyaların yüklendiğini kontrol edin
3. Commit geçmişini görüntüleyin

