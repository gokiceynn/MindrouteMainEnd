"""
Google Places API entegrasyonu servisi.
Mekanlar için fotoğraf, rating ve review bilgilerini getirir.
"""
import asyncio
import time
from typing import Optional, List
import requests
from app.models import PlaceItem


class GooglePlacesError(Exception):
    """Raised when Google Places API returns an error."""


class GooglePlacesClient:
    BASE_NEARBY = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    BASE_DETAILS = "https://maps.googleapis.com/maps/api/place/details/json"
    BASE_PHOTO = "https://maps.googleapis.com/maps/api/place/photo"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Google Places API key is missing.")
        self.api_key = api_key

    def search_nearby(self, lat: float, lon: float, radius_m: int, keyword: Optional[str] = None) -> dict:
        """
        Tek sayfalık Google Nearby Search çağrısı.
        Legacy kullanım için tutuluyor.
        """
        params = {
            "location": f"{lat},{lon}",
            "radius": radius_m,
            "key": self.api_key,
        }
        if keyword:
            params["keyword"] = keyword

        response = requests.get(self.BASE_NEARBY, params=params, timeout=20)
        data = response.json()

        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            raise GooglePlacesError(
                f"Nearby Search Error: {data.get('status')} - {data.get('error_message')}"
            )

        return data

    def search_nearby_paginated(
        self,
        lat: float,
        lon: float,
        radius_m: int,
        keyword: Optional[str] = None,
        max_results: int = 60,
    ) -> List[dict]:
        """
        Google Places Nearby Search API ile sayfalı arama yapar.
        Google maksimum 3 sayfa döndürebilir (her sayfada ~20 sonuç = ~60 sonuç).

        max_results'e kadar result toplar, next_page_token'ları takip eder.
        """
        results: List[dict] = []
        page_token: Optional[str] = None
        pages_fetched = 0
        max_pages = 3  # Google Places API maksimum 3 sayfa döndürebilir

        while len(results) < max_results and pages_fetched < max_pages:
            params = {
                "location": f"{lat},{lon}",
                "radius": radius_m,
                "key": self.api_key,
            }
            if keyword:
                params["keyword"] = keyword
            if page_token:
                params["pagetoken"] = page_token

            response = requests.get(self.BASE_NEARBY, params=params, timeout=25)
            data = response.json()

            status = data.get("status")
            if status not in ("OK", "ZERO_RESULTS"):
                # Hata durumunda logla ve döngüyü kır
                print(f"Google NearbySearch error: {status} - {data.get('error_message')}")
                break

            page_results = data.get("results", []) or []
            results.extend(page_results)
            pages_fetched += 1
            
            print(f"DEBUG: Fetched page {pages_fetched}, got {len(page_results)} results, total: {len(results)}")

            if len(results) >= max_results:
                break

            page_token = data.get("next_page_token")
            if not page_token:
                print(f"DEBUG: No more pages available (fetched {pages_fetched} pages)")
                break

            # Google, next_page_token için kısa bir gecikme istiyor
            time.sleep(2.0)

        print(f"DEBUG: Total results fetched: {len(results)}")
        return results[:max_results]
    
    def search_text(
        self,
        query: str,
        lat: float,
        lon: float,
        radius_m: int = 5000,
        max_results: int = 20,
    ) -> List[dict]:
        """
        Google Places Text Search API kullanarak arama yapar.
        Nearby Search'e ek olarak daha fazla sonuç bulmak için kullanılabilir.
        """
        BASE_TEXT_SEARCH = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        
        results: List[dict] = []
        page_token: Optional[str] = None
        pages_fetched = 0
        max_pages = 3  # Google maksimum 3 sayfa döndürebilir

        while len(results) < max_results and pages_fetched < max_pages:
            params = {
                "query": query,
                "location": f"{lat},{lon}",
                "radius": radius_m,
                "key": self.api_key,
            }
            if page_token:
                params["pagetoken"] = page_token

            response = requests.get(BASE_TEXT_SEARCH, params=params, timeout=25)
            data = response.json()

            status = data.get("status")
            if status not in ("OK", "ZERO_RESULTS"):
                print(f"Google TextSearch error: {status} - {data.get('error_message')}")
                break

            page_results = data.get("results", []) or []
            results.extend(page_results)
            pages_fetched += 1
            
            print(f"DEBUG TextSearch: Fetched page {pages_fetched}, got {len(page_results)} results, total: {len(results)}")

            if len(results) >= max_results:
                break

            page_token = data.get("next_page_token")
            if not page_token:
                break

            time.sleep(2.0)

        return results[:max_results]

    def get_details(self, place_id: str) -> dict:
        """
        Calls Google Place Details API.
        Requests important fields: rating, photos, reviews, address, url, opening hours.
        """
        params = {
            "place_id": place_id,
            "fields": "rating,user_ratings_total,photos,reviews,formatted_address,url,opening_hours,name,geometry",
            "key": self.api_key,
        }
        response = requests.get(self.BASE_DETAILS, params=params, timeout=20)
        data = response.json()

        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            raise GooglePlacesError(
                f"Details API Error: {data.get('status')} - {data.get('error_message')}"
            )

        return data

    def build_photo_url(self, photo_reference: str, max_width: int = 800) -> str:
        """
        Builds a photo URL without fetching it.
        """
        return (
            f"{self.BASE_PHOTO}?maxwidth={max_width}"
            f"&photo_reference={photo_reference}&key={self.api_key}"
        )


# Helper function
def get_google_places_client(settings):
    """
    Creates a GooglePlacesClient from project settings.
    """
    key = getattr(settings, "GOOGLE_PLACES_API_KEY", None)
    if not key:
        raise RuntimeError("Google Places API key missing — Google integration disabled.")
    return GooglePlacesClient(key)


class GooglePlacesEnricher:
    """
    Search sonuçlarındaki OSM mekanlarını Google Places verisi ile zenginleştirir.
    """

    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key
        self.client = GooglePlacesClient(api_key) if api_key else None

    async def enrich_places(self, places: List[PlaceItem]) -> List[PlaceItem]:
        """
        PlaceItem listesini Google verisi ile zenginleştirir.
        """
        from app.services.google_places_enricher import enrich_place_document

        if not places or not self.client:
            return places

        enriched_items: List[PlaceItem] = []
        for place in places:
            try:
                # Mevcut Google verisi varsa dokunma
                if place.google:
                    enriched_items.append(place)
                    continue

                coords = self._extract_coordinates(place)
                if not coords:
                    enriched_items.append(place)
                    continue

                place_doc = {
                    "name": place.name,
                    "location": {"coordinates": coords},
                    "google": None,
                    "google_last_updated": None,
                }

                google_data = await asyncio.to_thread(
                    enrich_place_document,
                    place_doc,
                    self.client,
                    False,
                )

                if google_data:
                    place_data = place.model_dump()
                    place_data["google"] = google_data
                    enriched_items.append(PlaceItem(**place_data))
                else:
                    enriched_items.append(place)
            except Exception as exc:
                print(f"Google enrichment failed for {place.name}: {exc}")
                enriched_items.append(place)

        return enriched_items

    @staticmethod
    def _extract_coordinates(place: PlaceItem):
        if place.coordinates and len(place.coordinates) == 2:
            return place.coordinates

        if place.lon is not None and place.lat is not None:
            return [place.lon, place.lat]

        return None


