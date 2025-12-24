from app.routes.places import fetch_rich


async def fetch_places(lat, lon, radius):
    return await fetch_rich(lat=lat, lon=lon, radius=radius)

