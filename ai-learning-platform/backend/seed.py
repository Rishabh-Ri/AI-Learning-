"""Seed roadmaps spanning Class 6 -> PhD. Lesson text is generated lazily by the LLM on first open,
so you can also create unlimited extra roadmaps for ANY topic from the UI ("Generate with AI")."""
import re

from sqlalchemy.orm import Session

from common.config import settings

from .models import Module, Roadmap


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "roadmap"


def create_roadmap(db: Session, *, slug, prefix, title, description, level, modules, created_by=None) -> Roadmap:
    rm = Roadmap(slug=slug, title=title, description=description, level=level, created_by=created_by)
    db.add(rm)
    db.flush()
    ids = [f"mod_{prefix}_{i:02d}" for i in range(1, len(modules) + 1)]
    for i, m in enumerate(modules, start=1):
        accel = m["interview_weightage"] >= settings.ACCEL_MIN_IW or m["future_scope"] >= settings.ACCEL_MIN_FS
        db.add(
            Module(
                module_id=ids[i - 1],
                roadmap_id=rm.id,
                order_index=i,
                title=m["title"],
                phase=m["phase"],
                prerequisites=[ids[p - 1] for p in m.get("prereqs", []) if 1 <= p < i],
                track_eligibility=["FULL", "ACCELERATED"] if accel else ["FULL"],
                interview_weightage=m["interview_weightage"],
                theoretical_importance=m["theoretical_importance"],
                future_scope=m["future_scope"],
                estimated_time_minutes=m["estimated_time_minutes"],
                youtube_keywords=m.get("youtube_keywords", []),
                vector_index_namespace=f"{prefix}_{i:02d}_v1",
            )
        )
    db.commit()
    return rm


# (title, phase, prerequisite numbers, interview/exam weightage, theory importance, future scope, minutes, youtube queries)
ROADMAPS = [
    dict(
        slug="class6-math", prefix="m6", level="class_6",
        title="Class 6 Mathematics: Foundations",
        description="Numbers, fractions, geometry and first steps in algebra, explained simply for Class 6.",
        modules=[
            ("Numbers & Place Value", "Number Sense", [], 90, 9, 6, 30, ["class 6 maths place value", "large numbers class 6"]),
            ("Factors, Multiples & Primes", "Number Sense", [1], 68, 8, 6, 35, ["factors multiples class 6", "prime numbers for kids"]),
            ("Fractions & Decimals", "Number Sense", [1], 92, 9, 7, 40, ["fractions class 6 maths", "decimals class 6"]),
            ("Ratio & Proportion Basics", "Applied Math", [3], 62, 7, 7, 35, ["ratio and proportion class 6"]),
            ("Lines, Angles & Basic Shapes", "Geometry", [1], 66, 8, 6, 35, ["basic geometrical ideas class 6", "angles class 6"]),
            ("Perimeter & Area", "Geometry", [3, 5], 88, 8, 7, 40, ["perimeter and area class 6"]),
            ("Introduction to Algebra", "Algebra", [1, 3], 75, 9, 9, 40, ["introduction to algebra class 6"]),
            ("Data Handling & Graphs", "Data", [1], 55, 6, 6, 30, ["data handling class 6", "bar graphs class 6"]),
        ],
    ),
    dict(
        slug="class10-physics", prefix="phy", level="class_9_10",
        title="Class 9-10 Physics: Motion, Force & Energy",
        description="Board-exam oriented physics: kinematics, laws of motion, energy, light and electricity.",
        modules=[
            ("Motion & Kinematics", "Mechanics", [], 92, 9, 7, 45, ["motion class 9 physics", "equations of motion"]),
            ("Newton's Laws of Motion", "Mechanics", [1], 95, 9, 8, 45, ["newton laws of motion class 9"]),
            ("Work, Energy & Power", "Mechanics", [2], 88, 8, 8, 40, ["work energy power class 9"]),
            ("Gravitation", "Mechanics", [2], 66, 8, 6, 40, ["gravitation class 9 physics"]),
            ("Sound & Waves", "Waves & Optics", [1], 58, 7, 5, 35, ["sound class 9 physics"]),
            ("Light: Reflection & Refraction", "Waves & Optics", [], 90, 8, 7, 45, ["light reflection refraction class 10"]),
            ("Electricity & Ohm's Law", "Electricity & Magnetism", [], 93, 9, 9, 45, ["electricity class 10 ohm's law"]),
            ("Magnetic Effects of Current", "Electricity & Magnetism", [7], 65, 8, 7, 40, ["magnetic effects of electric current class 10"]),
        ],
    ),
    dict(
        slug="python-beginner", prefix="py", level="class_11_12",
        title="Python Programming for Beginners",
        description="From zero to building small API-powered projects in Python.",
        modules=[
            ("Setup, Syntax & Variables", "Basics", [], 55, 6, 7, 30, ["python for beginners setup", "python variables tutorial"]),
            ("Control Flow: if, loops", "Basics", [1], 85, 8, 9, 35, ["python if else loops tutorial"]),
            ("Functions & Scope", "Core Python", [2], 90, 9, 9, 40, ["python functions tutorial"]),
            ("Lists, Dicts, Sets & Tuples", "Core Python", [2], 95, 9, 9, 45, ["python data structures tutorial"]),
            ("Object-Oriented Programming", "Core Python", [3, 4], 88, 8, 9, 50, ["python oop tutorial"]),
            ("Files, Exceptions & JSON", "Practical Python", [3, 4], 62, 7, 7, 35, ["python file handling exceptions json"]),
            ("Modules, pip & Virtual Environments", "Practical Python", [3], 55, 6, 7, 30, ["python venv pip tutorial"]),
            ("Mini Project: Calling a Web API", "Practical Python", [5, 6, 7], 80, 6, 9.5, 60, ["python requests api project"]),
        ],
    ),
    dict(
        slug="dsa-undergrad", prefix="dsa", level="undergraduate",
        title="Data Structures & Algorithms",
        description="Core DSA for university courses and coding interviews.",
        modules=[
            ("Complexity Analysis (Big-O)", "Foundations", [], 90, 9, 8, 40, ["big o notation explained"]),
            ("Arrays & Strings", "Linear Structures", [1], 95, 8, 8, 45, ["arrays strings interview patterns"]),
            ("Linked Lists, Stacks & Queues", "Linear Structures", [1], 65, 8, 6, 50, ["linked list stack queue"]),
            ("Hash Tables", "Linear Structures", [2], 94, 8, 8, 40, ["hash table explained"]),
            ("Trees & Binary Search Trees", "Non-linear Structures", [3], 93, 9, 8, 55, ["binary search tree tutorial"]),
            ("Graphs: BFS, DFS & Shortest Paths", "Non-linear Structures", [3, 5], 90, 9, 9, 60, ["graph algorithms bfs dfs dijkstra"]),
            ("Sorting & Searching", "Algorithms", [1, 2], 66, 8, 5, 45, ["sorting algorithms explained"]),
            ("Dynamic Programming", "Algorithms", [1, 4], 91, 9, 8.5, 70, ["dynamic programming tutorial"]),
        ],
    ),
    dict(
        slug="genai-rag", prefix="rag", level="professional",
        title="Applied GenAI & RAG Engineering",
        description="Build production LLM apps: embeddings, RAG, agents, evaluation and deployment.",
        modules=[
            ("Python & API Foundations for AI", "Foundations", [], 60, 6, 7, 40, ["python for ai engineers", "rest api python"]),
            ("LLM Fundamentals & Transformers", "LLM Core", [1], 85, 9, 9.5, 50, ["transformer architecture explained", "how llms work"]),
            ("Embeddings & Chunking Strategies", "Retrieval & Context Engineering", [2], 82, 8, 9, 40, ["text embeddings explained", "chunking strategies rag"]),
            ("Retrieval-Augmented Generation (RAG) & Vector Search", "Retrieval & Context Engineering", [2, 3], 88, 8, 9.5, 45, ["Advanced RAG tutorial", "Vector DB indexing"]),
            ("Advanced Retrieval: Hybrid Search & Reranking", "Retrieval & Context Engineering", [4], 80, 7, 9, 45, ["hybrid search bm25 dense reranking"]),
            ("Agents & Tool Calling", "Agentic Systems", [2, 4], 84, 7, 9.5, 50, ["llm agents tool calling tutorial"]),
            ("Evaluating LLM Applications", "Production", [4], 78, 7, 9, 40, ["rag evaluation ragas"]),
            ("LLMOps: Serving, Caching & Cost", "Production", [4], 62, 6, 7, 40, ["llmops deploying llm apps"]),
            ("Fine-tuning & LoRA", "Advanced Models", [2], 62, 8, 7, 50, ["lora fine tuning explained"]),
            ("Safety, Guardrails & Prompt Injection", "Production", [6], 75, 6, 9, 35, ["llm prompt injection guardrails"]),
        ],
    ),
    dict(
        slug="statistical-learning-theory", prefix="slt", level="phd",
        title="Statistical Learning Theory (PhD)",
        description="Rigorous foundations of generalization: concentration, PAC, VC, Rademacher, optimization and modern deep-learning theory.",
        modules=[
            ("Probability & Measure-Theoretic Foundations", "Mathematical Foundations", [], 55, 10, 6.5, 60, ["measure theoretic probability for machine learning"]),
            ("Concentration Inequalities", "Mathematical Foundations", [1], 75, 10, 8.5, 60, ["concentration inequalities hoeffding bernstein"]),
            ("PAC Learning & VC Dimension", "Generalization Theory", [2], 85, 10, 8, 60, ["pac learning vc dimension lecture"]),
            ("Rademacher Complexity & Generalization Bounds", "Generalization Theory", [2, 3], 78, 10, 8.5, 70, ["rademacher complexity generalization bounds"]),
            ("Convex & Non-Convex Optimization for Learning", "Optimization", [1], 72, 9, 9, 65, ["non-convex optimization theory machine learning"]),
            ("Kernel Methods & RKHS", "Function Spaces", [1, 4], 65, 10, 7, 65, ["reproducing kernel hilbert space lecture"]),
            ("Deep Learning Theory: NTK & Double Descent", "Modern Theory", [4, 5], 70, 9, 9.5, 70, ["neural tangent kernel double descent"]),
            ("Causal Inference & Identifiability", "Modern Theory", [1], 60, 9, 7, 65, ["causal inference identifiability lecture"]),
        ],
    ),
]


def _to_dict(t):
    return {
        "title": t[0], "phase": t[1], "prereqs": t[2], "interview_weightage": t[3],
        "theoretical_importance": t[4], "future_scope": t[5], "estimated_time_minutes": t[6],
        "youtube_keywords": t[7],
    }


def run(db: Session):
    """Idempotent: only inserts roadmaps that do not exist yet."""
    for r in ROADMAPS:
        if db.query(Roadmap).filter(Roadmap.slug == r["slug"]).first():
            continue
        create_roadmap(
            db, slug=r["slug"], prefix=r["prefix"], title=r["title"], description=r["description"],
            level=r["level"], modules=[_to_dict(t) for t in r["modules"]],
        )
        print(f"[seed] created roadmap {r['slug']}")


if __name__ == "__main__":
    from .db import SessionLocal, init_db

    init_db()
    with SessionLocal() as session:
        run(session)
