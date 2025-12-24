import whisper


model_stt = whisper.load_model("small")


def speech_to_text(wav_path: str) -> str:
    """
    Verilen wav dosyasını Whisper modeli ile yazıya çevirir.
    """
    result = model_stt.transcribe(wav_path, fp16=False)
    return result["text"]


