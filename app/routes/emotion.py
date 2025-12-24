from fastapi import APIRouter, UploadFile, HTTPException
import cv2
import numpy as np
import os
import uuid

# Servisler
from app.services.audio_emotion import SpeechEmotionONNX
from app.services.video_emotion import VideoEmotionONNX

router = APIRouter()

# Modelleri başlat (try-except ile hata yönetimi)
try:
    audio_model = SpeechEmotionONNX()
except Exception as e:
    print(f"⚠️ Audio emotion model yüklenemedi: {e}")
    audio_model = None

try:
    video_model = VideoEmotionONNX()
except Exception as e:
    print(f"⚠️ Video emotion model yüklenemedi: {e}")
    video_model = None


# ------------------------
# SES DUYGU ANALİZİ
# ------------------------
@router.post("/speech-emotion")
async def speech_emotion(file: UploadFile):
    if audio_model is None:
        raise HTTPException(status_code=503, detail="Audio emotion model yüklenemedi")
    
    file_id = str(uuid.uuid4())
    file_location = f"temp_audio_{file_id}.wav"

    try:
        # dosyayı kaydet
        with open(file_location, "wb") as f:
            f.write(await file.read())

        label, prob = audio_model.predict(file_location)

        return {
            "emotion": label,
            "confidence": prob
        }
    finally:
        # Geçici dosyayı sil
        if os.path.exists(file_location):
            os.remove(file_location)


# ------------------------
# VİDEO YÜZ DUYGU ANALİZİ
# ------------------------
@router.post("/video-emotion")
async def video_emotion(file: UploadFile):
    if video_model is None:
        raise HTTPException(status_code=503, detail="Video emotion model yüklenemedi")
    
    file_id = str(uuid.uuid4())
    file_location = f"temp_video_{file_id}.mp4"

    try:
        # gelen videoyu kaydet
        with open(file_location, "wb") as f:
            f.write(await file.read())

        cap = cv2.VideoCapture(file_location)
        results = []

        # kareleri tek tek işle
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            result = video_model.analyze_frame(frame)
            results.append(result)

        cap.release()

        # yüz hiç bulunmadıysa
        emotions = [r["emotion"] for r in results if r["emotion"] != "no_face"]
        if not emotions:
            return {"emotion": "no_face"}

        # majority vote
        final = max(set(emotions), key=emotions.count)

        return {
            "emotion": final,
            "frame_count": len(results)
        }
    finally:
        # Geçici dosyayı sil
        if os.path.exists(file_location):
            os.remove(file_location)
