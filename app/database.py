import os
import logging
from typing import Optional
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING
from dotenv import load_dotenv

# app klasöründeki .env dosyasını yükle
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

# Logging ayarla
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB bağlantı bilgileri
MONGO_URL = os.getenv("MONGO_URL", "mongodb://127.0.0.1:27017")
DB_NAME = os.getenv("DB_NAME", "mindroute")
COLL_NAME = os.getenv("COLL_NAME", "places")

# Global client ve database değişkenleri - güvenli başlatma
client: Optional[AsyncIOMotorClient] = None
db = None
places_collection = None


async def connect_to_mongo():
    """MongoDB'ye bağlan"""
    global client, db, places_collection
    
    try:
        if client is not None:
            logger.info("MongoDB zaten bağlı")
            return
            
        logger.info(f"MongoDB'ye bağlanılıyor: {MONGO_URL}")
        client = AsyncIOMotorClient(
            MONGO_URL,
            serverSelectionTimeoutMS=5000,  # 5 saniye timeout
            connectTimeoutMS=10000,         # 10 saniye bağlantı timeout
            maxPoolSize=10,                 # Connection pool
            minPoolSize=1
        )
        
        db = client[DB_NAME]
        places_collection = db[COLL_NAME]
        
        # Bağlantıyı test et
        await client.admin.command('ping')
        logger.info(f"✅ MongoDB'ye başarıyla bağlandı: {DB_NAME}.{COLL_NAME}")
        
    except Exception as e:
        logger.error(f"❌ MongoDB bağlantı hatası: {e}")
        # Bağlantı başarısız olursa global değişkenleri temizle
        client = None
        db = None
        places_collection = None
        raise


async def close_mongo_connection():
    """MongoDB bağlantısını kapat"""
    global client, db, places_collection
    
    try:
        if client:
            client.close()
            logger.info("✅ MongoDB bağlantısı kapatıldı")
        else:
            logger.info("MongoDB bağlantısı zaten kapalı")
    except Exception as e:
        logger.error(f"❌ MongoDB bağlantısı kapatılırken hata: {e}")
    finally:
        # Global değişkenleri temizle
        client = None
        db = None
        places_collection = None


async def create_indexes():
    """Gerekli indeksleri oluştur"""
    if not places_collection:
        logger.warning("Places collection bulunamadı, bağlantı kuruluyor...")
        await connect_to_mongo()
    
    if not places_collection:
        logger.error("❌ Places collection hala bulunamadı!")
        raise Exception("Places collection bulunamadı")
    
    try:
        logger.info("MongoDB indeksleri oluşturuluyor...")
        
        # osm_id üzerinde unique index
        await places_collection.create_index("osm_id", unique=True)
        logger.info("✅ osm_id unique index oluşturuldu")
        
        # location üzerinde 2dsphere index (GeoJSON için)
        await places_collection.create_index([("location", "2dsphere")])
        logger.info("✅ location 2dsphere index oluşturuldu")
        
        # type üzerinde normal index
        await places_collection.create_index("type")
        logger.info("✅ type index oluşturuldu")
        
        logger.info("✅ Tüm indeksler başarıyla oluşturuldu")
        
    except Exception as e:
        logger.error(f"❌ Index oluşturma hatası: {e}")
        raise


def get_places_collection():
    """Places koleksiyonunu döndür"""
    if places_collection is None:
        logger.warning("Places collection henüz başlatılmamış!")
    return places_collection


def is_connected() -> bool:
    """MongoDB bağlantısının aktif olup olmadığını kontrol et"""
    return client is not None and places_collection is not None


async def health_check() -> dict:
    """MongoDB bağlantı durumunu kontrol et"""
    try:
        if not is_connected():
            return {"status": "disconnected", "message": "MongoDB bağlantısı yok"}
        
        # Ping test
        await client.admin.command('ping')
        return {"status": "connected", "message": "MongoDB bağlantısı aktif"}
        
    except Exception as e:
        logger.error(f"MongoDB health check hatası: {e}")
        return {"status": "error", "message": str(e)}
