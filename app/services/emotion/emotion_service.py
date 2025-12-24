import cv2
import numpy as np
import os

# Optional import for DeepFace
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False

# Check if mock mode is enabled
EMOTION_BACKEND = os.getenv("EMOTION_BACKEND", "mock")


class EmotionService:
    def analyze_image(self, image_path: str):
        """
        Analyze emotion from a static image.
        """
        # Return mock result if deepface is not available or mock mode is enabled
        if EMOTION_BACKEND == "mock" or not DEEPFACE_AVAILABLE:
            return {
                "happy": 0.25,
                "sad": 0.15,
                "angry": 0.10,
                "surprise": 0.20,
                "fear": 0.10,
                "disgust": 0.05,
                "neutral": 0.15,
                "dominant_emotion": "happy"
            }
        
        try:
            result = DeepFace.analyze(img_path=image_path, actions=["emotion"])
            return result["emotion"]
        except Exception as e:
            return {"error": str(e)}

    def analyze_frame(self, frame: np.ndarray):
        """
        Analyze emotion directly from a video frame (OpenCV ndarray).
        """
        # Return mock result if deepface is not available or mock mode is enabled
        if EMOTION_BACKEND == "mock" or not DEEPFACE_AVAILABLE:
            return {
                "happy": 0.25,
                "sad": 0.15,
                "angry": 0.10,
                "surprise": 0.20,
                "fear": 0.10,
                "disgust": 0.05,
                "neutral": 0.15,
                "dominant_emotion": "happy"
            }
        
        try:
            # Convert frame BGR → RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = DeepFace.analyze(
                img_path=rgb, actions=["emotion"], enforce_detection=False
            )
            return result["emotion"]
        except Exception as e:
            return {"error": str(e)}

