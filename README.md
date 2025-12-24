 # 🌿 MindRoute — Duygusal Navigasyon Uygulaması

Bu proje, kullanıcının 10 saniyelik videosundan **ruh hâlini analiz edip**, şehirde ona uygun mekanları öneren bir sistemdir.  
MindRoute, yapay zekâ destekli duygusal analiz ile şehir yaşamını kişiselleştirmeyi amaçlar.

---

## 🚀 Teknolojiler
### 🧠 Backend
- **FastAPI** (Python)
- **MongoDB** (veri saklama)
- **Overpass API (OpenStreetMap)** — mekan verilerini çekme
- **python-dotenv** — ortam değişkeni yönetimi

### 💻 Frontend
- **React + Vite**
- **Tailwind CSS** (arayüz)
- **Fetch API / Axios** (backend iletişimi)

---

## ⚙️ Kurulum (Özet)

### 🧩 Backend
```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows: .venv\Scripts\activate
pip install -U pip
pip install requests pymongo tenacity python-dotenv fastapi uvicorn pytest
```

**`.env` dosyası oluştur (repo kökünde):**
```ini
DB_NAME=mindroute
COLL_NAME=places
DEFAULT_LAT=41.0369
DEFAULT_LON=28.9850
DEFAULT_RADIUS_M=1500
MONGO_URL=mongodb://localhost:27017
EMOTION_BACKEND=mock
```

**Sunucuyu başlat:**
```bash
uvicorn app.main:app --reload --port 8002
```

**Sağlık kontrolü:**
```bash
curl http://127.0.0.1:8002/health
```

### 💡 Frontend
```bash
cd mindroute-web
npm install
npm run dev
```

**İsteğe bağlı `.env` dosyası:**
```ini
VITE_API_URL=http://localhost:8002
```

Tarayıcıda aç:
👉 http://localhost:5173

### 🧪 İşlev Testi

**Frontend Test Akışı:**
1. **Konum İzni:** Tarayıcı geolocation izni verin (localhost için https gerekmez)
2. **Konum Tanılama:** "📍 Konum Tanılama" kutusunda lat/lon/accuracy ve reverse geocoding (adres) görünür
3. **Konumu Seç:** "Bu konumu kullan" ile App state'e alın
4. **Video Analizi:** Video yükleyip "Analiz Et" ile mood analizi yapın
5. **Önerileri Getir:** `/places/search` gerçek koordinat ve mood ile çağrılır
6. **Sonuçlar:** JSON formatında mekan listesi döner

**Önemli Notlar:**
- Geolocation için https veya localhost kullanın
- Video analiz endpoint'i: `POST {API_URL}/analyze/video` (Form-data field: "file")
- Reverse geocoding: Nominatim (OSM) kullanıyoruz; yalnızca metin gösterimi içindir

🌍 API Uçları (Endpoints)

**Health Check:**
```bash
GET /health
# Response: { "status": "healthy", "mongo": "ok", "places_count": 3676, "config": {...} }
```

**Place Search (Akıllı Skorlama):**
```bash
GET /places/search?lat=41.0369&lon=28.9850&radius_km=2&limit=20&mood=stresli&all=false&q=cafe
# Parametreler:
#   lat: float (zorunlu) - Enlem
#   lon: float (zorunlu) - Boylam
#   radius_km: float (default 2.0) - Arama yarıçapı (km)
#   mood: str (opsiyonel) - Ruh hali (mutlu, üzgün, stresli, kaygılı, nötr)
#   all: bool (default false) - Mood ağırlığını kapatır
#   q: str (opsiyonel) - Metin arama sorgusu
# Response: { "count": 10, "items": [ { "score": 0.7417, "name": "...", "type": "park", ... } ] }
```

**Mood Analyze (Form-data):**
```bash
POST /mood/analyze
Content-Type: multipart/form-data
Body: video=<file> veya video_id=test123
# Response: { "mood": "stresli", "scores": {...}, "frames_used": 30 }
```

**Mood Analyze (JSON):**
```bash
POST /mood/analyze/json
Content-Type: application/json
Body: { "video_id": "test123" }
# Response: { "mood": "stresli", "scores": {...}, "frames_used": 30 }
```

### Test Örneği
```bash
# Health check
curl http://127.0.0.1:8002/health

# Place search (mood filtresiyle)
curl "http://127.0.0.1:8002/places/search?lat=41.015&lon=28.979&radius_km=10&limit=10&mood=stresli"

# Place search (text + all)
curl "http://127.0.0.1:8002/places/search?lat=41.015&lon=28.979&radius_km=20&limit=5&q=Starbucks&all=true"

# Mood analyze (JSON)
curl -X POST -H "Content-Type: application/json" -d '{"video_id":"test"}' http://127.0.0.1:8002/mood/analyze/json
```

🗂️ Dosya Yapısı
```
mindroute/
├── app/                  # FastAPI backend
│   ├── main.py           # Ana API endpoint'leri
│   ├── fetch_places.py   # OSM'den mekan çekme
│   ├── routes/           # Route modülleri
│   └── .env.example
│
├── mindroute-web/        # React frontend
│   ├── src/
│   │   ├── App.jsx       # Ana component
│   │   ├── components/   # VideoMood, LocationDebug
│   │   └── main.jsx
│   ├── .env              # VITE_API_URL
│   └── package.json
│
├── .env                  # Backend config (repo kökünde)
├── .gitignore
└── README.md
```

🧠 Özellikler

- 🎥 **Video analizi** → DeepFace / Mediapipe destekli ruh hâli çıkarımı (mock backend mevcut)
- 🗺️ **OpenStreetMap** üzerinden yakın mekan önerisi
- 🧮 **MongoDB upsert** → Tekil kayıt garantisi (sparse unique index)
- ⚡ **Gerçek zamanlı** frontend-backend etkileşimi
- 🎯 **Akıllı skorlama** → Mesafe, mood ağırlığı ve text search kombinasyonu
- 🔍 **Text search** → Mekan isimleri ve etiketlerde arama
- 📊 **Health check** → MongoDB bağlantı ve veritabanı istatistikleri

## 🗄️ MongoDB Seed Komutları

Veritabanını OSM mekanları ile doldurmak için:

### Nokta Bazlı Arama

```bash
# Taksim Çevresi (örnek)
python app/fetch_places.py --lat 41.0369 --lon 28.9850 --r 1500 --limit 500

# Kadıköy Çevresi
python app/fetch_places.py --lat 40.9900 --lon 29.0250 --r 3000 --limit 1000

# Üsküdar Çevresi
python app/fetch_places.py --lat 41.0247 --lon 29.0150 --r 2500 --limit 800
```

**Parametreler:**
- `--lat`: Enlem (float)
- `--lon`: Boylam (float)
- `--r`: Yarıçap (metre, int)
- `--limit`: Maksimum kayıt sayısı (int, opsiyonel)

### Şehir Bazlı Grid Arama (Yeni!)

```bash
# Elazığ - Grid tarama
python app/fetch_places.py --city "Elazığ, Türkiye" --grid-size-m 1000 --sleep-ms 600

# İstanbul - Geniş grid tarama
python app/fetch_places.py --city "İstanbul" --country TR --grid-size 2000 --sleep 1000

# Özel filtrelerle tarama
python app/fetch_places.py --city "Elazığ, Türkiye" \
  --grid-size-m 1000 --sleep-ms 600 \
  --amenities "restaurant,cafe,fast_food,library,school,university,place_of_worship" \
  --leisure "park,garden,fitness_centre" \
  --tourism "museum,hotel,hostel,information,viewpoint" \
  --shop "supermarket,bakery,chemist,convenience,clothes,books" \
  --healthcare "clinic,doctor,pharmacy" \
  --sport "fitness,swimming,tennis,football" \
  --limit 5000
```

**Şehir Grid Parametreleri:**
- `--city`: Şehir adı (örn: "Elazığ, Türkiye")
- `--country`: Ülke kodu (default: tr)
- `--grid-size` / `--grid-size-m`: Grid karo boyutu (metre, default: 2000)
- `--sleep` / `--sleep-ms`: Grid tarama arası bekleme (ms, default: 500)
- `--amenities`: Comma-separated amenity listesi
- `--leisure`: Comma-separated leisure listesi
- `--tourism`: Comma-separated tourism listesi
- `--shop`: Comma-separated shop listesi
- `--healthcare`: Comma-separated healthcare listesi
- `--sport`: Comma-separated sport listesi
- `--limit`: Toplam kayıt sayısı limiti (opsiyonel)

**Grid Tarama Nasıl Çalışır:**
1. Nominatim ile şehrin bbox'ını alır
2. Bbox'ı grid hücrelerine böler
3. Her hücrenin merkezinden Overpass sorgusu yapar
4. Tüm sonuçları MongoDB'ye upsert eder

**Toplam Kayıt Kontrolü:**
```bash
curl http://127.0.0.1:8002/health | jq '.places_count'
```

**Not:** Aynı `osm_id` için upsert/unique kuralı vardır, bu yüzden yinelenen kayıtlar eklenmez.

## 🔧 Sorun Giderme

**Veri yoksa:**
```bash
# Önce fetch_places.py ile seed atın
python app/fetch_places.py --lat 41.0369 --lon 28.9850 --r 2000 --limit 500

# Health check ile veritabanını kontrol edin
curl http://127.0.0.1:8002/health
```

**Overpass fallback:**
- Sonuç gelmezse backend otomatik olarak Overpass API'den (amenity/leisure/tourism) çeker, Mongo'ya upsert eder ve aramayı yeniden dener
- Overpass kota limitlerine takılmamak için arka arkaya çok sık denemelerde bekleme koyun

**API hatası:**
- MongoDB'nin çalıştığından emin olun: `mongod --version`
- `.env` dosyasının repo kökünde olduğunu kontrol edin
- Virtual environment'ı aktive edin: `.venv\Scripts\activate` (Windows)

🧰 Geliştirici Notları

- Aynı `osm_id` iki kez eklenmez (sparse unique index)
- `.env` dosyaları `.gitignore` ile gizlidir
- `.venv/`, `__pycache__/`, `.cache/` klasörleri ignore edilir
- Text search index: name ve tags alanları üzerinde
- Geo index: location alanı üzerinde 2dsphere
- Mood ağırlıkları: kaygılı/stresli (park, garden, library), üzgün (cafe, museum, viewpoint), mutlu/enerjik (cafe, restaurant, pub, bar)

📄 Lisans
MIT License © 2025 Gökçen Usta



