from fastapi import APIRouter, HTTPException

from app.config.sqlite import get_sqlite


router = APIRouter(prefix="/users")


@router.post("/register")
def register(username: str, password: str):
    conn = get_sqlite()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password),
        )
        conn.commit()
        return {"ok": True, "msg": "User created"}
    except Exception:
        raise HTTPException(status_code=400, detail="Username already exists")
    finally:
        conn.close()


@router.post("/login")
def login(username: str, password: str):
    conn = get_sqlite()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM users WHERE username=? AND password=?",
        (username, password),
    )
    user = cur.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=400, detail="Wrong credentials")
    return {"ok": True, "user_id": user["id"]}


