import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI

# app modülünü path'e ekle
sys.path.append(str(Path(__file__).parent))

from routes import places
from routes import mood
from database import connect_to_mongo, create_indexes, close_mongo_connection

# app klasöründeki .env dosyasını yükle
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

app = FastAPI(title='MindRoute API', version='0.1.0')

@app.on_event('startup')
async def on_startup():
    """Uygulama başlangıcında MongoDB'ye bağlan ve indeksleri oluştur"""
    await connect_to_mongo()
    await create_indexes()
    print("✅ MindRoute API başlatıldı")

@app.on_event('shutdown')
async def on_shutdown():
    """Uygulama kapanırken MongoDB bağlantısını kapat"""
    await close_mongo_connection()
    print("✅ MindRoute API kapatıldı")

app.include_router(places.router)
app.include_router(mood.router)