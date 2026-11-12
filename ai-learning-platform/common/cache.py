"""Tiny JSON-file cache (protects the free YouTube / LLM quotas)."""
import json
import threading
import time

from .config import settings

_lock = threading.Lock()
_path = settings.DATA_DIR / "yt_cache.json"


def _load():
    try:
        return json.loads(_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get(key, ttl=None):
    with _lock:
        item = _load().get(key)
    if not item:
        return None
    if ttl and time.time() - item["ts"] > ttl:
        return None
    return item["value"]


def put(key, value):
    with _lock:
        data = _load()
        data[key] = {"ts": time.time(), "value": value}
        _path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
