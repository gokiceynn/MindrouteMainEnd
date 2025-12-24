import os, time, json
from typing import Dict, List, Tuple
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from pymongo import ASCENDING
from ..db import get_places

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

DEFAULTS = {
    "amenities": "restaurant,cafe,fast_food,bar,library,school,university,place_of_worship",
    "leisure":   "park,garden,fitness_centre",
    "tourism":   "museum,hotel,hostel,information,viewpoint",
    "shop":      "supermarket,bakery,chemist,convenience,clothes,books",
    "healthcare":"clinic,doctor,pharmacy",
    "sport":     "fitness,swimming,tennis,football",
}

def build_circle_query(lat: float, lon: float, radius_m: int, selects: Dict[str,str]) -> str:
    parts = []
    for key, csv in selects.items():
        values = [v.strip() for v in csv.split(",") if v.strip()]
        for val in values:
            parts.append(f'  nwr["{key}"="{val}"](around:{radius_m},{lat},{lon});')
    body = "(\n" + "\n".join(parts) + "\n);\n"
    # Timeout'u 120 saniyeye çıkar (504 hatası için)
    return f"[out:json][timeout:120];\n{body}out center;"

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.6, max=5))
def _call_overpass(query: str) -> dict:
    last_exc = None
    for url in ENDPOINTS:
        try:
            # Timeout'u 130 saniyeye çıkar (query timeout 120 + buffer)
            with httpx.Client(timeout=130.0, headers={"User-Agent": "mindroute-live/1.0"}) as c:
                r = c.post(url, data=query)
                
                # 504 Gateway Timeout için özel işlem
                if r.status_code == 504:
                    print(f"Overpass {url} returned 504 Gateway Timeout, trying next endpoint...")
                    last_exc = Exception(f"504 Gateway Timeout from {url}")
                    continue
                
                r.raise_for_status()
                return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 504:
                print(f"Overpass {url} returned 504 Gateway Timeout, trying next endpoint...")
                last_exc = e
                continue
            last_exc = e
            continue
        except Exception as e:
            last_exc = e
            continue
    raise last_exc

def _doc_from_el(el: dict) -> dict:
    tags = el.get("tags", {}) or {}
    name = tags.get("name")
    place_type = None
    for k in ("amenity","leisure","tourism","shop","healthcare","sport"):
        if k in tags:
            place_type = tags[k]; break
    lat = el.get("lat") or (el.get("center") or {}).get("lat")
    lon = el.get("lon") or (el.get("center") or {}).get("lon")
    if lat is None or lon is None:
        return None
    tags_list = sorted({f"{k}={v}" for k,v in tags.items() if v})
    return {
        "name": name,
        "type": place_type,
        "location": {"type":"Point","coordinates":[float(lon), float(lat)]},
        "address": tags.get("addr:full") or tags.get("addr:street"),
        "tags": tags,
        "tags_list": tags_list,
        "sources": {"osm_id": el.get("id"), "osm_type": el.get("type")},
        "source": "osm",
    }

def upsert_many(elements: List[dict]) -> Tuple[int,int,int]:
    coll = get_places()
    coll.create_index([("location", "2dsphere")])
    coll.create_index([("name","text"),("type","text"),("address","text"),("tags_list","text")])
    ins=upd=skip=0
    for el in elements:
        doc = _doc_from_el(el)
        if not doc: 
            skip += 1; 
            continue
        filt = {"sources.osm_id": doc["sources"]["osm_id"], "sources.osm_type": doc["sources"]["osm_type"]}
        res = coll.find_one_and_update(filt, {"$set": doc}, upsert=True, return_document=True)
        if res is None: ins += 1
        else: upd += 1
    return ins, upd, skip

def live_fetch_circle(lat: float, lon: float, radius_m: int, limit: int=1000, selects: Dict[str,str]=None) -> dict:
    selects = selects or DEFAULTS
    q = build_circle_query(lat, lon, radius_m, selects)
    data = _call_overpass(q)
    elements = data.get("elements", [])[:limit]
    ins, upd, skip = upsert_many(elements)
    return {"inserted": ins, "updated": upd, "skipped": skip, "fetched": len(elements)}
