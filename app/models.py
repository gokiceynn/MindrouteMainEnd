"""
Pydantic models for API responses.
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class GoogleReview(BaseModel):
    """Google review model."""
    author_name: Optional[str] = None
    rating: Optional[float] = None
    text: Optional[str] = None
    time: Optional[int] = None
    relative_time_description: Optional[str] = None


class GooglePlaceInfo(BaseModel):
    """Google Places enrichment data."""
    place_id: Optional[str] = None
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    address: Optional[str] = None
    url: Optional[str] = None
    opening_hours: Optional[dict] = None
    photos: Optional[List[str]] = None
    reviews: Optional[List[GoogleReview]] = None
    types: Optional[List[str]] = None


class FoursquareDetails(BaseModel):
    """Foursquare Places enrichment data."""
    fsq_id: Optional[str] = None
    rating: Optional[float] = None
    photos: Optional[List[str]] = None
    categories: Optional[List[dict]] = None
    url: Optional[str] = None


class PlaceItem(BaseModel):
    """Single place item in search response."""
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    address: Optional[dict] = None
    coordinates: Optional[List[float]] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    distance_m: Optional[float] = None
    score: Optional[float] = None
    google: Optional[GooglePlaceInfo] = None
    foursquare: Optional[FoursquareDetails] = None
    mood_score: Optional[float] = None
    mood_reason: Optional[str] = None
    is_recommended: bool = False
    photo: Optional[str] = None  # birincil fotoğraf (Yelp > Google > Wiki)
    photos: Optional[List[str]] = None  # tüm foto URL'leri
    rating: Optional[float] = None  # Yelp öncelikli
    rating_source: Optional[str] = None  # "yelp" veya "google"


class PlacesSearchResponse(BaseModel):
    """Response model for /places/search endpoint."""
    items: List[PlaceItem]
    count: int
    warming_up: Optional[bool] = False
    tiles_checked: Optional[int] = None
    tiles_to_fetch: Optional[int] = None


class MoodAnalyzeRequest(BaseModel):
    text: Optional[str] = None
    audio_base64: Optional[str] = None


class MoodAnalyzeResult(BaseModel):
    mood: str
    confidence: float
    source: str  # "text" or "audio"


class MoodAnalyzeResponse(BaseModel):
    ok: bool
    result: MoodAnalyzeResult


class MoodTextRequest(BaseModel):
    """MiniAssistant için mood-text endpoint request modeli."""
    message: str
    history: Optional[List[dict]] = []
    source: Optional[str] = "default"


class MoodTextResponse(BaseModel):
    """MiniAssistant için mood-text endpoint response modeli."""
    mood_label: str
    emotion: str
    reply: str
