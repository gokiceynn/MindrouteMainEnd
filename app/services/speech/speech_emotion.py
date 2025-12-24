from app.services.speech_emotion import analyze_voice_emotion


def predict_speech_emotion(wav_path: str) -> tuple[str, float]:
    """
    Konuşma duygu analizini yapar ve (mood, confidence) döner.
    Mevcut analyze_voice_emotion çıktısını basitçe sarmalar.
    Confidence şu an için 1.0 sabit veriliyor (model logit bilgisi yok).
    """
    res = analyze_voice_emotion(wav_path)
    mood = res.get("voice_emotion", "neutral")
    confidence = 1.0
    return mood, confidence


__all__ = ["predict_speech_emotion"]


