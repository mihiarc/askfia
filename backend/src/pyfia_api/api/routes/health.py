"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "service": "pyfia-api",
        "version": "1.0.0",
    }


@router.get("/health/ready")
async def readiness_check():
    """Readiness check - verify dependencies are available."""
    checks = {
        "pyfia": False,
        "anthropic": False,
    }

    # Check pyFIA
    try:
        import pyfia
        checks["pyfia"] = True
    except ImportError:
        pass

    # Check Anthropic
    try:
        from ..config import settings
        checks["anthropic"] = bool(settings.anthropic_api_key)
    except Exception:
        pass

    all_ready = all(checks.values())

    return {
        "status": "ready" if all_ready else "not_ready",
        "checks": checks,
    }
