from typing import Optional

from pydantic import BaseModel


class MoodAnalyzeRequest(BaseModel):
    text: Optional[str] = None
    audio_base64: Optional[str] = None


class MoodAnalyzeResult(BaseModel):
    mood: str
    confidence: float
    source: str  # "text" or "audio"


class MoodAnalyzeResponse(BaseModel):
    ok: bool
    result: MoodAnalyzeResult


