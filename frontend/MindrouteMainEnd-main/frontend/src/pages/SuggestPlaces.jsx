import { useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import "./SuggestPlaces.css";
import LocationToggle from "../components/LocationToggle";

const API =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8002";

export default function SuggestPlaces() {
  const navigate = useNavigate();
  const location = useLocation();

  const mood = location.state?.mood || location.state?.emotion || "unknown";

  const [city, setCity] = useState("");
  const [places, setPlaces] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [geoStatus, setGeoStatus] = useState("");
  const [useGeolocation, setUseGeolocation] = useState(true);
  const [currentCoords, setCurrentCoords] = useState(null);
  const [radiusKm, setRadiusKm] = useState(2);

  // Şehir adını normalize et
  const normalizeCity = (text) => {
    return text
      .toLowerCase()
      .replace(/ı/g, "i")
      .replace(/ç/g, "c")
      .replace(/ş/g, "s")
      .replace(/ö/g, "o")
      .replace(/ü/g, "u")
      .replace(/ğ/g, "g");
  };

  const geocodeCity = async (rawCity) => {
    const normalizedCity = normalizeCity(rawCity);
    const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(
      normalizedCity
    )}`;
    const res = await fetch(url, {
      headers: {
        "User-Agent": "mindroute-frontend",
      },
    });
    if (!res.ok) {
      throw new Error("Şehir bulunamadı (geocoding hatası)");
    }
    const data = await res.json();
    if (!data || data.length === 0) {
      throw new Error("Bu şehir için koordinat bulunamadı");
    }
    const first = data[0];
    return {
      lat: parseFloat(first.lat),
      lon: parseFloat(first.lon),
    };
  };

  const getCurrentCoords = () =>
    new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        return reject(new Error("Konum alınamadı: Geolocation desteklenmiyor"));
      }
      navigator.geolocation.getCurrentPosition(
        (pos) =>
          resolve({
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
          }),
        (err) => reject(err),
        { enableHighAccuracy: true, timeout: 8000 }
      );
    });

  const getSuggestions = async () => {
    setLoading(true);
    setGeoStatus("");

    try {
      let lat = null;
      let lon = null;
      let usedGeolocation = false;

      if (useGeolocation) {
        try {
          const coords = await getCurrentCoords();
          lat = coords.lat;
          lon = coords.lon;
          usedGeolocation = true;
          setCurrentCoords({ lat, lon });
          setGeoStatus("Konum izni verildi, mevcut konum kullanılıyor.");
        } catch (geoErr) {
          setGeoStatus("Konum alınamadı, şehir ile devam ediliyor.");
        }
      }

      if (!lat || !lon) {
        if (!city.trim()) {
          alert("Konum izni yoksa lütfen bir şehir gir.");
          setLoading(false);
          return;
        }
        const cityCoords = await geocodeCity(city);
        lat = cityCoords.lat;
        lon = cityCoords.lon;
        setCurrentCoords({ lat, lon });
      }

      const params = new URLSearchParams({
        lat: String(lat),
        lon: String(lon),
        radius_km: String(radiusKm || 2),
        limit: "20",
        mood: mood,
      });

      const response = await fetch(`${API}/places/search?${params.toString()}`);
      const data = await response.json();

      const items = data.items || data.places || [];

      if (items.length > 0) {
        setPlaces(items);
        setCurrentIndex(0);
      } else {
        setPlaces([]);
        alert("Mekan bulunamadı");
      }

      if (!usedGeolocation && city) {
        setGeoStatus(`Şehirden arama: ${city}`);
      }
    } catch (err) {
      console.error(err);
      alert(err.message || "Bir hata oluştu. Lütfen tekrar deneyin.");
    } finally {
      setLoading(false);
    }
  };

  const nextPlace = () => {
    if (places.length === 0) return;
    setCurrentIndex((prev) => (prev + 1) % places.length);
  };

  const currentPlace = places[currentIndex];
  const getPhoto = (place) => {
    if (!place) return null;
    return (
      place.photo ||
      (place.photos && place.photos[0]) ||
      (place.yelp_photos && place.yelp_photos[0]) ||
      (place.google_photos && place.google_photos[0])
    );
  };

  const getRating = (place) => {
    if (!place) return null;
    return (
      place.rating ||
      place.yelp_rating ||
      place.google_rating ||
      (place.google && place.google.rating)
    );
  };

  return (
    <div className="suggest-bg">
      {/* Geri tuşu */}
      <button
        className="back-btn"
        onClick={() => navigate(-1)}
        aria-label="Geri"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ width: "20px", height: "20px" }}
        >
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>

      {/* Cam blur kutusu */}
      <div className="glass-panel">
        <h2>Duygun: {mood}</h2>

        <label style={{ fontWeight: 600 }}>Şehir Seç:</label>
        <input
          type="text"
          placeholder="Örn: İstanbul"
          value={city}
          onChange={(e) => setCity(e.target.value)}
          onKeyPress={(e) => {
            if (e.key === "Enter") {
              getSuggestions();
            }
          }}
          disabled={useGeolocation}
        />
        <label style={{ display: "flex", gap: "8px", alignItems: "center", marginTop: "8px" }}>
          <span style={{ fontWeight: 600 }}>Yarıçap (km):</span>
          <input
            type="number"
            min="0.5"
            max="10"
            step="0.5"
            value={radiusKm}
            onChange={(e) => setRadiusKm(parseFloat(e.target.value) || 2)}
            style={{ width: "80px", padding: "8px", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.4)" }}
          />
        </label>
        <LocationToggle
          checked={useGeolocation}
          onChange={(next) => setUseGeolocation(next)}
        />

        <button onClick={getSuggestions} className="suggest-btn" disabled={loading}>
          {loading ? "Yükleniyor..." : "Önerileri Getir"}
        </button>

        {geoStatus && (
          <div
            style={{
              marginTop: "12px",
              fontSize: "12px",
              opacity: 0.95,
              lineHeight: 1.5,
              backgroundColor: "rgba(255,255,255,0.08)",
              border: "1px solid rgba(255,255,255,0.18)",
              borderRadius: "10px",
              padding: "10px 12px",
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: "4px" }}>{geoStatus}</div>
            {currentCoords && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", alignItems: "center" }}>
                <span style={{ fontWeight: 600 }}>Koordinatlar:</span>
                <span>
                  {currentCoords.lat.toFixed(5)}, {currentCoords.lon.toFixed(5)}
                </span>
                <span style={{ opacity: 0.8 }}>•</span>
                <a
                  href={`https://www.google.com/maps/search/?api=1&query=${currentCoords.lat},${currentCoords.lon}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: "#10b981" }}
                >
                  Google Maps
                </a>
                <span style={{ opacity: 0.8 }}>|</span>
                <a
                  href={`https://www.openstreetmap.org/?mlat=${currentCoords.lat}&mlon=${currentCoords.lon}#map=17/${currentCoords.lat}/${currentCoords.lon}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: "#10b981" }}
                >
                  OpenStreetMap
                </a>
              </div>
            )}
          </div>
        )}

        {/* Mekan kartı */}
        {loading && <p style={{ marginTop: "20px" }}>Mekanlar yükleniyor…</p>}

        {!loading && places.length === 0 && city && (
          <p style={{ marginTop: "20px", opacity: 0.8 }}>
            Mekan önerileri burada görünecek…
          </p>
        )}

        {!loading && currentPlace && (
          <div className="place-card">
            {getPhoto(currentPlace) && (
              <img
                src={getPhoto(currentPlace)}
                alt={currentPlace.name || "Mekan fotoğrafı"}
                style={{
                  width: "100%",
                  borderRadius: "12px",
                  objectFit: "cover",
                  maxHeight: "220px",
                  marginBottom: "12px",
                }}
              />
            )}
            <h3>{currentPlace.name || "İsimsiz Mekan"}</h3>
            <p>
              <strong>Tür:</strong> {currentPlace.type || "Bilinmiyor"}
            </p>
            {getRating(currentPlace) && (
              <p>
                <strong>Puan:</strong> {getRating(currentPlace)}{" "}
                {currentPlace.rating_source ? `(${currentPlace.rating_source})` : ""}
              </p>
            )}

            <div className="place-buttons">
              <a
                href={`https://www.google.com/maps/search/?api=1&query=${currentPlace.lat},${currentPlace.lon}`}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-google"
              >
                Google Maps'te Aç
              </a>

              <a
                href={`https://www.openstreetmap.org/?mlat=${currentPlace.lat}&mlon=${currentPlace.lon}#map=18/${currentPlace.lat}/${currentPlace.lon}`}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-osm"
              >
                OpenStreetMap'te Aç
              </a>
            </div>

            {places.length > 1 && (
              <button className="next-btn" onClick={nextPlace}>
                Sonraki Mekan → ({currentIndex + 1}/{places.length})
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
