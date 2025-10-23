import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING
from dotenv import load_dotenv

# .env yükle
load_dotenv()

# MongoDB bağlantı bilgileri
MONGO_URL = os.getenv("MONGO_URL", "mongodb://127.0.0.1:27017")
DB_NAME = os.getenv("DB_NAME", "mindroute")
COLL_NAME = os.getenv("COLL_NAME", "places")

# Global client ve database değişkenleri
client: AsyncIOMotorClient = None
db = None
places_collection = None


async def connect_to_mongo():
    """MongoDB'ye bağlan"""
    global client, db, places_collection
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    places_collection = db[COLL_NAME]
    
    # Bağlantıyı test et
    await client.admin.command('ping')
    print(f"✅ MongoDB'ye bağlandı: {DB_NAME}.{COLL_NAME}")


async def close_mongo_connection():
    """MongoDB bağlantısını kapat"""
    if client:
        client.close()
        print("✅ MongoDB bağlantısı kapatıldı")


async def create_indexes():
    """Gerekli indeksleri oluştur"""
    if not places_collection:
        await connect_to_mongo()
    
    try:
        # osm_id üzerinde unique index
        await places_collection.create_index("osm_id", unique=True)
        print("✅ osm_id unique index oluşturuldu")
        
        # location üzerinde 2dsphere index (GeoJSON için)
        await places_collection.create_index([("location", "2dsphere")])
        print("✅ location 2dsphere index oluşturuldu")
        
        # type üzerinde normal index
        await places_collection.create_index("type")
        print("✅ type index oluşturuldu")
        
    except Exception as e:
        print(f"❌ Index oluşturma hatası: {e}")


def get_places_collection():
    """Places koleksiyonunu döndür"""
    return places_collection
