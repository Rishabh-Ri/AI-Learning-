"""Verify your setup: python -m scripts.check_setup"""
import requests
from sqlalchemy import text

from common import llm
from common.config import settings

ok = lambda m: print(f"  [OK]   {m}")  # noqa: E731
bad = lambda m: print(f"  [FAIL] {m}")  # noqa: E731


def main():
    print("1) MySQL")
    try:
        from backend.db import ensure_database, engine

        ensure_database()
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        ok("connected (database exists or was created)")
    except Exception as e:  # noqa: BLE001
        bad(f"{e}\n         -> check MySQL is running and DATABASE_URL (user/password) in .env")

    print("2) LLM (free tier)")
    if not (settings.GROQ_API_KEY or settings.GEMINI_API_KEY):
        bad("no GROQ_API_KEY or GEMINI_API_KEY set in .env")
    else:
        try:
            r = llm.chat([{"role": "user", "content": "Reply with the single word: pong"}], max_tokens=20)
            ok(f"model replied: {r.strip()[:40]}")
        except Exception as e:  # noqa: BLE001
            bad(str(e))

    print("3) Embeddings")
    v = llm.embed(["hello world"], "RETRIEVAL_QUERY")
    if v:
        ok(f"Gemini embeddings working ({len(v[0])} dims)")
    else:
        print("  [INFO] embeddings off/unavailable -> tutor will use keyword (BM25) retrieval. Fine, but Gemini key improves answers.")

    print("4) YouTube Data API")
    if not settings.YOUTUBE_API_KEY:
        bad("YOUTUBE_API_KEY not set (video recommendations disabled; everything else works)")
    else:
        r = requests.get("https://www.googleapis.com/youtube/v3/videos",
                         params={"part": "id", "id": "dQw4w9WgXcQ", "key": settings.YOUTUBE_API_KEY}, timeout=15)
        ok("key works") if r.status_code == 200 else bad(f"{r.status_code}: {r.text[:200]}")


if __name__ == "__main__":
    main()
