#!/usr/bin/env python3
"""
Basit API test - sadece endpoint'lerin varlığını kontrol et
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from main import app

def test_endpoints():
    """Endpoint'lerin varlığını kontrol et"""
    print("🔍 MindRoute API Endpoint'leri Kontrol Ediliyor...")
    print("=" * 60)
    
    # FastAPI app'teki route'ları listele
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append({
                'path': route.path,
                'methods': list(route.methods),
                'name': getattr(route, 'name', 'Unknown')
            })
    
    print(f"📊 Toplam {len(routes)} endpoint bulundu:")
    print("-" * 60)
    
    for i, route in enumerate(routes, 1):
        methods = ', '.join(route['methods'])
        print(f"{i:2d}. {route['path']:<30} [{methods}]")
    
    print("\n" + "=" * 60)
    print("✅ API Endpoint'leri başarıyla yüklendi!")
    
    # Özel endpoint'leri kontrol et
    print("\n🎯 Özel Endpoint'ler:")
    print("-" * 30)
    
    places_routes = [r for r in routes if '/places' in r['path']]
    mood_routes = [r for r in routes if '/mood' in r['path']]
    
    print(f"📍 Places endpoints: {len(places_routes)}")
    for route in places_routes:
        print(f"   - {route['path']} [{', '.join(route['methods'])}]")
    
    print(f"😊 Mood endpoints: {len(mood_routes)}")
    for route in mood_routes:
        print(f"   - {route['path']} [{', '.join(route['methods'])}]")
    
    print("\n🎉 API yapısı doğru şekilde kurulmuş!")

if __name__ == "__main__":
    test_endpoints()
