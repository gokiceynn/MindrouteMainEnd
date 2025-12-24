import os
import asyncio

import httpx


def _yelp_headers() -> dict:
    key = os.getenv("YELP_API_KEY")
    if not key:
        return {}
    key = key.strip()
    return {"Authorization": f"Bearer {key}"}


async def yelp_search_by_coords(lat, lon, term: str = "", radius: int = 150):
    headers = _yelp_headers()
    if not headers:
        return []

    url = "https://api.yelp.com/v3/businesses/search"
    params = {
        "latitude": lat,
        "longitude": lon,
        "radius": radius,
        "term": term or "cafe",
        "categories": "cafes,coffee,restaurants,food",
        "limit": 5,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        for attempt in (1, 2):  # 2 deneme: normal + 429 durumunda bekleyerek
            r = await client.get(url, params=params, headers=headers)
            if r.status_code == 200:
                return r.json().get("businesses", [])
            if r.status_code == 429 and attempt == 1:
                print("Yelp error 429: rate limited, retrying...")
                await asyncio.sleep(1.0)
                continue
            print("Yelp error:", r.status_code, r.text)
            return []


async def yelp_business_details(business_id: str):
    headers = _yelp_headers()
    if not headers:
        return None

    url = f"https://api.yelp.com/v3/businesses/{business_id}"
    async with httpx.AsyncClient(timeout=10) as client:
        for attempt in (1, 2):
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429 and attempt == 1:
                print("Yelp error 429: rate limited, retrying...")
                await asyncio.sleep(1.0)
                continue
            print("Yelp error:", r.status_code, r.text)
            return None


