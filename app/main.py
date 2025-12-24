from fastapi import FastAPI, Query, HTTPException, BackgroundTasks, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from math import radians, cos, sin, asin, sqrt, log
from typing import Optional, List, Dict
import os, time
import hashlib
from pydantic import BaseModel

from app.db import get_places, get_db
from app.models import PlaceItem, PlacesSearchResponse, GooglePlaceInfo, GoogleReview
from app.services.mood_recommender import (
    compute_mood_score,
    build_mood_reason,
    normalize_mood,
)
from app.routes.google_search import router as google_search_router, google_only_search
from app.routes.mood import router as mood_router
from app.routes.places import router as places_router
from app.routes.emotion import router as emotion_router
from app.services.emotion.emotion_service import EmotionService
from app.config import settings

load_dotenv()

app = FastAPI(title="MindRoute API")
emotion_service = EmotionService()

# CORS middleware'i router'lardan ÖNCE ekle
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'ları ekle
app.include_router(mood_router)  # /mood/analyze endpoint'i için
app.include_router(emotion_router, prefix="/api")  # /api/speech-emotion, /api/video-emotion için
app.include_router(google_search_router)
app.include_router(places_router)

# İndeksler (varsa tekrar oluşturmaz)
places = get_places()
try:
    places.create_index([("location", "2dsphere")])
    places.create_index([("sources.osm_id", 1), ("sources.osm_type", 1)], unique=True, sparse=True)
    places.create_index([("name", "text"), ("tags", "text")])
except Exception:
    pass  # Index zaten varsa hata verme

@app.get("/health")
def health():
    db = get_db()
    try:
        db.command("ping")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"mongo ping failed: {e}")
    places = get_places()
    return {
        "ok": True,
        "db": db.name,
        "places_count": places.estimated_document_count()
    }

@app.get("/places/search")
async def places_search(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(2.0, gt=0, le=30),
    limit: int = Query(20, ge=1, le=100),
    mood: Optional[str] = None,
    q: Optional[str] = None,
    all: bool = False,
    city: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
):
    """
    Backward-compatible endpoint adı korunarak tamamen Google Places tabanlı arama yapılır.
    OSM / Overpass / tile tabanlı mantık artık kullanılmıyor.
    """
    try:
        # q parametresini Google keyword olarak kullan
        keyword = q
        resp: PlacesSearchResponse = await google_only_search(
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            limit=limit,
            mood=mood,
            keyword=keyword,
        )
        # FastAPI zaten model instance'ını JSON'a çevirir; dict() ile de dönebiliriz
        return resp
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)
