"""Flask microservice: finds top YouTube tutorials and builds AI summaries asynchronously.
Run with: python -m youtube_service.app"""
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

from common import cache, llm
from common.config import settings

app = Flask(__name__)
CORS(app)
pool = ThreadPoolExecutor(max_workers=3)
jobs = {}
jobs_lock = threading.Lock()

YT = "https://www.googleapis.com/youtube/v3"
LANGS = ["en", "en-US", "en-GB", "en-IN", "hi"]
CHAR_BUDGET = 14000  # keeps the prompt inside free-tier token limits


def _iso_to_text(d: str) -> str:
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return ""
    h, mi, s = (int(x or 0) for x in m.groups())
    return f"{h}:{mi:02d}:{s:02d}" if h else f"{mi}:{s:02d}"


@app.get("/health")
def health():
    return jsonify({"ok": True, "youtube_key": bool(settings.YOUTUBE_API_KEY)})


@app.get("/videos")
def videos():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Missing q"}), 400
    key = "search:" + q.lower()
    cached = cache.get(key, ttl=7 * 86400)
    if cached:
        return jsonify({"videos": cached, "cached": True})
    if not settings.YOUTUBE_API_KEY:
        return jsonify({"error": "YOUTUBE_API_KEY is not set in .env"}), 400
    try:
        r = requests.get(
            f"{YT}/search",
            params={"part": "snippet", "q": q, "type": "video", "maxResults": 10, "videoEmbeddable": "true",
                    "videoCaption": "closedCaption", "relevanceLanguage": "en", "safeSearch": "strict",
                    "key": settings.YOUTUBE_API_KEY},
            timeout=20,
        )
        if r.status_code != 200:
            msg = r.json().get("error", {}).get("message", r.text[:200])
            return jsonify({"error": f"YouTube API: {msg}"}), 502
        items = r.json().get("items", [])
        ids = ",".join(i["id"]["videoId"] for i in items if i.get("id", {}).get("videoId"))
        if not ids:
            return jsonify({"videos": []})
        s = requests.get(f"{YT}/videos", params={"part": "statistics,contentDetails", "id": ids,
                                                  "key": settings.YOUTUBE_API_KEY}, timeout=20)
        stats = {v["id"]: v for v in s.json().get("items", [])} if s.status_code == 200 else {}
        out = []
        for it in items:
            vid = it["id"]["videoId"]
            st = stats.get(vid, {})
            views = int(st.get("statistics", {}).get("viewCount", 0))
            likes = int(st.get("statistics", {}).get("likeCount", 0))
            out.append({
                "id": vid, "title": it["snippet"]["title"], "channel": it["snippet"]["channelTitle"],
                "thumbnail": it["snippet"]["thumbnails"].get("medium", {}).get("url", ""),
                "views": views, "likes": likes,
                "duration": _iso_to_text(st.get("contentDetails", {}).get("duration", "")),
                "score": math.log10(views + 1) + 2 * math.log10(likes + 1),
            })
        out.sort(key=lambda v: v["score"], reverse=True)
        out = out[:5]
        cache.put(key, out)
        return jsonify({"videos": out})
    except requests.RequestException as e:
        return jsonify({"error": f"Network error: {e}"}), 502


# ---------------------------------------------------------------- transcript + summary
def fetch_transcript(video_id: str):
    from youtube_transcript_api import YouTubeTranscriptApi

    try:  # youtube-transcript-api >= 1.0
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=LANGS)
        return [{"text": sn.text, "start": sn.start} for sn in fetched]
    except AttributeError:  # older versions
        data = YouTubeTranscriptApi.get_transcript(video_id, languages=LANGS)
        return [{"text": d["text"], "start": d["start"]} for d in data]


def build_blocks(snips, window=30):
    blocks, cur, start = [], [], 0
    for s in snips:
        if not cur:
            start = s["start"]
        cur.append(s["text"].replace("\n", " "))
        if s["start"] - start >= window:
            blocks.append((start, " ".join(cur)))
            cur = []
    if cur:
        blocks.append((start, " ".join(cur)))
    return blocks


def fmt_ts(sec):
    sec = int(sec)
    return f"{sec // 60:02d}:{sec % 60:02d}"


def run_job(video_id: str, title: str):
    try:
        snips = fetch_transcript(video_id)
        if not snips:
            raise RuntimeError("No transcript available for this video")
        blocks = build_blocks(snips)
        text = "\n".join(f"[{fmt_ts(t)}] {x}" for t, x in blocks)
        if len(text) > CHAR_BUDGET:
            keep = max(1, int(len(blocks) * CHAR_BUDGET / len(text)))
            step = len(blocks) / keep
            blocks = [blocks[int(i * step)] for i in range(keep)]
            text = "\n".join(f"[{fmt_ts(t)}] {x}" for t, x in blocks)
        duration = int(snips[-1]["start"])
        data = llm.chat_json([
            {"role": "system", "content": "You summarise educational videos. Output ONLY valid JSON, in English."},
            {"role": "user", "content": f"""Video title: {title}
Timestamped transcript (possibly sampled):
{text}

Return JSON: {{"executive_summary": "3-4 sentences",
"takeaways": ["exactly 5 core technical takeaways"],
"chapters": [{{"time_seconds": integer, "title": "chapter title"}}]}}
Give 5-10 chapters in chronological order. time_seconds must come from the transcript timestamps (first chapter near 0)."""},
        ], temperature=0.3, max_tokens=1500)
        chapters = []
        for c in data.get("chapters", []):
            try:
                t = int(c["time_seconds"])
            except (KeyError, TypeError, ValueError):
                continue
            chapters.append({"time_seconds": max(0, min(t, duration)), "time": fmt_ts(max(0, min(t, duration))),
                             "title": str(c.get("title", ""))[:120]})
        chapters.sort(key=lambda c: c["time_seconds"])
        result = {"executive_summary": data.get("executive_summary", ""),
                  "takeaways": data.get("takeaways", [])[:5], "chapters": chapters}
        cache.put("summary:" + video_id, result)
        with jobs_lock:
            jobs.pop(video_id, None)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "Subtitles are disabled" in msg or "No transcript" in msg:
            msg = "This video has no transcript. Pick another video."
        with jobs_lock:
            jobs[video_id] = {"status": "error", "error": msg[:400], "ts": time.time()}


@app.get("/summary/<video_id>")
def summary(video_id):
    if not re.fullmatch(r"[\w-]{11}", video_id):
        return jsonify({"error": "Bad video id"}), 400
    done = cache.get("summary:" + video_id)
    if done:
        return jsonify({"status": "done", "data": done})
    with jobs_lock:
        job = jobs.get(video_id)
        if job is None:
            jobs[video_id] = {"status": "pending", "ts": time.time()}
            pool.submit(run_job, video_id, request.args.get("title", "")[:200])
            return jsonify({"status": "pending"})
        if job["status"] == "error":
            jobs.pop(video_id, None)  # next call retries
            return jsonify({"status": "error", "error": job["error"]})
        return jsonify({"status": "pending"})


if __name__ == "__main__":
    app.run(host=settings.YOUTUBE_SERVICE_HOST, port=settings.YOUTUBE_SERVICE_PORT, debug=False, threaded=True)
