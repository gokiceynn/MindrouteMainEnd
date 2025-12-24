import os


def get_photo_url(photo_reference: str, max_width: int = 800):
    """
    Google Places photo reference'inden fotoğraf URL'si oluşturur.
    
    Args:
        photo_reference: Google Places API'den gelen photo_reference
        max_width: Fotoğrafın maksimum genişliği (piksel)
    
    Returns:
        Fotoğraf URL'si veya None
    """
    if not photo_reference:
        return None
    api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return None
    return (
        f"https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth={max_width}"
        f"&photo_reference={photo_reference}"
        f"&key={api_key}"
    )


def extract_photo_from_place(place: dict) -> str | None:
    """
    Place dict'inden ilk fotoğraf URL'sini çıkarır.
    
    Args:
        place: Google Places API response'unun result kısmı veya nearby search result'u
    
    Returns:
        Fotoğraf URL'si veya None
    """
    place_photos = place.get("photos")
    if place_photos and len(place_photos) > 0:
        photo_ref = place_photos[0].get("photo_reference")
        photo_url = get_photo_url(photo_ref)
        return photo_url
    return None

