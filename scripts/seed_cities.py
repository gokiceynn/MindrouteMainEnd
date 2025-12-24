#!/usr/bin/env python3
"""
Türkiye şehirlerini CSV'den okuyup fetch_places.py ile MongoDB'ye seed eden script.

Kullanım:
    python scripts/seed_cities.py
"""

import os
import sys
import csv
import subprocess
import time
import random
from pathlib import Path
from dotenv import load_dotenv

# .env yükle
load_dotenv()

# Proje kök dizini (bu script scripts/ içinde)
PROJECT_ROOT = Path(__file__).parent.parent
CSV_PATH = PROJECT_ROOT / "data" / "cities_tr.csv"
FETCH_SCRIPT = PROJECT_ROOT / "app" / "fetch_places.py"

def read_cities(csv_path):
    """CSV'den şehir adlarını oku"""
    cities = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0].strip():
                    # CSV formatından şehir adını temizle
                    city = row[0].strip().strip('"')
                    if city:
                        cities.append(city)
    except FileNotFoundError:
        print(f"❌ CSV dosyası bulunamadı: {csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ CSV okuma hatası: {e}")
        sys.exit(1)
    
    return cities

def run_fetch_places(city_name, grid_size_m=1000, sleep_ms=600, limit=5000,
                     amenities=None, leisure=None, tourism=None,
                     shop=None, healthcare=None, sport=None):
    """fetch_places.py'yi subprocess ile çağır"""
    
    # Python interpreter
    python = sys.executable
    
    # Komut argümanları
    cmd = [
        str(python),
        str(FETCH_SCRIPT),
        "--city", city_name,
        "--grid-size-m", str(grid_size_m),
        "--sleep-ms", str(sleep_ms),
        "--limit", str(limit),
    ]
    
    # Opsiyonel filtreler
    if amenities:
        cmd.extend(["--amenities", amenities])
    if leisure:
        cmd.extend(["--leisure", leisure])
    if tourism:
        cmd.extend(["--tourism", tourism])
    if shop:
        cmd.extend(["--shop", shop])
    if healthcare:
        cmd.extend(["--healthcare", healthcare])
    if sport:
        cmd.extend(["--sport", sport])
    
    print(f"\n{'='*80}")
    print(f"🏙️  Şehir işleniyor: {city_name}")
    print(f"📝 Komut: {' '.join(cmd)}")
    print(f"{'='*80}\n")
    
    # Subprocess çalıştır
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=False,  # Output'u direkt göster
            text=True,
            check=False  # Hata olsa bile devam et
        )
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Subprocess hatası: {e}")
        return False

def main():
    """Ana fonksiyon"""
    print("🚀 Türkiye şehirleri seed işlemi başlıyor...")
    print(f"📂 CSV: {CSV_PATH}")
    print(f"📂 Script: {FETCH_SCRIPT}\n")
    
    # Şehirleri oku
    cities = read_cities(CSV_PATH)
    total_cities = len(cities)
    print(f"✅ {total_cities} şehir bulundu.\n")
    
    # Varsayılan filtreler (fetch_places.py ile uyumlu)
    amenities = "restaurant,cafe,fast_food,library,school,university,place_of_worship"
    leisure = "park,garden,fitness_centre"
    tourism = "museum,hotel,hostel,information,viewpoint"
    shop = "supermarket,bakery,chemist,convenience,clothes,books"
    healthcare = "clinic,doctor,pharmacy"
    sport = "fitness,swimming,tennis,football"
    
    # Her şehir için işlem yap
    success_count = 0
    failed_count = 0
    
    for i, city in enumerate(cities, 1):
        print(f"\n{'#'*80}")
        print(f"📍 [{i}/{total_cities}] {city}")
        print(f"{'#'*80}\n")
        
        # fetch_places.py çağır
        success = run_fetch_places(
            city_name=city,
            grid_size_m=1000,
            sleep_ms=600,
            limit=5000,
            amenities=amenities,
            leisure=leisure,
            tourism=tourism,
            shop=shop,
            healthcare=healthcare,
            sport=sport
        )
        
        if success:
            success_count += 1
            print(f"\n✅ [{i}/{total_cities}] {city} başarıyla tamamlandı.")
        else:
            failed_count += 1
            print(f"\n❌ [{i}/{total_cities}] {city} işlenirken hata oluştu.")
        
        # Son şehir değilse bekleme (rate-limit için)
        if i < total_cities:
            wait_time = random.randint(10, 20)
            print(f"\n⏳ Sonraki şehre geçmeden önce {wait_time} saniye bekleniyor...")
            time.sleep(wait_time)
    
    # Özet
    print(f"\n{'='*80}")
    print(f"📊 İşlem Tamamlandı")
    print(f"{'='*80}")
    print(f"✅ Başarılı: {success_count}/{total_cities}")
    print(f"❌ Başarısız: {failed_count}/{total_cities}")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
