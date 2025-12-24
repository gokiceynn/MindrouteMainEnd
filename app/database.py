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
    if places_collection is None:
        logger.warning("Places collection bulunamadı, bağlantı kuruluyor...")
        await connect_to_mongo()
    
    if places_collection is None:
        logger.error("❌ Places collection hala bulunamadı!")
        raise Exception("Places collection bulunamadı")
    
    try:
        logger.info("MongoDB indeksleri oluşturuluyor...")
        
        # Mevcut indexleri kontrol et ve sil
        existing_indexes = await places_collection.list_indexes().to_list(length=None)
        for index in existing_indexes:
            index_name = index.get("name", "")
            if index_name in ["osm_id_1", "u_osm_id", "location_2dsphere", "type_1"]:
                try:
                    await places_collection.drop_index(index_name)
                    logger.info(f"→ Mevcut index silindi: {index_name}")
                except Exception as e:
                    logger.warning(f"→ Index silinemedi {index_name}: {e}")
        
        # osm_id üzerinde unique index
        try:
            await places_collection.create_index("osm_id", unique=True, name="u_osm_id")
            logger.info("✅ osm_id unique index oluşturuldu")
        except Exception as e:
            if "already exists" not in str(e):
                logger.error(f"❌ osm_id index hatası: {e}")
        
        # location üzerinde 2dsphere index (GeoJSON için)
        try:
            await places_collection.create_index([("location", "2dsphere")], name="location_2dsphere")
            logger.info("✅ location 2dsphere index oluşturuldu")
        except Exception as e:
            if "already exists" not in str(e):
                logger.error(f"❌ location index hatası: {e}")
        
        # type üzerinde normal index
        try:
            await places_collection.create_index("type", name="type_1")
            logger.info("✅ type index oluşturuldu")
        except Exception as e:
            if "already exists" not in str(e):
                logger.error(f"❌ type index hatası: {e}")
        
        logger.info("✅ Tüm indeksler başarıyla oluşturuldu")
        
    except Exception as e:
        logger.error(f"❌ Index oluşturma hatası: {e}")
        # Index hatası sunucuyu durdurmasın, sadece log'la
        logger.warning("Sunucu index hatası ile devam ediyor...")


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
