"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env for local dev (ignored in production)
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Data directory (local: ../data, Railway: /data volume)
DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).resolve().parent.parent.parent / "data")))


class Settings:
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{DATA_DIR / 'quiz.db'}"
    )
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "720"))
    JWT_ALGORITHM: str = "HS256"
    PORT: int = int(os.getenv("PORT", "8001"))

    # Frontend static files (only used locally)
    FRONTEND_DIST: Path = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


settings = Settings()
