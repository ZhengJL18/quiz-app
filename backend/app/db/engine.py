"""SQLAlchemy engine and session factory — SQLite (dev) + PostgreSQL (prod)."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.config import settings

# ── Database URL detection ──
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# ── Engine ──
_connect_args = {}
_pool_config = {}

if _is_sqlite:
    _connect_args = {"check_same_thread": False}
    # Use QueuePool for SQLite too — background tasks need >5 connections
    _pool_config = {"pool_size": 20, "max_overflow": 30, "pool_timeout": 60}
else:
    # PostgreSQL
    _pool_config = {"pool_size": 10, "max_overflow": 20, "pool_pre_ping": True}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    echo=False,
    **_pool_config,
)

# ── SQLite pragmas ──
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# ── Session ──
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency: yields a DB session and closes it after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Run Alembic migrations (or create_all as fallback). Call once at startup."""
    from pathlib import Path
    _backend_dir = Path(__file__).resolve().parent.parent

    _alembic_ini = _backend_dir / "alembic.ini"
    if _alembic_ini.exists():
        import alembic.config
        alembic.config.main(argv=["-c", str(_alembic_ini), "upgrade", "head"])
    else:
        from app.db.models import Base
        Base.metadata.create_all(bind=engine)
