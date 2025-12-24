from math import radians, cos, sin, asin, sqrt, log
from typing import List, Optional, Set, Dict

import asyncio
from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.models import PlaceItem, PlacesSearchResponse, GooglePlaceInfo, GoogleReview
from app.services.google_places_service import (
    get_google_places_client,
    GooglePlacesError,
)
from app.services.google_places_enricher import enrich_place_with_google
from app.services.mood_recommender import (
    normalize_mood,
    compute_mood_score,
    build_mood_reason,
    base_score,
)


router = APIRouter()


# SOFT PREFERENCE: Leisure places we boost (but don't filter others)
ALLOWED_TYPES: Set[str] = {
    "cafe", "coffee_shop", "restaurant", "bar", "night_club",
    "bakery", "meal_takeaway", "meal_delivery",
    "shopping_mall", "movie_theater", "bowling_alley",
    "tourist_attraction", "amusement_park",
    "park", "garden", "campground",
    "museum", "art_gallery", "library",
    "book_store", "spa", "gym"
}

# HARD BLOCK LIST: Things we NEVER show in a mood-based venue app
BLOCKED_TYPES: Set[str] = {
    "school", "university", "primary_school", "secondary_school",
    "hospital", "doctor", "dentist", "pharmacy",
    "bank", "police", "atm", "cemetery",
    "government", "courthouse", "fire_station", "mosque",
    "church", "temple", "place_of_worship",
    "warehouse", "factory", "industrial"
}


def is_place_allowed(place: Dict) -> bool:
    """
    Unified final filter:
    - Allow ALL cafes / coffee / restaurants explicitly
    - Block only real unwanted places (school, hospital, market, police, bank)
    - Do NOT block cafés with generic google types
    """

    name = (place.get("name") or "").lower()

    # --------------------------------------------
    # 1) COFFEE / CAFE FAST PASS → ASLA BLOKLANMAZ
    # --------------------------------------------
    coffee_keywords = [
        "cafe", "kahve", "coffee", "kafe", "café",
        "espresso", "latte", "arabica", "starbucks",
        "mackbear", "looq", "brew", "roastery"
    ]

    if any(kw in name for kw in coffee_keywords):
        return True   # bu mekan kesin kafe → direkt geç

    # --------------------------------------------
    # 2) İSİM-BAZLI KÖTÜ YER FİLTRESİ
    # --------------------------------------------
    blocked_keywords = [
        "market", "grocery", "bakkal", "supermarket",
        "okul", "school", "üniversite", "university",
        "fakülte", "faculty",
        "hastane", "hospital",
        "klinik", "clinic",
        "eczane", "pharmacy",
        "bank", "atm",
        "polis", "police",
        "cami", "mosque",
        "kilise", "church",
        "mezarlık", "cemetery",
        "veteriner", "veterinary",
        "government", "courthouse",
        "warehouse", "factory", "industrial"
    ]

    if any(bad in name for bad in blocked_keywords):
        return False

    # --------------------------------------------
    # 3) GOOGLE TYPES ALLOWED CHECK
    # --------------------------------------------
    google_info = place.get("google") or {}
    gtypes = {t.lower() for t in google_info.get("types", [])}

    # Eğer google types tamamen boşsa → yine kabul et
    # çünkü bazen Google place details veremiyor ama mekan cafe
    if not gtypes:
        return True

    # Eğer sadece generic türler varsa:
    if gtypes <= {"point_of_interest", "establishment"}:
        return True  # artık exclude etmiyoruz

    # Eğer allowed leisure types varsa → kabul
    if gtypes & ALLOWED_TYPES:
        return True

    return True  # fallback → çoğu mekan gelsin diye


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki koordinat arasındaki mesafeyi metre cinsinden hesaplar."""
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))


@router.get("/places/google-search", response_model=PlacesSearchResponse)
async def google_only_search(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(3.0, gt=0, le=30),
    limit: int = Query(20, ge=1, le=60),
    mood: Optional[str] = None,
    keyword: Optional[str] = None,
) -> PlacesSearchResponse:
    """
    Tamamen Google Places (Nearby Search + Details) kullanan dinamik arama endpoint'i.
    OSM veya tile veritabanına dokunmaz.
    """
    if not settings.GOOGLE_PLACES_API_KEY:
        raise HTTPException(status_code=503, detail="Google Places API key missing")

    try:
        client = get_google_places_client(settings)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=503, detail=str(e))

    radius_m = int(radius_km * 1000.0)
    # Collect more results for better ranking pool (up to 60 places)
    max_results = min(max(limit * 3, limit), 60)

    try:
        # Nearby Search (blocking çağrıyı thread'e atıyoruz)
        raw_results: List[dict] = await asyncio.to_thread(
            client.search_nearby_paginated,
            lat,
            lon,
            radius_m,
            keyword,
            max_results,
        )
    except GooglePlacesError as e:
        raise HTTPException(status_code=502, detail=f"Google NearbySearch error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google NearbySearch failed: {e}")

    if not raw_results:
        return PlacesSearchResponse(
            items=[],
            count=0,
            warming_up=False,
            tiles_checked=0,
            tiles_to_fetch=0,
        )

    # Normalize mood for ranking
    normalized_mood = normalize_mood(mood)

    # MindRoute business rule:
    # - Always DROP obviously irrelevant categories for a "going out" app:
    #   supermarkets, schools, hospitals, etc. (BLOCKED_TYPES).
    # - PREFER leisure venues (cafes, restaurants, parks, entertainment, culture)
    #   by boosting their base score (ALLOWED_TYPES), but do not hard-filter others.
    #   This keeps enough results in dense areas while still focusing on "places to go".

    # 1) Build base place structures with HARD block list and SOFT preference boost
    tmp_places: List[Dict] = []
    for r in raw_results:
        geometry = r.get("geometry", {}) or {}
        loc = geometry.get("location", {}) or {}
        g_lat = loc.get("lat")
        g_lon = loc.get("lng")
        if g_lat is None or g_lon is None:
            continue

        types = r.get("types") or []
        # Normalize types to lowercase for comparison
        tset = {t.lower() for t in types} if types else set()
        
        # 1) HARD BLOCK: skip completely if any blocked type is present
        if tset & BLOCKED_TYPES:
            continue
        
        # 2) Keep a flag for whether this is a "leisure" place we prefer
        is_leisure = bool(tset & ALLOWED_TYPES)
        
        distance_m = _haversine_m(lat, lon, g_lat, g_lon)
        rating = r.get("rating")
        user_ratings = r.get("user_ratings_total", 0)
        
        # Compute base score (distance + rating)
        rating_factor = (rating if rating is not None else 3.5) / 5.0
        distance_factor = max(0.0, 1.0 - (distance_m / 3000.0))
        base_score_value = 0.7 * rating_factor + 0.3 * distance_factor
        
        # 3) BOOST base_score if this is a leisure place
        if is_leisure:
            base_score_value += 0.15  # small but meaningful boost
            if base_score_value > 1.0:
                base_score_value = 1.0

        main_type = types[0] if types else None

        # Build place dict for mood scoring
        place_dict = {
            "name": r.get("name"),
            "type": main_type,
            "distance_m": distance_m,
            "google": {
                "rating": rating,
                "types": types,
            },
        }

        # Compute mood score if mood is provided
        mood_score_value = None
        mood_reason_text = None
        if normalized_mood:
            mood_score_value = compute_mood_score(place_dict, normalized_mood)
            mood_reason_text = build_mood_reason(place_dict, normalized_mood, mood_score_value)
        else:
            # If no mood, use base score as mood score
            mood_score_value = base_score_value

        # Extract photo URL from nearby search result if available
        from app.services.google.google_places_helper import extract_photo_from_place
        photo_url = extract_photo_from_place(r)
        
        # Store basic Google data (will be enriched later for top results)
        google_data = {
            "place_id": r.get("place_id"),
            "rating": rating,
            "user_ratings_total": user_ratings,
            "address": r.get("vicinity") or r.get("formatted_address") or "",
            "url": None,
            "opening_hours": None,
            "photos": [photo_url] if photo_url else None,
            "reviews": [],
            "types": types,
        }

        tmp_places.append(
            {
                "raw": r,
                "name": r.get("name"),
                "type": main_type,
                "coordinates": [g_lon, g_lat],
                "lat": g_lat,
                "lon": g_lon,
                "distance_m": distance_m,
                "score": round(base_score_value, 6),  # Base score (with leisure boost if applicable)
                "mood_score": round(mood_score_value, 6) if mood_score_value is not None else None,
                "mood_reason": mood_reason_text,
                "google": google_data,
                "is_leisure": is_leisure,  # Flag for debugging/monitoring
                "photo": photo_url,  # İlk fotoğraf URL'si
            }
        )

    if not tmp_places:
        return PlacesSearchResponse(
            items=[],
            count=0,
            warming_up=False,
            tiles_checked=0,
            tiles_to_fetch=0,
        )

    # 2) Sort by mood_score (or base score) and enrich top N with details
    # Use mood_score for ranking if available, otherwise fall back to base score
    sort_key = lambda x: (x.get("mood_score") or x.get("score") or 0.0)
    tmp_places.sort(key=sort_key, reverse=True)
    top_for_details = tmp_places[: min(len(tmp_places), min(limit, 20))]

    async def enrich_one(place_dict: dict) -> None:
        place_id = place_dict["raw"].get("place_id")
        if not place_id:
            return
        try:
            details = await asyncio.to_thread(client.get_details, place_id)
            osm_like_doc = {
                "name": place_dict.get("name"),
                "location": {
                    "coordinates": place_dict.get("coordinates", [place_dict["lon"], place_dict["lat"]])
                },
            }
            enrichment = enrich_place_with_google(osm_like_doc, details, client)
            if enrichment:
                # Tip bilgisini de ekle
                if "types" not in enrichment:
                    enrichment["types"] = place_dict["google"].get("types") or []
                place_dict["google"] = enrichment
        except GooglePlacesError as e:
            print(f"Google Details error for {place_id}: {e}")
        except Exception as e:
            print(f"Error enriching Google place {place_id}: {e}")

    await asyncio.gather(*(enrich_one(p) for p in top_for_details))

    # 3) Apply strict filtering: only keep places with allowed types
    # After enrichment, we have full google.types data, so we can filter properly
    filtered_places: List[Dict] = []
    for p in tmp_places:
        # Apply is_place_allowed filter
        if not is_place_allowed(p):
            continue
        
        # Must have mood_score to be included in recommendations
        if p.get("mood_score") is None:
            continue
        
        filtered_places.append(p)
    
    # 4) Rank by mood_score (or base score if no mood)
    # Use mood_score for ranking if available, otherwise fall back to base score
    sort_key = lambda x: (x.get("mood_score") or x.get("score") or 0.0)
    filtered_places.sort(key=sort_key, reverse=True)
    
    # Apply limit after ranking
    filtered_places = filtered_places[:limit]
    
    # Mark all filtered places as recommended (they passed the strict filter)
    for p in filtered_places:
        p["is_recommended"] = True

    # 5) Pydantic modellere dönüştür
    items: List[PlaceItem] = []
    for p in filtered_places:
        g_data = p.get("google") or {}

        reviews_models: List[GoogleReview] = []
        raw_reviews = g_data.get("reviews") or []
        for rev in raw_reviews[:3]:
            if isinstance(rev, dict):
                reviews_models.append(GoogleReview(**rev))

        google_obj = GooglePlaceInfo(
            place_id=g_data.get("place_id"),
            rating=g_data.get("rating"),
            user_ratings_total=g_data.get("user_ratings_total"),
            address=g_data.get("address"),
            url=g_data.get("url"),
            opening_hours=g_data.get("opening_hours"),
            photos=g_data.get("photos", [])[:5] if g_data.get("photos") else None,
            reviews=reviews_models or None,
            types=g_data.get("types"),
        )

        # Photo URL'ini al (enrichment'ten veya direkt place dict'inden)
        photo_url = None
        if google_obj.photos and len(google_obj.photos) > 0:
            photo_url = google_obj.photos[0]
        elif p.get("photo"):
            photo_url = p.get("photo")
        
        item = PlaceItem(
            id=g_data.get("place_id"),  # Add place_id as id
            name=p.get("name"),
            type=p.get("type"),
            address={"full": google_obj.address} if google_obj.address else None,
            coordinates=p.get("coordinates"),
            lat=p.get("lat"),
            lon=p.get("lon"),
            distance_m=p.get("distance_m"),
            score=p.get("score"),  # Base score
            google=google_obj,
            mood_score=p.get("mood_score"),
            mood_reason=p.get("mood_reason"),
            is_recommended=p.get("is_recommended", False),
            photo=photo_url,  # Fotoğraf URL'si
        )
        items.append(item)

    return PlacesSearchResponse(
        items=items,
        count=len(items),
        warming_up=False,
        tiles_checked=0,
        tiles_to_fetch=0,
    )


