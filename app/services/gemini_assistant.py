"""
Gemini AI Mini Asistan Servisi
FastAPI backend için Gemini AI entegrasyonu
"""
import os
from typing import Optional, List, Dict
import google.generativeai as genai

# Gemini API key'ini environment variable'dan al
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini client'ı başlat
gemini_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Kullanılabilir modelleri listele ve uygun olanı bul
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            print(f"📋 Kullanılabilir Gemini modelleri: {available_models}")
            
            # Öncelik sırasına göre model seç (free tier için uygun modeller)
            preferred_models = [
                "models/gemini-2.5-flash",  # Yeni free tier model
                "models/gemini-2.0-flash-lite",  # Lite versiyonu daha uygun
                "models/gemini-flash-latest",  # Latest flash
                "models/gemini-2.0-flash",  # Flash model
            ]
            
            selected_model = None
            for pref in preferred_models:
                # Tam eşleşme kontrolü
                if pref in available_models:
                    selected_model = pref
                    break
                # Kısmi eşleşme kontrolü (model adının son kısmı)
                model_suffix = pref.split('/')[-1]
                for avail in available_models:
                    if model_suffix in avail or avail.endswith(model_suffix):
                        selected_model = avail
                        break
                if selected_model:
                    break
            
            # Eğer öncelikli modeller bulunamazsa, ilk kullanılabilir modeli kullan
            if not selected_model and available_models:
                selected_model = available_models[0]
            
            if selected_model:
                # Model'i başlat (test çağrısı yapmadan - quota tasarrufu için)
                gemini_model = genai.GenerativeModel(
                    model_name=selected_model,
                    system_instruction="Sen MindRoute web sitesinin mini destek asistanısın. Türkçe yanıt ver, net, sıcak ve empatik ol. Kullanıcı bir sorun ya da istek yazdığında önce kısa özetle, gerekirse 1-3 adımlık yönlendirme sun, ihtiyaç varsa hangi bilgileri vermesi gerektiğini sor. Tıbbi veya hukuki iddialar kullanma. Yanıtlarını tam ve anlaşılır tut, gereksiz kısaltma yapma."
                )
                print(f"✅ Gemini AI model başarıyla yüklendi: {selected_model}")
            else:
                print("⚠️ Kullanılabilir Gemini model bulunamadı")
                gemini_model = None
        except Exception as list_error:
            print(f"⚠️ Model listesi alınamadı, varsayılan model deneniyor: {list_error}")
            # Fallback: varsayılan model adlarını dene (free tier için)
            model_names_to_try = [
                "models/gemini-2.5-flash",
                "models/gemini-2.0-flash-lite",
                "models/gemini-flash-latest",
                "models/gemini-pro",
            ]
            gemini_model = None
            last_error = None
            
            for model_name in model_names_to_try:
                try:
                    gemini_model = genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction="Sen MindRoute web sitesinin mini destek asistanısın. Türkçe yanıt ver, net, sıcak ve empatik ol. Kullanıcı bir sorun ya da istek yazdığında önce kısa özetle, gerekirse 1-3 adımlık yönlendirme sun, ihtiyaç varsa hangi bilgileri vermesi gerektiğini sor. Tıbbi veya hukuki iddialar kullanma. Yanıtlarını tam ve anlaşılır tut, gereksiz kısaltma yapma."
                    )
                    # Test çağrısı yapmadan direkt kullan (quota tasarrufu)
                    print(f"✅ Gemini AI model başarıyla yüklendi: {model_name}")
                    break
                except Exception as e:
                    last_error = e
                    gemini_model = None
                    continue
            
            if gemini_model is None:
                print(f"⚠️ Hiçbir Gemini model yüklenemedi. Son hata: {last_error}")
    except Exception as e:
        print(f"⚠️ Gemini AI yapılandırma hatası: {e}")
        gemini_model = None
else:
    print("⚠️ GEMINI_API_KEY bulunamadı, Gemini AI devre dışı")


def normalize_token(token: str) -> str:
    """Token'ı normalize et (Türkçe karakterler için)."""
    return (token or '').lower().replace('ç', 'c').replace('ğ', 'g').replace('ı', 'i').replace('ö', 'o').replace('ş', 's').replace('ü', 'u')


ALLOWED_MOODS = ["mutlu", "üzgün", "kaygılı", "öfkeli", "yorgun", "heyecanlı", "nötr"]
MOOD_SYNONYMS = {
    "sad": "üzgün", "unhappy": "üzgün", "depressed": "üzgün", "blues": "üzgün",
    "angry": "öfkeli", "mad": "öfkeli", "furious": "öfkeli",
    "anxious": "kaygılı", "worry": "kaygılı", "worried": "kaygılı", "nervous": "kaygılı",
    "tired": "yorgun", "exhausted": "yorgun", "sleepy": "yorgun",
    "excited": "heyecanlı", "thrilled": "heyecanlı",
    "happy": "mutlu", "joy": "mutlu", "joyful": "mutlu", "cheerful": "mutlu",
    "neutral": "nötr", "calm": "nötr"
}


def fallback_mood_from_text(text: str) -> Optional[str]:
    """Text'ten basit pattern matching ile mood tespit et (fallback)."""
    if not text:
        return None
    norm = normalize_token(text)
    patterns = [
        {"key": "mutlu", "terms": ["mutlu", "sevindim", "çok sevindim", "harika", "iyi hissediyorum"]},
        {"key": "üzgün", "terms": ["üzgün", "üzüldüm", "kederli", "moralsiz", "yıkıldım"]},
        {"key": "kaygılı", "terms": ["kaygılı", "endişe", "korku", "gergin", "telaş"]},
        {"key": "öfkeli", "terms": ["öfkeli", "sinirli", "kızgın", "çok sinirliyim"]},
        {"key": "yorgun", "terms": ["yorgun", "bitkin", "uykusuz", "halsiz"]},
        {"key": "heyecanlı", "terms": ["heyecanlı", "sabırsız", "meraklı"]},
    ]
    for pattern in patterns:
        if any(term in norm for term in pattern["terms"]):
            return pattern["key"]
    return None


async def generate_gemini_reply(history: List[Dict], latest_user_text: str, source: str = "default") -> Optional[str]:
    """Gemini AI ile kullanıcı mesajına yanıt üretir."""
    if not gemini_model:
        return None
    
    try:
        # Basit prompt ile yanıt üret (chat session yerine - daha az API çağrısı)
        safe_history = history if isinstance(history, list) else []
        
        # Conversation context'i oluştur (son 3 mesaj)
        context_parts = []
        recent_history = safe_history[-3:] if len(safe_history) > 3 else safe_history
        for item in recent_history:
            if isinstance(item, dict) and "content" in item:
                role = item.get("role", "")
                content = item["content"]
                if role == "user":
                    context_parts.append(f"Kullanıcı: {content}")
                elif role == "assistant":
                    context_parts.append(f"Asistan: {content}")
        
        # Son kullanıcı mesajını ekle
        if latest_user_text:
            context_parts.append(f"Kullanıcı: {latest_user_text}")
        
        # Full prompt
        full_prompt = "\n".join(context_parts) if context_parts else latest_user_text
        
        # Gemini'ye gönder (rate limit için retry mekanizması olmadan direkt)
        response = gemini_model.generate_content(
            full_prompt,
            generation_config={
                "max_output_tokens": 1024,  # Artırıldı: 256 -> 1024 (tam cevaplar için)
                "temperature": 0.7,
            }
        )
        text = response.text if hasattr(response, 'text') else None
        return text.strip() if text else None
    except Exception as e:
        # 429 quota hatası için sessizce devam et (fallback kullanılacak)
        error_str = str(e)
        if "429" in error_str or "quota" in error_str.lower() or "ResourceExhausted" in error_str:
            print(f"⚠️ Gemini quota limiti aşıldı, fallback kullanılacak")
        else:
            print(f"⚠️ Gemini reply error: {e}")
        return None


async def generate_gemini_mood(history: List[Dict], latest_user_text: str) -> Optional[str]:
    """Gemini AI ile kullanıcının ruh halini tespit eder. 
    NOT: Quota tasarrufu için bu fonksiyon kullanılmıyor, reply'den mood çıkarılıyor.
    """
    # Quota tasarrufu için mood tespiti devre dışı - text pattern matching kullanılıyor
    return None


def is_gemini_ready() -> bool:
    """Gemini model'in hazır olup olmadığını kontrol eder."""
    return gemini_model is not None

