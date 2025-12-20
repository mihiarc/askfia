# FIA Data Storage Strategy

## The Challenge

pyFIA downloads FIA data from the USDA DataMart and stores it in DuckDB files. These files can be substantial:

| State | Approx Size | Notes |
|-------|-------------|-------|
| Small (RI, DE) | 50-100 MB | Few plots |
| Medium (NC, VA) | 300-500 MB | Moderate forest |
| Large (OR, CA, GA) | 500-800 MB | Extensive inventory |
| All 50 states | ~15-20 GB | Complete national coverage |

We need a strategy that handles:
1. **Cold start latency** - First query for a state shouldn't take 2+ minutes
2. **Multi-user access** - Multiple concurrent users querying same data
3. **Cost efficiency** - Not paying for idle compute/storage
4. **Data freshness** - FIA updates annually, need periodic refresh
5. **Deployment flexibility** - Works on VPS, Railway, Fly.io, or cloud

---

## Recommended Architecture: Tiered Storage

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         STORAGE TIERS                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │
│  │   HOT CACHE     │    │  WARM STORAGE   │    │  COLD ORIGIN    │     │
│  │  (Local Disk)   │    │   (S3/R2/GCS)   │    │  (FIA DataMart) │     │
│  │                 │    │                 │    │                 │     │
│  │  - Mounted Vol  │◄───│  - All states   │◄───│  - pyfia.download│    │
│  │  - Preloaded    │    │  - Pre-built    │    │  - Annual update│     │
│  │  - <100ms       │    │  - DuckDB files │    │  - 2+ min/state │     │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘     │
│         ▲                       ▲                                       │
│         │                       │                                       │
│    On container            On cache miss                                │
│    startup/LRU             or scheduled                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Option 1: Pre-built S3/R2 + Local Cache (Recommended)

**Best for: Production deployments with predictable costs**

### How it works:

1. **Build Phase** (weekly/monthly cron):
   - Download all 50 states using pyFIA
   - Store DuckDB files in S3/Cloudflare R2
   - ~$0.50/month storage for 20GB on R2 (free egress!)

2. **Runtime**:
   - Container starts with empty/minimal local cache
   - On query, check local disk → S3 → FIA DataMart
   - Cache to local persistent volume
   - LRU eviction when disk fills

### Implementation:

```python
# backend/src/pyfia_api/services/storage.py
import os
import boto3
from pathlib import Path
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

class FIAStorage:
    """Tiered storage for FIA DuckDB files."""
    
    def __init__(
        self,
        local_dir: str = "/data/fia",
        s3_bucket: str | None = None,
        s3_prefix: str = "fia-duckdb",
        max_local_gb: float = 5.0,
    ):
        self.local_dir = Path(local_dir)
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.max_local_bytes = max_local_gb * 1e9
        
        # Initialize S3 client if configured
        if s3_bucket:
            self.s3 = boto3.client(
                's3',
                endpoint_url=os.getenv('S3_ENDPOINT_URL'),  # For R2/Minio
                aws_access_key_id=os.getenv('S3_ACCESS_KEY'),
                aws_secret_access_key=os.getenv('S3_SECRET_KEY'),
            )
        else:
            self.s3 = None
    
    def get_db_path(self, state: str) -> Path:
        """Get path to state DuckDB file, downloading if necessary."""
        state = state.upper()
        local_path = self.local_dir / f"{state}.duckdb"
        
        # Tier 1: Check local cache
        if local_path.exists():
            logger.debug(f"Cache hit: {state} (local)")
            self._touch(local_path)  # Update access time for LRU
            return local_path
        
        # Tier 2: Check S3/R2
        if self.s3_bucket and self._download_from_s3(state, local_path):
            logger.info(f"Cache hit: {state} (S3)")
            self._enforce_cache_limit()
            return local_path
        
        # Tier 3: Download from FIA DataMart
        logger.info(f"Cache miss: {state} - downloading from FIA DataMart...")
        self._download_from_fia(state, local_path)
        self._enforce_cache_limit()
        
        # Optionally upload to S3 for future use
        if self.s3_bucket:
            self._upload_to_s3(state, local_path)
        
        return local_path
    
    def _download_from_s3(self, state: str, local_path: Path) -> bool:
        """Try to download from S3. Returns True if successful."""
        if not self.s3:
            return False
        
        s3_key = f"{self.s3_prefix}/{state}.duckdb"
        try:
            self.s3.download_file(self.s3_bucket, s3_key, str(local_path))
            return True
        except self.s3.exceptions.NoSuchKey:
            return False
        except Exception as e:
            logger.warning(f"S3 download failed for {state}: {e}")
            return False
    
    def _upload_to_s3(self, state: str, local_path: Path) -> bool:
        """Upload to S3 for future cache hits."""
        if not self.s3:
            return False
        
        s3_key = f"{self.s3_prefix}/{state}.duckdb"
        try:
            self.s3.upload_file(str(local_path), self.s3_bucket, s3_key)
            logger.info(f"Uploaded {state} to S3")
            return True
        except Exception as e:
            logger.warning(f"S3 upload failed for {state}: {e}")
            return False
    
    def _download_from_fia(self, state: str, local_path: Path):
        """Download fresh from FIA DataMart using pyFIA."""
        from pyfia import download
        
        # pyfia.download() returns the path
        temp_path = download(state, dir=str(self.local_dir.parent / "temp"))
        
        # Move to our managed location
        Path(temp_path).rename(local_path)
    
    def _touch(self, path: Path):
        """Update access time for LRU tracking."""
        path.touch()
    
    def _enforce_cache_limit(self):
        """Remove oldest files if over cache limit."""
        files = list(self.local_dir.glob("*.duckdb"))
        total_size = sum(f.stat().st_size for f in files)
        
        if total_size <= self.max_local_bytes:
            return
        
        # Sort by access time (oldest first)
        files.sort(key=lambda f: f.stat().st_atime)
        
        while total_size > self.max_local_bytes and files:
            oldest = files.pop(0)
            size = oldest.stat().st_size
            oldest.unlink()
            total_size -= size
            logger.info(f"Evicted {oldest.name} from cache ({size / 1e6:.1f} MB)")
    
    def preload(self, states: list[str]):
        """Preload states into local cache (call on startup)."""
        for state in states:
            try:
                self.get_db_path(state)
            except Exception as e:
                logger.warning(f"Failed to preload {state}: {e}")


# Singleton
storage = FIAStorage(
    local_dir=os.getenv("FIA_LOCAL_DIR", "/data/fia"),
    s3_bucket=os.getenv("FIA_S3_BUCKET"),
    s3_prefix=os.getenv("FIA_S3_PREFIX", "fia-duckdb"),
    max_local_gb=float(os.getenv("FIA_LOCAL_CACHE_GB", "5")),
)
```

### Build Script (GitHub Actions / Cron):

```python
# scripts/build_fia_cache.py
"""
Pre-build all state DuckDB files and upload to S3.
Run monthly or after FIA data updates.
"""
import os
import boto3
from pyfia import download
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

def build_and_upload():
    s3 = boto3.client(
        's3',
        endpoint_url=os.getenv('S3_ENDPOINT_URL'),
        aws_access_key_id=os.getenv('S3_ACCESS_KEY'),
        aws_secret_access_key=os.getenv('S3_SECRET_KEY'),
    )
    bucket = os.getenv('FIA_S3_BUCKET')
    prefix = os.getenv('FIA_S3_PREFIX', 'fia-duckdb')
    
    work_dir = Path("/tmp/fia-build")
    work_dir.mkdir(exist_ok=True)
    
    for state in STATES:
        logger.info(f"Processing {state}...")
        try:
            # Download from FIA
            db_path = download(state, dir=str(work_dir))
            
            # Upload to S3
            s3_key = f"{prefix}/{state}.duckdb"
            s3.upload_file(db_path, bucket, s3_key)
            logger.info(f"  ✓ Uploaded {state} ({Path(db_path).stat().st_size / 1e6:.1f} MB)")
            
            # Clean up local file
            Path(db_path).unlink()
            
        except Exception as e:
            logger.error(f"  ✗ Failed {state}: {e}")
    
    logger.info("Build complete!")

if __name__ == "__main__":
    build_and_upload()
```

### GitHub Action:

```yaml
# .github/workflows/build-fia-cache.yml
name: Build FIA Cache

on:
  schedule:
    - cron: '0 0 1 * *'  # Monthly on the 1st
  workflow_dispatch:  # Manual trigger

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 180  # 3 hours max
    
    steps:
      - uses: actions/checkout@v4
      
      - uses: astral-sh/setup-uv@v4
      
      - name: Install dependencies
        run: |
          cd backend
          uv sync
      
      - name: Build and upload FIA cache
        env:
          S3_ENDPOINT_URL: ${{ secrets.S3_ENDPOINT_URL }}
          S3_ACCESS_KEY: ${{ secrets.S3_ACCESS_KEY }}
          S3_SECRET_KEY: ${{ secrets.S3_SECRET_KEY }}
          FIA_S3_BUCKET: ${{ secrets.FIA_S3_BUCKET }}
        run: |
          cd backend
          uv run python scripts/build_fia_cache.py
```

---

## Option 2: Persistent Volume Only

**Best for: Simple VPS deployments**

### How it works:

- Mount a persistent volume to `/data/fia`
- First request downloads from FIA DataMart (slow)
- Subsequent requests use cached files (fast)
- Volume persists across container restarts

### Docker Compose:

```yaml
services:
  backend:
    volumes:
      - fia_data:/data/fia  # Persistent volume
    environment:
      - FIA_LOCAL_DIR=/data/fia
      - FIA_LOCAL_CACHE_GB=20  # Size limit

volumes:
  fia_data:
    driver: local
```

### Pros/Cons:

| Pros | Cons |
|------|------|
| Simple setup | Cold start on first query per state |
| No cloud storage costs | Volume tied to single host |
| Works on any VPS | No multi-region replication |

---

## Option 3: MotherDuck (Serverless DuckDB)

**Best for: Teams wanting managed infrastructure**

### How it works:

MotherDuck provides serverless DuckDB in the cloud with:
- Persistent storage
- Hybrid local/cloud execution
- No server management

### Implementation:

```python
import duckdb

# Connect to MotherDuck
conn = duckdb.connect("md:my_database?motherduck_token=<token>")

# Load FIA data once
conn.execute("""
    CREATE TABLE IF NOT EXISTS nc_tree AS 
    SELECT * FROM read_parquet('s3://fia-data/NC/TREE.parquet')
""")

# Query from anywhere
result = conn.execute("SELECT COUNT(*) FROM nc_tree").fetchall()
```

### Pros/Cons:

| Pros | Cons |
|------|------|
| Zero ops | Monthly cost (~$20-100) |
| Hybrid execution | Vendor lock-in |
| Built-in sharing | Requires data conversion to Parquet |

---

## Option 4: DuckDB over S3 (Read-Only)

**Best for: Read-heavy public access**

DuckDB can query `.duckdb` files directly from S3 in read-only mode:

```python
import duckdb

conn = duckdb.connect()
conn.execute("INSTALL httpfs; LOAD httpfs;")
conn.execute("""
    CREATE SECRET (
        TYPE s3,
        KEY_ID 'xxx',
        SECRET 'yyy',
        REGION 'us-east-1'
    )
""")

# Attach remote database (read-only)
conn.execute("ATTACH 's3://fia-bucket/NC.duckdb' AS nc (READ_ONLY)")

# Query directly from S3
result = conn.execute("SELECT COUNT(*) FROM nc.tree").fetchall()
```

### Pros/Cons:

| Pros | Cons |
|------|------|
| No local storage needed | Higher latency per query |
| Always fresh data | S3 egress costs (use R2 for free) |
| Scales to any size | Read-only access |

---

## Recommended Setup by Deployment Target

### Railway / Fly.io / Render

```
┌─────────────────────────────────────────┐
│  Cloudflare R2 (free egress)            │
│  └── fia-duckdb/                        │
│      ├── NC.duckdb                      │
│      ├── GA.duckdb                      │
│      └── ...                            │
└─────────────────────────────────────────┘
              │
              ▼ Download on cache miss
┌─────────────────────────────────────────┐
│  Railway/Fly Container                  │
│  └── /data/fia/ (ephemeral or volume)   │
│      ├── NC.duckdb (cached)             │
│      └── GA.duckdb (cached)             │
│                                         │
│  LRU eviction at 2-5GB                  │
└─────────────────────────────────────────┘
```

**Config:**
```env
FIA_S3_BUCKET=fia-data
S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
S3_ACCESS_KEY=xxx
S3_SECRET_KEY=yyy
FIA_LOCAL_CACHE_GB=2
```

### Single VPS (DigitalOcean, Hetzner, Linode)

```
┌─────────────────────────────────────────┐
│  VPS with 50GB+ disk                    │
│  └── /data/fia/ (persistent)            │
│      ├── NC.duckdb                      │
│      ├── GA.duckdb                      │
│      └── ... (all 50 states)            │
│                                         │
│  Preload popular states on startup      │
└─────────────────────────────────────────┘
```

**Config:**
```env
FIA_LOCAL_DIR=/data/fia
FIA_LOCAL_CACHE_GB=40
PRELOAD_STATES=NC,GA,SC,VA,FL,OR,WA,CA
```

### AWS / GCP / Azure

```
┌─────────────────────────────────────────┐
│  S3 / GCS / Azure Blob                  │
│  └── fia-duckdb/                        │
│      └── *.duckdb (all states)          │
└─────────────────────────────────────────┘
              │
              ▼ Direct query OR cache
┌─────────────────────────────────────────┐
│  ECS / Cloud Run / Container Apps       │
│  └── /tmp/fia/ (ephemeral 10GB)         │
│                                         │
│  Option A: DuckDB ATTACH from S3        │
│  Option B: Download + LRU cache         │
└─────────────────────────────────────────┘
```

---

## Cloudflare R2 Pricing (Recommended)

R2 provides S3-compatible object storage with **zero egress fees**.

| Tier | Free Allowance | Overage |
|------|----------------|---------|
| Storage | 10 GB/month | $0.015/GB/month |
| Class A ops (writes) | 1M/month | $4.50/million |
| Class B ops (reads) | 10M/month | $0.36/million |

### FIA Data Cost Estimate

| Scenario | Storage | Ops | Monthly Cost |
|----------|---------|-----|--------------|
| 10 states (~5GB) | Free | Free | **$0** |
| All 50 states (~25GB) | (25-10) × $0.015 | Free | **$0.23** |
| High traffic (1M reads) | $0.23 | Free | **$0.23** |

**Note:** FIA databases average 300-600MB per state. The free tier covers significant usage.

---

## Cost Comparison

| Option | Storage | Compute | Egress | Total/mo |
|--------|---------|---------|--------|----------|
| R2 + Railway | ~$0.25 | $5-20 | $0 | **$5-20** |
| R2 + Fly.io | ~$0.25 | $5-20 | $0 | **$5-20** |
| S3 + Lambda | $0.50 | Pay-per-use | ~$5 | **$5-15** |
| VPS (Hetzner) | Included | $5-10 | Included | **$5-10** |
| MotherDuck | Included | $20+ | N/A | **$20-100** |

---

## Implementation Checklist

### Phase 1: Basic (Week 1)
- [ ] Add `FIAStorage` class to backend
- [ ] Configure persistent volume in Docker Compose
- [ ] Add `PRELOAD_STATES` env var for startup caching
- [ ] Test with 3-5 states

### Phase 2: S3/R2 Integration (Week 2)
- [ ] Set up Cloudflare R2 bucket
- [ ] Create build script for all 50 states
- [ ] Set up GitHub Action for monthly rebuild
- [ ] Add S3 fallback to `FIAStorage`

### Phase 3: Optimization (Week 3)
- [ ] Add Redis cache for query results
- [ ] Implement query result caching (60 min TTL)
- [ ] Add cache hit/miss metrics
- [ ] Monitor storage usage and latency

---

## Environment Variables

```bash
# Storage configuration
FIA_LOCAL_DIR=/data/fia           # Local cache directory
FIA_LOCAL_CACHE_GB=5              # Max local cache size
FIA_S3_BUCKET=fia-data            # S3/R2 bucket name
FIA_S3_PREFIX=fia-duckdb          # S3 key prefix

# S3-compatible storage (Cloudflare R2, MinIO, etc.)
S3_ENDPOINT_URL=https://xxx.r2.cloudflarestorage.com
S3_ACCESS_KEY=xxx
S3_SECRET_KEY=yyy

# Preload states on startup (comma-separated)
PRELOAD_STATES=NC,GA,SC,VA,FL

# Query result caching (optional)
REDIS_URL=redis://localhost:6379
CACHE_TTL_SECONDS=3600
```

---

## Recommendation

**For your use case, I recommend Option 1 (R2 + Local Cache):**

1. **Pre-build all 50 states** once a month using GitHub Actions
2. **Store in Cloudflare R2** (~$0.50/month, free egress)
3. **Cache locally** with 2-5GB LRU on Railway/Fly
4. **Preload Southeast states** on startup (NC, GA, SC, VA, FL)

This gives you:
- Sub-second queries for cached states
- 5-10 second queries for S3 cache hits
- Full coverage without cold-start pain
- Minimal monthly costs ($5-20 total)

Want me to add this storage layer to the project scaffold?
