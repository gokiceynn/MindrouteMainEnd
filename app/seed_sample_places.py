#!/usr/bin/env python3
"""
Örnek mekan verilerini MongoDB'ye ekler.
İstanbul civarı koordinatlar kullanır.
"""

import asyncio
import os
from dotenv import load_dotenv
from app.database import connect_to_mongo, get_places_collection

# .env yükle
load_dotenv()

# Örnek mekan verileri (İstanbul civarı)
SAMPLE_PLACES = [
    {
        "name": "Emirgan Korusu",
        "type": "park",
        "location": {
            "type": "Point",
            "coordinates": [29.0500, 41.1080]  # [lon, lat]
        },
        "osm_id": 1001
    },
    {
        "name": "Starbucks Kadıköy",
        "type": "cafe",
        "location": {
            "type": "Point",
            "coordinates": [29.0260, 40.9900]
        },
        "osm_id": 1002
    },
    {
        "name": "Beylerbeyi Sarayı",
        "type": "museum",
        "location": {
            "type": "Point",
            "coordinates": [29.0400, 41.0420]
        },
        "osm_id": 1003
    },
    {
        "name": "Çamlıca Tepesi",
        "type": "viewpoint",
        "location": {
            "type": "Point",
            "coordinates": [29.0800, 41.0200]
        },
        "osm_id": 1004
    },
    {
        "name": "MacFit Beşiktaş",
        "type": "gym",
        "location": {
            "type": "Point",
            "coordinates": [29.0100, 41.0420]
        },
        "osm_id": 1005
    },
    {
        "name": "Bebek Parkı",
        "type": "garden",
        "location": {
            "type": "Point",
            "coordinates": [29.0450, 41.0800]
        },
        "osm_id": 1006
    },
    {
        "name": "Süreyya Operası",
        "type": "cinema",
        "location": {
            "type": "Point",
            "coordinates": [29.0300, 40.9850]
        },
        "osm_id": 1007
    },
    {
        "name": "Kadıköy Halk Kütüphanesi",
        "type": "library",
        "location": {
            "type": "Point",
            "coordinates": [29.0250, 40.9880]
        },
        "osm_id": 1008
    }
]


async def seed_places():
    """Örnek mekan verilerini veritabanına ekler"""
    try:
        # MongoDB'ye bağlan
        await connect_to_mongo()
        places_collection = get_places_collection()
        
        if not places_collection:
            print("❌ Veritabanı bağlantısı kurulamadı")
            return
        
        # Mevcut verileri temizle (isteğe bağlı)
        print("🗑️  Mevcut örnek veriler temizleniyor...")
        await places_collection.delete_many({"osm_id": {"$gte": 1001, "$lte": 1008}})
        
        # Yeni verileri ekle
        print("📝 Örnek mekan verileri ekleniyor...")
        result = await places_collection.insert_many(SAMPLE_PLACES)
        
        print(f"✅ {len(result.inserted_ids)} mekan başarıyla eklendi:")
        for place in SAMPLE_PLACES:
            print(f"   - {place['name']} ({place['type']})")
        
        # Eklenen verileri kontrol et
        count = await places_collection.count_documents({})
        print(f"📊 Toplam mekan sayısı: {count}")
        
    except Exception as e:
        print(f"❌ Hata oluştu: {e}")
    finally:
        # Bağlantıyı kapat
        from app.database import close_mongo_connection
        await close_mongo_connection()


if __name__ == "__main__":
    print("🌱 Örnek mekan verileri ekleniyor...")
    asyncio.run(seed_places())
