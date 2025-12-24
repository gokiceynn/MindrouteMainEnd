import math, os, time
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Dict
from ..db import get_tiles

# Optional fetcher import
try:
    from . import fetcher
    _FETCHER_AVAILABLE = True
except ImportError:
    _FETCHER_AVAILABLE = False

TILE_SIZE_M = int(os.getenv("TILE_SIZE_M", "1000"))
TILE_TTL_DAYS = int(os.getenv("TILE_TTL_DAYS", "30"))

def meters_to_deg_lat(m: float) -> float:
    return m / 111320.0

def meters_to_deg_lon(m: float, lat: float) -> float:
    return m / (111320.0 * max(0.1, math.cos(math.radians(lat))))

def tile_bounds_for_circle(lat: float, lon: float, radius_km: float) -> List[Tuple[float,float,float,float]]:
    """Çemberi kapsayan bbox → 1km kare karolara böl."""
    r_m = radius_km*1000.0
    dlat = meters_to_deg_lat(r_m)
    dlon = meters_to_deg_lon(r_m, lat)
    south, north = lat - dlat, lat + dlat
    west, east   = lon - dlon, lon + dlon

    step_lat = meters_to_deg_lat(TILE_SIZE_M)
    # grid için enlem ortalamasıyla lon adımı
    step_lon = meters_to_deg_lon(TILE_SIZE_M, lat)

    tiles = []
    y=south
    while y < north:
        x=west
        while x < east:
            s,w,n,e = y, x, min(y+step_lat, north), min(x+step_lon, east)
            tiles.append((s,w,n,e))
            x += step_lon
        y += step_lat
    return tiles

def now_utc():
    return datetime.now(timezone.utc)

def is_stale(last) -> bool:
    """last_fetched_at None ise veya TTL'den eskiyse True döndür."""
    if not last:
        return True
    # MongoDB'den gelen datetime objesi olabilir veya None
    if isinstance(last, datetime):
        # MongoDB'den gelen datetime timezone-naive olabilir, UTC olarak kabul et
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return now_utc() - last > timedelta(days=TILE_TTL_DAYS)
    return True  # Bilinmeyen tip -> stale kabul et

def ensure_tiles_metadata(tiles_bboxes: List[Tuple[float,float,float,float]]) -> List[Dict]:
    """tiles koleksiyonunda doküman oluştur/oku."""
    coll = get_tiles()
    result=[]
    for (s,w,n,e) in tiles_bboxes:
        _id = f"{round(s,5)},{round(w,5)},{round(n,5)},{round(e,5)}"
        doc = coll.find_one({"_id": _id})
        if not doc:
            doc = {
                "_id": _id,
                "bbox": {"south":s,"west":w,"north":n,"east":e},
                "last_fetched_at": None,
                "status": "never",   # never|ok|fetching|error
                "provider": "OSM",
                "fetch_count": 0
            }
            coll.insert_one(doc)
        result.append(doc)
    return result

def mark_fetching(tile_id: str):
    coll = get_tiles()
    coll.update_one({"_id": tile_id}, {"$set": {"status":"fetching"}})

def mark_fetched(tile_id: str, ok: bool):
    coll = get_tiles()
    coll.update_one(
        {"_id": tile_id},
        {"$set": {"status": "ok" if ok else "error", "last_fetched_at": now_utc()}, "$inc": {"fetch_count": 1}}
    )

def schedule_fetch_for_tiles(tiles_docs: List[Dict], sleep_ms: int = 600):
    """Arkaplanda sırayla fetch_places.py çağır; non-blocking iş tetikleyici fetcher.run_bbox kullan."""
    if not _FETCHER_AVAILABLE:
        print("Warning: fetcher module not available, skipping tile fetch scheduling")
        return
    for doc in tiles_docs:
        tile_id = doc["_id"]
        bbox = doc["bbox"]
        mark_fetching(tile_id)
        fetcher.run_bbox_async(bbox["south"], bbox["west"], bbox["north"], bbox["east"], tile_id=tile_id, sleep_ms=sleep_ms)
