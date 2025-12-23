import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

const API =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8002";

export default function MiniAssistant() {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [chatHistory, setChatHistory] = useState([
    {
      role: "assistant",
      content: "Merhaba, ruh hâlini anlatmak ister misin? Beraber nefes alalım.",
      moodLabel: "başlangıç",
    },
  ]);
  const [currentMessage, setCurrentMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [latestMoodLabel, setLatestMoodLabel] = useState("");
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (isOpen && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatHistory, isOpen]);

  const handleSend = async (event) => {
    event.preventDefault();
    const trimmed = currentMessage.trim();
    if (!trimmed || isLoading) return;

    const userMessage = { role: "user", content: trimmed };
    const historyForRequest = [...chatHistory, userMessage];

    setChatHistory(historyForRequest);
    setCurrentMessage("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API}/mood/analyze/legacy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: trimmed,
        }),
      });

      if (!response.ok) {
        throw new Error("AI servisi şu anda yanıt veremedi.");
      }

      const data = await response.json();
      const mood =
        data?.result?.mood || data?.mood_label || "";
      const assistantMessage = {
        role: "assistant",
        content:
          data.reply || "Şu anda seni dinlemeye devam ediyorum.",
        moodLabel: mood,
      };

      setLatestMoodLabel(mood || "");
      setChatHistory((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("MiniAssistant error:", error);
      setChatHistory((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "Şu anda yanıt veremedim ama yanında olduğumu bilmeni isterim. Birazdan tekrar dener misin?",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const renderBubble = (message, index) => {
    const baseStyle = {
      padding: "12px 16px",
      borderRadius: "18px",
      maxWidth: "90%",
      fontSize: "14px",
      lineHeight: 1.5,
      boxShadow: "0 6px 20px rgba(0,0,0,0.15)",
      border: "1px solid rgba(255,255,255,0.1)",
      position: "relative",
      wordBreak: "break-word",
    };

    const userStyle = {
      ...baseStyle,
      alignSelf: "flex-end",
      background: "linear-gradient(135deg, #ffb347, #ff5f6d)",
      color: "#fff7ed",
      borderBottomRightRadius: "4px",
    };

    const assistantStyle = {
      ...baseStyle,
      alignSelf: "flex-start",
      backgroundColor: "rgba(255, 255, 255, 0.12)",
      color: "#f8fafc",
      borderBottomLeftRadius: "4px",
    };

    return (
      <div
        key={`${message.role}-${index}`}
        style={message.role === "user" ? userStyle : assistantStyle}
      >
        {message.content}
      </div>
    );
  };

  return (
    <>
      {/* Toggle button */}
      <button
        aria-label="Mini ruh hâli asistanını aç"
        onClick={() => setIsOpen((prev) => !prev)}
        style={{
          position: "fixed",
          bottom: "24px",
          right: "24px",
          width: "64px",
          height: "64px",
          borderRadius: "50%",
          border: "none",
          background: "linear-gradient(135deg, #ffb347, #ff5f6d)",
          color: "#fff",
          fontSize: "26px",
          boxShadow: "0 20px 50px rgba(0,0,0,0.35)",
          cursor: "pointer",
          zIndex: 999,
          transition: "transform 0.25s ease, box-shadow 0.25s ease",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = "scale(1.05)";
          e.currentTarget.style.boxShadow = "0 18px 40px rgba(0,0,0,0.55)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = "scale(1)";
          e.currentTarget.style.boxShadow = "0 20px 50px rgba(0,0,0,0.35)";
        }}
      >
        💬
      </button>

      {/* Chat panel */}
      {isOpen && (
        <div
          style={{
            position: "fixed",
            bottom: "110px",
            right: "24px",
            width: "360px",
            maxHeight: "520px",
            display: "flex",
            flexDirection: "column",
            backgroundColor: "rgba(15, 23, 42, 0.9)",
            borderRadius: "24px",
            border: "1px solid rgba(255,255,255,0.1)",
            boxShadow: "0 30px 60px rgba(0,0,0,0.45)",
            backdropFilter: "blur(16px)",
            WebkitBackdropFilter: "blur(16px)",
            zIndex: 999,
            overflow: "hidden",
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: "18px 24px",
              borderBottom: "1px solid rgba(255,255,255,0.08)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              color: "#fff",
            }}
          >
            <div>
              <div style={{ fontWeight: 700, letterSpacing: "0.02em" }}>
                Mini Ruh Hâli Asistanı
              </div>
              {latestMoodLabel && (
                <div
                  style={{
                    marginTop: "6px",
                    fontSize: "12px",
                    color: "#f97316",
                    fontWeight: 600,
                  }}
                >
                  Ruh hâlin: {latestMoodLabel}
                </div>
              )}
            </div>
            <button
              aria-label="Mini asistanı kapat"
              onClick={() => setIsOpen(false)}
              style={{
                background: "transparent",
                border: "none",
                color: "#e5e7eb",
                fontSize: "22px",
                cursor: "pointer",
              }}
            >
              ×
            </button>
          </div>

          {/* Messages */}
          <div
            style={{
              flex: 1,
              padding: "20px",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              overflowY: "auto",
            }}
          >
            {chatHistory.map((message, index) => renderBubble(message, index))}
            {isLoading && (
              <div
                style={{
                  alignSelf: "flex-start",
                  padding: "10px 16px",
                  borderRadius: "18px",
                  backgroundColor: "rgba(255, 255, 255, 0.12)",
                  color: "#fff",
                  fontSize: "14px",
                }}
              >
                Yazıyor...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <form
            onSubmit={handleSend}
            style={{
              borderTop: "1px solid rgba(255,255,255,0.08)",
              padding: "16px 18px",
              display: "flex",
              gap: "10px",
              backgroundColor: "rgba(15, 23, 42, 0.85)",
            }}
          >
            <input
              type="text"
              value={currentMessage}
              onChange={(e) => setCurrentMessage(e.target.value)}
              placeholder="Nasıl hissediyorsun?"
              style={{
                flex: 1,
                padding: "12px 14px",
                borderRadius: "14px",
                border: "1px solid rgba(255,255,255,0.15)",
                backgroundColor: "rgba(15, 23, 42, 0.6)",
                color: "#fff",
                fontSize: "14px",
                outline: "none",
              }}
            />
            <button
              type="submit"
              disabled={isLoading || !currentMessage.trim()}
              style={{
                padding: "12px 18px",
                borderRadius: "14px",
                border: "none",
                backgroundColor: isLoading ? "#94a3b8" : "#f97316",
                color: "#fff",
                fontWeight: 600,
                cursor:
                  isLoading || !currentMessage.trim() ? "not-allowed" : "pointer",
                opacity: isLoading ? 0.6 : 1,
                transition: "background-color 0.2s ease",
              }}
            >
              Gönder
            </button>
          </form>
        </div>
      )}

    </>
  );
}


