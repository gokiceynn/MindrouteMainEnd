"""
Google Places API entegrasyonu için enrichment servisi.
OSM mekanlarını Google Places verisi ile zenginleştirir.
"""
import re
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt

from .google_places_service import GooglePlacesClient, GooglePlacesError


def sanitize_place_name(name: str) -> str:
    """
    Place adını normalize eder (karşılaştırma için).
    - Küçük harfe çevir
    - Özel karakterleri temizle
    - Fazla boşlukları temizle
    """
    if not name:
        return ""
    
    # Küçük harfe çevir ve Türkçe karakterleri normalize et
    normalized = name.lower()
    
    # Türkçe karakter dönüşümü
    replacements = {
        'ş': 's', 'Ş': 's',
        'ı': 'i', 'İ': 'i',
        'ğ': 'g', 'Ğ': 'g',
        'ü': 'u', 'Ü': 'u',
        'ö': 'o', 'Ö': 'o',
        'ç': 'c', 'Ç': 'c'
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    
    # Özel karakterleri ve fazla boşlukları temizle
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def _haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki koordinat arası mesafe hesapla (metre)"""
    R = 6371000  # Dünya yarıçapı (metre)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c


def _name_similarity(name1: str, name2: str) -> float:
    """
    İki isim arasındaki benzerlik skoru (0.0 - 1.0).
    Basit jaccard benzerliği kullanır.
    """
    if not name1 or not name2:
        return 0.0
    
    s1 = set(sanitize_place_name(name1).split())
    s2 = set(sanitize_place_name(name2).split())
    
    if not s1 or not s2:
        return 0.0
    
    intersection = len(s1 & s2)
    union = len(s1 | s2)
    
    if union == 0:
        return 0.0
    
    return intersection / union


def match_osm_to_google(
    osm_doc: Dict,
    google_search_results: List[Dict],
    max_distance_m: float = 150.0,
    min_name_similarity: float = 0.3
) -> Optional[Dict]:
    """
    OSM dokümanını Google Places sonuçlarıyla eşleştirir.
    
    Args:
        osm_doc: OSM place dokümanı
        google_search_results: Google Nearby Search sonuçları (results listesi)
        max_distance_m: Maksimum mesafe eşiği (metre)
        min_name_similarity: Minimum isim benzerliği (0.0-1.0)
    
    Returns:
        En iyi eşleşen Google place dict veya None
    """
    if not google_search_results:
        return None
    
    osm_name = osm_doc.get("name")
    osm_location = osm_doc.get("location", {}).get("coordinates")
    
    if not osm_location or len(osm_location) != 2:
        return None
    
    osm_lon, osm_lat = osm_location[0], osm_location[1]
    
    best_match = None
    best_score = 0.0
    
    for google_place in google_search_results:
        geometry = google_place.get("geometry", {})
        location = geometry.get("location", {})
        
        if not location:
            continue
        
        google_lat = location.get("lat")
        google_lon = location.get("lng")
        
        if google_lat is None or google_lon is None:
            continue
        
        # Mesafe kontrolü
        distance = _haversine_distance_m(osm_lat, osm_lon, google_lat, google_lon)
        if distance > max_distance_m:
            continue
        
        # İsim benzerliği
        google_name = google_place.get("name", "")
        name_sim = _name_similarity(osm_name or "", google_name)
        if name_sim < min_name_similarity:
            continue
        
        # Skorlama: mesafe ve isim benzerliği kombinasyonu
        distance_score = 1.0 - min(distance / max_distance_m, 1.0)
        combined_score = 0.6 * name_sim + 0.4 * distance_score
        
        if combined_score > best_score:
            best_score = combined_score
            best_match = google_place
    
    return best_match


def sanitize_review(review: Dict) -> Dict:
    """
    Google review'unu temizler ve basitleştirir.
    
    Args:
        review: Google review dict
    
    Returns:
        Basitleştirilmiş review dict
    """
    return {
        "author_name": review.get("author_name", "Anonymous"),
        "rating": review.get("rating"),
        "text": review.get("text", ""),
        "time": review.get("time"),  # Unix timestamp
        "relative_time_description": review.get("relative_time_description", "")
    }


def enrich_place_with_google(
    osm_doc: Dict,
    google_details: Dict,
    google_client: GooglePlacesClient
) -> Dict:
    """
    OSM dokümanını Google Places detay verileriyle zenginleştirir.
    
    Args:
        osm_doc: OSM place dokümanı
        google_details: Google Place Details API response'unun result kısmı
        google_client: GooglePlacesClient instance (photo URL'leri için)
    
    Returns:
        Google enrichment verisi (place["google"] için)
    """
    result = google_details.get("result", {})
    
    # Fotoğraf URL'lerini oluştur
    photos = []
    photo_refs = result.get("photos", [])
    for photo in photo_refs[:5]:  # En fazla 5 fotoğraf
        photo_ref = photo.get("photo_reference")
        if photo_ref:
            photo_url = google_client.build_photo_url(photo_ref, max_width=800)
            photos.append(photo_url)
    
    # Review'ları temizle ve sınırla
    reviews = []
    raw_reviews = result.get("reviews", [])
    # Rating'e göre sırala (yüksekten düşüğe) ve en fazla 10 al
    sorted_reviews = sorted(
        raw_reviews,
        key=lambda r: (r.get("rating", 0), r.get("time", 0)),
        reverse=True
    )
    for review in sorted_reviews[:10]:
        reviews.append(sanitize_review(review))
    
    # Opening hours
    opening_hours = {}
    if "opening_hours" in result:
        opening_hours = {
            "open_now": result["opening_hours"].get("open_now"),
            "weekday_text": result["opening_hours"].get("weekday_text", [])
        }
    
    enrichment = {
        "place_id": result.get("place_id"),
        "rating": result.get("rating"),
        "user_ratings_total": result.get("user_ratings_total", 0),
        "address": result.get("formatted_address", ""),
        "url": result.get("url", ""),
        "opening_hours": opening_hours,
        "photos": photos,
        "reviews": reviews,
    }
    
    # None değerleri temizle
    enrichment = {k: v for k, v in enrichment.items() if v is not None}
    
    return enrichment


def is_google_data_stale(place_doc: Dict, stale_days: int = 30) -> bool:
    """
    Place dokümanındaki Google verisinin güncelliğini kontrol eder.
    
    Args:
        place_doc: MongoDB place dokümanı
        stale_days: Veri kaç gün sonra eski kabul edilir
    
    Returns:
        True eğer veri eksik veya eski ise
    """
    if "google" not in place_doc or not place_doc.get("google"):
        return True
    
    last_updated = place_doc.get("google_last_updated")
    if not last_updated:
        return True
    
    # Eğer string ise datetime'a çevir
    if isinstance(last_updated, str):
        try:
            last_updated = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        except:
            return True
    
    # Eğer datetime değilse
    if not isinstance(last_updated, datetime):
        return True
    
    cutoff = datetime.utcnow() - timedelta(days=stale_days)
    return last_updated < cutoff


def enrich_place_document(
    place_doc: Dict,
    google_client: Optional[GooglePlacesClient],
    force_refresh: bool = False
) -> Optional[Dict]:
    """
    Place dokümanını Google verisiyle zenginleştirir (async wrapper).
    
    Args:
        place_doc: MongoDB place dokümanı
        google_client: GooglePlacesClient instance veya None
        force_refresh: Mevcut veri olsa bile yenile
    
    Returns:
        Google enrichment dict veya None
    """
    if not google_client:
        return None
    
    # Mevcut veri varsa ve fresh ise ve force_refresh değilse skip
    if not force_refresh and not is_google_data_stale(place_doc):
        return place_doc.get("google")
    
    try:
        location = place_doc.get("location", {}).get("coordinates")
        if not location or len(location) != 2:
            return None
        
        lon, lat = location[0], location[1]
        place_name = place_doc.get("name")
        
        # Nearby Search
        nearby_results = google_client.search_nearby(
            lat=lat,
            lon=lon,
            radius_m=200,  # 200m yarıçap
            keyword=place_name
        )
        
        results = nearby_results.get("results", [])
        if not results:
            return None
        
        # OSM ile eşleştir
        matched = match_osm_to_google(place_doc, results)
        if not matched:
            return None
        
        # Place Details çek
        place_id = matched.get("place_id")
        if not place_id:
            return None
        
        details = google_client.get_details(place_id)
        
        # Enrichment oluştur
        enrichment = enrich_place_with_google(place_doc, details, google_client)
        
        return enrichment
        
    except GooglePlacesError as e:
        print(f"Google Places API error during enrichment: {e}")
        return None
    except Exception as e:
        print(f"Error enriching place {place_doc.get('_id')}: {e}")
        return None

