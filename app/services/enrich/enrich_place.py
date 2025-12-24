async def enrich_place_data(osm_place, google_place, yelp_place, wiki_photos):
    # Google foto URL'lerini çıkar
    google_photos_raw = google_place.get("photos", [])
    google_photo_urls = []
    if google_photos_raw:
        for photo in google_photos_raw:
            if isinstance(photo, str):
                google_photo_urls.append(photo)
            elif isinstance(photo, dict) and photo.get("photo_reference"):
                from app.services.google.google_places_helper import get_photo_url
                url = get_photo_url(photo.get("photo_reference"))
                if url:
                    google_photo_urls.append(url)

    # Yelp / Google / Wiki foto öncelik sırası: Yelp > Google > Wiki
    photos = []
    if yelp_place and yelp_place.get("photos"):
        photos.extend(yelp_place.get("photos") or [])
    if google_photo_urls:
        photos.extend(google_photo_urls)
    if wiki_photos:
        photos.extend(wiki_photos)
    # unique sıra korunsun
    if photos:
        photos = list(dict.fromkeys(photos))
    primary_photo = photos[0] if photos else None

    # Rating önceliği: Yelp varsa onu, yoksa Google
    rating = None
    rating_source = None
    if yelp_place and yelp_place.get("rating") is not None:
        rating = yelp_place.get("rating")
        rating_source = "yelp"
    elif google_place.get("rating") is not None:
        rating = google_place.get("rating")
        rating_source = "google"

    enriched = {
        "name": google_place.get("name") or yelp_place.get("name") or osm_place["name"],
        "lat": osm_place["lat"],
        "lon": osm_place["lon"],
        "types": google_place.get("types", []),
        "rating": rating,
        "rating_source": rating_source,
        "google_rating": google_place.get("rating"),
        "google_user_ratings": google_place.get("user_ratings_total"),
        "google_photos": google_photo_urls,  # URL array'i
        "google_url": google_place.get("url"),
        "yelp_rating": yelp_place.get("rating") if yelp_place else None,
        "yelp_review_count": yelp_place.get("review_count") if yelp_place else None,
        "yelp_photos": yelp_place.get("photos") if yelp_place else [],
        "yelp_categories": yelp_place.get("categories") if yelp_place else [],
        "yelp_price": yelp_place.get("price") if yelp_place else None,
        "wiki_photos": wiki_photos,
        "photos": photos,
        "photo": primary_photo,  # İlk fotoğraf URL'si (Yelp > Google > Wiki)
        "source": ["osm", "google", "yelp", "wikidata"],
    }

    return enriched


