"""
Mood bazlı mekan öneri yardımcıları.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.models import GooglePlaceInfo

MOOD_PREFERENCES: Dict[str, Dict[str, List[str]]] = {
    "mutlu": {
        "boost_types": ["cafe", "restaurant", "park", "bar", "shopping_mall", "cinema"],
        "avoid_types": [],
    },
    "üzgün": {
        "boost_types": ["park", "garden", "museum", "library", "place_of_worship"],
        "avoid_types": ["bar"],
    },
    "stresli": {
        "boost_types": ["park", "spa", "garden", "cafe"],
        "avoid_types": ["night_club"],
    },
    "sıkılmış": {
        "boost_types": ["cinema", "shopping_mall", "amusement_park", "museum"],
        "avoid_types": [],
    },
    "yalnız": {
        "boost_types": ["library", "park", "cafe"],
        "avoid_types": [],
    },
}

MOOD_REASON_HINTS: Dict[str, str] = {
    "mutlu": "enerjini yüksek tutacak sosyal bir ortam sunuyor",
    "üzgün": "sakin atmosferiyle moralini toparlamana yardımcı olur",
    "stresli": "rahatlaman için dingin bir kaçamak sağlar",
    "sıkılmış": "yeni bir deneyimle sıkıntını dağıtabilir",
    "yalnız": "sessiz ama sıcak bir ortamda zaman geçirmeni sağlar",
}


def normalize_mood(mood: Optional[str]) -> Optional[str]:
    """Geçerli mood'u normalize eder, yoksa None döndürür."""
    if not mood:
        return None
    mood_key = mood.strip().lower()
    return mood_key if mood_key in MOOD_PREFERENCES else None


def get_place_types(place: Dict) -> List[str]:
    """OSM tipi, tag'ler ve Google tiplerini tek listede toplar."""
    types: List[str] = []

    osm_type = place.get("type")
    if isinstance(osm_type, str):
        types.append(osm_type.lower())

    tags = place.get("tags") or []
    if isinstance(tags, list):
        types.extend([str(tag).lower() for tag in tags if isinstance(tag, str)])

    google_obj = place.get("google")
    if isinstance(google_obj, GooglePlaceInfo):
        google_types = getattr(google_obj, "types", None) or []
    elif isinstance(google_obj, dict):
        google_types = google_obj.get("types") or []
    else:
        google_types = []

    types.extend([str(t).lower() for t in google_types if isinstance(t, str)])

    # Benzersiz hale getir
    seen = set()
    unique_types = []
    for t in types:
        if t not in seen:
            seen.add(t)
            unique_types.append(t)
    return unique_types


def base_score(place: Dict) -> float:
    """Google rating ve mesafeyi [0,1] aralığında baz skor olarak birleştirir."""
    google_obj = place.get("google")
    rating: Optional[float] = None
    if isinstance(google_obj, GooglePlaceInfo):
        rating = google_obj.rating
    elif isinstance(google_obj, dict):
        rating = google_obj.get("rating")

    rating_factor = (rating if rating is not None else 3.5) / 5.0
    distance_m = place.get("distance_m") or 0.0
    distance_factor = max(0.0, 1.0 - (distance_m / 3000.0))

    return max(0.0, min(1.0, 0.7 * rating_factor + 0.3 * distance_factor))


def mood_type_boost(types: List[str], mood: str) -> float:
    """Mood tercihine göre tip bazlı boost/penalty uygular."""
    pref = MOOD_PREFERENCES.get(mood, {})
    boost_types = set(pref.get("boost_types", []))
    avoid_types = set(pref.get("avoid_types", []))

    boost = 0.0
    if boost_types and boost_types.intersection(types):
        boost += 0.2
    if avoid_types and avoid_types.intersection(types):
        boost -= 0.2

    return boost


def compute_mood_score(place: Dict, mood: str) -> float:
    """Baz skor ile tip boost'unu birleştirerek mood skorunu hesaplar."""
    types = get_place_types(place)
    score = base_score(place) + mood_type_boost(types, mood)
    return max(0.0, min(1.0, score))


def build_mood_reason(place: Dict, mood: str, score: float) -> str:
    """Mekan + mood ilişkisini anlatan kısa Türkçe açıklama üretir."""
    name = place.get("name") or "Bu mekan"
    place_type = place.get("type") or "mekan"
    distance_m = place.get("distance_m")
    google_obj = place.get("google")
    rating = None
    if isinstance(google_obj, GooglePlaceInfo):
        rating = google_obj.rating
    elif isinstance(google_obj, dict):
        rating = google_obj.get("rating")

    proximity = "yürüme mesafesinde" if (distance_m is not None and distance_m < 800) else "kolay ulaşılabilir"
    rating_text = "yüksek puanlı" if rating and rating >= 4.0 else "rahat"
    mood_hint = MOOD_REASON_HINTS.get(mood, "ruh haline iyi gelebilir")

    return f"{name}, {proximity} {rating_text} bir {place_type} olduğu için {mood_hint}."

