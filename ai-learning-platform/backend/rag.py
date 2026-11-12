"""Module-scoped RAG: chunk -> embed (Gemini, free) -> store in MySQL -> hybrid retrieve (cosine + BM25).

Each module has its own `namespace`, so the tutor can only ever see the active module's content.
If embeddings are unavailable, retrieval silently falls back to pure BM25 keyword search.
"""
import math
import re
from collections import Counter

from sqlalchemy.orm import Session

from common import llm

from .models import Chunk

STOP = set(
    "a an the and or of to in on for with is are was were be been it this that as at by from how what why when "
    "which do does can i you we they me my about into than then so if".split()
)


def tokens(text: str):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 1]


def chunk_text(text: str, size: int = 900, overlap: int = 120):
    text = (text or "").strip()
    if not text:
        return []
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 2 <= size:
            cur = f"{cur}\n\n{p}".strip()
            continue
        if cur:
            chunks.append(cur)
            cur = ""
        if len(p) > size:
            start = 0
            while start < len(p):
                chunks.append(p[start : start + size])
                start += size - overlap
        else:
            cur = p
    if cur:
        chunks.append(cur)
    return chunks


def has_chunks(db: Session, namespace: str) -> bool:
    return db.query(Chunk.id).filter(Chunk.namespace == namespace).first() is not None


def ingest(db: Session, namespace: str, blocks):
    db.query(Chunk).filter(Chunk.namespace == namespace).delete()
    chunks = []
    for b in blocks:
        chunks += chunk_text(b)
    embs = llm.embed(chunks, "RETRIEVAL_DOCUMENT") or [None] * len(chunks)
    for text, emb in zip(chunks, embs):
        db.add(Chunk(namespace=namespace, text=text, embedding=emb))
    db.commit()
    return len(chunks)


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _bm25(chunks, query, k1=1.5, b=0.75):
    docs = [tokens(c.text) for c in chunks]
    n = len(docs)
    avgdl = (sum(len(d) for d in docs) / n) or 1
    df = Counter()
    for d in docs:
        df.update(set(d))
    q = tokens(query)
    scores = []
    for d in docs:
        tf = Counter(d)
        s = 0.0
        for w in q:
            if w in tf:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(d) / avgdl))
        scores.append(s)
    return scores


def retrieve(db: Session, namespace: str, query: str, k: int = 4):
    chunks = db.query(Chunk).filter(Chunk.namespace == namespace).all()
    if not chunks:
        return []
    kw = _bm25(chunks, query)
    kmax = max(kw) or 1
    kw = [s / kmax for s in kw]
    scores = kw
    if all(c.embedding for c in chunks):
        qv = llm.embed([query], "RETRIEVAL_QUERY")
        if qv:
            dense = [_cosine(qv[0], c.embedding) for c in chunks]
            scores = [0.7 * d + 0.3 * s for d, s in zip(dense, kw)]
    ranked = sorted(zip(scores, chunks), key=lambda t: t[0], reverse=True)
    return [c.text for _, c in ranked[:k]]
