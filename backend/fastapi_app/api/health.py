from fastapi import APIRouter, Response
from redis import Redis
from sqlalchemy import create_engine, text

from core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness probe: the process is up. No dependency checks."""
    return {"success": True, "data": {"status": "ok"}, "message": "healthy", "errors": []}


@router.get("/ready")
def ready(response: Response) -> dict:
    """Readiness probe: the process can serve traffic (DB + cache reachable)."""
    settings = get_settings()
    checks = {
        "database": _check_database(settings.database_url),
        "cache": _check_cache(settings.redis_url),
    }
    is_ready = all(checks.values())
    response.status_code = 200 if is_ready else 503
    return {
        "success": is_ready,
        "data": {"status": "ready" if is_ready else "not_ready", "checks": checks},
        "message": "ready" if is_ready else "not ready",
        "errors": [] if is_ready else ["dependency check failed"],
    }


def _check_database(database_url: str) -> bool:
    try:
        engine = create_engine(database_url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _check_cache(redis_url: str) -> bool:
    try:
        client = Redis.from_url(redis_url, socket_connect_timeout=3)
        return bool(client.ping())
    except Exception:
        return False
