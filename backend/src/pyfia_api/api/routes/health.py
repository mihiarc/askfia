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
        from ...config import settings
        checks["anthropic"] = bool(settings.anthropic_api_key)
    except Exception:
        pass

    all_ready = all(checks.values())

    return {
        "status": "ready" if all_ready else "not_ready",
        "checks": checks,
    }


@router.get("/debug/storage")
async def debug_storage():
    """Debug storage configuration."""
    from ...config import settings
    from ...services.storage import storage

    # Test S3 connection
    s3_status = "not configured"
    s3_objects = []
    s3_client_exists = storage.s3 is not None

    if storage.s3_bucket and s3_client_exists:
        try:
            response = storage.s3.list_objects_v2(
                Bucket=storage.s3_bucket,
                Prefix=storage.s3_prefix + "/",
                MaxKeys=5
            )
            s3_objects = [obj["Key"] for obj in response.get("Contents", [])]
            s3_status = "connected"
        except Exception as e:
            s3_status = f"error: {type(e).__name__}: {str(e)}"
    elif not storage.s3_bucket:
        s3_status = "bucket not configured"
    elif not s3_client_exists:
        s3_status = "client failed to initialize"

    return {
        "s3_bucket": storage.s3_bucket,
        "s3_prefix": storage.s3_prefix,
        "s3_endpoint": settings.s3_endpoint_url,
        "s3_access_key_set": bool(settings.s3_access_key),
        "s3_secret_key_set": bool(settings.s3_secret_key),
        "s3_client_exists": s3_client_exists,
        "s3_status": s3_status,
        "s3_objects": s3_objects,
        "local_dir": str(storage.local_dir),
        "cached_states": storage.list_cached_states(),
    }
