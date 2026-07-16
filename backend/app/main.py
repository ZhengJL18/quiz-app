"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.config import settings
from app.db.engine import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup."""
    init_db()
    yield


app = FastAPI(title="Quiz App API", version="0.1.0", lifespan=lifespan)

# CORS — allow frontend dev server and Cloudflare Tunnel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health check ──
@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


# ── Router registration ──
from app.routers import auth, subjects, chapters, questions  # noqa: E402
from app.routers import study, practice  # noqa: E402
from app.routers import wrong_book  # noqa: E402
from app.routers import mastery, srs  # noqa: E402

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(subjects.router, prefix="/api/subjects", tags=["subjects"])
app.include_router(chapters.router, prefix="/api", tags=["chapters"])
app.include_router(questions.router, prefix="/api/questions", tags=["questions"])
app.include_router(study.router, prefix="/api/study", tags=["study"])
app.include_router(practice.router, prefix="/api/practice", tags=["practice"])
app.include_router(wrong_book.router, prefix="/api/wrong-book", tags=["wrong_book"])
app.include_router(mastery.router, prefix="/api/mastery", tags=["mastery"])
app.include_router(srs.router, prefix="/api/srs", tags=["srs"])


# ── Serve frontend static files (production) ──
FRONTEND_DIST = Path(settings.FRONTEND_DIST)
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
