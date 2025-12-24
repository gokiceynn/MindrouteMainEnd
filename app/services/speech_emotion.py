import librosa
import torch
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification


MODEL_NAME = "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"

_VOICE_MODEL_AVAILABLE = False
_voice_extractor = None
_voice_model = None

try:
    _voice_extractor = AutoFeatureExtractor.from_pretrained(MODEL_NAME)
    _voice_model = AutoModelForAudioClassification.from_pretrained(MODEL_NAME)
    _VOICE_MODEL_AVAILABLE = True
except Exception as e:  # pragma: no cover - sadece ortamda model yüklenemezse
    # Model yüklenemezse backend'in komple çökmesini engelle.
    print(f"[speech_emotion] Uyarı: Ses duygu modeli yüklenemedi: {e}")
    _VOICE_MODEL_AVAILABLE = False


emotion_labels = [
    "angry",
    "happy",
    "sad",
    "neutral",
    "fear",
    "disgust",
    "surprise",
]


def analyze_voice_emotion(wav_path: str) -> dict:
    """
    Tek bir wav dosyası üzerinden temel konuşma-duygu tahmini yapar.
    Eğer model yüklenemediyse, basit bir fallback ile 'neutral' döner.
    """
    # Model yüklü değilse basit fallback
    if not _VOICE_MODEL_AVAILABLE or _voice_extractor is None or _voice_model is None:
        return {
            "voice_emotion": "neutral",
            "voice_emotion_index": 3,
            "detail": "voice_emotion model not available; returned fallback result",
        }

    audio, sr = librosa.load(wav_path, sr=16000)
    inputs = _voice_extractor(audio, sampling_rate=16000, return_tensors="pt")
    with torch.no_grad():
        logits = _voice_model(**inputs).logits
    pred = torch.argmax(logits, dim=-1).item()

    return {
        "voice_emotion": emotion_labels[pred],
        "voice_emotion_index": pred,
    }


