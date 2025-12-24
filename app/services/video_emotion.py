import cv2
import numpy as np
import onnxruntime as ort

class VideoEmotionONNX:
    def __init__(self, model_path="ferplus.onnx"):
        import os
        base_path = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_path, "ferplus.onnx")
        # CPU execution provider ile session oluştur
        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])

        # FER+ model emotion labels
        self.labels = [
            "neutral",    # 0
            "happy",      # 1
            "surprise",   # 2
            "sad",        # 3
            "anger",      # 4
            "disgust",    # 5
            "fear",       # 6
            "contempt"    # 7
        ]

        # Yüz tespiti için Haar Cascade
        # Windows'ta Türkçe karakter encoding sorununu önlemek için dosyayı direkt oku
        cascade_filename = "haarcascade_frontalface_default.xml"
        
        try:
            # cv2.data.haarcascades path'ini al
            cascade_dir = cv2.data.haarcascades
            cascade_path = os.path.join(cascade_dir, cascade_filename)
            
            # Dosya varsa içeriğini oku ve temp file'a yaz (encoding sorununu çözer)
            if os.path.exists(cascade_path):
                import tempfile
                with open(cascade_path, 'rb') as f:
                    cascade_data = f.read()
                
                # Temp file oluştur (Türkçe karakter olmayan bir yerde)
                temp_dir = tempfile.gettempdir()
                temp_path = os.path.join(temp_dir, cascade_filename)
                with open(temp_path, 'wb') as f:
                    f.write(cascade_data)
                
                self.face_detector = cv2.CascadeClassifier(temp_path)
                
                # Cascade yüklenip yüklenmediğini test et
                if self.face_detector.empty():
                    raise ValueError(f"Cascade yüklenemedi")
            else:
                raise FileNotFoundError(f"Cascade dosyası bulunamadı: {cascade_path}")
        except Exception as e:
            print(f"⚠️ Cascade yüklenirken hata: {e}")
            # Alternatif: cv2 modül path'ini direkt kullan
            import cv2 as cv2_module
            cv2_dir = os.path.dirname(cv2_module.__file__)
            cascade_path = os.path.join(cv2_dir, 'data', cascade_filename)
            
            if os.path.exists(cascade_path):
                import tempfile
                with open(cascade_path, 'rb') as f:
                    cascade_data = f.read()
                
                temp_dir = tempfile.gettempdir()
                temp_path = os.path.join(temp_dir, cascade_filename)
                with open(temp_path, 'wb') as f:
                    f.write(cascade_data)
                
                self.face_detector = cv2.CascadeClassifier(temp_path)
                if self.face_detector.empty():
                    raise RuntimeError(f"Cascade dosyası yüklenemedi")
            else:
                raise RuntimeError(f"Cascade dosyası hiçbir yerde bulunamadı")

    def analyze_frame(self, frame):
        # griye çevir
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # yüz algıla
        faces = self.face_detector.detectMultiScale(
            gray, scaleFactor=1.3, minNeighbors=5
        )

        if len(faces) == 0:
            return {"emotion": "no_face", "confidence": 0.0}

        (x, y, w, h) = faces[0]  # ilk yüz
        face = gray[y:y+h, x:x+w]

        # FER+ input boyutu: 64x64
        face = cv2.resize(face, (64, 64))
        face = face.astype(np.float32)
        face = face.reshape(1, 1, 64, 64)

        # ONNX modeline ver
        outputs = self.session.run(None, {"Input3": face})
        logits = outputs[0][0]

        # softmax
        exp = np.exp(logits)
        probs = exp / np.sum(exp)

        idx = np.argmax(probs)

        return {
            "emotion": self.labels[idx],
            "confidence": float(probs[idx])
        }
