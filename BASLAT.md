# 🚀 MindRoute Başlatma Komutları

## Backend Başlatma

### Terminal 1 - Backend:

```bash
cd app
python -m uvicorn app.main:app --reload --port 8002 --host 127.0.0.1
```

**Veya Windows'ta:**

```cmd
cd app
python -m uvicorn app.main:app --reload --port 8002 --host 127.0.0.1
```

**Başarılı başladığında göreceksiniz:**
```
INFO:     Uvicorn running on http://127.0.0.1:8002 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Application startup complete.
```

---

## Frontend Başlatma

### Terminal 2 - Frontend:

```bash
cd mindroute-web
npm run dev
```

**Veya Windows'ta:**

```cmd
cd mindroute-web
npm run dev
```

**Başarılı başladığında göreceksiniz:**
```
VITE v7.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

---

## Test

1. **Backend sağlık kontrolü:**
   ```bash
   curl http://127.0.0.1:8002/health
   ```
   
   Veya:
   ```bash
   python check_server.py
   ```

2. **Tarayıcıda açın:**
   - Frontend: http://localhost:5173
   - Backend API: http://127.0.0.1:8002/docs (Swagger UI)

---

## ⚠️ Notlar

- **İki ayrı terminal penceresi açın** (biri backend, biri frontend için)
- Backend ve Frontend aynı anda çalışmalı
- MongoDB'nin çalıştığından emin olun
- Backend'i durdurmak için: `CTRL+C`
- Frontend'i durdurmak için: `CTRL+C`

---

## 🐛 Sorun Giderme

### "Port already in use" hatası:
- Port 8002 veya 5173 kullanımda
- Kullanan process'i kapatın veya farklı port kullanın

### "Module not found" hatası:
```bash
pip install -r app/requirements.txt
```

### Frontend "node_modules not found":
```bash
cd mindroute-web
npm install
```








