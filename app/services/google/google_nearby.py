import httpx
import os

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")


async def google_nearby(name: str, lat: float, lon: float):
    """
    Google Places Text Search → Place Details → Foto, rating, types döndürür.
    """
    text_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    detail_url = "https://maps.googleapis.com/maps/api/place/details/json"

    params = {
        "query": name,
        "location": f"{lat},{lon}",
        "radius": 200,
        "key": GOOGLE_PLACES_API_KEY
    }

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(text_url, params=params)
        data = r.json()

        if not data.get("results"):
            return None

        place_id = data["results"][0]["place_id"]

        r2 = await client.get(detail_url, params={
            "place_id": place_id,
            "fields": "name,rating,user_ratings_total,types,photos,url",
            "key": GOOGLE_PLACES_API_KEY
        })
        detail = r2.json()
        return detail.get("result")

