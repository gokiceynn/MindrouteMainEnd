"""
Background task modülü: OSM verilerini çekip MongoDB'ye kaydet
"""
import os
import time
import math
from datetime import datetime
from typing import Tuple, Optional, List

import requests
from ..db import get_places
from .tiles import mark_fetching, mark_fetched

# Config
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "MindRoute/0.1 (+local dev)"}

# Varsayılan kategoriler
DEFAULT_AMENITIES = ["restaurant", "cafe", "fast_food", "library", "school", "university", "place_of_worship"]
DEFAULT_LEISURE = ["park", "garden", "fitness_centre"]
DEFAULT_TOURISM = ["museum", "hotel", "hostel", "information", "viewpoint"]
DEFAULT_SHOP = ["supermarket", "bakery", "chemist", "convenience", "clothes", "books"]
DEFAULT_HEALTHCARE = ["clinic", "doctor", "pharmacy"]
DEFAULT_SPORT = ["fitness", "swimming", "tennis", "football"]


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki nokta arası mesafe hesapla (metre)"""
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def _get_city_bbox(city: str, country: Optional[str] = None) -> Tuple[float, float, float, float]:
    """Nominatim ile şehir bbox'ını al"""
    params = {"q": city, "format": "json", "limit": 1, "addressdetails": 1}
    if country:
        params["countrycodes"] = country.lower()
    
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        if not data:
            raise RuntimeError(f"'{city}' şehri bulunamadı")
        
        bbox = data[0].get("boundingbox")
        if not bbox or len(bbox) != 4:
            raise RuntimeError(f"'{city}' için bbox alınamadı")
        
        south, north, west, east = [float(x) for x in bbox]
        return south, north, west, east
    except requests.RequestException as e:
        raise RuntimeError(f"Nominatim isteği başarısız: {e}")


def _overpass_query(lat: float, lon: float, radius_m: int,
                   amenity_list: List[str] = None,
                   leisure_list: List[str] = None,
                   tourism_list: List[str] = None,
                   shop_list: List[str] = None,
                   healthcare_list: List[str] = None,
                   sport_list: List[str] = None) -> str:
    """Overpass QL sorgusu oluştur"""
    if amenity_list is None:
        amenity_list = DEFAULT_AMENITIES
    if leisure_list is None:
        leisure_list = DEFAULT_LEISURE
    if tourism_list is None:
        tourism_list = DEFAULT_TOURISM
    
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
    
    if not parts:
        amenity_regex = "|".join(DEFAULT_AMENITIES)
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


def _fetch_from_overpass(lat: float, lon: float, radius_m: int,
                         amenity_list: List[str] = None,
                         leisure_list: List[str] = None,
                         tourism_list: List[str] = None,
                         shop_list: List[str] = None,
                         healthcare_list: List[str] = None,
                         sport_list: List[str] = None) -> List[dict]:
    """Overpass'tan veri çek - retry ve mirror desteği"""
    query = _overpass_query(lat, lon, radius_m, amenity_list, leisure_list,
                           tourism_list, shop_list, healthcare_list, sport_list)
    
    last_err = None
    for attempt in range(1, 4):
        for base_url in OVERPASS_URLS:
            try:
                resp = requests.post(base_url, data={"data": query}, headers=HEADERS, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                return data.get("elements", [])
            except Exception as e:
                last_err = e
                print(f"  [Attempt {attempt}] Overpass {base_url} failed: {e}")
        
        if attempt < 3:
            time.sleep(2 * attempt)
    
    raise RuntimeError(f"Overpass erişimi başarısız: {last_err}")


def _normalize_element(element: dict) -> dict:
    """OSM element'ini normalize et"""
    tags = element.get("tags", {}) or {}
    
    t = (tags.get("amenity") or tags.get("shop") or tags.get("healthcare") or 
         tags.get("sport") or tags.get("leisure") or tags.get("tourism"))
    
    lat = element.get("lat")
    lon = element.get("lon")
    if lat is None or lon is None:
        center = element.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")
    
    tags_list = sorted(set(tags.keys()))
    osm_tags = {k: v for k, v in tags.items()}
    
    return {
        "source": "osm",
        "osm_id": element.get("id"),
        "sources": {
            "osm_id": element.get("id"),
            "osm_type": element.get("type")
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


def _upsert_elements(coll, elements: List[dict]) -> Tuple[int, int]:
    """Element'leri MongoDB'ye upsert et ve Google verisiyle zenginleştir"""
    added = 0
    updated = 0
    
    # Google Places client'ı hazırla (eğer API key varsa)
    google_client = None
    try:
        from ..config import settings
        from .google_places_service import get_google_places_client
        google_client = get_google_places_client(settings)
    except (RuntimeError, ValueError, ImportError):
        # Google API key yok veya başka bir hata - enrichment atlanacak
        pass
    
    for el in elements:
        doc = _normalize_element(el)
        
        if not doc.get("type"):
            continue
        if doc.get("location", {}).get("coordinates") is None:
            continue
        
        # created_at'i doc'tan çıkar (sadece $setOnInsert'te kullanılacak)
        doc_without_created = {k: v for k, v in doc.items() if k != "created_at"}
        
        filter_doc = {"sources.osm_id": doc["osm_id"], "sources.osm_type": doc["sources"]["osm_type"]}
        
        # Mevcut dokümanı kontrol et (Google verisi eksik mi/eski mi?)
        existing = coll.find_one(filter_doc)
        
        # Google enrichment kontrolü
        should_enrich = False
        if existing:
            # Mevcut doküman var - Google verisi eksik veya eski mi kontrol et
            from .google_places_enricher import is_google_data_stale
            if is_google_data_stale(existing, stale_days=30):
                should_enrich = True
        else:
            # Yeni doküman - Google verisi ekle
            should_enrich = True
        
        # Google enrichment (opsiyonel - sadece API key varsa ve gerekirse)
        if should_enrich and google_client:
            try:
                from .google_places_enricher import enrich_place_document
                # Mevcut doküman varsa onu kullan, yoksa yeni doc'u
                doc_for_enrichment = existing if existing else doc
                google_data = enrich_place_document(doc_for_enrichment, google_client, force_refresh=False)
                
                if google_data:
                    doc_without_created["google"] = google_data
                    doc_without_created["google_last_updated"] = datetime.utcnow()
            except Exception as e:
                # Google enrichment hatası - devam et (OSM verisi zaten kaydedilecek)
                print(f"Google enrichment hatası (osm_id={doc.get('osm_id')}): {e}")
        
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


def _generate_grid_cells(bbox: Tuple[float, float, float, float], grid_size_m: int) -> List[Tuple[float, float]]:
    """Bbox'ı grid hücrelerine böl"""
    south, north, west, east = bbox
    
    width_m = _haversine_distance(south, west, south, east)
    height_m = _haversine_distance(south, west, north, west)
    
    cells_x = max(1, int(math.ceil(width_m / grid_size_m)))
    cells_y = max(1, int(math.ceil(height_m / grid_size_m)))
    
    centers = []
    for i in range(cells_y):
        for j in range(cells_x):
            lat_factor = (i + 0.5) / cells_y if cells_y > 1 else 0.5
            lon_factor = (j + 0.5) / cells_x if cells_x > 1 else 0.5
            
            center_lat = south + (north - south) * lat_factor
            center_lon = west + (east - west) * lon_factor
            
            centers.append((center_lat, center_lon))
    
    return centers


def run_bbox_async(south: float, west: float, north: float, east: float,
                   tile_id: Optional[str] = None, sleep_ms: int = 600):
    """
    Bir bbox için veri çek (background task)
    
    Args:
        south, west, north, east: Bbox koordinatları
        tile_id: Tile ID (metadata güncellemesi için)
        sleep_ms: Bekleme süresi (ms)
    """
    try:
        if tile_id:
            mark_fetching(tile_id)
        
        coll = get_places()
        
        # Bbox merkezi ve yarıçapı hesapla
        center_lat = (south + north) / 2.0
        center_lon = (west + east) / 2.0
        radius_m = max(
            _haversine_distance(center_lat, west, center_lat, east) / 2.0,
            _haversine_distance(south, center_lon, north, center_lon) / 2.0
        )
        radius_m = int(radius_m) + 100  # Biraz padding ekle
        
        # Overpass'tan çek
        elements = _fetch_from_overpass(center_lat, center_lon, radius_m)
        
        # MongoDB'ye kaydet
        added, updated = _upsert_elements(coll, elements)
        
        if tile_id:
            mark_fetched(tile_id, ok=True)
        
        print(f"Tile {tile_id or 'unknown'}: +{added} eklendi, ~{updated} güncellendi")
        
        time.sleep(sleep_ms / 1000.0)
        
    except Exception as e:
        print(f"Tile {tile_id or 'unknown'} fetch hatası: {e}")
        if tile_id:
            mark_fetched(tile_id, ok=False)


def run_city_async(city: str, country: Optional[str] = None,
                   grid_size_m: int = 1000, sleep_ms: int = 600,
                   max_tiles: int = 1200):
    """
    Şehir bazlı grid arama (background task)
    
    Args:
        city: Şehir adı (örn: "Elazığ, Türkiye")
        country: Ülke kodu (opsiyonel)
        grid_size_m: Grid karo boyutu (metre)
        sleep_ms: Her hücre arası bekleme (ms)
        max_tiles: Maksimum taranacak karo sayısı
    """
    try:
        print(f"City fetch başlıyor: {city}")
        
        # Bbox al
        bbox = _get_city_bbox(city, country)
        south, north, west, east = bbox
        
        # Grid hücreleri oluştur
        cells = _generate_grid_cells(bbox, grid_size_m)
        
        if len(cells) > max_tiles:
            cells = cells[:max_tiles]
        
        print(f"Grid: {len(cells)} hücre taranacak")
        
        coll = get_places()
        total_added = 0
        total_updated = 0
        
        sleep_sec = sleep_ms / 1000.0
        
        for i, (lat, lon) in enumerate(cells, 1):
            try:
                elements = _fetch_from_overpass(lat, lon, grid_size_m)
                added, updated = _upsert_elements(coll, elements)
                total_added += added
                total_updated += updated
                
                if i % 50 == 0:
                    print(f"[{i}/{len(cells)}] {city}: +{total_added}, ~{total_updated}")
                
                if i < len(cells):
                    time.sleep(sleep_sec)
                    
            except Exception as e:
                print(f"[{i}/{len(cells)}] Hata: {e}")
        
        print(f"City fetch tamamlandı: {city} - +{total_added}, ~{total_updated}")
        
    except Exception as e:
        print(f"City fetch hatası ({city}): {e}")
