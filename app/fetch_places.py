# app/fetch_places.py
"""
OSM (Overpass API) mekânlarını çekip MongoDB'ye kaydeder.

Kullanım:
  # Nokta bazlı arama
  python app/fetch_places.py
  python app/fetch_places.py --lat 41.015 --lon 28.979 --r 4000
  python app/fetch_places.py --lat 41.0369 --lon 28.9850 --r 2000 --limit 2000
  
  # Şehir bazlı grid arama
  python app/fetch_places.py --city "Elazığ, Türkiye"
  python app/fetch_places.py --city "İstanbul" --country TR --grid-size 2000 --sleep 1000

Örnek kayıt şeması:
  {
    "osm_id": 123456789,
    "name": "Example Place",
    "type": "cafe",
    "location": { "type": "Point", "coordinates": [lon, lat] },
    "tags": ["name", "amenity", "outdoor_seating", "wheelchair"],
    "osm_tags": { "amenity": "cafe", "outdoor_seating": "yes", "wheelchair": "yes" }
  }
"""

import os
import time
import argparse
import math
from datetime import datetime
from typing import Tuple, Optional, List

import requests
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv

load_dotenv()

# --- Config ---
MONGO_URL = os.getenv("MONGO_URL", "mongodb://127.0.0.1:27017")
DB_NAME = os.getenv("DB_NAME", "mindroute")
COLL_NAME = os.getenv("COLL_NAME", "places")

# Frontend/Backend ile uyumlu tip havuzu
MOOD_MAP = {
    "stresli": ["park", "garden", "forest", "viewpoint"],
    "mutlu": ["cafe", "cinema", "pub", "bar", "restaurant", "fast_food"],
    "durgun": ["museum", "library", "park"],
    "enerjik": ["sports_centre", "stadium", "fitness_centre", "bar", "nightclub"],
    "neutral": ["cafe", "park", "library", "museum"],
}
OSM_TYPES = sorted({t for v in MOOD_MAP.values() for t in v})

DEFAULT_LAT = 41.015137   # İstanbul
DEFAULT_LON = 28.979530
DEFAULT_RADIUS_M = 4000  # 4km = 4000 metre
DEFAULT_GRID_SIZE_M = 2000  # Grid için varsayılan karo boyutu
DEFAULT_SLEEP_MS = 500  # Grid tarama arası bekleme

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "MindRoute/0.1 (+local dev)"}

# Basit cache (geliştirme/test için)
_OVERPASS_CACHE = {}

# ====== NOMINATIM İŞLEMLERİ ======

def get_city_bbox(city: str, country: Optional[str] = None) -> Tuple[float, float, float, float]:
    """
    Nominatim ile şehir bbox'ını al
    
    Returns:
        Tuple[south, north, west, east] (lat, lat, lon, lon)
    
    Raises:
        RuntimeError: Şehir bulunamazsa veya bbox yoksa
    """
    params = {
        "q": city,
        "format": "json",
        "limit": 1,
        "addressdetails": 1
    }
    
    if country:
        params["countrycodes"] = country.lower()
    
    try:
        print(f"Nominatim sorgusu: {params}")
        resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        if not data:
            raise RuntimeError(f"'{city}' şehri bulunamadı")
        
        result = data[0]
        bbox = result.get("boundingbox")
        
        if not bbox or len(bbox) != 4:
            raise RuntimeError(f"'{city}' için bbox alınamadı")
        
        # bbox: [south, north, west, east] (string olarak)
        south, north, west, east = [float(x) for x in bbox]
        
        print(f"Şehir: {result.get('display_name', city)}")
        print(f"BBOX: south={south:.6f}, north={north:.6f}, west={west:.6f}, east={east:.6f}")
        
        return south, north, west, east
        
    except requests.RequestException as e:
        raise RuntimeError(f"Nominatim isteği başarısız: {e}")
    except (ValueError, IndexError) as e:
        raise RuntimeError(f"BBOX parse hatası: {e}")

# ====== GRID BBOX İŞLEMLERİ ======

def generate_grid_cells(bbox: Tuple[float, float, float, float], grid_size_m: int) -> List[Tuple[float, float]]:
    """
    Bbox'ı grid hücrelerine böl ve her hücrenin merkez koordinatlarını döndür
    
    Args:
        bbox: (south, north, west, east)
        grid_size_m: Grid karo boyutu (metre)
    
    Returns:
        List[(lat, lon)] - Her grid hücresinin merkez koordinatı
    """
    south, north, west, east = bbox
    
    # Bbox genişliği/yüksekliği (metre)
    width_m = haversine_distance(south, west, south, east)
    height_m = haversine_distance(south, west, north, west)
    
    # Grid hücre sayısı
    cells_x = max(1, int(math.ceil(width_m / grid_size_m)))
    cells_y = max(1, int(math.ceil(height_m / grid_size_m)))
    
    print(f"Grid boyutları: {cells_x}x{cells_y} hücre")
    
    # Her hücre için merkez hesapla
    centers = []
    for i in range(cells_y):
        for j in range(cells_x):
            # Hücre merkezinin oransal pozisyonu
            lat_factor = (i + 0.5) / cells_y if cells_y > 1 else 0.5
            lon_factor = (j + 0.5) / cells_x if cells_x > 1 else 0.5
            
            center_lat = south + (north - south) * lat_factor
            center_lon = west + (east - west) * lon_factor
            
            centers.append((center_lat, center_lon))
    
    return centers

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki nokta arası mesafe hesapla (metre)"""
    R = 6371000  # Dünya yarıçapı (metre)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# ====== OVERPASS İŞLEMLERİ ======

def overpass_query(lat: float, lon: float, radius_m: int, 
                   amenity_list: List[str] = None,
                   leisure_list: List[str] = None,
                   tourism_list: List[str] = None,
                   shop_list: List[str] = None,
                   healthcare_list: List[str] = None,
                   sport_list: List[str] = None) -> str:
    """
    Overpass QL sorgusu oluştur - dinamik kategori desteği
    
    Args:
        lat, lon, radius_m: Koordinat ve yarıçap
        amenity_list, leisure_list, etc.: Her kategori için filtre listesi
           None ise o kategori dahil edilmez
    """
    # Varsayılan değerler
    if amenity_list is None:
        amenity_list = OSM_TYPES
    if leisure_list is None:
        leisure_list = ["park", "garden", "forest"]
    if tourism_list is None:
        tourism_list = ["viewpoint", "museum"]
    
    # Regex pattern'leri oluştur
    parts = []
    
    if amenity_list:
        amenity_regex = "|".join(amenity_list)
        parts.append(f'node["amenity"~"^{amenity_regex}$"](around:{radius_m},{lat},{lon});')
        parts.append(f'way["amenity"~"^{amenity_regex}$"](around:{radius_m},{lat},{lon});')
        parts.append(f'relation["amenity"~"^{amenity_regex}$"](around:{radius_m},{lat},{lon});')
    
    if leisure_list:
        leisure_regex = "|".join(leisure_list)
        parts.append(f'node["leisure"~"^{leisure_regex}$"](around:{radius_m},{lat},{lon});')
        parts.append(f'way["leisure"~"^{leisure_regex}$"](around:{radius_m},{lat},{lon});')
        parts.append(f'relation["leisure"~"^{leisure_regex}$"](around:{radius_m},{lat},{lon});')
    
    if tourism_list:
        tourism_regex = "|".join(tourism_list)
        parts.append(f'node["tourism"~"^{tourism_regex}$"](around:{radius_m},{lat},{lon});')
        parts.append(f'way["tourism"~"^{tourism_regex}$"](around:{radius_m},{lat},{lon});')
        parts.append(f'relation["tourism"~"^{tourism_regex}$"](around:{radius_m},{lat},{lon});')
    
    if shop_list:
        shop_regex = "|".join(shop_list)
        parts.append(f'node["shop"~"^{shop_regex}$"](around:{radius_m},{lat},{lon});')
        parts.append(f'way["shop"~"^{shop_regex}$"](around:{radius_m},{lat},{lon});')
        parts.append(f'relation["shop"~"^{shop_regex}$"](around:{radius_m},{lat},{lon});')
    
    if healthcare_list:
        healthcare_regex = "|".join(healthcare_list)
        parts.append(f'node["healthcare"~"^{healthcare_regex}$"](around:{radius_m},{lat},{lon});')
        parts.append(f'way["healthcare"~"^{healthcare_regex}$"](around:{radius_m},{lat},{lon});')
        parts.append(f'relation["healthcare"~"^{healthcare_regex}$"](around:{radius_m},{lat},{lon});')
    
    if sport_list:
        sport_regex = "|".join(sport_list)
        parts.append(f'node["sport"~"^{sport_regex}$"](around:{radius_m},{lat},{lon});')
        parts.append(f'way["sport"~"^{sport_regex}$"](around:{radius_m},{lat},{lon});')
        parts.append(f'relation["sport"~"^{sport_regex}$"](around:{radius_m},{lat},{lon});')
    
    # En az bir part olmalı
    if not parts:
        amenity_regex = "|".join(OSM_TYPES)
        parts = [
            f'node["amenity"~"^{amenity_regex}$"](around:{radius_m},{lat},{lon});',
            f'way["amenity"~"^{amenity_regex}$"](around:{radius_m},{lat},{lon});',
            f'relation["amenity"~"^{amenity_regex}$"](around:{radius_m},{lat},{lon});'
        ]
    
    query_body = "\n".join(parts)

    q = f"""
    [out:json][timeout:60];
    (
    {query_body}
    );
    out center;
    """
    return q

def _overpass_cache_key(lat: float, lon: float, radius_m: int) -> str:
    """Cache key oluştur"""
    return f"{lat:.6f},{lon:.6f},{radius_m}"

def clear_overpass_cache():
    """Cache'i temizle (test için)"""
    global _OVERPASS_CACHE
    _OVERPASS_CACHE = {}

def fetch_from_overpass(lat: float, lon: float, radius_m: int, 
                        use_cache: bool = True,
                        amenity_list: List[str] = None,
                        leisure_list: List[str] = None,
                        tourism_list: List[str] = None,
                        shop_list: List[str] = None,
                        healthcare_list: List[str] = None,
                        sport_list: List[str] = None):
    """
    Overpass'tan veri çek - mirror desteği ve retry/backoff ile
    
    Args:
        use_cache: Cache kullanılsın mı (default: True)
        amenity_list, leisure_list, etc.: Kategori filtreleri
    
    Returns:
        List[dict] - OSM elements
    """
    # Cache key (şimdilik basit, filtreleri de içerebilir)
    cache_key = _overpass_cache_key(lat, lon, radius_m)
    
    # Cache kontrolü
    if use_cache and cache_key in _OVERPASS_CACHE:
        return _OVERPASS_CACHE[cache_key]
    
    # Overpass sorgusu
    query = overpass_query(lat, lon, radius_m, amenity_list, leisure_list, 
                          tourism_list, shop_list, healthcare_list, sport_list)
    
    # Retry logic with mirrors
    last_err = None
    for attempt in range(1, 4):
        for base_url in OVERPASS_URLS:
            try:
                resp = requests.post(base_url, data={"data": query}, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    data = resp.json()
                elements = data.get("elements", [])
                
                # Cache'e kaydet
                if use_cache:
                    _OVERPASS_CACHE[cache_key] = elements
                
                return elements
                
            except Exception as e:
                last_err = e
                print(f"  [Attempt {attempt}] Overpass {base_url} failed: {e}")
        
        if attempt < 3:
            time.sleep(2 * attempt)
    
    raise RuntimeError(f"Overpass erişimi başarısız: {last_err}")

# ====== NORMALİZASYON ======

def normalize(element: dict) -> dict:
    """OSM element'ini normalize et"""
    tags = element.get("tags", {}) or {}
    
    # Tür önceliği: amenity > shop > healthcare > sport > leisure > tourism
    t = (tags.get("amenity") or tags.get("shop") or tags.get("healthcare") or 
         tags.get("sport") or tags.get("leisure") or tags.get("tourism"))
    
    # Koordinat al
    lat = element.get("lat")
    lon = element.get("lon")
    if lat is None or lon is None:
        center = element.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")
    
    # tags listesi ve osm_tags dict
    tags_list = sorted(set(tags.keys()))
    osm_tags = {k: v for k, v in tags.items()}
    
    return {
        "source": "osm",
        "osm_id": element.get("id"),
        "sources": {
            "osm_id": element.get("id"),
            "osm_type": element.get("type")  # node/way/relation
        },
        "type": t,
        "name": tags.get("name"),
        "lat": lat,
        "lon": lon,
        "location": {
            "type": "Point",
            "coordinates": [lon, lat] if lon is not None and lat is not None else None
        },
        "address": {
            "city": tags.get("addr:city"),
            "street": tags.get("addr:street"),
            "housenumber": tags.get("addr:housenumber"),
        },
        "tags": tags_list,
        "osm_tags": osm_tags,
        "created_at": datetime.utcnow(),
    }

# ====== MONGODB İŞLEMLERİ ======

def ensure_indexes(coll):
    """İndeksleri oluştur"""
    from pymongo.errors import OperationFailure

    try:
        coll.create_index([("location", "2dsphere")])
    except OperationFailure:
        pass
    
    try:
        coll.create_index([("osm_id", ASCENDING)], unique=True, sparse=True)
    except OperationFailure:
        pass
    
    try:
        coll.create_index([("name", "text"), ("tags", "text")])
    except OperationFailure:
        pass
    
    try:
        coll.create_index([("sources.osm_id", 1), ("sources.osm_type", 1)], unique=True, sparse=True)
    except OperationFailure:
        pass

def upsert_elements(coll, elements: List[dict]) -> Tuple[int, int]:
    """
    Element'leri MongoDB'ye upsert et ve Google verisiyle zenginleştir
    
    Returns:
        Tuple[added_count, updated_count]
    """
    added = 0
    updated = 0
    
    # Google Places client'ı hazırla (eğer API key varsa)
    google_client = None
    try:
        from app.config import settings
        from app.services.google_places_service import get_google_places_client
        google_client = get_google_places_client(settings)
    except (RuntimeError, ValueError, ImportError):
        # Google API key yok veya başka bir hata - enrichment atlanacak
        pass
    
    for el in elements:
        # Normalize et
        doc = normalize(el)
        
        # Tip yoksa veya koordinat yoksa atla
        if not doc.get("type"):
            continue
        if doc.get("location", {}).get("coordinates") is None:
            continue
        
        # Upsert - sources.osm_id ve sources.osm_type kullan
        filter_doc = {"sources.osm_id": doc["osm_id"], "sources.osm_type": doc["sources"]["osm_type"]}
        
        # Mevcut dokümanı kontrol et (Google verisi eksik mi/eski mi?)
        existing = coll.find_one(filter_doc)
        
        # Google enrichment kontrolü
        should_enrich = False
        if existing:
            # Mevcut doküman var - Google verisi eksik veya eski mi kontrol et
            from app.services.google_places_enricher import is_google_data_stale
            if is_google_data_stale(existing, stale_days=30):
                should_enrich = True
        else:
            # Yeni doküman - Google verisi ekle
            should_enrich = True
        
        # Google enrichment (opsiyonel - sadece API key varsa ve gerekirse)
        if should_enrich and google_client:
            try:
                from app.services.google_places_enricher import enrich_place_document
                # Mevcut doküman varsa onu kullan, yoksa yeni doc'u
                doc_for_enrichment = existing if existing else doc
                google_data = enrich_place_document(doc_for_enrichment, google_client, force_refresh=False)
                
                if google_data:
                    doc["google"] = google_data
                    doc["google_last_updated"] = datetime.utcnow()
            except Exception as e:
                # Google enrichment hatası - devam et (OSM verisi zaten kaydedilecek)
                print(f"Google enrichment hatası (osm_id={doc.get('osm_id')}): {e}")
        
        # created_at'i doc'tan çıkar (sadece $setOnInsert'te kullanılacak)
        doc_without_created = {k: v for k, v in doc.items() if k != "created_at"}
        
        update_doc = {
            "$set": doc_without_created,
            "$setOnInsert": {"created_at": datetime.utcnow()}
        }
        
        res = coll.update_one(filter_doc, update_doc, upsert=True)
        
        if res.upserted_id is not None:
            added += 1
        elif res.modified_count > 0:
            updated += 1
    
    return added, updated

# ====== MOD İŞLEMLERİ ======

def mode_point_based(args, coll, amenity_list, leisure_list, tourism_list, 
                     shop_list, healthcare_list, sport_list):
    """Nokta bazlı arama modu (lat/lon)"""
    print(f"📍 Nokta bazlı arama: lat={args.lat}, lon={args.lon}, radius={args.r}m")
    
    elements = fetch_from_overpass(args.lat, args.lon, args.r, use_cache=True,
                                   amenity_list=amenity_list, leisure_list=leisure_list,
                                   tourism_list=tourism_list, shop_list=shop_list,
                                   healthcare_list=healthcare_list, sport_list=sport_list)
    
    if args.limit:
        elements = elements[:args.limit]
    
    print(f"Overpass döndü: {len(elements)} element")
    
    added, updated = upsert_elements(coll, elements)
    print(f"✅ Upsert tamamlandı: +{added} eklendi, ~{updated} güncellendi")
    
    return added + updated

def mode_city_grid(args, coll, amenity_list, leisure_list, tourism_list,
                   shop_list, healthcare_list, sport_list):
    """Şehir bazlı grid arama modu"""
    # Bbox al
    try:
        bbox = get_city_bbox(args.city, args.country)
    except RuntimeError as e:
        print(f"❌ Hata: {e}")
        return 0
    
    # Grid hücreleri oluştur
    grid_size_m = args.grid_size if args.grid_size else DEFAULT_GRID_SIZE_M
    cells = generate_grid_cells(bbox, grid_size_m)
    total_cells = len(cells)
    
    print(f"🔍 Grid tarama başlıyor: {total_cells} hücre")
    print(f"📐 Grid boyutu: {grid_size_m}m, Bekleme: {args.sleep}ms")
    
    total_found = 0
    total_added = 0
    total_updated = 0
    sleep_sec = args.sleep / 1000.0
    
    for i, (lat, lon) in enumerate(cells, 1):
        try:
            # Overpass'tan çek
            elements = fetch_from_overpass(lat, lon, grid_size_m, use_cache=True,
                                          amenity_list=amenity_list, leisure_list=leisure_list,
                                          tourism_list=tourism_list, shop_list=shop_list,
                                          healthcare_list=healthcare_list, sport_list=sport_list)
            total_found += len(elements)
            
            # Upsert et
            added, updated = upsert_elements(coll, elements)
            total_added += added
            total_updated += updated
            
            print(f"[{i}/{total_cells}] Cell ({lat:.4f}, {lon:.4f}): "
                  f"{len(elements)} bulundu, +{added}, ~{updated}")
            
            # Bekleme
            if i < total_cells:
                time.sleep(sleep_sec)
                
        except Exception as e:
            print(f"[{i}/{total_cells}] Hata: {e}")
    
    print("\n" + "=" * 80)
    print(f"✅ Grid tarama tamamlandı")
    print(f"   Şehir: {args.city}")
    print(f"   Kullanılan bbox: {bbox}")
    print(f"   Taranan hücre sayısı: {total_cells}")
    print(f"   Toplam bulunan: {total_found} element")
    print(f"   Upsert: +{total_added} eklendi, ~{total_updated} güncellendi")
    print("=" * 80)
    
    return total_added + total_updated

# ====== MAIN ======

def main():
    parser = argparse.ArgumentParser(
        description="OSM mekânlarını MongoDB'ye kaydet",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Mod: nokta bazlı
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT, help="Enlem (lat)")
    parser.add_argument("--lon", type=float, default=DEFAULT_LON, help="Boylam (lon)")
    parser.add_argument("--r", type=int, default=DEFAULT_RADIUS_M, 
                        help="Arama yarıçapı (metre)")
    parser.add_argument("--limit", type=int, default=None, 
                        help="Maksimum kayıt sayısı (opsiyonel)")
    
    # Mod: şehir bazlı grid
    parser.add_argument("--city", type=str, help="Şehir adı (örn: 'Elazığ, Türkiye')")
    parser.add_argument("--country", type=str, default=None, 
                        help="Ülke kodu (örn: tr, de, fr)")
    parser.add_argument("--grid-size", type=int, default=DEFAULT_GRID_SIZE_M,
                        help=f"Grid karo boyutu metre (default: {DEFAULT_GRID_SIZE_M})", dest="grid_size")
    parser.add_argument("--grid-size-m", type=int, default=DEFAULT_GRID_SIZE_M,
                        help=f"Grid karo boyutu metre (default: {DEFAULT_GRID_SIZE_M})", dest="grid_size")
    parser.add_argument("--sleep", type=int, default=DEFAULT_SLEEP_MS,
                        help=f"Grid tarama arası bekleme ms (default: {DEFAULT_SLEEP_MS})", dest="sleep")
    parser.add_argument("--sleep-ms", type=int, default=DEFAULT_SLEEP_MS,
                        help=f"Grid tarama arası bekleme ms (default: {DEFAULT_SLEEP_MS})", dest="sleep")
    
    # OSM kategori filtreleri
    parser.add_argument("--amenities", type=str, help="Comma-separated amenity listesi (örn: restaurant,cafe)")
    parser.add_argument("--leisure", type=str, help="Comma-separated leisure listesi (örn: park,garden)")
    parser.add_argument("--tourism", type=str, help="Comma-separated tourism listesi (örn: museum,hotel)")
    parser.add_argument("--shop", type=str, help="Comma-separated shop listesi (örn: supermarket,bakery)")
    parser.add_argument("--healthcare", type=str, help="Comma-separated healthcare listesi (örn: clinic,pharmacy)")
    parser.add_argument("--sport", type=str, help="Comma-separated sport listesi (örn: fitness,swimming)")
    
    args = parser.parse_args()

    # Comma-separated string'leri list'e çevir (boşlukları temizle)
    amenity_list = [x.strip() for x in args.amenities.split(",")] if args.amenities else None
    leisure_list = [x.strip() for x in args.leisure.split(",")] if args.leisure else None
    tourism_list = [x.strip() for x in args.tourism.split(",")] if args.tourism else None
    shop_list = [x.strip() for x in args.shop.split(",")] if args.shop else None
    healthcare_list = [x.strip() for x in args.healthcare.split(",")] if args.healthcare else None
    sport_list = [x.strip() for x in args.sport.split(",")] if args.sport else None
    
    # MongoDB bağlantısı
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=4000)
    db = client[DB_NAME]
    coll = db[COLL_NAME]
    ensure_indexes(coll)

    # Mod seçimi
    if args.city:
        mode_city_grid(args, coll, amenity_list, leisure_list, tourism_list, 
                      shop_list, healthcare_list, sport_list)
    else:
        mode_point_based(args, coll, amenity_list, leisure_list, tourism_list,
                        shop_list, healthcare_list, sport_list)
    
    # Özet
    total = coll.count_documents({})
    print(f"\n📊 Toplam MongoDB kayıt sayısı: {total}")

    client.close()

if __name__ == "__main__":
    main()
