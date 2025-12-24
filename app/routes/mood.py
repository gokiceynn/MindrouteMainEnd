import base64
import os

from fastapi import APIRouter, Body, File, HTTPException, UploadFile
import cv2
import numpy as np
import tempfile

from app.models import MoodAnalyzeRequest, MoodAnalyzeResponse, MoodAnalyzeResult, MoodTextRequest, MoodTextResponse
from app.services.gemini_assistant import generate_gemini_reply, generate_gemini_mood, fallback_mood_from_text, is_gemini_ready
from app.services.mood_logger import save_mood_log
from app.services.speech.audio_extractor import extract_audio_from_base64
from app.services.speech.speech_emotion import predict_speech_emotion
from app.services.speech.speech_to_text import speech_to_text
from app.services.text.text_emotion import predict_text_emotion
from app.services.emotion.emotion_service import EmotionService
from app.services.video_emotion import VideoEmotionONNX

emotion_service = EmotionService()

# Video emotion modeli (ONNX tabanlı)
try:
    video_emotion_model = VideoEmotionONNX()
except Exception as e:
    print(f"⚠️ Video emotion model yüklenemedi: {e}")
    video_emotion_model = None


router = APIRouter(prefix="/mood", tags=["mood"])


@router.post("/analyze/legacy", response_model=MoodAnalyzeResponse)
async def analyze_mood(
    req: MoodAnalyzeRequest | None = Body(None),
    user_id: int | None = None,
    video: UploadFile | None = File(None),
):
    """
    - JSON body (text / audio_base64) VEYA
    - multipart/form-data (video dosyası)
    kabul eder.
    Herhangi bir hata olursa nötr fallback döner (demo için güvenli davranış).
    """
    payload = req or MoodAnalyzeRequest()

    try:
        # Eğer video dosyası geldiyse onu base64'e çevir
        if video is not None:
            raw_bytes = await video.read()
            payload.audio_base64 = base64.b64encode(raw_bytes).decode("utf-8")

        if not payload.text and not payload.audio_base64:
            raise HTTPException(status_code=400, detail="Provide text or audio")

        # 1) Metin analizi
        if payload.text:
            mood, confidence = predict_text_emotion(payload.text)
            source = "text"

        # 2) Ses analizi
        else:
            audio_path = extract_audio_from_base64(payload.audio_base64 or "")
            _ = speech_to_text(audio_path)  # şu an için sadece pipeline parçası, istersen loglayabiliriz
            mood, confidence = predict_speech_emotion(audio_path)
            source = "audio"

        # 3) Mood log (SQLITE)
        if user_id is not None:
            save_mood_log(user_id, mood, confidence)

        return MoodAnalyzeResponse(
            ok=True,
            result=MoodAnalyzeResult(mood=mood, confidence=confidence, source=source),
        )

    except HTTPException:
        # HTTPException'ları FastAPI'ye aynen bırak
        raise
    except Exception as e:
        # Demo senaryosu için: Backend hata verirse bile fallback dön.
        print(f"[mood.analyze] Error in pipeline: {e}")
        fallback_mood = "neutral"
        fallback_conf = 0.0
        return MoodAnalyzeResponse(
            ok=False,
            result=MoodAnalyzeResult(
                mood=fallback_mood,
                confidence=fallback_conf,
                source="error_fallback",
            ),
        )


@router.post("/analyze")
async def mood_analyze(file: UploadFile):
    video_bytes = await file.read()
    
    # Önce görsel olarak dene
    np_data = np.frombuffer(video_bytes, np.uint8)
    frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)

    if frame is None:
        # Görsel değilse video varsay: ilk kareyi oku
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(video_bytes)
                tmp.flush()
                tmp_path = tmp.name

            cap = cv2.VideoCapture(tmp_path)
            if not cap.isOpened():
                raise HTTPException(status_code=400, detail="Video açılamadı")
            
            success, frame = cap.read()
            cap.release()
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        if not success or frame is None:
            raise HTTPException(status_code=400, detail="Video/görsel kare okunamadı")

    # Önce ONNX modelini dene, yoksa DeepFace kullan
    mood = "neutral"
    confidence = 0.0
    source = "unknown"
    
    if video_emotion_model is not None:
        try:
            result = video_emotion_model.analyze_frame(frame)
            print(f"[DEBUG] Video emotion result: {result}")
            
            if result.get("emotion") == "no_face":
                return MoodAnalyzeResponse(
                    ok=False,
                    result=MoodAnalyzeResult(
                        mood="neutral",  # Frontend için neutral döndür
                        confidence=0.0,
                        source="video_onnx"
                    )
                )
            
            # Emotion'ı mood'a çevir (FER+ labels → mood)
            emotion_to_mood = {
                "happy": "mutlu",
                "sad": "üzgün",
                "anger": "stresli",
                "fear": "kaygılı",
                "surprise": "şaşkın",
                "disgust": "tiksinti",
                "contempt": "küçümseme",
                "neutral": "neutral"
            }
            
            emotion = result.get("emotion", "neutral")
            mood = emotion_to_mood.get(emotion.lower(), emotion)  # Türkçe'ye çevir veya olduğu gibi bırak
            confidence = result.get("confidence", 0.0)
            source = "video_onnx"
        except Exception as e:
            print(f"⚠️ Video emotion analizi hatası: {e}")
            # Fallback olarak DeepFace kullan
            emotion = emotion_service.analyze_frame(frame)
            
            if isinstance(emotion, dict):
                mood = emotion.get("dominant_emotion") or emotion.get("emotion") or "neutral"
                confidence = emotion.get(mood, 0.0) if mood in emotion else 0.0
                source = "deepface"
            else:
                mood = str(emotion) if emotion else "neutral"
                source = "deepface"
    else:
        # Fallback: DeepFace (mock modda çalışabilir)
        emotion = emotion_service.analyze_frame(frame)
        
        if isinstance(emotion, dict):
            mood = emotion.get("dominant_emotion") or emotion.get("emotion") or "neutral"
            confidence = emotion.get(mood, 0.0) if mood in emotion else 0.0
            source = "deepface"
        else:
            mood = str(emotion) if emotion else "neutral"
            source = "deepface"
    
    # Frontend'in beklediği format: MoodAnalyzeResponse
    return MoodAnalyzeResponse(
        ok=True,
        result=MoodAnalyzeResult(
            mood=mood,
            confidence=confidence,
            source=source
        )
    )


@router.post("/text", response_model=MoodTextResponse)
async def mood_text(req: MoodTextRequest):
    """
    MiniAssistant için Gemini AI destekli mood-text endpoint'i.
    Kullanıcı mesajına AI yanıtı üretir ve ruh halini tespit eder.
    """
    try:
        user_text = req.message or ""
        history = req.history or []
        source = req.source or "default"

        if not user_text.strip():
            raise HTTPException(status_code=400, detail="Mesaj boş olamaz")

        # Gemini hazır mı kontrol et
        if not is_gemini_ready():
            fallback_mood = fallback_mood_from_text(user_text) or "belirsiz"
            return MoodTextResponse(
                mood_label=fallback_mood,
                emotion=fallback_mood,
                reply="Şu anda yanıt veremiyorum ama yanındayım. Lütfen birazdan tekrar dene."
            )

        # Gemini AI ile yanıt üret (tek çağrı - quota tasarrufu için)
        gemini_reply = await generate_gemini_reply(history, user_text, source)
        
        # Mood tespiti: text pattern matching kullan (ek API çağrısı yok)
        mood_label = fallback_mood_from_text(user_text) or "belirsiz"
        
        # Reply varsa kullan, yoksa fallback
        final_reply = (gemini_reply and gemini_reply.strip()) or "Şu anda yanıt oluşturamadım ama seni dinliyorum. Birazdan tekrar dener misin?"

        return MoodTextResponse(
            mood_label=mood_label,
            emotion=mood_label,
            reply=final_reply
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"⚠️ mood-text endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Sunucu hatası")


