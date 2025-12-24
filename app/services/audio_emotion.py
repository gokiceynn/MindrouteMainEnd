import numpy as np
import onnxruntime as ort
import librosa

class SpeechEmotionONNX:
    def __init__(self, model_path="speech_emo.onnx"):
        import os
        base_path = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_path, "speech_emo.onnx")
        # CPU execution provider ile session oluştur
        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.labels = ["angry", "happy", "sad", "neutral"]

    def predict(self, wav_path):
        # Ses dosyasını yükle
        audio, sr = librosa.load(wav_path, sr=16000)
        audio = audio.astype(np.float32)

        # Modelin beklediği formata sok
        input_tensor = audio.reshape(1, audio.shape[0])

        outputs = self.session.run(None, {"input": input_tensor})
        logits = outputs[0][0]

        # Softmax
        exp = np.exp(logits)
        probs = exp / np.sum(exp)

        idx = np.argmax(probs)
        return self.labels[idx], float(probs[idx])
