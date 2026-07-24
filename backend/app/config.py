"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (backend/.env or quiz-app/.env)
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    # Fallback: try backend/.env
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{Path(__file__).resolve().parent.parent.parent / 'data' / 'quiz.db'}"
    )
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
    JWT_ALGORITHM: str = "HS256"

    # Frontend static files path (can be overridden via FRONTEND_DIST env var for Docker)
    FRONTEND_DIST: Path = Path(
        os.getenv(
            "FRONTEND_DIST",
            str(Path(__file__).resolve().parent.parent.parent / "frontend" / "dist")
        )
    )

    # CORS — comma-separated origins, defaults to localhost dev
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:8001,https://localhost:8001,http://localhost,https://localhost,capacitor://localhost,https://311007.xyz,https://www.311007.xyz,https://quiz.312233.xyz"
    ).split(",")


settings = Settings()


def ensure_production_secrets() -> None:
    """Refuse to start in production if any secret uses its dev default.

    Only enforced when NOT in uvicorn reload mode (i.e. production).
    Reload detection: uvicorn sets the env var `UVICORN_RELOAD` to `'true'`.
    Call this from main.py's lifespan, NOT at import time.
    """
    import os as _os
    if _os.getenv("UVICORN_RELOAD", "").lower() == "true":
        return  # dev reload — allow defaults

    errors: list[str] = []
    if settings.JWT_SECRET == "dev-secret-change-in-production":
        errors.append("JWT_SECRET is still the default 'dev-secret-change-in-production'")
    if errors:
        msg = "Production secret check FAILED:\n  " + "\n  ".join(errors)
        raise RuntimeError(msg)
