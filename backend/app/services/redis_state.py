"""Redis-backed state layer (with in-memory fallback for dev without Redis).

Replaces three memory data structures that break multi-worker:
1. Rate limiting counters → Redis INCR + EXPIRE
2. _generating_lesson / _generating_questions sets → Redis SET
3. Login failure counters → Redis INCR + EXPIRE
"""

import time
from collections import defaultdict

# Lazy Redis — only import+connect on first use, fall back to memory
_redis_client = None
_has_redis = None  # None = not tried yet

async def _get_redis():
    global _redis_client, _has_redis
    if _has_redis is not None:
        return _redis_client if _has_redis else None
    try:
        import redis.asyncio as redis_mod
        client = redis_mod.Redis.from_url("redis://localhost:6379/0", decode_responses=True)
        await client.ping()  # Test connection
        _redis_client = client
        _has_redis = True
        return client
    except Exception:
        _has_redis = False
        return None


# ── Rate Limiting ──

_rate_store: dict[str, list[float]] = defaultdict(list)

async def rate_limit_check(ip: str, max_requests: int = 60, window: int = 60) -> bool:
    """Return True if request is allowed, False if rate limited."""
    now = time.time()
    r = await _get_redis()
    if r:
        key = f"rate:{ip}"
        current = await r.incr(key)
        if current == 1:
            await r.expire(key, window)
        return current <= max_requests
    else:
        _rate_store[ip] = [t for t in _rate_store[ip] if now - t < window]
        if len(_rate_store[ip]) >= max_requests:
            return False
        _rate_store[ip].append(now)
        return True


# ── Background Generation Tracking ──

_generating_lesson: set[int] = set()
_generating_questions: set[int] = set()

async def generation_start(chapter_id: int, gen_type: str = "lesson") -> bool:
    """Try to mark a chapter as being generated. Returns True if marking succeeded."""
    r = await _get_redis()
    if r:
        key = f"gen:{gen_type}:{chapter_id}"
        return await r.set(key, "1", ex=300, nx=True)
    else:
        store = _generating_lesson if gen_type == "lesson" else _generating_questions
        if chapter_id in store:
            return False
        store.add(chapter_id)
        return True

async def generation_done(chapter_id: int, gen_type: str = "lesson"):
    """Mark generation as complete."""
    r = await _get_redis()
    if r:
        await r.delete(f"gen:{gen_type}:{chapter_id}")
    else:
        store = _generating_lesson if gen_type == "lesson" else _generating_questions
        store.discard(chapter_id)

def generation_has(chapter_id: int, gen_type: str = "lesson") -> bool:
    """Check if currently generating (sync — only for memory fallback)."""
    if _has_redis:
        # Sync check for Redis — use a sync client or just assume not generating
        return False  # Non-blocking fallback
    store = _generating_lesson if gen_type == "lesson" else _generating_questions
    return chapter_id in store


# ── Login Failure Tracking ──

_login_failures: dict[str, list[float]] = defaultdict(list)

async def login_failure_check(username: str, max_attempts: int = 5, lockout: int = 60) -> bool:
    """Return True if login is allowed, False if locked out."""
    now = time.time()
    key = f"login_fail:{username}"
    r = await _get_redis()
    if r:
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, lockout)
        return count <= max_attempts
    else:
        _login_failures[username] = [t for t in _login_failures[username] if now - t < lockout]
        if len(_login_failures[username]) >= max_attempts:
            return False
        _login_failures[username].append(now)
        return True
