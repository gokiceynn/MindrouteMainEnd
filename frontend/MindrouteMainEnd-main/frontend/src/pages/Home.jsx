import { useState } from "react";
import Analyzer from "./Analyzer";

export default function Home() {
  const [mood, setMood] = useState("unknown");

  return (
    <div className="relative w-screen min-h-screen bg-cover bg-center bg-no-repeat" style={{ backgroundImage: "url('/anasayfa1.png')" }}>
      <div className="absolute inset-0 bg-black bg-opacity-40"></div>

      <div className="relative z-10 text-center text-white flex flex-col items-center justify-center pt-16">
        <h1 className="text-6xl font-extrabold mb-4 drop-shadow-lg">MindRoute</h1>
        <p className="mb-6 text-xl drop-shadow-md">Duygularına Göre Şehirde Yolculuk</p>
        <div className="bg-white/10 border border-white/20 rounded-2xl px-6 py-4 mb-8">
          <p className="text-lg">Şu anda kendini şöyle hissettiğini anlıyorum:</p>
          <h2 className="text-2xl font-bold mt-2">{mood}</h2>
        </div>
      </div>

      <div className="relative z-10 pb-12">
        <Analyzer onMoodDetected={setMood} />
      </div>
    </div>
  );
}








