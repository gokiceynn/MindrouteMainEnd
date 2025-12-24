import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification


_TEXT_MODEL_NAME = "j-hartmann/emotion-english-distilroberta-base"

_TEXT_MODEL_AVAILABLE = False
_text_tokenizer = None
_text_model = None

try:
    _text_tokenizer = AutoTokenizer.from_pretrained(_TEXT_MODEL_NAME)
    _text_model = AutoModelForSequenceClassification.from_pretrained(_TEXT_MODEL_NAME)
    _TEXT_MODEL_AVAILABLE = True
except Exception as e:  # pragma: no cover - sadece ortamda model yüklenemezse
    print(f"[text_emotion] Uyarı: Metin duygu modeli yüklenemedi: {e}")
    _TEXT_MODEL_AVAILABLE = False


def analyze_text_emotion(text: str) -> dict:
    """
    Metin bazlı duygu analizi yapar.
    Boş veya sadece whitespace ise nötr bir sonuç döner.
    Model yüklenemediyse fallback döner.
    """
    if not text or text.strip() == "":
        return {"text_emotion": None, "confidence": 0.0}

    if not _TEXT_MODEL_AVAILABLE or _text_model is None or _text_tokenizer is None:
        return {
            "text_emotion": "neutral",
            "confidence": 0.0,
            "detail": "text_emotion model not available; returned fallback result",
        }

    inputs = _text_tokenizer(text, return_tensors="pt", truncation=True)
    with torch.no_grad():
        outputs = _text_model(**inputs)
        logits = outputs.logits
        probs = torch.softmax(logits, dim=-1)[0]
        pred_idx = int(torch.argmax(probs).item())
        confidence = float(probs[pred_idx].item())

    label = _text_model.config.id2label.get(pred_idx, str(pred_idx))
    return {
        "text_emotion": label,
        "confidence": confidence,
    }




