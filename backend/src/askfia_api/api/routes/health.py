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
    import importlib.util
    checks["pyfia"] = importlib.util.find_spec("pyfia") is not None

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
async def debug_query(step: int = 10):
    """Debug: test a MotherDuck query directly with step-by-step execution.

    Use step parameter to limit execution:
    - step=1-4: Basic MotherDuck connectivity tests
    - step=5-6: Import tests
    - step=7: Create MotherDuckFIA (may OOM)
    - step=8-10: Run actual query (may OOM)
    """
    import gc
    import resource
    import sys
    import traceback

    completed_steps = []

    # Get memory info
    try:
        mem_info = resource.getrusage(resource.RUSAGE_SELF)
        max_rss_mb = mem_info.ru_maxrss / 1024  # Convert to MB on Linux
    except Exception:
        max_rss_mb = 0

    try:
        completed_steps.append(f"0. Memory at start: {max_rss_mb:.1f} MB")

        if step >= 1:
            completed_steps.append("1. Importing settings")
            from ...config import settings
            completed_steps.append(f"   - motherduck_token set: {bool(settings.motherduck_token)}")

        if step >= 2:
            completed_steps.append("2. Importing duckdb")
            import duckdb
            completed_steps.append(f"   - duckdb version: {duckdb.__version__}")

        if step >= 3:
            completed_steps.append("3. Testing raw MotherDuck connection")
            import duckdb

            from ...config import settings
            conn = duckdb.connect(f"md:?motherduck_token={settings.motherduck_token}")
            result = conn.execute("SELECT 1 as test").fetchone()
            completed_steps.append(f"   - Basic query result: {result}")
            conn.close()

        if step >= 4:
            completed_steps.append("4. Testing MotherDuck database access")
            import duckdb

            from ...config import settings
            conn = duckdb.connect(f"md:?motherduck_token={settings.motherduck_token}")
            result = conn.execute("SHOW DATABASES").fetchall()
            fia_dbs = [r[0] for r in result if r[0].startswith("fia_")]
            completed_steps.append(f"   - FIA databases: {fia_dbs}")
            conn.close()

        if step >= 5:
            completed_steps.append("5. Testing pyfia import")
            completed_steps.append("   - pyfia imported successfully")
            gc.collect()  # Force garbage collection

        if step >= 6:
            completed_steps.append("6. Testing MotherDuckFIA import")
            from pyfia import MotherDuckFIA
            completed_steps.append("   - MotherDuckFIA imported from pyfia")

        if step >= 7:
            completed_steps.append("7. Creating MotherDuckFIA connection for GA")
            from pyfia import MotherDuckFIA

            from ...config import settings
            gc.collect()  # Clean up before creating connection
            db = MotherDuckFIA("fia_ga", motherduck_token=settings.motherduck_token)
            completed_steps.append("   - MotherDuckFIA created")

        if step >= 8:
            completed_steps.append("8. Running area query")
            from pyfia import MotherDuckFIA

            from ...config import settings
            gc.collect()
            db = MotherDuckFIA("fia_ga", motherduck_token=settings.motherduck_token)
            db.clip_most_recent()
            result_df = db.area(land_type="forest")
            completed_steps.append(f"   - Query completed, type: {type(result_df)}")

        if step >= 9:
            completed_steps.append("9. Converting to pandas")
            df = result_df.to_pandas() if hasattr(result_df, "to_pandas") else result_df
            completed_steps.append(f"   - DataFrame shape: {df.shape}")
            completed_steps.append(f"   - Columns: {list(df.columns)}")

        if step >= 10:
            completed_steps.append("10. Extracting results and closing")
            est_col = "AREA" if "AREA" in df.columns else "ESTIMATE"
            total = float(df[est_col].sum()) if est_col in df.columns else 0.0
            # Clean up connection
            if hasattr(db, '_backend') and hasattr(db._backend, 'disconnect'):
                db._backend.disconnect()
            gc.collect()

            # Get final memory
            try:
                mem_info = resource.getrusage(resource.RUSAGE_SELF)
                final_rss_mb = mem_info.ru_maxrss / 1024
            except Exception:
                final_rss_mb = 0
            completed_steps.append(f"   - Final memory: {final_rss_mb:.1f} MB")

            return {
                "status": "success",
                "steps": completed_steps,
                "total_area_acres": total,
                "columns": list(df.columns),
                "sample": df.head(2).to_dict(),
            }

        return {
            "status": "partial",
            "max_step": step,
            "steps": completed_steps,
            "message": f"Completed steps 1-{step} successfully",
        }
    except Exception as e:
        return {
            "status": "error",
            "steps": completed_steps,
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
