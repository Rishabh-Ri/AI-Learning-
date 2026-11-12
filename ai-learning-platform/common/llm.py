"""Thin LLM + embedding client for the FREE tiers of Groq and Google Gemini (plain HTTP, no SDKs)."""
import json
import re
import time

import requests

from .config import settings as s

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


class LLMError(Exception):
    pass


def _groq(messages, json_mode, temperature, max_tokens):
    body = {
        "model": s.GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if "gpt-oss" in s.GROQ_MODEL:
        body["reasoning_effort"] = "low"
    
    r = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {s.GROQ_API_KEY}"}, json=body, timeout=120)
    if r.status_code != 200:
        raise LLMError(f"Groq error {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def _gemini(messages, json_mode, temperature, max_tokens):
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    contents = [
        {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
        for m in messages
        if m["role"] != "system"
    ]
    gen = {"temperature": temperature, "maxOutputTokens": max(max_tokens, 4096)}
    if json_mode:
        gen["responseMimeType"] = "application/json"
    if "2.5" in s.GEMINI_MODEL and "pro" not in s.GEMINI_MODEL:
        gen["thinkingConfig"] = {"thinkingBudget": 0}
    body = {"contents": contents, "generationConfig": gen}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    r = requests.post(
        f"{GEMINI_BASE}/models/{s.GEMINI_MODEL}:generateContent",
        headers={"x-goog-api-key": s.GEMINI_API_KEY},
        json=body,
        timeout=120,
    )
    if r.status_code != 200:
        raise LLMError(f"Gemini error {r.status_code}: {r.text[:300]}")
    data = r.json()
    try:
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError):
        raise LLMError(f"Gemini returned no text: {str(data)[:300]}")


def _providers():
    order = ["groq", "gemini"] if s.LLM_PROVIDER != "gemini" else ["gemini", "groq"]
    keys = {"groq": s.GROQ_API_KEY, "gemini": s.GEMINI_API_KEY}
    return [p for p in order if keys[p]]


def chat(messages, json_mode=False, temperature=0.4, max_tokens=3000) -> str:
    """Call the primary provider; fall back to the other one if it fails (e.g. free-tier rate limit)."""
    provs = _providers()
    if not provs:
        raise LLMError("No LLM key configured. Set GROQ_API_KEY and/or GEMINI_API_KEY in .env")
    errors = []
    for p in provs:
        fn = _groq if p == "groq" else _gemini
        for attempt in range(2):
            try:
                return fn(messages, json_mode, temperature, max_tokens)
            except LLMError as e:
                errors.append(str(e))
                if "429" in str(e) and attempt == 0:
                    time.sleep(3)
                    continue
                break
            except requests.RequestException as e:
                errors.append(f"{p} network error: {e}")
                break
    raise LLMError(" | ".join(errors))


def extract_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise LLMError("Model did not return JSON")
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise LLMError(f"Could not parse model JSON: {e}")


def chat_json(messages, temperature=0.4, max_tokens=4000):
    last = None
    for _ in range(2):
        try:
            return extract_json(chat(messages, json_mode=True, temperature=temperature, max_tokens=max_tokens))
        except LLMError as e:
            last = e
    raise last


def embed(texts, task="RETRIEVAL_DOCUMENT"):
    """Return a list of vectors, or None if embeddings are disabled/unavailable (RAG then uses keyword search)."""
    if not texts:
        return []
    if s.EMBEDDING_PROVIDER != "gemini" or not s.GEMINI_API_KEY:
        return None
    try:
        out = []
        for i in range(0, len(texts), 50):
            batch = texts[i : i + 50]
            body = {
                "requests": [
                    {
                        "model": f"models/{s.GEMINI_EMBEDDING_MODEL}",
                        "content": {"parts": [{"text": t}]},
                        "taskType": task,
                        "outputDimensionality": s.EMBEDDING_DIMENSIONS,
                    }
                    for t in batch
                ]
            }
            r = requests.post(
                f"{GEMINI_BASE}/models/{s.GEMINI_EMBEDDING_MODEL}:batchEmbedContents",
                headers={"x-goog-api-key": s.GEMINI_API_KEY},
                json=body,
                timeout=60,
            )
            if r.status_code != 200:
                print(f"[embed] Gemini embedding failed ({r.status_code}): {r.text[:200]} -> using keyword search")
                return None
            out += [e["values"] for e in r.json()["embeddings"]]
        return out
    except Exception as e:  # noqa: BLE001
        print(f"[embed] failed: {e} -> using keyword search")
        return None
