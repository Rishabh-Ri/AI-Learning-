"""Central settings, loaded from the .env file in the project root."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _s(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _i(key: str, default: int) -> int:
    try:
        return int(_s(key, str(default)))
    except ValueError:
        return default


def _f(key: str, default: float) -> float:
    try:
        return float(_s(key, str(default)))
    except ValueError:
        return default


class Settings:
    BACKEND_HOST = _s("BACKEND_HOST", "127.0.0.1")
    BACKEND_PORT = _i("BACKEND_PORT", 8000)
    YOUTUBE_SERVICE_HOST = _s("YOUTUBE_SERVICE_HOST", "127.0.0.1")
    YOUTUBE_SERVICE_PORT = _i("YOUTUBE_SERVICE_PORT", 5001)
    YOUTUBE_SERVICE_URL = _s("YOUTUBE_SERVICE_URL", "http://127.0.0.1:5001").rstrip("/")

    JWT_SECRET = _s("JWT_SECRET", "dev-secret-change-me")
    JWT_EXPIRE_HOURS = _i("JWT_EXPIRE_HOURS", 168)

    DATABASE_URL = _s("DATABASE_URL", "mysql+pymysql://root:password@127.0.0.1:3306/ai_learning")

    LLM_PROVIDER = _s("LLM_PROVIDER", "groq").lower()
    GROQ_API_KEY = _s("GROQ_API_KEY")
    GROQ_MODEL = _s("GROQ_MODEL", "llama-3.3-70b-versatile")
    GEMINI_API_KEY = _s("GEMINI_API_KEY")
    GEMINI_MODEL = _s("GEMINI_MODEL", "gemini-2.5-flash")

    EMBEDDING_PROVIDER = _s("EMBEDDING_PROVIDER", "gemini").lower()
    GEMINI_EMBEDDING_MODEL = _s("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    EMBEDDING_DIMENSIONS = _i("EMBEDDING_DIMENSIONS", 768)

    YOUTUBE_API_KEY = _s("YOUTUBE_API_KEY")

    MASTERY_THRESHOLD = _f("MASTERY_THRESHOLD", 80)
    ACCEL_MIN_IW = _f("ACCELERATED_MIN_INTERVIEW_WEIGHTAGE", 70)
    ACCEL_MIN_FS = _f("ACCELERATED_MIN_FUTURE_SCOPE", 8)
    QUIZ_QUESTION_COUNT = _i("QUIZ_QUESTION_COUNT", 10)

    DATA_DIR = ROOT / "data"


settings = Settings()
settings.DATA_DIR.mkdir(exist_ok=True)
