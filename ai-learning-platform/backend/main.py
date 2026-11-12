"""FastAPI backend: auth, roadmaps (FULL / ACCELERATED), modules, RAG tutor, YouTube proxy, quizzes, skills."""
import secrets
from contextlib import asynccontextmanager
from typing import Optional

import requests
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common.config import ROOT, settings
from common.llm import LLMError

from . import ai_tasks, rag, security, seed
from .db import SessionLocal, get_db, init_db
from .models import Module, Progress, Quiz, QuizAttempt, Roadmap, User


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as e:  # noqa: BLE001
        print("\n[!] Could not connect to MySQL. Check that MySQL is running and DATABASE_URL in .env is correct.")
        print(f"    Details: {e}\n")
        raise
    with SessionLocal() as db:
        seed.run(db)
    yield


app = FastAPI(title="AI Learning Platform", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer(auto_error=False)


# ------------------------------------------------------------------ helpers
def current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(401, "Not authenticated")
    uid = security.decode_token(creds.credentials)
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(401, "Invalid or expired token")
    return user


def llm_guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except LLMError as e:
        raise HTTPException(503, f"AI service error: {e}")


def accelerated_ok(m: Module) -> bool:
    return m.interview_weightage >= settings.ACCEL_MIN_IW or m.future_scope >= settings.ACCEL_MIN_FS


def get_module(db: Session, module_id: str) -> Module:
    m = db.query(Module).filter(Module.module_id == module_id).first()
    if not m:
        raise HTTPException(404, "Module not found")
    return m


def roadmap_modules(db: Session, roadmap_id: int):
    return db.query(Module).filter(Module.roadmap_id == roadmap_id).order_by(Module.order_index).all()


def compute_status(db: Session, user_id: int, mods, track: str):
    in_track = [m for m in mods if track != "ACCELERATED" or accelerated_ok(m)]
    ids = {m.module_id for m in in_track}
    prog = {p.module_pk: p for p in db.query(Progress).filter(Progress.user_id == user_id).all()}
    mastered = {m.module_id for m in in_track if prog.get(m.id) and prog[m.id].status == "mastered"}
    out = {}
    for m in in_track:
        p = prog.get(m.id)
        if m.module_id in mastered:
            st = "mastered"
        else:
            pre = [x for x in (m.prerequisites or []) if x in ids]  # skipped prerequisites are ignored
            if all(x in mastered for x in pre):
                st = "in_progress" if p and p.attempts else "available"
            else:
                st = "locked"
        out[m.module_id] = {"status": st, "best_score": p.best_score if p else 0, "attempts": p.attempts if p else 0}
    return in_track, out


def ser_module(m: Module, st: Optional[dict] = None) -> dict:
    d = {
        "module_id": m.module_id, "title": m.title, "phase": m.phase, "order": m.order_index,
        "prerequisites": m.prerequisites, "track_eligibility": m.track_eligibility,
        "metrics": {
            "interview_weightage": f"{m.interview_weightage}%",
            "interview_weightage_value": m.interview_weightage,
            "theoretical_importance": m.theoretical_importance,
            "future_scope": m.future_scope,
            "estimated_time_minutes": m.estimated_time_minutes,
        },
        "integrations": {"youtube_keywords": m.youtube_keywords, "vector_index_namespace": m.vector_index_namespace},
    }
    if st:
        d.update(st)
    return d


def ensure_content(db: Session, m: Module, rm: Roadmap):
    c = m.content or {}
    if not c.get("theoretical_summary"):
        m.content = llm_guard(ai_tasks.generate_content, m, rm)
        db.commit()
        rag.ingest(db, m.vector_index_namespace, ai_tasks.content_blocks(m))
    elif not rag.has_chunks(db, m.vector_index_namespace):
        rag.ingest(db, m.vector_index_namespace, ai_tasks.content_blocks(m))
    return m.content


# ------------------------------------------------------------------ schemas
class RegisterIn(BaseModel):
    email: str
    password: str
    name: str


class LoginIn(BaseModel):
    email: str
    password: str


class GenerateIn(BaseModel):
    topic: str
    level: str = "professional"
    count: int = 8


class ChatIn(BaseModel):
    message: str
    history: list = []
    mode: str = "normal"


class SubmitIn(BaseModel):
    answers: list


# ------------------------------------------------------------------ auth
@app.get("/api/health")
def health():
    return {"ok": True, "llm_providers": [p for p in ("groq", "gemini")
            if (settings.GROQ_API_KEY if p == "groq" else settings.GEMINI_API_KEY)],
            "youtube_key": bool(settings.YOUTUBE_API_KEY), "embeddings": settings.EMBEDDING_PROVIDER}


@app.post("/api/auth/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if "@" not in email or len(body.password) < 6:
        raise HTTPException(400, "Enter a valid email and a password of at least 6 characters")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "Email already registered")
    u = User(email=email, name=body.name.strip()[:100] or email, password_hash=security.hash_password(body.password))
    db.add(u)
    db.commit()
    return {"token": security.create_token(u.id), "user": {"id": u.id, "name": u.name, "email": u.email}}


@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not u or not security.verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return {"token": security.create_token(u.id), "user": {"id": u.id, "name": u.name, "email": u.email}}


# ------------------------------------------------------------------ roadmaps
@app.get("/api/levels")
def levels():
    return [{"key": k, "label": v["label"]} for k, v in ai_tasks.LEVELS.items()]


@app.get("/api/roadmaps")
def list_roadmaps(user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for rm in db.query(Roadmap).order_by(Roadmap.id).all():
        mods = roadmap_modules(db, rm.id)
        _, st = compute_status(db, user.id, mods, "FULL")
        done = sum(1 for v in st.values() if v["status"] == "mastered")
        out.append({"slug": rm.slug, "title": rm.title, "description": rm.description, "level": rm.level,
                    "level_label": ai_tasks.LEVELS.get(rm.level, {}).get("label", rm.level),
                    "module_count": len(mods), "mastered": done})
    return out


@app.post("/api/roadmaps/generate")
def generate_roadmap(body: GenerateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    topic = body.topic.strip()[:150]
    if len(topic) < 3:
        raise HTTPException(400, "Enter a topic")
    if body.level not in ai_tasks.LEVELS:
        raise HTTPException(400, "Unknown level")
    data = llm_guard(ai_tasks.generate_roadmap, topic, body.level, body.count)
    token = secrets.token_hex(3)
    rm = seed.create_roadmap(
        db, slug=f"{seed.slugify(topic)[:50]}-{token}", prefix=f"g{token}", title=data["title"],
        description=data["description"], level=body.level, modules=data["modules"], created_by=user.id,
    )
    return {"slug": rm.slug}


@app.get("/api/roadmaps/{slug}")
def get_roadmap(slug: str, track: str = "FULL", user: User = Depends(current_user), db: Session = Depends(get_db)):
    rm = db.query(Roadmap).filter(Roadmap.slug == slug).first()
    if not rm:
        raise HTTPException(404, "Roadmap not found")
    track = "ACCELERATED" if track.upper() == "ACCELERATED" else "FULL"
    mods = roadmap_modules(db, rm.id)
    in_track, st = compute_status(db, user.id, mods, track)
    return {
        "roadmap": {"slug": rm.slug, "title": rm.title, "description": rm.description, "level": rm.level,
                    "level_label": ai_tasks.LEVELS.get(rm.level, {}).get("label", rm.level)},
        "track": track, "total_modules": len(mods), "visible_modules": len(in_track),
        "modules": [ser_module(m, st[m.module_id]) for m in in_track],
    }


@app.get("/api/roadmaps/{slug}/skills")
def skills(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rm = db.query(Roadmap).filter(Roadmap.slug == slug).first()
    if not rm:
        raise HTTPException(404, "Roadmap not found")
    mods = roadmap_modules(db, rm.id)
    prog = {p.module_pk: p for p in db.query(Progress).filter(Progress.user_id == user.id).all()}
    phases = {}
    for m in mods:
        ph = phases.setdefault(m.phase, {"phase": m.phase, "total": 0, "mastered": 0, "score_sum": 0.0})
        ph["total"] += 1
        p = prog.get(m.id)
        if p:
            ph["score_sum"] += p.best_score
            ph["mastered"] += 1 if p.status == "mastered" else 0
    result = [{"phase": v["phase"], "score": round(v["score_sum"] / v["total"], 1), "mastered": v["mastered"], "total": v["total"]}
              for v in phases.values()]
    weak = [r["phase"] for r in result if r["score"] < settings.MASTERY_THRESHOLD]
    return {"phases": result, "weak_phases": weak}


# ------------------------------------------------------------------ modules
@app.get("/api/modules/{module_id}")
def module_detail(module_id: str, track: str = "FULL", user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = get_module(db, module_id)
    rm = db.get(Roadmap, m.roadmap_id)
    mods = roadmap_modules(db, rm.id)
    track = "ACCELERATED" if track.upper() == "ACCELERATED" else "FULL"
    in_track, st = compute_status(db, user.id, mods, track)
    if m.module_id not in st:  # module hidden in accelerated track but opened directly -> evaluate in FULL
        in_track, st = compute_status(db, user.id, mods, "FULL")
    if st[m.module_id]["status"] == "locked":
        raise HTTPException(403, "Locked: master the prerequisite modules first (score >= "
                            f"{int(settings.MASTERY_THRESHOLD)}% on their quizzes).")
    content = ensure_content(db, m, rm)
    ids = [x.module_id for x in in_track]
    i = ids.index(m.module_id) if m.module_id in ids else -1
    return {
        "module": ser_module(m, st[m.module_id]), "content": content,
        "roadmap": {"slug": rm.slug, "title": rm.title, "level": rm.level},
        "prev": ids[i - 1] if i > 0 else None, "next": ids[i + 1] if 0 <= i < len(ids) - 1 else None,
    }


@app.post("/api/modules/{module_id}/chat")
def module_chat(module_id: str, body: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    msg = body.message.strip()[:1500]
    if not msg:
        raise HTTPException(400, "Empty message")
    if ai_tasks.looks_like_injection(msg):
        return {"answer": "I can only help with this module's topic. Ask me something about it and I'll gladly explain.", "sources": []}
    m = get_module(db, module_id)
    rm = db.get(Roadmap, m.roadmap_id)
    ensure_content(db, m, rm)
    ctx = rag.retrieve(db, m.vector_index_namespace, f"{msg} {m.title}", k=4)
    answer = llm_guard(ai_tasks.tutor_answer, m, rm, ctx, body.history, msg, body.mode)
    return {"answer": answer, "sources": [c[:140] + "..." for c in ctx[:3]]}


# ------------------------------------------------------------------ YouTube (proxy to Flask microservice)
def _yt(path: str, params: dict, timeout=30):
    try:
        r = requests.get(f"{settings.YOUTUBE_SERVICE_URL}{path}", params=params, timeout=timeout)
    except requests.ConnectionError:
        raise HTTPException(503, "YouTube service is not running. Start it with run_all.bat (or the VSCode 'YouTube Service' launch config).")
    except requests.RequestException as e:
        raise HTTPException(503, f"YouTube service error: {e}")
    data = r.json() if r.content else {}
    if r.status_code != 200:
        raise HTTPException(r.status_code if r.status_code < 500 else 502, data.get("error", "YouTube service error"))
    return data


@app.get("/api/modules/{module_id}/videos")
def module_videos(module_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = get_module(db, module_id)
    kws = m.youtube_keywords or [f"{m.title} tutorial"]
    return _yt("/videos", {"q": kws[0]})


@app.get("/api/youtube/{video_id}/summary")
def video_summary(video_id: str, title: str = Query("", max_length=200), user: User = Depends(current_user)):
    return _yt(f"/summary/{video_id}", {"title": title})


# ------------------------------------------------------------------ quiz / evaluation engine
@app.post("/api/modules/{module_id}/quiz")
def new_quiz(module_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = get_module(db, module_id)
    rm = db.get(Roadmap, m.roadmap_id)
    ensure_content(db, m, rm)
    questions = llm_guard(ai_tasks.generate_quiz, m, rm, settings.QUIZ_QUESTION_COUNT)
    q = Quiz(user_id=user.id, module_pk=m.id, questions=questions)
    db.add(q)
    db.commit()
    return {"quiz_id": q.id, "threshold": settings.MASTERY_THRESHOLD,
            "questions": [{"type": x["type"], "question": x["question"], "options": x["options"]} for x in questions]}


@app.post("/api/quiz/{quiz_id}/submit")
def submit_quiz(quiz_id: int, body: SubmitIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    quiz = db.get(Quiz, quiz_id)
    if not quiz or quiz.user_id != user.id:
        raise HTTPException(404, "Quiz not found")
    m = db.get(Module, quiz.module_pk)
    rm = db.get(Roadmap, m.roadmap_id)
    results, breakdown, correct = [], {}, 0
    for i, q in enumerate(quiz.questions):
        given = body.answers[i] if i < len(body.answers) else None
        ok = given == q["answer_index"]
        correct += 1 if ok else 0
        b = breakdown.setdefault(q["type"], {"correct": 0, "total": 0})
        b["total"] += 1
        b["correct"] += 1 if ok else 0
        results.append({"type": q["type"], "question": q["question"], "options": q["options"],
                        "your_index": given, "answer_index": q["answer_index"], "correct": ok,
                        "explanation": q["explanation"]})
    total = len(quiz.questions)
    score = round(100 * correct / total, 1)
    passed = score >= settings.MASTERY_THRESHOLD

    p = db.query(Progress).filter(Progress.user_id == user.id, Progress.module_pk == m.id).first()
    if not p:
        p = Progress(user_id=user.id, module_pk=m.id, status="in_progress", best_score=0, attempts=0)
        db.add(p)
    p.attempts += 1
    p.best_score = max(p.best_score or 0, score)
    if passed:
        p.status = "mastered"
    db.add(QuizAttempt(user_id=user.id, module_pk=m.id, quiz_id=quiz.id, score=score, breakdown=breakdown))
    db.commit()

    remediation = None
    if not passed:
        wrong = [{"question": r["question"], "your": r["options"][r["your_index"]] if isinstance(r["your_index"], int) and 0 <= r["your_index"] < 4 else "(no answer)",
                  "correct": r["options"][r["answer_index"]], "explanation": r["explanation"]} for r in results if not r["correct"]]
        try:
            remediation = ai_tasks.remediate(m, rm, wrong)
        except LLMError:
            remediation = "Review the explanations below for each missed question, then retake the quiz."
    return {"score": score, "passed": passed, "threshold": settings.MASTERY_THRESHOLD, "correct": correct,
            "total": total, "breakdown": breakdown, "results": results, "remediation": remediation}


# ------------------------------------------------------------------ frontend (static, no build step)
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
