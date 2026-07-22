"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import time
from collections import defaultdict

from app.config import settings
from app.config import ensure_production_secrets
from app.db.engine import init_db
from app.services.redis_state import rate_limit_check


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_production_secrets()
    if not os.getenv("PYTEST_RUNNING"):
        init_db()
    yield


app = FastAPI(title="Quiz App API", version="0.1.0", lifespan=lifespan)
API_PREFIX = "/api/v1"

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiting (Redis-backed, in-memory fallback) ──
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/health"):
        return await call_next(request)  # no rate limit on health
    ip = request.client.host if request.client else "unknown"
    if not await rate_limit_check(ip):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    return await call_next(request)

# ── Cache middleware: static data endpoints get short browser cache ──
CACHEABLE_PREFIXES = ("/api/v1/subjects", "/api/v1/chapters", "/api/v1/vocab")

@app.middleware("http")
async def cache_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.method == "GET" and any(request.url.path.startswith(p) for p in CACHEABLE_PREFIXES):
        response.headers["Cache-Control"] = "private, max-age=300"
    return response

# ── Security headers ──
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' data: https://cdn.jsdelivr.net https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self' https://api.deepseek.com; "
        "frame-ancestors 'none'; "
        "base-uri 'none';"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ── Health check ──
@app.get(f"{API_PREFIX}/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get(f"{API_PREFIX}/health/detailed")
def health_detailed():
    """Detailed health check — used by monitoring tools (Uptime Kuma, etc.)."""
    import time as _time
    from app.db.engine import SessionLocal
    from app.db.models import User, Subject, Question, PracticeSession
    checks = {}
    t0 = _time.time()

    # DB connectivity
    try:
        db = SessionLocal()
        user_count = db.query(User).count()
        subj_count = db.query(Subject).filter(Subject.is_active == True).count()
        q_count = db.query(Question).count()
        sess_count = db.query(PracticeSession).count()
        db.close()
        checks["database"] = {"status": "ok", "users": user_count, "subjects": subj_count, "questions": q_count, "sessions": sess_count}
    except Exception as e:
        checks["database"] = {"status": "error", "detail": str(e)[:200]}

    checks["latency_ms"] = round((_time.time() - t0) * 1000, 1)
    overall = "ok" if all(v.get("status") == "ok" for v in checks.values() if isinstance(v, dict)) else "degraded"
    return {"status": overall, "checks": checks, "version": "0.1.0"}


# ── Router registration ──
from app.routers import auth, subjects, chapters, questions  # noqa: E402
from app.routers import study, practice  # noqa: E402
from app.routers import wrong_book  # noqa: E402
from app.routers import mastery, srs, vocab, admin, assistant  # noqa: E402
from app.routers import vault_api, stats, conversations, notes, agent, ai_query  # noqa: E402
from app.routers import admin_vault, user_vault  # noqa: E402

app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["auth"])
app.include_router(subjects.router, prefix=f"{API_PREFIX}/subjects", tags=["subjects"])
app.include_router(chapters.router, prefix=f"{API_PREFIX}", tags=["chapters"])
app.include_router(questions.router, prefix=f"{API_PREFIX}/questions", tags=["questions"])
app.include_router(study.router, prefix=f"{API_PREFIX}/study", tags=["study"])
app.include_router(practice.router, prefix=f"{API_PREFIX}/practice", tags=["practice"])
app.include_router(wrong_book.router, prefix=f"{API_PREFIX}/wrong-book", tags=["wrong_book"])
app.include_router(mastery.router, prefix=f"{API_PREFIX}/mastery", tags=["mastery"])
app.include_router(srs.router, prefix=f"{API_PREFIX}/srs", tags=["srs"])
app.include_router(vocab.router, prefix=f"{API_PREFIX}/vocab", tags=["vocab"])
app.include_router(admin.router, prefix=f"{API_PREFIX}/admin", tags=["admin"])
app.include_router(admin_vault.router, prefix=f"{API_PREFIX}/admin/vault", tags=["admin_vault"])
app.include_router(assistant.router, prefix=f"{API_PREFIX}/assistant", tags=["assistant"])
app.include_router(vault_api.router, prefix=f"{API_PREFIX}/vault", tags=["vault"])
app.include_router(stats.router, prefix=f"{API_PREFIX}/stats", tags=["stats"])
app.include_router(conversations.router, prefix=f"{API_PREFIX}/conversations", tags=["conversations"])
app.include_router(notes.router, prefix=f"{API_PREFIX}/notes", tags=["notes"])
app.include_router(agent.router, prefix=f"{API_PREFIX}/agent", tags=["agent"])
app.include_router(ai_query.router, prefix=f"{API_PREFIX}/ai", tags=["ai"])
app.include_router(user_vault.router, prefix=f"{API_PREFIX}/vault/files", tags=["vault"])

# Legacy alias — keep old /api/ working
app.include_router(auth.router, prefix="/api/auth", tags=["auth-legacy"], include_in_schema=False)
app.include_router(subjects.router, prefix="/api/subjects", tags=["subjects-legacy"], include_in_schema=False)
app.include_router(practice.router, prefix="/api/practice", tags=["practice-legacy"], include_in_schema=False)
app.include_router(wrong_book.router, prefix="/api/wrong-book", tags=["wrong-legacy"], include_in_schema=False)
app.include_router(srs.router, prefix="/api/srs", tags=["srs-legacy"], include_in_schema=False)
app.include_router(vocab.router, prefix="/api/vocab", tags=["vocab-legacy"], include_in_schema=False)
app.include_router(assistant.router, prefix="/api/assistant", tags=["asst-legacy"], include_in_schema=False)


# ── Serve frontend static files (must be BEFORE SPA catch-all) ──
FRONTEND_DIST = Path(settings.FRONTEND_DIST)
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

# ── SPA catch-all: serve index.html for all non-API, non-asset routes ──
from fastapi.responses import FileResponse
INDEX_HTML = FRONTEND_DIST / "index.html"

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """Serve index.html for SPA client-side routing (excludes api/ and assets/)."""
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)
    from fastapi import HTTPException
    raise HTTPException(status_code=404)
