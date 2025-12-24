import base64
import ffmpeg
import os
import tempfile
import uuid


def extract_audio(video_path: str) -> str:
    """
    Verilen video dosyasından mono, 16kHz wav ses dosyası çıkarır.
    Geçici bir dosya adı üretir ve path'ini döner.
    """
    audio_path = f"temp_audio_{uuid.uuid4().hex}.wav"
    (
        ffmpeg.input(video_path)
        .output(audio_path, ac=1, ar=16000)
        .overwrite_output()
        .run(quiet=True)
    )
    return audio_path


def extract_audio_from_base64(video_base64: str) -> str:
    """
    Base64 video/ses datasından geçici bir video dosyası oluşturur
    ve ondan 16kHz wav ses dosyası çıkarır.
    """
    raw = base64.b64decode(video_base64)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(raw)
        tmp_path = tmp.name

    try:
        audio_path = extract_audio(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    return audio_path


