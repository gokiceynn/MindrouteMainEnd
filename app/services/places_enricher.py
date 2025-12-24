"""
Mekan öneri pipeline'ı: OSM → Google → Yelp → Score → Rank
Ana veri kaynağı OSM/Overpass, zenginleştirme Google (ve opsiyonel Yelp/Wiki) ile.
Foursquare entegrasyonu tamamen kaldırıldı.
"""
import asyncio
from typing import List, Optional, Dict
from math import radians, sin, cos, sqrt, atan2
import httpx

from app.config import settings
from app.models import PlaceItem, GooglePlaceInfo, FoursquareDetails, GoogleReview
from app.services.google_places_service import get_google_places_client, GooglePlacesError
from app.services.google_places_enricher import enrich_place_with_google
from app.services.mood_recommender import normalize_mood, compute_mood_score, build_mood_reason


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki koordinat arası mesafe hesapla (metre)"""
    R = 6371000  # Dünya yarıçapı (metre)
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


async def fetch_osm_places(
    lat: float,
    lon: float,
    radius_m: int = 3000,
    limit: int = 1000,  # Artırıldı - Overpass timeout ile sınırlı zaten
    categories: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Overpass API kullanarak OSM'den kafe / restoran vb. mekanları çeker.
    Mevcut live_osm.py implementasyonunu kullanır.
    """
    from app.services.live_osm import build_circle_query, _call_overpass
    
    # Leisure mekanlar için kategori seçimi - ÇOK GENİŞLETİLDİ
    # NOT: live_osm.py'deki build_circle_query "amenities" key'ini bekliyor
    if categories is None:
        selects = {
            # Tüm yemek/içecek mekanları (marketplace YOK - market değil, yemek mekanı)
            "amenity": "cafe,restaurant,fast_food,bar,pub,biergarten,food_court,ice_cream,nightclub,cinema,theatre,arts_centre,music_venue,community_centre,bistro,brasserie,brewery,winery,distillery,coffee_shop,juice_bar,smoothie_bar,bbq,drinking_water",
            # Tüm eğlence/boş zaman mekanları - MÜMKÜN OLDUĞUNCA GENİŞ
            "leisure": "park,garden,fitness_centre,sports_centre,amusement_arcade,beach_resort,escape_game,water_park,bowling_alley,miniature_golf,dance,adult_gaming_centre,beach,marina,playground,stadium,swimming_pool,recreation_ground,outdoor_seating,slipway,summer_camp,tanning_salon",
            # Tüm turizm/kültür mekanları - MÜMKÜN OLDUĞUNCA GENİŞ
            "tourism": "museum,art_gallery,attraction,viewpoint,theme_park,zoo,aquarium,information,exhibition,planetarium,observatory,monument,memorial,ruins,castle,fortress,hostel,hotel,guest_house,apartment,chalet,resort,camp_site,caravan_site",
            # Sadece eğlence odaklı alışveriş mekanları (market/supermarket YOK)
            "shop": "bakery,books,clothes,coffee,confectionery,music,art,craft,toys,games,outdoor,sports,florist,gift,seafood,fishmonger,butcher,cheese,wine,alcohol,tea,spices,chocolate,pastry",
        }
    else:
        # Kategorileri amenity'ye map et
        selects = {"amenity": ",".join(categories)}
    
    try:
        # Radius'u maksimum 5000m ile sınırla (Overpass timeout'larını önlemek için)
        effective_radius = min(radius_m, 5000)
        query = build_circle_query(lat, lon, effective_radius, selects)
        print(f"DEBUG: Calling Overpass API with radius={effective_radius}m")
        data = await asyncio.to_thread(_call_overpass, query)
        
        # Limit'i kaldır - tüm sonuçları al (Overpass zaten timeout ile sınırlı)
        elements = data.get("elements", [])
        places: List[Dict] = []
        
        for element in elements:
            tags = element.get("tags", {}) or {}
            name = tags.get("name")
            # İsim yoksa da devam et - tip veya ID kullan
            if not name:
                # Tip varsa onu kullan, yoksa ID kullan
                place_type_temp = None
                for k in ("amenity", "leisure", "tourism", "shop"):
                    if k in tags:
                        place_type_temp = tags[k]
                        break
                if place_type_temp:
                    name = place_type_temp.title()
                else:
                    name = f"Place {element.get('id', 'unknown')}"
            
            # İSİM BAZLI FİLTRELEME: Market, okul, hastane gibi yerleri engelle
            # AMA kahve/cafe mekanlarını engelleme!
            name_lower = name.lower()
            
            # Önce kahve/cafe kontrolü - eğer kahve/cafe içeriyorsa direkt geç
            is_coffee_place = any(kw in name_lower for kw in [
                "cafe", "kahve", "coffee", "kafe", "café", "espresso", "latte",
                "arabica", "starbucks", "nero", "costa", "mackbear", "looq"
            ])
            
            # Eğer kahve mekanıysa direkt geç, filtreleme yapma
            if not is_coffee_place:
                blocked_keywords = [
                    "market", "süpermarket", "supermarket", "grocery", "gıda", "bakkal", "migros", "a101", "bim", "şok",
                    "okul", "school", "üniversite", "university", "fakülte", "faculty", "college", "lise", "ilkokul",
                    "hastane", "hospital", "klinik", "clinic", "sağlık", "health",
                    "eczane", "pharmacy", "ilaç", "drug", "medikal", "medical",
                    "bank", "banka", "atm", "kredi", "credit", "ziraat", "garanti", "iş bankası", "yapı kredi",
                    "polis", "police", "karakol", "station", "jandarma", "güvenlik",
                    "cami", "mosque", "kilise", "church", "mescit",
                    "mezarlık", "cemetery", "kabristan",
                    "veteriner", "veterinary", "hayvan",
                    "ofis", "office", "büro", "bureau", "sigorta", "insurance",
                    "fabrika", "factory", "üretim", "production",
                    "depo", "warehouse", "stok", "stock",
                    "oto", "otomobil", "car", "galeri", "servis",
                    "parking", "otopark", "park yeri"
                ]
                if any(keyword in name_lower for keyword in blocked_keywords):
                    continue  # Bu mekanı atla
                
                # Generic isimleri filtrele (sadece "Park", "Stadium" gibi tek kelimelik generic isimler)
                generic_only_names = ["park", "stadium", "plaza", "center", "merkez", "building", "bina"]
                if name_lower.strip() in generic_only_names or (len(name_lower.split()) == 1 and name_lower in generic_only_names):
                    continue  # Generic isimleri atla
            
            # Koordinatları al
            el_lat = element.get("lat") or (element.get("center") or {}).get("lat")
            el_lon = element.get("lon") or (element.get("center") or {}).get("lon")
            if el_lat is None or el_lon is None:
                continue
            
            # Mesafe hesapla
            distance = haversine_distance_m(lat, lon, el_lat, el_lon)
            
            # Tip belirle
            place_type = None
            for k in ("amenity", "leisure", "tourism", "shop"):
                if k in tags:
                    place_type = tags[k]
                    break
            if not place_type:
                place_type = "point_of_interest"
            
            # TİP BAZLI FİLTRELEME: Market, okul, hastane gibi tipleri engelle
            # AMA cafe/coffee shop'ları asla engelleme!
            place_type_lower = place_type.lower()
            
            # Cafe/coffee tiplerini kontrol et
            is_coffee_type = any(kw in place_type_lower for kw in [
                "cafe", "coffee", "coffee_shop", "bakery"
            ])
            
            # Eğer cafe/coffee tipindeyse direkt geç
            if not is_coffee_type:
                blocked_types = [
                    "supermarket", "convenience", "grocery", "marketplace", "food_court",
                    "school", "university", "college", "kindergarten", "primary_school", "secondary_school",
                    "hospital", "clinic", "pharmacy", "dentist", "doctor", "health",
                    "bank", "atm", "police", "fire_station", "post_office",
                    "place_of_worship", "mosque", "church", "temple", "synagogue",
                    "cemetery", "funeral_hall",
                    "veterinary", "office", "courthouse", "government", "real_estate_agency", "insurance_agency",
                    "factory", "warehouse", "industrial", "storage",
                    "car_dealer", "car_repair", "gas_station", "parking"
                ]
                if place_type_lower in blocked_types:
                    continue  # Bu mekanı atla
            
            # Adres
            address_full = tags.get("addr:full") or tags.get("addr:street") or ""
            
            place_dict = {
                "id": f"osm_{element.get('id')}",
                "name": name,
                "type": place_type,
                "address": {"full": address_full},
                "coordinates": [el_lon, el_lat],
                "lat": el_lat,
                "lon": el_lon,
                "distance_m": distance,
                "score": 0.0,
                "tags": tags,
                "osm_id": element.get("id"),
                "osm_type": element.get("type"),
                "source": "osm",  # Kaynak belirteci
            }
            places.append(place_dict)
            
            # DEBUG: Cafe/coffee mekanlarını logla
            if is_coffee_place or is_coffee_type:
                print(f"DEBUG: OSM CAFE/COFFEE found: {name} (type: {place_type})")
        
        return places
    except Exception as e:
        print(f"OSM fetch error: {e}")
        import traceback
        traceback.print_exc()
        return []


async def enrich_with_google(place: Dict, google_client) -> Dict:
    """Google Places API ile mekanı zenginleştirir (opsiyonel)."""
    if not google_client:
        return place
    
    try:
        # Nearby Search ile eşleştirme - timeout artırıldı
        nearby_results = await asyncio.to_thread(
            google_client.search_nearby,
            lat=place["lat"],
            lon=place["lon"],
            radius_m=200,
            keyword=place.get("name", "")
        )
        
        results = nearby_results.get("results", [])
        if not results:
            return place
        
        # En yakın eşleşmeyi bul
        best_match = None
        min_distance = float('inf')
        
        for result in results:
            geometry = result.get("geometry", {})
            loc = geometry.get("location", {})
            g_lat = loc.get("lat")
            g_lon = loc.get("lng")
            
            if g_lat is None or g_lon is None:
                continue
            
            distance = haversine_distance_m(place["lat"], place["lon"], g_lat, g_lon)
            if distance < min_distance and distance < 150:  # 150m içinde
                min_distance = distance
                best_match = result
        
        if not best_match:
            return place
        
        # Place Details çek
        place_id = best_match.get("place_id")
        if not place_id:
            return place
        
        details = await asyncio.to_thread(google_client.get_details, place_id)
        
        # Enrichment oluştur
        osm_like_doc = {
            "name": place.get("name"),
            "location": {"coordinates": place.get("coordinates")},
        }
        enrichment = enrich_place_with_google(osm_like_doc, details, google_client)
        
        if enrichment:
            place["google"] = enrichment
        
        return place
    except Exception as e:
        print(f"Google enrichment error for {place.get('name')}: {e}")
        return place


def compute_base_score(
    distance_m: float,
    rating: Optional[float],
    max_distance_m: float,
) -> float:
    """Base score hesapla: rating + distance kombinasyonu."""
    # Rating factor: 0..1
    r = rating if rating is not None else 4.0
    rating_factor = min(max(r / 5.0, 0), 1)
    
    # Distance factor: 0..1 (yakınsa yüksek)
    # Mesafe faktörünü daha agresif yap - yakın mekanlara daha fazla öncelik
    d_norm = min(distance_m / max(max_distance_m, 1000.0), 1.0)  # En az 1km referans
    distance_factor = 1.0 - (d_norm ** 0.7)  # Daha yumuşak eğri
    
    # Ağırlıklar - mesafeye daha fazla önem ver (yakın mekanlar öncelikli)
    return 0.5 * rating_factor + 0.5 * distance_factor


def compute_mood_score_for_place(
    place: Dict,
    normalized_mood: Optional[str],
) -> tuple[float, Optional[str]]:
    """Mood score ve reason hesapla."""
    if not normalized_mood:
        return place.get("score", 0.0), None
    
    try:
        mood_score = compute_mood_score(place, normalized_mood)
        mood_reason = build_mood_reason(place, normalized_mood, mood_score)
        return mood_score, mood_reason
    except:
        return place.get("score", 0.0), None


async def get_nearby_places(
    user_lat: float,
    user_lon: float,
    mood: Optional[str] = None,
    radius_m: int = 3000,
    limit: int = 30,
) -> List[PlaceItem]:
    """
    Ana fonksiyon: OSM + Foursquare base → (opsiyonel Google) → skorla → sırala.
    """
    # 1) OSM'den mekanlar
    print(f"DEBUG: Fetching OSM places for lat={user_lat}, lon={user_lon}, radius={radius_m}m")
    osm_places = await fetch_osm_places(
        lat=user_lat,
        lon=user_lon,
        radius_m=radius_m,
        limit=500,  # Artırıldı: 300 -> 500
    )
    for p in osm_places:
        p.setdefault("source", "osm")

    print(f"DEBUG: Fetched {len(osm_places)} places from OSM")
    if len(osm_places) > 0:
        print(f"DEBUG: OSM sample names: {[p.get('name') for p in osm_places[:5]]}")
        # Cafe/coffee mekanlarını say
        coffee_count = sum(1 for p in osm_places if any(kw in (p.get('name') or '').lower() for kw in ['cafe', 'kahve', 'coffee', 'kafe']) or any(kw in (p.get('type') or '').lower() for kw in ['cafe', 'coffee']))
        print(f"DEBUG: OSM coffee/cafe places: {coffee_count} out of {len(osm_places)}")

    # 2) Foursquare TAMAMEN DEVRE DIŞI
    # Yeni mimaride sadece OSM + Google + Yelp kullanıyoruz.
    fsq_places: List[Dict] = []

    # 2.5) Google Places API'den direkt mekanlar (yeni kafeler için)
    google_places = []
    if settings.GOOGLE_PLACES_API_KEY:
        try:
            from app.services.google_places_service import get_google_places_client
            google_client = get_google_places_client(settings)
            from app.services.google.google_places_helper import get_photo_url
            
            # Google Places API'den mekanları çek
            print(f"DEBUG: Fetching Google Places for lat={user_lat}, lon={user_lon}, radius={radius_m}m")
            raw_google_results = await asyncio.to_thread(
                google_client.search_nearby_paginated,
                user_lat,
                user_lon,
                radius_m,
                None,  # keyword yok
                60,  # max 60 sonuç
            )
            
            # Google sonuçlarını OSM formatına çevir ve filtrele
            from app.routes.places import ALLOWED_TYPES, BLOCKED_TYPES
            
            for r in raw_google_results:
                geometry = r.get("geometry", {}) or {}
                loc = geometry.get("location", {}) or {}
                g_lat = loc.get("lat")
                g_lon = loc.get("lng")
                if g_lat is None or g_lon is None:
                    continue
                
                types = r.get("types", [])
                tset = {t.lower() for t in types} if types else set()
                
                # Blocked types kontrolü
                if tset & BLOCKED_TYPES:
                    continue
                
                # İsim bazlı filtreleme
                name = (r.get("name") or "").lower()
                coffee_keywords = ["cafe", "kahve", "coffee", "kafe", "café", "espresso", "latte", "arabica", "starbucks", "mackbear", "looq"]
                is_coffee = any(kw in name for kw in coffee_keywords)
                
                if not is_coffee:
                    blocked_keywords = [
                        "market", "grocery", "bakkal", "supermarket", "migros", "a101", "bim", "şok",
                        "okul", "school", "üniversite", "university", "college", "fakülte", "faculty", "lise", "ilkokul",
                        "hastane", "hospital", "klinik", "clinic", "sağlık", "health",
                        "eczane", "pharmacy", "medikal", "medical",
                        "bank", "atm", "ziraat", "garanti", "iş bankası", "yapı kredi",
                        "polis", "police", "jandarma", "güvenlik",
                        "cami", "mosque", "kilise", "church", "mescit",
                        "mezarlık", "cemetery", "kabristan",
                        "veteriner", "veterinary",
                        "government", "courthouse", "belediye", "kaymakamlık", "valilik",
                        "warehouse", "factory", "industrial", "depo", "fabrika",
                        "ofis", "office", "büro", "sigorta", "insurance",
                        "oto", "otomobil", "car", "galeri", "servis",
                        "parking", "otopark", "park yeri"
                    ]
                    if any(bad in name for bad in blocked_keywords):
                        continue
                    
                    # Generic isimleri filtrele (sadece "Park", "Stadium" gibi tek kelimelik generic isimler)
                    generic_only_names = ["park", "stadium", "plaza", "center", "merkez", "building", "bina"]
                    if name.strip() in generic_only_names or (len(name.split()) == 1 and name in generic_only_names):
                        continue
                
                distance = haversine_distance_m(user_lat, user_lon, g_lat, g_lon)
                main_type = types[0] if types else "point_of_interest"

                # Foto referanslarını URL'ye çevir (ilk 3)
                photo_urls = []
                for ph in (r.get("photos") or [])[:3]:
                    ref = ph.get("photo_reference")
                    if ref:
                        url = get_photo_url(ref)
                        if url:
                            photo_urls.append(url)
                
                google_place = {
                    "id": f"google_{r.get('place_id')}",
                    "name": r.get("name"),
                    "type": main_type,
                    "address": {"full": r.get("vicinity") or r.get("formatted_address") or ""},
                    "coordinates": [g_lon, g_lat],
                    "lat": g_lat,
                    "lon": g_lon,
                    "distance_m": distance,
                    "score": 0.0,
                    "source": "google",
                    "photos": photo_urls,
                    "google": {
                        "place_id": r.get("place_id"),
                        "rating": r.get("rating"),
                        "user_ratings_total": r.get("user_ratings_total", 0),
                        "types": types,
                        "photos": photo_urls,
                    }
                }
                google_places.append(google_place)
            
            print(f"DEBUG: Fetched {len(google_places)} places from Google Places")
            if len(google_places) > 0:
                print(f"DEBUG: Google Places sample names: {[p.get('name') for p in google_places[:5]]}")
        except Exception as e:
            print(f"DEBUG: Google Places API error (continuing without Google base): {e}")
            google_places = []

    # 3) OSM + Google birleştir
    # Tüm mekanları al, duplicate kontrolü yapma
    combined_places: List[Dict] = []
    
    # Sadece aynı ID'ye sahip mekanları filtrele (farklı kaynaklardan gelen aynı mekan)
    seen_ids = set()
    
    for p in osm_places + fsq_places + google_places:
        place_id = p.get("id")
        if place_id and place_id in seen_ids:
            continue
        if place_id:
            seen_ids.add(place_id)
        combined_places.append(p)

    if not combined_places:
        return []

    # En uzak mesafe
    max_dist = max(p.get("distance_m", 0) for p in combined_places) or 1.0

    # 4) En yakın 150 için enrichment (artırıldı: 100 -> 150)
    combined_sorted = sorted(combined_places, key=lambda p: p.get("distance_m", float("inf")))
    top_for_enrichment = combined_sorted[:150]
    
    print(f"DEBUG: Combined places: {len(combined_places)} total (OSM: {len(osm_places)}, Google: {len(google_places)})")
    print(f"DEBUG: Enriching top {len(top_for_enrichment)} places")

    # İlk 20 mekanın isimlerini logla
    if len(combined_sorted) > 0:
        print(
            "DEBUG: Top 20 by distance: "
            f"{[p.get('name', 'No name') for p in combined_sorted[:20]]}"
        )

    # Google client (opsiyonel)
    google_client = None
    if settings.GOOGLE_PLACES_API_KEY:
        try:
            google_client = get_google_places_client(settings)
        except Exception:
            google_client = None

    # 4.a) Başlangıçta tüm mekanlar için "enriched" listesi combined_places'tir
    enriched_places = list(combined_places)

    # 4.b) Google enrichment (opsiyonel, ilk 50 için - artırıldı: 30 -> 50)
    # Daha fazla mekan için Google'dan rating/fotoğraf bilgisi al
    if google_client:
        top_50 = enriched_places[:50]
        google_tasks = [enrich_with_google(p, google_client) for p in top_50]
        enriched_top_50 = await asyncio.gather(
            *google_tasks, return_exceptions=True
        )
        # Hataları filtrele
        enriched_top_50_clean = [
            p for p in enriched_top_50 if not isinstance(p, Exception)
        ]
        enriched_places[: len(enriched_top_50_clean)] = enriched_top_50_clean

    # enriched_map oluştur (id üzerinden)
    enriched_map = {p.get("id"): p for p in enriched_places}

    # 4.c) Yelp + Wikimedia fotoğrafları ile zenginleştir (ilk 30 için)
    try:
        from app.services.external.yelp_service import yelp_search_by_coords
        from app.services.external.wikidata_service import find_wikidata_id
        from app.services.external.wikimedia_photos import get_wikimedia_images
    except Exception:
        yelp_search_by_coords = None
        find_wikidata_id = None
        get_wikimedia_images = None

    if yelp_search_by_coords or get_wikimedia_images:
        top_for_ext = enriched_places[:30]
        yelp_results = []
        wiki_ids = []

        # Yelp: sıralı istek + küçük bekleme (rate limit için)
        if yelp_search_by_coords:
            for p in top_for_ext:
                try:
                    res = await yelp_search_by_coords(
                        p.get("lat"), p.get("lon"),
                        # Yelp'in kategori eşleşmesi için: isim + genel kategoriler
                        (p.get("name") or "")[:60],  # isimden 60 karaktere kadar
                        radius=700,  # biraz genişletildi
                    )
                except Exception as e:
                    res = e
                # İlk sonuç için detay çek (foto/rating/yorum sayısı daha zengin)
                if isinstance(res, list) and len(res) > 0:
                    best = res[0]
                    try:
                        from app.services.external.yelp_service import yelp_business_details
                        detail = await yelp_business_details(best.get("id"))
                        if detail:
                            res[0] = detail
                    except Exception:
                        pass

                yelp_results.append(res)
                await asyncio.sleep(0.5)  # biraz daha bekle, 429 azaltmak için

        # Wikidata ID'leri topla
        if get_wikimedia_images and find_wikidata_id:
            wiki_tasks = []
            for p in top_for_ext:
                wiki_tasks.append(find_wikidata_id(p.get("name") or ""))
            try:
                wiki_ids = await asyncio.gather(*wiki_tasks, return_exceptions=True)
            except Exception:
                wiki_ids = []

        wiki_photos_map = {}
        if wiki_ids and get_wikimedia_images:
            # Wikimedia Commons API rate limiting için sequential çağrılar yap
            # Paralel çağrılar 403 Forbidden'a neden olabilir
            for idx, wid in enumerate(wiki_ids):
                if isinstance(wid, Exception) or not wid:
                    continue
                try:
                    # Her çağrı arasında 0.3 saniye bekle (rate limiting önlemi)
                    if idx > 0:
                        await asyncio.sleep(0.3)
                    photos = await get_wikimedia_images(qid=wid)
                    if photos:
                        wiki_photos_map[idx] = photos
                except Exception as e:
                    # 403 veya diğer hataları sessizce geç (optional özellik)
                    continue

        for idx, base_place in enumerate(top_for_ext):
            place_id = base_place.get("id")
            place = enriched_map.get(place_id, base_place)

            # Yelp
            if yelp_results and idx < len(yelp_results):
                yr = yelp_results[idx]
                if yr and not isinstance(yr, Exception):
                    best = yr[0] if isinstance(yr, list) and len(yr) > 0 else None
                    if best:
                        place["yelp"] = {
                            "rating": best.get("rating"),
                            "review_count": best.get("review_count"),
                            "price": best.get("price"),
                            "url": best.get("url"),
                            "photos": best.get("photos") or [],
                            "categories": best.get("categories") or [],
                        }

            # Wikimedia photos
            if wiki_photos_map.get(idx):
                place_photos = place.get("photos") or []
                place_photos.extend(wiki_photos_map[idx])
                # unique
                place["photos"] = list(dict.fromkeys(place_photos))

            enriched_map[place_id] = place
            enriched_places[idx] = place

    # 5) Gelişmiş Skorlama - Tip bazlı + Rating + Mesafe
    normalized_mood = normalize_mood(mood)
    final_places: List[Dict] = []

    # Generic isimler listesi (düşük skor alacak veya filtrelenecek)
    generic_names = {
        "park", "stadium", "place", "point", "location", "area", "zone",
        "plaza", "center", "merkez", "building", "bina", "complex"
    }

    for base in combined_places:
        place = enriched_map.get(base.get("id"), base)
        name = (place.get("name") or "").lower().strip()
        place_type = (place.get("type") or "").lower()
        distance_m = place.get("distance_m", float("inf"))

        # Generic isim kontrolü - "Park", "Stadium" gibi isimler düşük skor alır veya filtrelenir
        is_generic_name = (
            name in generic_names or 
            (len(name.split()) == 1 and name in generic_names) or
            name.startswith("park ") or name.startswith("stadium ") or
            name == "park" or name == "stadium"
        )
        
        # Gençlerin gitmeyeceği yerleri tamamen filtrele
        youth_blocked_keywords = [
            "okul", "school", "üniversite", "university", "fakülte", "college",
            "hastane", "hospital", "klinik", "clinic",
            "eczane", "pharmacy", "bank", "atm",
            "polis", "police", "cami", "mosque", "kilise", "church",
            "mezarlık", "cemetery", "market", "grocery", "bakkal", "supermarket",
            "ofis", "office", "warehouse", "factory", "industrial"
        ]
        if any(bad in name for bad in youth_blocked_keywords):
            continue  # Bu mekanı tamamen atla

        # Rating kaynağı: önce Foursquare, sonra Google
        rating = None
        if place.get("foursquare") and place["foursquare"].get("rating") is not None:
            rating = place["foursquare"]["rating"]
        elif place.get("google") and place["google"].get("rating") is not None:
            rating = place["google"]["rating"]

        # Tip bazlı skor (gençlerin gitmek isteyeceği mekanlar yüksek skor alır)
        type_score = 0.3  # Varsayılan (daha düşük başlangıç)
        
        # Gençlerin gitmek isteyeceği yerler (yüksek öncelik)
        youth_preferred_types = {
            "cafe", "coffee_shop", "restaurant", "bar", "night_club", "pub",
            "bakery", "meal_takeaway", "meal_delivery", "fast_food",
            "movie_theater", "bowling_alley", "amusement_park", "arcade",
            "tourist_attraction", "shopping_mall", "book_store",
            "spa", "gym", "fitness_center"
        }
        
        # Orta öncelik (bazı gençler gidebilir)
        medium_types = {
            "museum", "art_gallery", "library", "theater", "concert_hall",
            "park", "garden", "beach", "viewpoint"
        }
        
        # Kaynak bazlı bonus - Google Places mekanları daha yüksek skor alır (güncel veri)
        source_bonus = 0.0
        if place.get("source") == "google":
            source_bonus = 0.2  # Google mekanları +0.2 bonus (yeni kafeler için)
        
        # İsim bazlı bonus - kafe/coffee/kahve içeren isimler ekstra bonus
        name_bonus = 0.0
        coffee_keywords = ["cafe", "kahve", "coffee", "kafe", "café", "espresso", "latte"]
        if any(kw in name for kw in coffee_keywords):
            name_bonus = 0.15  # Kafe isimleri ekstra bonus
        
        if place_type in youth_preferred_types:
            type_score = 1.0  # Gençlerin tercih ettiği mekanlar maksimum skor
        elif place_type in medium_types:
            type_score = 0.5  # Orta öncelik
        elif place_type in {"park", "garden", "stadium", "sports_centre"}:
            type_score = 0.2  # Park/stadium çok düşük skor
        elif is_generic_name:
            type_score = 0.05  # Generic isimler neredeyse hiç skor almasın

        # Rating faktörü
        if rating:
            rating_score = rating / 5.0
        else:
            rating_score = 0.5  # Rating yoksa neutral

        # Mesafe faktörü (yakın mekanlar yüksek skor)
        max_dist = max(p.get("distance_m", 0) for p in combined_places) or 5000.0
        distance_score = max(0.0, 1.0 - (distance_m / max_dist))

        # Kombine skor: Tip (50%) + Rating (30%) + Mesafe (20%) + Source Bonus + Name Bonus
        # Generic isimler için tip skorunu çok düşür
        if is_generic_name:
            final_score = 0.1 * type_score + 0.2 * rating_score + 0.7 * distance_score
        else:
            final_score = 0.5 * type_score + 0.3 * rating_score + 0.2 * distance_score + source_bonus + name_bonus

        place["score"] = max(0.0, min(1.0, final_score))

        # Mood score
        if normalized_mood:
            try:
                mood_score, mood_reason = compute_mood_score_for_place(place, normalized_mood)
                # Mood score'u base score ile birleştir
                place["mood_score"] = 0.7 * place["score"] + 0.3 * mood_score
                place["mood_reason"] = mood_reason
            except:
                place["mood_score"] = place["score"]
                place["mood_reason"] = None
        else:
            place["mood_score"] = place["score"]
            place["mood_reason"] = None

        final_places.append(place)
    
    print(f"DEBUG: Scored {len(final_places)} places")

    # 6) Gelişmiş Sıralama - Skor + Mesafe kombinasyonu
    # Önce skora göre, sonra mesafeye göre sırala
    # Generic isimli mekanları daha aşağıya it
    final_places_sorted = sorted(
        final_places,
        key=lambda p: (
            -(p.get("mood_score") or p.get("score", 0.0)),  # Önce skor (yüksekten düşüğe)
            p.get("distance_m", float("inf")),  # Sonra mesafe (küçükten büyüğe)
        ),
    )

    # Gençlerin gitmek isteyeceği eğlence/yiyecek-içecek mekanları öne çıkar
    preferred_types = {
        "cafe", "coffee_shop", "restaurant", "bar", "night_club", "pub",
        "bakery", "meal_takeaway", "meal_delivery", "fast_food",
        "amusement_park", "movie_theater", "bowling_alley", "arcade",
        "tourist_attraction", "shopping_mall", "book_store",
        "spa", "gym", "fitness_center"
    }

    def is_preferred(place: Dict) -> bool:
        t = (place.get("type") or "").lower()
        name = (place.get("name") or "").lower()
        
        # Generic isimleri tercih etme
        generic_names = {"park", "stadium", "place", "point", "location", "area", "zone", "plaza", "center", "merkez"}
        if name in generic_names or (len(name.split()) == 1 and name in generic_names):
            return False
        
        # Gençlerin gitmeyeceği yerleri tercih etme
        youth_blocked = [
            "okul", "school", "üniversite", "university", "fakülte", "college",
            "hastane", "hospital", "klinik", "clinic",
            "eczane", "pharmacy", "bank", "atm",
            "polis", "police", "cami", "mosque", "kilise", "church",
            "mezarlık", "cemetery", "market", "grocery", "bakkal", "supermarket",
            "ofis", "office", "warehouse", "factory", "industrial"
        ]
        if any(bad in name for bad in youth_blocked):
            return False
        
        # İsimde kafe/coffee geçenleri öne çek
        coffee_kw = ["cafe", "coffee", "kafe", "kahve", "café", "espresso", "latte"]
        if any(kw in name for kw in coffee_kw):
            return True
        
        # Tip kontrolü
        return t in preferred_types

    preferred_list = [p for p in final_places_sorted if is_preferred(p)]

    # Eğer yeterli yoksa (örn. uzak şehirde), kalanları ekle
    if len(preferred_list) < limit:
        remaining = [p for p in final_places_sorted if p not in preferred_list]
        top = (preferred_list + remaining)[:limit]
    else:
        top = preferred_list[:limit]

    for i, p in enumerate(top):
        p["is_recommended"] = i < 5

    # 7) PlaceItem'e dönüştür
    items: List[PlaceItem] = []
    for p in top:
        # Google info
        google_info = None
        if p.get("google"):
            g_data = p["google"]
            reviews = []
            for rev in g_data.get("reviews", [])[:3]:
                if isinstance(rev, dict):
                    reviews.append(GoogleReview(**rev))

            google_info = GooglePlaceInfo(
                place_id=g_data.get("place_id"),
                rating=g_data.get("rating"),
                user_ratings_total=g_data.get("user_ratings_total"),
                address=g_data.get("address"),
                url=g_data.get("url"),
                opening_hours=g_data.get("opening_hours"),
                photos=g_data.get("photos", [])[:5] if g_data.get("photos") else None,
                reviews=reviews or None,
                types=g_data.get("types"),
            )

        # Foursquare info
        foursquare_info = None
        if p.get("foursquare"):
            fsq_data = p["foursquare"]
            foursquare_info = FoursquareDetails(
                fsq_id=fsq_data.get("fsq_id"),
                rating=fsq_data.get("rating"),
                photos=fsq_data.get("photos"),
                categories=fsq_data.get("categories"),
                url=fsq_data.get("url"),
            )

        item = PlaceItem(
            id=p.get("id"),
            name=p.get("name"),
            type=p.get("type"),
            address=p.get("address"),
            coordinates=p.get("coordinates"),
            lat=p.get("lat"),
            lon=p.get("lon"),
            distance_m=p.get("distance_m"),
            score=p.get("score"),
            google=google_info,
            foursquare=foursquare_info,
            mood_score=p.get("mood_score"),
            mood_reason=p.get("mood_reason"),
            is_recommended=p.get("is_recommended", False),
            photo=p.get("photo"),
            photos=p.get("photos"),
            rating=p.get("rating"),
            rating_source=p.get("rating_source"),
        )
        items.append(item)

    print(f"DEBUG: Returning {len(items)} places (from {len(final_places)} total scored places)")
    if len(items) > 0:
        print(f"DEBUG: Top 5 places: {[p.get('name') for p in top[:5]]}")
    return items

