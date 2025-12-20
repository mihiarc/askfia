"""Tiered storage for FIA DuckDB files."""

import logging
import os
from functools import lru_cache
from pathlib import Path

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class FIAStorage:
    """
    Tiered storage for FIA DuckDB files.

    Tiers:
    1. Hot (local disk) - Fastest, limited size with LRU eviction
    2. Warm (S3/R2) - Pre-built databases, moderate latency
    3. Cold (FIA DataMart) - Fresh download, slowest
    """

    def __init__(
        self,
        local_dir: str = "./data/fia",
        s3_bucket: str | None = None,
        s3_prefix: str = "fia-duckdb",
        max_local_gb: float = 5.0,
    ):
        self.local_dir = Path(local_dir)
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.max_local_bytes = max_local_gb * 1e9
        self._s3_client = None

    @property
    def s3(self):
        """Lazy-load S3 client."""
        if self._s3_client is None and self.s3_bucket:
            try:
                import boto3
                from botocore.config import Config
                from ..config import settings

                endpoint = (settings.s3_endpoint_url or "").strip()
                access_key = (settings.s3_access_key or "").strip()
                secret_key = (settings.s3_secret_key or "").strip()

                logger.info(f"Initializing S3 client - endpoint: {endpoint}, bucket: {self.s3_bucket}")

                if not endpoint or not access_key or not secret_key:
                    logger.error(f"S3 config incomplete: endpoint={bool(endpoint)}, access_key={bool(access_key)}, secret_key={bool(secret_key)}")
                    self.s3_bucket = None
                    return None

                # Use session for better compatibility with custom endpoints
                session = boto3.session.Session(
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name='us-east-1',
                )
                self._s3_client = session.client(
                    's3',
                    endpoint_url=endpoint,
                    config=Config(signature_version='s3v4'),
                )
                logger.info("S3 client initialized successfully")
            except ImportError:
                logger.warning("boto3 not installed, S3 storage disabled")
                self.s3_bucket = None
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}", exc_info=True)
                self.s3_bucket = None
        return self._s3_client

    def get_db_path(self, state: str) -> str:
        """
        Get path to state DuckDB file, downloading if necessary.

        Returns the path as a string for compatibility with pyFIA.
        """
        state = state.upper()

        # Check for state directory structure (pyfia default)
        state_dir = self.local_dir / state.lower()
        possible_paths = [
            state_dir / f"{state.lower()}.duckdb",
            state_dir / "fia.duckdb",
            self.local_dir / f"{state}.duckdb",
        ]

        # Tier 1: Check local cache
        for local_path in possible_paths:
            if local_path.exists():
                logger.debug(f"Cache hit: {state} (local: {local_path})")
                self._touch(local_path)
                return str(local_path)

        # Tier 2: Check S3/R2
        target_path = self.local_dir / f"{state}.duckdb"
        if self.s3_bucket and self._download_from_s3(state, target_path):
            logger.info(f"Cache hit: {state} (S3)")
            self._enforce_cache_limit()
            return str(target_path)

        # No fallback to FIA DataMart - all data must be preloaded
        raise FileNotFoundError(
            f"State {state} not found in cache or R2. "
            f"Run 'uv run python scripts/build_fia_cache.py --states {state}' to preload."
        )

    def _download_from_s3(self, state: str, local_path: Path) -> bool:
        """Try to download from S3. Returns True if successful."""
        logger.info(f"Attempting S3 download for {state}, bucket={self.s3_bucket}, prefix={self.s3_prefix}")

        if not self.s3:
            logger.error(f"S3 client is None! Cannot download {state}")
            return False

        s3_key = f"{self.s3_prefix}/{state}.duckdb"
        try:
            # Ensure parent directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Downloading {state} from S3: s3://{self.s3_bucket}/{s3_key} -> {local_path}")
            self.s3.download_file(self.s3_bucket, s3_key, str(local_path))
            logger.info(f"Successfully downloaded {state} ({local_path.stat().st_size / 1e6:.1f} MB)")
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(f"S3 ClientError for {state}: {error_code} - {e}")
            return False
        except Exception as e:
            logger.error(f"S3 download failed for {state}: {type(e).__name__}: {e}", exc_info=True)
            return False

    def _upload_to_s3(self, state: str, local_path: Path) -> bool:
        """Upload to S3 for future cache hits."""
        if not self.s3:
            return False

        s3_key = f"{self.s3_prefix}/{state}.duckdb"
        try:
            logger.info(f"Uploading {state} to S3: {s3_key}")
            self.s3.upload_file(str(local_path), self.s3_bucket, s3_key)
            logger.info(f"Uploaded {state} to S3 ({local_path.stat().st_size / 1e6:.1f} MB)")
            return True
        except Exception as e:
            logger.warning(f"S3 upload failed for {state}: {e}")
            return False

    def _touch(self, path: Path):
        """Update access time for LRU tracking."""
        try:
            path.touch()
        except Exception:
            pass  # Ignore errors

    def _enforce_cache_limit(self):
        """Remove oldest files if over cache limit."""
        # Find all duckdb files recursively
        files = list(self.local_dir.rglob("*.duckdb"))
        if not files:
            return

        total_size = sum(f.stat().st_size for f in files)

        if total_size <= self.max_local_bytes:
            return

        # Sort by access time (oldest first)
        files.sort(key=lambda f: f.stat().st_atime)

        while total_size > self.max_local_bytes and files:
            oldest = files.pop(0)
            size = oldest.stat().st_size
            try:
                oldest.unlink()
                # Also remove parent directory if empty
                if oldest.parent != self.local_dir and not any(oldest.parent.iterdir()):
                    oldest.parent.rmdir()
                total_size -= size
                logger.info(f"Evicted {oldest.name} from cache ({size / 1e6:.1f} MB)")
            except Exception as e:
                logger.warning(f"Failed to evict {oldest}: {e}")

    def preload(self, states: list[str]):
        """Preload states into local cache (call on startup)."""
        for state in states:
            try:
                logger.info(f"Preloading {state}...")
                self.get_db_path(state)
            except Exception as e:
                logger.warning(f"Failed to preload {state}: {e}")

    def list_cached_states(self) -> list[dict]:
        """List all cached states with their sizes."""
        cached = []
        for db_file in self.local_dir.rglob("*.duckdb"):
            stat = db_file.stat()
            state = db_file.stem.upper()
            if state == "FIA":
                state = db_file.parent.name.upper()
            cached.append({
                "state": state,
                "path": str(db_file),
                "size_mb": stat.st_size / 1e6,
                "last_accessed": stat.st_atime,
            })
        return sorted(cached, key=lambda x: x["state"])

    def clear_cache(self):
        """Clear all cached files."""
        for db_file in self.local_dir.rglob("*.duckdb"):
            try:
                db_file.unlink()
                logger.info(f"Removed {db_file}")
            except Exception as e:
                logger.warning(f"Failed to remove {db_file}: {e}")


# Create singleton from settings
def get_storage() -> FIAStorage:
    """Get the configured FIAStorage instance."""
    from ..config import settings

    return FIAStorage(
        local_dir=settings.fia_local_dir,
        s3_bucket=settings.fia_s3_bucket,
        s3_prefix=settings.fia_s3_prefix,
        max_local_gb=settings.fia_local_cache_gb,
    )


# Singleton instance
storage = get_storage()
