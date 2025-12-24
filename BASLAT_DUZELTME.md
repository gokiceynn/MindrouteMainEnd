# 🚀 Backend Başlatma - DÜZELTME

## ❌ YANLIŞ (Hata verir):
```bash
cd app
python -m uvicorn app.main:app --reload --port 8002 --host 127.0.0.1
```
**Hata:** `ModuleNotFoundError: No module named 'app'`

## ✅ DOĞRU (Proje kök dizininden):
```bash
# Proje kök dizininde kal (mindroute-main)
python -m uvicorn app.main:app --reload --port 8002 --host 127.0.0.1
```

## Windows'ta:
```cmd
REM Proje kök dizininde (mindroute-main)
start_uvicorn.bat
```

Veya manuel:
```cmd
python -m uvicorn app.main:app --reload --port 8002 --host 127.0.0.1
```

## Önemli:
- **app klasörüne GİRME!** 
- Proje kök dizininde (mindroute-main) kal
- `app.main:app` şeklinde kullan (app. prefix'i gerekli)
