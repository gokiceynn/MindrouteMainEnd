"""
MindRoute uygulaması için yapılandırma ayarları.
python-dotenv kullanarak .env dosyasından değerleri yükler.
"""
from pathlib import Path
from dotenv import load_dotenv
import os
from typing import Optional

# Root .env (mindroute/.env) sadece bir kez yüklenir
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


class Settings:
    """Uygulama yapılandırma ayarları."""

    # MongoDB ayarları
    MONGO_URL: str = os.getenv("MONGO_URL", "mongodb://127.0.0.1:27017")
    DB_NAME: str = os.getenv("DB_NAME", "mindroute")
    COLL_NAME: str = os.getenv("COLL_NAME", "places")

    # Emotion backend
    EMOTION_BACKEND: str = os.getenv("EMOTION_BACKEND", "mock")

    # Google Places API anahtarı root .env dosyasından gelir
    # GOOGLE_MAPS_API_KEY, GOOGLE_API_KEY veya GOOGLE_PLACES_API_KEY kullanılabilir
    GOOGLE_PLACES_API_KEY: Optional[str] = (
        os.getenv("GOOGLE_PLACES_API_KEY") 
        or os.getenv("GOOGLE_API_KEY") 
        or os.getenv("GOOGLE_MAPS_API_KEY")
    )

    # Foursquare Places API anahtarı
    FOURSQUARE_API_KEY: Optional[str] = os.getenv("FOURSQUARE_API_KEY", None)

    @classmethod
    def get_mongo_url(cls) -> str:
        """MongoDB bağlantı URL'ini döndürür."""
        return cls.MONGO_URL

    @classmethod
    def get_db_name(cls) -> str:
        """Veritabanı adını döndürür."""
        return cls.DB_NAME

    @classmethod
    def get_coll_name(cls) -> str:
        """Koleksiyon adını döndürür."""
        return cls.COLL_NAME


# Global settings instance
settings = Settings()


