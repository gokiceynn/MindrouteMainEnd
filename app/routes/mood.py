from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from tempfile import NamedTemporaryFile
from deepface import DeepFace

router = APIRouter(prefix='/mood', tags=['mood'])

EMOTION_TO_MOOD = {
    'angry': 'stresli',
    'fear': 'stresli',
    'sad': 'yalnız',
    'neutral': 'huzurlu',
    'happy': 'mutlu',
    'surprise': 'enerjik',
    'disgust': 'stresli',
}

@router.post('/analyze')
async def analyze_mood(file: UploadFile = File(...)):
    if file.content_type not in {'image/jpeg', 'image/png'}:
        raise HTTPException(status_code=415, detail='Sadece jpeg/png yükleyin.')

    with NamedTemporaryFile(delete=True, suffix='.jpg') as tmp:
        tmp.write(await file.read())
        tmp.flush()
        try:
            res = DeepFace.analyze(
                img_path=tmp.name,
                actions=['emotion'],
                enforce_detection=False
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'DeepFace hata: {e}')

    if isinstance(res, list) and len(res) > 0:
        res = res[0]

    emotions = res.get('emotion', {})
    dominant = res.get('dominant_emotion', 'neutral')
    mood = EMOTION_TO_MOOD.get(dominant, 'huzurlu')

    return JSONResponse({
        'dominant_emotion': dominant,
        'emotions': emotions,
        'mapped_mood': mood
    })
