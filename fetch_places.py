import os
import time
import requests
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv

print(">>> file loaded")  # debug log


# ====== AYARLAR ======
CENTER_LAT = 41.0369   # Taksim
CENTER_LON = 28.9850
RADIUS_M   = 1500
TIMEOUT_S  = 60

AMENITY_REGEX = r"^(cafe|restaurant|fast_food|pub|bar|library)$"
LEISURE_REGEX = r"^(park|garden|forest|playground)$"
TOURISM_REGEX = r"^(museum|viewpoint)$"

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]

# ====== MONGO ======
load_dotenv()
MONGO_URL = os.getenv("MONGO_URL", "mongodb://127.0.0.1:27017")
client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=4000)
db = client["mindroute"]
places = db["places"]

def ensure_indexes():
    places.create_index([("location", "2dsphere")])
    places.create_index([("name", "text"), ("tags", "text")])
    places.create_index([("sources.osm_id", ASCENDING)], unique=True, sparse=True)

def build_query(lat: float, lon: float, r: int) -> str:
    return f"""
[out:json][timeout:{TIMEOUT_S}];
(
  node["amenity"~"{AMENITY_REGEX}"](around:{r},{lat},{lon});
  way["amenity"~"{AMENITY_REGEX}"](around:{r},{lat},{lon});
  relation["amenity"~"{AMENITY_REGEX}"](around:{r},{lat},{lon});

  node["leisure"~"{LEISURE_REGEX}"](around:{r},{lat},{lon});
  way["leisure"~"{LEISURE_REGEX}"](around:{r},{lat},{lon});
  relation["leisure"~"{LEISURE_REGEX}"](around:{r},{lat},{lon});

  node["tourism"~"{TOURISM_REGEX}"](around:{r},{lat},{lon});
  way["tourism"~"{TOURISM_REGEX}"](around:{r},{lat},{lon});
  relation["tourism"~"{TOURISM_REGEX}"](around:{r},{lat},{lon});
);
out center;
"""

def fetch_overpass(query: str) -> dict:
    last_err = None
    for attempt in range(1, 4):
        for base in OVERPASS_URLS:
            try:
                print(f"[{attempt}] Overpass → {base}")
                resp = requests.post(base, data={"data": query}, timeout=TIMEOUT_S)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_err = e
                print(f"   uyarı: {type(e).__name__}: {e}")
        time.sleep(2 * attempt)
    raise RuntimeError(f"Overpass erişimi başarısız: {last_err}")

def upsert_elements(data: dict):
    added = updated = skipped = 0
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name")
        place_type = tags.get("amenity") or tags.get("leisure") or tags.get("tourism")

        lat = el.get("lat")
        lon = el.get("lon")
        if (lat is None or lon is None) and "center" in el:
            lat = el["center"].get("lat")
            lon = el["center"].get("lon")

        if not (name and place_type and lat and lon):
            skipped += 1
            continue

        doc = {
            "name": name,
            "type": place_type,
            "location": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "address": tags.get("addr:full"),
            "tags": sorted(set(tags.keys())),
            "sources": {"osm_id": el.get("id"), "osm_type": el.get("type")},
            "source": "osm",
        }

        res = places.update_one(
            {"sources.osm_id": el.get("id")},
            {
                "$set": doc,
                "$setOnInsert": {"created_at": __import__("datetime").datetime.utcnow()},
                "$currentDate": {"updated_at": True},
            },
            upsert=True,
        )

        if res.matched_count == 0 and res.upserted_id is not None:
            added += 1
        else:
            updated += 1

    print(f"✅ İşlem bitti → eklendi: {added}, güncellendi: {updated}, atlandı: {skipped}")
def main():
    try:
        ensure_indexes()
    except Exception as e:
        print("Index hatası:", e)

    q = build_query(CENTER_LAT, CENTER_LON, RADIUS_M)
    data = fetch_overpass(q)
    upsert_elements(data)


if __name__ == "__main__":
    print(">>> running fetch_places.py")  # debug log
    main()



 