from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict, Any
from pymongo import GEOSPHERE
from app.database import get_places_collection
from app.mood_map import get_mood_types, is_valid_mood

router = APIRouter(prefix="/places", tags=["Places"])


@router.get("/search")
async def search_places(
    mood: str = Query(..., description="Kullanıcının ruh hali"),
    lat: float = Query(..., description="Enlem"),
    lon: float = Query(..., description="Boylam"),
    radius_km: float = Query(3.0, description="Arama yarıçapı (km)"),
    limit: int = Query(20, description="Maksimum sonuç sayısı")
) -> Dict[str, Any]:
    """
    Kullanıcının ruh haline göre yakındaki mekanları arar.
    
    Args:
        mood: Kullanıcının ruh hali (stresli, mutlu, huzurlu, yalnız, enerjik)
        lat: Enlem koordinatı
        lon: Boylam koordinatı
        radius_km: Arama yarıçapı kilometre cinsinden
        limit: Maksimum dönecek sonuç sayısı
        
    Returns:
        Dict: Arama sonuçları
    """
    # Mood'u normalize et ve kontrol et
    mood_normalized = mood.lower()
    if not is_valid_mood(mood_normalized):
        raise HTTPException(
            status_code=400,
            detail=f"Geçersiz mood: {mood}. Geçerli mood'lar: stresli, mutlu, huzurlu, yalnız, enerjik"
        )
    
    # Mood'a uygun mekan türlerini al
    mood_types = get_mood_types(mood_normalized)
    
    # Koordinat kontrolü
    if not (-90 <= lat <= 90):
        raise HTTPException(status_code=422, detail="Enlem -90 ile 90 arasında olmalı")
    if not (-180 <= lon <= 180):
        raise HTTPException(status_code=422, detail="Boylam -180 ile 180 arasında olmalı")
    
    # Radius kontrolü
    if radius_km <= 0 or radius_km > 50:
        raise HTTPException(status_code=422, detail="Yarıçap 0-50 km arasında olmalı")
    
    # Limit kontrolü
    if limit <= 0 or limit > 100:
        raise HTTPException(status_code=422, detail="Limit 1-100 arasında olmalı")
    
    try:
        places_collection = get_places_collection()
        if not places_collection:
            raise HTTPException(status_code=500, detail="Veritabanı bağlantısı kurulamadı")
        
        # MongoDB aggregate pipeline
        pipeline = [
            {
                "$geoNear": {
                    "near": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    },
                    "distanceField": "distance_m",
                    "maxDistance": radius_km * 1000,  # metre cinsinden
                    "spherical": True,
                    "query": {
                        "type": {"$in": mood_types}
                    }
                }
            },
            {
                "$addFields": {
                    "score": {
                        "$add": [
                            {
                                "$multiply": [
                                    0.6,
                                    {
                                        "$divide": [
                                            1,
                                            {
                                                "$add": [
                                                    1,
                                                    {
                                                        "$divide": [
                                                            "$distance_m",
                                                            1000
                                                        ]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "$multiply": [
                                    0.4,
                                    {
                                        "$cond": [
                                            {"$in": ["$type", mood_types]},
                                            1,
                                            0
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "name": 1,
                    "type": 1,
                    "distance_m": 1,
                    "location.coordinates": 1,
                    "score": 1
                }
            },
            {
                "$sort": {
                    "score": -1,
                    "distance_m": 1
                }
            },
            {
                "$limit": limit
            }
        ]
        
        # Sorguyu çalıştır
        results = await places_collection.aggregate(pipeline).to_list(length=limit)
        
        return {
            "mood": mood,
            "location": {"lat": lat, "lon": lon},
            "radius_km": radius_km,
            "count": len(results),
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Arama sırasında hata oluştu: {str(e)}")
