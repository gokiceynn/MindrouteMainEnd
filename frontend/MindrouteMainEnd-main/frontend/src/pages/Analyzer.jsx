import { useState } from "react";

const API =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8002";

const Analyzer = ({ onMoodDetected }) => {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text) return;

    const res = await fetch(`${API}/mood/analyze/legacy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });

    const data = await res.json();

    const moodLabel =
      data?.result?.mood || data?.mood_label || "neutral";
    const reply =
      data?.reply ||
      "Yazdıklarını okudum ve seni anlıyorum. Birlikte senin için uygun mekanları bulalım.";

    setMessages((prev) => [
      ...prev,
      { from: "user", text },
      { from: "bot", text: reply }
    ]);

    if (onMoodDetected && moodLabel) {
      onMoodDetected(moodLabel);
    }

    setInput("");
  };

  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center bg-gradient-to-br from-indigo-900 to-indigo-700 text-white p-6">
      <h1 className="text-4xl font-bold mb-4">Video Analiz Sayfası</h1>
      <p className="text-lg mb-6">Burada videonu yükleyip ruh hali analizini yapacağız.</p>

      <div className="w-full max-w-2xl bg-white/10 border border-white/20 rounded-2xl p-4 space-y-3">
        <div className="flex space-x-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ruh hâlini yaz..."
            className="flex-1 px-3 py-2 rounded-lg text-black"
          />
          <button
            onClick={sendMessage}
            className="px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white font-semibold rounded-lg"
          >
            Gönder
          </button>
        </div>

        <div className="h-64 overflow-y-auto space-y-2">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`px-3 py-2 rounded-lg ${
                m.from === "user" ? "bg-orange-500 text-white ml-auto max-w-[80%]" : "bg-white/20 text-white max-w-[80%]"
              }`}
            >
              {m.text}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Analyzer;



