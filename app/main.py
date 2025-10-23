# app/main.py
# Çalıştırma komutu:
# uvicorn app.main:app --reload --port 8002

import os
import cv2
import numpy as np
import tempfile
from typing import Optional
from fastapi import FastAPI, Query, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from dotenv import load_dotenv
from deepface import DeepFace
from collections import Counter

# Yeni importlar
from app.database import create_indexes, connect_to_mongo, close_mongo_connection
from app.routes import places, mood

# .env yükle
load_dotenv()

# Mongo bağlantısı (eski kod - yeni database.py kullanılacak)
MONGO_URL = os.getenv("MONGO_URL", "mongodb://127.0.0.1:27017")
client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=4000)
db = client["mindroute"]
places = db["places"]

# FastAPI uygulaması
app = FastAPI(title="MindRoute — Duygusal Navigasyon API", version="0.1.0")

# 🔹 React (localhost:5173) için CORS izni
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup ve shutdown event'leri
@app.on_event("startup")
async def startup_event():
    """Uygulama başlangıcında çalışır"""
    await connect_to_mongo()
    await create_indexes()
    print("✅ MindRoute API başlatıldı")

@app.on_event("shutdown")
async def shutdown_event():
    """Uygulama kapanırken çalışır"""
    await close_mongo_connection()
    print("✅ MindRoute API kapatıldı")

# Router'ları dahil et
app.include_router(places.router)
app.include_router(mood.router)

# 🔹 Duygu → mekan haritası (OSM field "type" ile eşleşir)
MOOD_MAP = {
    "stresli": ["park", "garden", "forest", "viewpoint"],
    "mutlu": ["cafe", "cinema", "pub", "bar", "restaurant", "fast_food"],
    "durgun": ["museum", "library", "park"],
    "enerjik": ["sports_centre", "stadium", "fitness_centre", "bar", "nightclub"],
    "neutral": ["cafe", "park", "library", "museum"]
}

# DeepFace -> MindRoute etiket eşlemesi
EMO_MAP = {
    "angry": "stresli",
    "fear": "stresli", 
    "disgust": "stresli",
    "sad": "üzgün",
    "neutral": "sakin",
    "happy": "mutlu",
    "surprise": "enerjik"
}

def map_emotion(e: str) -> str:
    e = e.lower()
    return EMO_MAP.get(e, "sakin")

# ------------------- ENDPOINTLER -------------------

@app.get("/", tags=["Home"])
def home():
    return {"status": "OK", "message": "MindRoute API aktif ✅"}

@app.get("/health", tags=["Health"])
def health():
    ok = True
    try:
        client.admin.command("ping")
    except Exception:
        ok = False
    return {"mongo": ok}

@app.get("/recommend", tags=["Recommend"])
def recommend(
    mood: str = Query(..., description="Kullanıcının ruh hali: stresli, mutlu, durgun, enerjik, neutral"),
    limit: int = Query(10, description="Maksimum dönecek mekan sayısı")
):
    mood_types = MOOD_MAP.get(mood.lower(), [])
    if not mood_types:
        return {"error": f"{mood} için tanımlı mekan türü yok."}

    # MongoDB sorgusu
    query = {"type": {"$in": mood_types}}
    results = list(places.find(query, {"_id": 0}).limit(limit))
    return {"count": len(results), "results": results}

# 🔹 Video analizi (gerçek DeepFace implementasyonu)
@app.post("/mood/analyze", tags=["Analyze"])
async def analyze_video(file: UploadFile = File(...)):
    """
    Kullanıcının yüklediği videodan ruh halini tespit eder.
    DeepFace kullanarak video karelerini analiz eder.
    """
    if not file.filename.lower().endswith((".mp4", ".mov", ".webm", ".avi", ".mkv")):
        raise HTTPException(status_code=400, detail="Lütfen bir video dosyası yükleyin.")
    
    with tempfile.NamedTemporaryFile(suffix=file.filename[file.filename.rfind("."):], delete=True) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp.flush()

        cap = cv2.VideoCapture(tmp.name)
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Video açılamadı.")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        step = max(int(fps), 1)
        frame_idx = 0
        votes = []
        faces_seen = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % step == 0:
                try:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    result = DeepFace.analyze(
                        img_path=rgb,
                        actions=["emotion"],
                        detector_backend="mtcnn",
                        enforce_detection=False
                    )
                    if isinstance(result, list):
                        for r in result:
                            if "dominant_emotion" in r:
                                faces_seen += 1
                                votes.append(map_emotion(r["dominant_emotion"]))
                    else:
                        if "dominant_emotion" in result:
                            faces_seen += 1
                            votes.append(map_emotion(result["dominant_emotion"]))
                except Exception:
                    pass
            frame_idx += 1

        cap.release()

        if not votes:
            return JSONResponse({
                "mood": "sakin",
                "confidence": 0.35,
                "reason": "Yüz tespit edilemedi; nötr varsayıldı.",
                "frames_analyzed": frame_idx,
                "faces_seen": faces_seen
            })

        counts = Counter(votes)
        top_mood, top_count = counts.most_common(1)[0]
        confidence = round(top_count / max(len(votes), 1), 3)

        return JSONResponse({
            "mood": top_mood,
            "confidence": confidence,
            "distribution": counts,
            "frames_analyzed": frame_idx,
            "faces_seen": faces_seen
        })
