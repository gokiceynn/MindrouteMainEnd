import httpx

# Wikimedia Commons API için gerekli User-Agent header'ı
# Format: "ProjectName/Version (contact email or URL)"
WIKIMEDIA_HEADERS = {
    "User-Agent": "Mindroute/1.0 (https://github.com/mindroute/mindroute-main)",
    "Accept": "application/json",
}


async def get_wikimedia_images(qid: str):
    """
    Wikimedia Commons API'den mekan fotoğraflarını çeker.
    
    Args:
        qid: Wikidata QID (örn: "Q12345")
    
    Returns:
        List[str]: Fotoğraf URL'leri listesi (boş liste dönebilir)
    """
    if not qid or not qid.strip():
        return []
    
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "pageimages",
        "piprop": "thumbnail|original",
        "pithumbsize": 2000,
        "titles": qid,
    }
    
    try:
        async with httpx.AsyncClient(timeout=10, headers=WIKIMEDIA_HEADERS) as client:
            r = await client.get(url, params=params)
            
            # 403 veya diğer hataları kontrol et
            if r.status_code == 403:
                print(f"DEBUG: Wikimedia Commons 403 Forbidden for QID {qid} - API rate limit veya erişim kısıtlaması")
                return []  # Sessizce boş liste döndür (optional özellik)
            
            r.raise_for_status()
            data = r.json()
            pages = data.get("query", {}).get("pages", {})
            photos = []
            
            for _, v in pages.items():
                if "thumbnail" in v:
                    photos.append(v["thumbnail"]["source"])
                elif "original" in v:
                    photos.append(v["original"]["source"])
            
            return photos
            
    except httpx.HTTPStatusError as e:
        # 403 dışındaki HTTP hataları için log
        if e.response.status_code != 403:
            print(f"DEBUG: Wikimedia Commons HTTP error {e.response.status_code} for QID {qid}: {e}")
        return []
    except Exception as e:
        print(f"DEBUG: Wikimedia Commons error for QID {qid}: {e}")
        return []


