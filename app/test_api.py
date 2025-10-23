#!/usr/bin/env python3
"""
API test scripti
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from main import app
from fastapi.testclient import TestClient

async def test_api():
    """API'yi test et"""
    # Startup event'ini manuel olarak çalıştır
    from database import connect_to_mongo, create_indexes
    
    await connect_to_mongo()
    await create_indexes()
    
    client = TestClient(app)
    
    print("🚀 MindRoute API Test Başlıyor...")
    print("=" * 50)
    
    # Test 1: Root endpoint
    print("\n📋 Test 1: Root Endpoint")
    print("-" * 30)
    try:
        response = client.get("/")
        print(f"✅ Status: {response.status_code}")
        print(f"📄 Response: {response.json()}")
    except Exception as e:
        print(f"❌ Hata: {e}")
    
    # Test 2: Places search - geçerli mood
    print("\n📋 Test 2: Places Search - Geçerli Mood")
    print("-" * 30)
    try:
        response = client.get("/places/search?mood=mutlu&lat=41.0082&lon=28.9784&limit=5")
        print(f"✅ Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"📊 Count: {data.get('count', 0)}")
            print(f"📍 Location: {data.get('location', {})}")
            print(f"🎯 Mood: {data.get('mood', 'N/A')}")
            results = data.get('results', [])
            print(f"🏢 Results: {len(results)} mekan bulundu")
            if results:
                print("   İlk mekan:", results[0].get('name', 'N/A'))
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ Hata: {e}")
    
    # Test 3: Places search - geçersiz mood
    print("\n📋 Test 3: Places Search - Geçersiz Mood")
    print("-" * 30)
    try:
        response = client.get("/places/search?mood=geçersiz&lat=41.0082&lon=28.9784")
        print(f"✅ Status: {response.status_code}")
        if response.status_code == 400:
            print("✅ Geçersiz mood doğru şekilde reddedildi")
        else:
            print(f"❌ Beklenmeyen status: {response.status_code}")
    except Exception as e:
        print(f"❌ Hata: {e}")
    
    # Test 4: Places search - farklı mood'lar
    print("\n📋 Test 4: Places Search - Farklı Mood'lar")
    print("-" * 30)
    moods = ["stresli", "huzurlu", "yalnız", "enerjik"]
    for mood in moods:
        try:
            response = client.get(f"/places/search?mood={mood}&lat=41.0082&lon=28.9784&limit=3")
            status = "✅" if response.status_code == 200 else "❌"
            print(f"   {status} {mood}: {response.status_code}")
        except Exception as e:
            print(f"   ❌ {mood}: {e}")
    
    # Test 5: Mood analyze endpoint (sadece varlığını kontrol et)
    print("\n📋 Test 5: Mood Analyze Endpoint")
    print("-" * 30)
    try:
        # OPTIONS request ile endpoint'in varlığını kontrol et
        response = client.options("/mood/analyze")
        print(f"✅ Mood analyze endpoint mevcut: {response.status_code}")
        print("ℹ️  File upload gerektiriyor, test edilemedi")
    except Exception as e:
        print(f"❌ Hata: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 API Test Tamamlandı!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_api())
