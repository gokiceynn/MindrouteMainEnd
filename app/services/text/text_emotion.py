from app.services.text_emotion import analyze_text_emotion


def predict_text_emotion(text: str) -> tuple[str, float]:
    """
    Metin duygu analizini yapar ve (mood, confidence) döner.
    Mevcut analyze_text_emotion fonksiyonunu sarmalar.
    """
    res = analyze_text_emotion(text)
    mood = res.get("text_emotion") or "neutral"
    confidence = float(res.get("confidence") or 0.0)
    return mood, confidence


__all__ = ["predict_text_emotion"]


