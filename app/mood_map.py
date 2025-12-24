# Mood-Mekan türü eşleştirme haritası
MOOD_MAP = {
    "stresli": ["park", "garden", "forest", "viewpoint"],
    "mutlu": ["cafe", "cinema", "pub", "restaurant", "fast_food", "bar"],
    "huzurlu": ["park", "garden", "viewpoint"],
    "yalnız": ["library", "museum", "art_gallery", "cafe"],
    "enerjik": ["gym", "sports_centre", "stadium", "nightclub", "bar"],
    "nötr": ["cafe", "park", "library", "museum", "restaurant"],
    "üzgün": ["cafe", "library", "museum", "park"],
    "kızgın": ["park", "garden", "forest", "viewpoint"],
    "şaşkın": ["cafe", "cinema", "museum", "restaurant"],
    "korkmuş": ["cafe", "library", "park"],
    "tiksinmiş": ["park", "garden", "viewpoint"]
}


def get_mood_types(mood: str) -> list:
    """
    Verilen mood için uygun mekan türlerini döndürür.
    
    Args:
        mood: Kullanıcının ruh hali (stresli, mutlu, huzurlu, yalnız, enerjik)
        
    Returns:
        list: Mood'a uygun mekan türleri listesi
    """
    return MOOD_MAP.get(mood.lower(), [])


def is_valid_mood(mood: str) -> bool:
    """
    Verilen mood'un geçerli olup olmadığını kontrol eder.
    
    Args:
        mood: Kontrol edilecek mood
        
    Returns:
        bool: Mood geçerliyse True, değilse False
    """
    return mood.lower() in MOOD_MAP
