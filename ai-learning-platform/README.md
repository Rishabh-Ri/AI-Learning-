# AI Learning Platform (Full + Accelerated tracks, Class 6 to PhD)

Runs entirely on a Windows laptop with VSCode, MySQL and Python. All AI services use **free tiers**.

## What you get

| Blueprint item | Implementation |
|---|---|
| Client (Next.js) | `frontend/` - no-build SPA (Tailwind CDN + vanilla JS), served by FastAPI. No Node needed. |
| Primary API (FastAPI) | `backend/main.py` - auth, roadmaps, modules, quiz/evaluation engine, skills |
| LangChain RAG tutor | `backend/rag.py` + `ai_tasks.py` - own lightweight RAG (chunk, embed, hybrid cosine + BM25), scoped to each module namespace |
| YouTube microservice (Flask) | `youtube_service/app.py` - top-video search, transcript, async AI summary and chapters |
| MySQL | users, roadmaps, modules, progress, quizzes, attempts, **and the vector chunks** |
| Full vs Accelerated | Toggle on roadmap page. Accelerated = Interview weightage >= 70 **or** Future scope >= 8; skipped prerequisites are ignored when unlocking |
| Levels | Class 6, 7-8, 9-10, 11-12, Undergrad, Postgrad, PhD, Professional. Six seeded roadmaps, plus **"Generate with AI" for any topic at any level** |
| Quiz | 60% scenario, 20% theory, 20% code/debug; 80% to master; remediation when below |

Design notes: LangChain and pgvector were replaced by plain Python + MySQL so setup on Windows has no native-build
problems. The retrieval code is isolated in `rag.py` if you later want LangChain, Chroma or pgvector.

## 1. Install prerequisites (once)

1. **Python 3.10 - 3.12** from python.org (tick "Add Python to PATH").
2. **MySQL 8** (MySQL Installer for Windows). Remember the root password. Make sure the MySQL service is running.
3. **VSCode** with the Python extension.

## 2. Get free API keys

| Key | Where | Needed for |
|---|---|---|
| `GROQ_API_KEY` | https://console.groq.com/keys | LLM (fast, free tier) |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey | LLM fallback + free embeddings for RAG |
| `YOUTUBE_API_KEY` | Google Cloud Console: enable "YouTube Data API v3", then Credentials > Create API key | Video recommendations (free quota 10,000 units/day, one search = 100 units) |

You need at least one of Groq/Gemini. Free-tier limits change over time, check each dashboard. The app caches
lessons, video searches and summaries to save quota, and falls back to the other LLM if one is rate-limited.
Transcripts use `youtube-transcript-api` and need no key.

## 3. Setup

1. Open the folder `ai-learning-platform` in VSCode (File > Open Folder).
2. Edit **`.env`**: set `DATABASE_URL` (your MySQL password), `JWT_SECRET`, and the API keys.
3. Double-click **`setup.bat`** (creates `.venv` and installs packages).
4. Verify: in a VSCode terminal run `.venv\Scripts\python -m scripts.check_setup` (all lines should say OK).

## 4. Run

Double-click **`run_all.bat`**: starts the Flask YouTube service (port 5001) and the FastAPI backend (port 8000),
then opens http://127.0.0.1:8000. In VSCode you can instead use Run and Debug > **Run everything**.

On first start the database and tables are created and the six roadmaps are seeded automatically.
Register an account, open a roadmap, and click a module. **The first open of each module generates its lesson with
the LLM (15-30 s), saves it, and indexes it for the tutor.** After that it is instant.

API docs: http://127.0.0.1:8000/docs

## Using it

- **Roadmap page**: metric badges, lock/unlock status, Full/Accelerated toggle, skill-gap radar.
- **Module page**: Learn (theory or fast-track summary, examples, scenarios, sandbox), Videos (top picks with AI summary,
  takeaways, clickable chapters), Mastery quiz, and the AI Tutor sidebar (Explain or Socratic mode).
- **Home page**: generate a roadmap for any subject, e.g. "Photosynthesis" at Class 7-8, or "Algebraic Topology" at PhD.

## Troubleshooting

- `Access denied for user 'root'`: wrong password in `DATABASE_URL`. URL-encode special characters (`@` becomes `%40`).
- `Can't connect to MySQL server`: start the MySQL80 service (Services app).
- `AI service error ... 429`: free-tier rate limit. Wait a minute, or set both Groq and Gemini keys so fallback works.
- Videos tab says service not running: start the YouTube service (`run_all.bat`).
- "This video has no transcript": pick another video.
- Tutor answers feel keyword-based: add `GEMINI_API_KEY` and keep `EMBEDDING_PROVIDER=gemini`.
- Changed `.env`? Restart both services.

## Project layout

```
.env                    all settings and API keys
backend/                FastAPI app (main.py, models.py, rag.py, ai_tasks.py, seed.py)
youtube_service/app.py  Flask microservice
common/                 shared config, LLM client, cache
frontend/               index.html + app.js
scripts/check_setup.py  diagnostics
setup.bat, run_all.bat  Windows helpers
```
