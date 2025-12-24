import httpx

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

OSM_FILTERS = [
    ("amenity", "cafe"),
    ("amenity", "restaurant"),
    ("amenity", "fast_food"),
    ("amenity", "bar"),
    ("tourism", "museum"),
    ("tourism", "gallery"),
    ("tourism", "attraction"),
    ("leisure", "park"),
    ("leisure", "garden"),
    ("amenity", "library"),
]


def build_overpass_query(lat, lon, radius):
    blocks = []
    for key, value in OSM_FILTERS:
        blocks.append(f'node["{key}"="{value}"](around:{radius},{lat},{lon});')

    query = f"""
    [out:json];
    (
        {' '.join(blocks)}
    );
    out center;
    """

    return query


async def fetch_overpass_places(lat, lon, radius):
    query = build_overpass_query(lat, lon, radius)
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(OVERPASS_URL, data={"data": query})
        if r.status_code != 200:
            print("Overpass error:", r.text)
            return []
        data = r.json()

        results = []
        for e in data.get("elements", []):
            name = e.get("tags", {}).get("name")
            if not name:
                continue

            results.append(
                {
                    "osm_id": e.get("id"),
                    "name": name,
                    "lat": e.get("lat") or e.get("center", {}).get("lat"),
                    "lon": e.get("lon") or e.get("center", {}).get("lon"),
                    "raw_osm": e,
                }
            )
        return results


