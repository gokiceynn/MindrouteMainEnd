import pytest
import httpx
import sys
from pathlib import Path
from fastapi.testclient import TestClient

# app modülünü path'e ekle
sys.path.append(str(Path(__file__).parent.parent))
from main import app

client = TestClient(app)


class TestPlacesSearch:
    """Places search endpoint testleri"""
    
    def test_search_places_valid_mood(self):
        """Geçerli mood ile arama testi"""
        response = client.get(
            "/places/search",
            params={
                "mood": "mutlu",
                "lat": 41.0082,
                "lon": 28.9784,
                "radius_km": 5.0,
                "limit": 10
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Response şemasını kontrol et
        assert "mood" in data
        assert "location" in data
        assert "radius_km" in data
        assert "count" in data
        assert "results" in data
        
        assert data["mood"] == "mutlu"
        assert data["location"]["lat"] == 41.0082
        assert data["location"]["lon"] == 28.9784
        assert data["radius_km"] == 5.0
        assert isinstance(data["results"], list)
    
    def test_search_places_invalid_mood(self):
        """Geçersiz mood ile arama testi"""
        response = client.get(
            "/places/search",
            params={
                "mood": "geçersiz_mood",
                "lat": 41.0082,
                "lon": 28.9784
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Geçersiz mood" in data["detail"]
    
    def test_search_places_invalid_coordinates(self):
        """Geçersiz koordinatlar ile test"""
        # Geçersiz enlem
        response = client.get(
            "/places/search",
            params={
                "mood": "mutlu",
                "lat": 95.0,  # Geçersiz enlem
                "lon": 28.9784
            }
        )
        assert response.status_code == 422
        
        # Geçersiz boylam
        response = client.get(
            "/places/search",
            params={
                "mood": "mutlu",
                "lat": 41.0082,
                "lon": 185.0  # Geçersiz boylam
            }
        )
        assert response.status_code == 422
    
    def test_search_places_invalid_radius(self):
        """Geçersiz yarıçap ile test"""
        response = client.get(
            "/places/search",
            params={
                "mood": "mutlu",
                "lat": 41.0082,
                "lon": 28.9784,
                "radius_km": 100.0  # Çok büyük yarıçap
            }
        )
        assert response.status_code == 422
    
    def test_search_places_invalid_limit(self):
        """Geçersiz limit ile test"""
        response = client.get(
            "/places/search",
            params={
                "mood": "mutlu",
                "lat": 41.0082,
                "lon": 28.9784,
                "limit": 150  # Çok büyük limit
            }
        )
        assert response.status_code == 422
    
    def test_search_places_missing_required_params(self):
        """Gerekli parametreler eksik test"""
        # Mood eksik
        response = client.get(
            "/places/search",
            params={
                "lat": 41.0082,
                "lon": 28.9784
            }
        )
        assert response.status_code == 422
        
        # Lat eksik
        response = client.get(
            "/places/search",
            params={
                "mood": "mutlu",
                "lon": 28.9784
            }
        )
        assert response.status_code == 422
        
        # Lon eksik
        response = client.get(
            "/places/search",
            params={
                "mood": "mutlu",
                "lat": 41.0082
            }
        )
        assert response.status_code == 422
    
    def test_search_places_different_moods(self):
        """Farklı mood'lar ile test"""
        moods = ["stresli", "mutlu", "huzurlu", "yalnız", "enerjik"]
        
        for mood in moods:
            response = client.get(
                "/places/search",
                params={
                    "mood": mood,
                    "lat": 41.0082,
                    "lon": 28.9784,
                    "limit": 5
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["mood"] == mood
    
    def test_search_places_default_params(self):
        """Varsayılan parametreler ile test"""
        response = client.get(
            "/places/search",
            params={
                "mood": "mutlu",
                "lat": 41.0082,
                "lon": 28.9784
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["radius_km"] == 3.0  # Varsayılan radius
        assert len(data["results"]) <= 20  # Varsayılan limit
