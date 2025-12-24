from app.config.sqlite import get_sqlite


def save_mood_log(user_id: int, mood: str, confidence: float) -> None:
    """
    Kullanıcının mood analiz sonucunu SQLite mood_logs tablosuna yazar.
    """
    conn = get_sqlite()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO mood_logs (user_id, mood, confidence) VALUES (?, ?, ?)",
            (user_id, mood, confidence),
        )
        conn.commit()
    finally:
        conn.close()


