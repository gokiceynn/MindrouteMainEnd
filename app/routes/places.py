import asyncio
from math import radians, cos, sin, asin, sqrt
from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Dict, Any, List, Optional
from app.database import get_places_collection
from app.config import settings
from app.models import PlaceItem, PlacesSearchResponse
from app.services.places_enricher import get_nearby_places
from app.services.foursquare_service import FoursquareClient, get_foursquare_client
# Google Places API için import - circular import'u önlemek için lazy import kullanacağız

router = APIRouter(prefix="/places", tags=["Places"])

# ALLOWED_TYPES: Leisure places we BOOST (not a strict filter)
ALLOWED_TYPES = {
    "cafe", "coffee_shop", "restaurant", "bar", "night_club",
    "bakery", "meal_takeaway", "meal_delivery",
    "shopping_mall", "movie_theater", "bowling_alley",
    "tourist_attraction", "amusement_park",
    "park", "garden", "campground",
    "museum", "art_gallery", "library",
    "book_store", "spa", "gym"
}

# Hard exclude (BLOCK) - Gençlerin gitmeyeceği yerler
BLOCKED_TYPES = {
    "school", "university", "primary_school", "secondary_school", "college",
    "hospital", "doctor", "dentist", "pharmacy", "clinic", "health",
    "bank", "police", "atm", "cemetery", "funeral_home",
    "government", "courthouse", "fire_station", "post_office",
    "mosque", "church", "temple", "place_of_worship", "synagogue",
    "warehouse", "factory", "industrial", "storage",
    "office", "real_estate_agency", "insurance_agency", "lawyer",
    "car_dealer", "car_repair", "gas_station", "parking",
    "supermarket", "grocery_store", "convenience_store", "market"
}

GENERIC_TYPES = {"point_of_interest", "establishment"}


def is_blocked(types: list[str], name: str) -> bool:
    """Check if a place should be blocked based on types and name."""
    lower_name = name.lower() if name else ""
    
    # Fast-pass coffee check - kafe isimleri asla bloklanmaz
    coffee_keywords = [
        "cafe", "kahve", "coffee", "kafe", "café",
        "espresso", "latte", "arabica", "starbucks",
        "mackbear", "looq", "brew", "roastery"
    ]
    if any(kw in lower_name for kw in coffee_keywords):
        return False  # Kafe isimleri asla bloklanmaz
    
    # if ANY blocked type matches exactly (sadece tam eşleşme)
    if any(t in BLOCKED_TYPES for t in types):
        return True
    
    # name-based blacklist - Gençlerin gitmeyeceği yerler
    blocked_keywords = [
        "market", "grocery", "bakkal", "supermarket", "migros", "a101", "bim", "şok",
        "okul", "school", "üniversite", "university", "college", "fakülte", "faculty", "lise", "ilkokul",
        "hastane", "hospital", "klinik", "clinic", "sağlık", "health",
        "eczane", "pharmacy", "medikal", "medical",
        "bank", "atm", "ziraat", "garanti", "iş bankası", "yapı kredi",
        "polis", "police", "jandarma", "güvenlik",
        "cami", "mosque", "kilise", "church", "mescit",
        "mezarlık", "cemetery", "kabristan",
        "veteriner", "veterinary",
        "government", "courthouse", "belediye", "kaymakamlık", "valilik",
        "warehouse", "factory", "industrial", "depo", "fabrika",
        "ofis", "office", "büro", "sigorta", "insurance",
        "oto", "otomobil", "car", "galeri", "servis",
        "parking", "otopark", "park yeri"
    ]
    if any(bad in lower_name for bad in blocked_keywords):
        return True
    
    return False


def compute_leisure_boost(types: list[str]) -> float:
    """Compute boost score for leisure places."""
    tset = {t.lower() for t in types}
    if tset.intersection(ALLOWED_TYPES):
        return 0.15      # boost leisure
    return 0.0            # don't exclude others


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki koordinat arasındaki mesafeyi metre cinsinden hesaplar."""
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))


@router.get("/")
async def get_places(limit: int = Query(10, description="Maksimum sonuç sayısı")):
    """Tüm mekanları listele (test için)"""
    try:
        places_collection = get_places_collection()
        if places_collection is None:
            raise HTTPException(status_code=500, detail="Veritabanı bağlantısı kurulamadı")
        
        results = await places_collection.find({}).limit(limit).to_list(length=limit)
        return {
            "count": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hata: {str(e)}")


@router.get("/search", response_model=PlacesSearchResponse)
async def search_places(
    lat: float = Query(..., description="Enlem"),
    lon: float = Query(..., description="Boylam"),
    radius_km: float = Query(5.0, ge=0.1, le=20.0, description="Arama yarıçapı (km)"),
    mood: Optional[str] = Query(None, description="Kullanıcının ruh hali (opsiyonel)"),
    limit: int = Query(20, ge=1, le=100, description="Maksimum sonuç sayısı"),
    live: Optional[bool] = Query(None, description="Canlı arama modu (opsiyonel)")
) -> PlacesSearchResponse:
    """
    YENİ PIPELINE: Google Places API → Ana Veri Kaynağı
    - Ana veri kaynağı: Google Places API (güncel ve kapsamlı)
    - OSM: Sadece destekleyici kaynak (Google'da olmayan mekanlar için)
    - Mood sıralamayı etkiler, katı filtreleme yapmaz
    """
    # Koordinat kontrolü
    if not (-90 <= lat <= 90):
        raise HTTPException(status_code=422, detail="Enlem -90 ile 90 arasında olmalı")
    if not (-180 <= lon <= 180):
        raise HTTPException(status_code=422, detail="Boylam -180 ile 180 arasında olmalı")
    
    try:
        radius_m = int(radius_km * 1000.0)
        
        # Hibrit pipeline: OSM + Foursquare + Google kombinasyonu
        # OSM: Geniş veri kaynağı (eski mekanlar)
        # Foursquare: Rating ve fotoğraf zenginleştirme
        # Google: Güncel mekanlar ve detaylı bilgi
        items = await get_nearby_places(
            user_lat=lat,
            user_lon=lon,
            mood=mood,
            radius_m=radius_m,
            limit=limit,
        )
        
        return PlacesSearchResponse(
            items=items,
            count=len(items),
            warming_up=False,
            tiles_checked=0,
            tiles_to_fetch=0,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in search_places: {e}")
        print(error_trace)
        raise HTTPException(
            status_code=500, 
            detail=f"Arama sırasında hata oluştu: {type(e).__name__}: {str(e)}"
        )


@router.get("/debug/foursquare")
async def debug_foursquare(
    lat: float = Query(..., description="Enlem"),
    lon: float = Query(..., description="Boylam"),
    radius_km: float = Query(3.0, description="Arama yarıçapı (km)"),
    client: FoursquareClient = Depends(get_foursquare_client),
):
    """
    Foursquare Places API için ham (filtrelenmemiş) debug endpoint'i.
    Foursquare'den gelen tüm sonuçları direkt döndürür.
    """
    radius_m = int(radius_km * 1000)
    data = await client.search_raw(lat=lat, lon=lon, radius_m=radius_m)
    return data


@router.post("/debug/foursquare/reset-flag")
async def reset_foursquare_flag():
    """
    Geriye dönük uyumluluk için bırakılmış stub endpoint.
    Artık Foursquare için deprecated flag mekanizması kullanılmıyor.
    """
    return {
        "message": "Foursquare deprecated flag mekanizması kaldırıldı, bu endpoint artık sadece stub olarak mevcut.",
        "status": "noop",
    }


@router.post("/fetch-rich")
async def fetch_rich(lat: float = Query(...), lon: float = Query(...), radius: int = Query(300)):
    try:
        from app.config.mongo_sync import places_col
        from app.services.enrich.enrich_place import enrich_place_data
        from app.services.external.wikidata_service import find_wikidata_id
        from app.services.external.wikimedia_photos import get_wikimedia_images
        from app.services.external.yelp_service import yelp_search_by_coords
        from app.services.google.google_nearby import google_nearby
        from app.services.osm.overpass import fetch_overpass_places

        col = places_col()
        results = []

        print(">>> FETCH-RICH STARTED <<<")
        osm_places = await fetch_overpass_places(lat, lon, radius)
        print(f"OSM count: {len(osm_places)}")
        max_items = 10
        osm_places = osm_places[:max_items]

        for osm_place in osm_places:
            name = osm_place.get("name")
            if not name:
                continue

            print("Calling Yelp & Wikidata for:", name)

            try:
                g = await google_nearby(name, osm_place["lat"], osm_place["lon"])
                # Google'dan gelen photo_reference'ları URL'ye çevir
                if g and g.get("photos"):
                    from app.services.google.google_places_helper import get_photo_url
                    photo_urls = []
                    for photo in g.get("photos", [])[:5]:  # En fazla 5 fotoğraf
                        photo_ref = photo.get("photo_reference")
                        if photo_ref:
                            photo_url = get_photo_url(photo_ref)
                            if photo_url:
                                photo_urls.append(photo_url)
                    if photo_urls:
                        g["photos"] = photo_urls
            except Exception as e:
                print(f"Google nearby error for {name}: {e}")
                g = None

            try:
                yelp_list = await yelp_search_by_coords(
                    osm_place["lat"], osm_place["lon"], name
                )
                yelp_best = yelp_list[0] if yelp_list else None
            except Exception as e:
                print(f"Yelp error for {name}: {e}")
                yelp_best = None

            try:
                wiki_id = await find_wikidata_id(name)
                wiki_photos = []
                if wiki_id:
                    wiki_photos = await get_wikimedia_images(qid=wiki_id)
            except Exception as e:
                print(f"Wikidata error for {name}: {e}")
                wiki_photos = []

            try:
                enriched = await enrich_place_data(
                    osm_place, g or {}, yelp_best or {}, wiki_photos
                )

                # OSM tag değerlerini filtreleme için sakla (amenity/leisure/tourism/shop)
                raw_tags = (osm_place.get("raw_osm") or {}).get("tags", {})
                osm_types = []
                for key in ("amenity", "tourism", "leisure", "shop"):
                    val = raw_tags.get(key)
                    if val:
                        osm_types.append(val)
                enriched["osm_types"] = osm_types

                col.update_one(
                    {"lat": osm_place["lat"], "lon": osm_place["lon"]},
                    {"$set": enriched},
                    upsert=True,
                )

                results.append(enriched)
            except Exception as e:
                print(f"Enrich error for {name}: {e}")
                continue

        # İstenmeyen tipleri filtrele
        blocked_types = [
            "pharmacy",
            "hospital",
            "doctors",
            "clinic",
            "bank",
            "marketplace",
            "supermarket",
        ]

        items = [
            p for p in results
            if not any(bt in (p.get("osm_types") or []) for bt in blocked_types)
        ]

        max_items = 12
        items = items[:max_items]

        return {"ok": True, "count": len(items), "items": items}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in fetch_rich: {e}")
        print(error_trace)
        raise HTTPException(
            status_code=500,
            detail=f"fetch-rich hatası: {type(e).__name__}: {str(e)}"
        )