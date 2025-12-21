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


@router.get("/debug/query")
async def debug_query():
    """Debug: test a MotherDuck query directly."""
    import traceback
    import sys

    steps = []

    try:
        steps.append("1. Importing settings")
        from ...config import settings
        steps.append(f"   - motherduck_token set: {bool(settings.motherduck_token)}")

        steps.append("2. Importing fia_service")
        from ...services.fia_service import fia_service
        steps.append("   - fia_service imported")

        steps.append("3. Testing raw MotherDuck connection")
        import duckdb
        conn = duckdb.connect(f"md:?motherduck_token={settings.motherduck_token}")
        result = conn.execute("SELECT 1 as test").fetchone()
        steps.append(f"   - Basic query result: {result}")
        conn.close()

        steps.append("4. Testing MotherDuck database access")
        conn = duckdb.connect(f"md:?motherduck_token={settings.motherduck_token}")
        result = conn.execute("SHOW DATABASES").fetchall()
        fia_dbs = [r[0] for r in result if r[0].startswith("fia_")]
        steps.append(f"   - FIA databases: {fia_dbs}")
        conn.close()

        steps.append("5. Testing pyfia import")
        from pyfia import area, FIA
        steps.append("   - pyfia imported successfully")

        steps.append("6. Testing MotherDuckFIA import")
        from ...services.motherduck_fia import MotherDuckFIA
        steps.append("   - MotherDuckFIA imported")

        steps.append("7. Creating MotherDuckFIA connection for GA")
        db = MotherDuckFIA(state="GA", motherduck_token=settings.motherduck_token)
        steps.append("   - MotherDuckFIA created")

        steps.append("8. Running area query")
        result_df = area(db, land_type="forest")
        steps.append(f"   - Query completed, type: {type(result_df)}")

        steps.append("9. Converting to pandas")
        df = result_df.to_pandas() if hasattr(result_df, "to_pandas") else result_df
        steps.append(f"   - DataFrame shape: {df.shape}")
        steps.append(f"   - Columns: {list(df.columns)}")

        steps.append("10. Closing connection")
        db._backend.disconnect()
        steps.append("   - Connection closed")

        # Extract result
        est_col = "AREA" if "AREA" in df.columns else "ESTIMATE"
        total = float(df[est_col].sum()) if est_col in df.columns else 0.0

        return {
            "status": "success",
            "steps": steps,
            "total_area_acres": total,
            "columns": list(df.columns),
            "sample": df.head(2).to_dict(),
        }
    except Exception as e:
        return {
            "status": "error",
            "steps": steps,
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "python_version": sys.version,
        }


@router.get("/debug/storage")
async def debug_storage():
    """Debug storage configuration."""
    from ...config import settings
    from ...services.storage import storage

    # Test S3 connection (legacy)
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

    # Test MotherDuck connection
    md_status = "not configured"
    md_databases = []

    if settings.motherduck_token:
        try:
            import duckdb
            conn = duckdb.connect(f"md:?motherduck_token={settings.motherduck_token}")
            result = conn.execute("SHOW DATABASES").fetchall()
            md_databases = [row[0] for row in result if row[0].startswith("fia_")]
            md_status = "connected"
            conn.close()
        except Exception as e:
            md_status = f"error: {type(e).__name__}: {str(e)}"

    return {
        "storage_mode": "motherduck" if settings.motherduck_token else "s3/local",
        "motherduck_token_set": bool(settings.motherduck_token),
        "motherduck_status": md_status,
        "motherduck_databases": md_databases,
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
