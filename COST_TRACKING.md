# Cost Tracking Strategy for pyFIA Agent

## Cost Breakdown

| Category | Type | Component | Est. Monthly Cost |
|----------|------|-----------|-------------------|
| **Fixed** | Infrastructure | Railway/Fly.io hosting | $5-20 |
| **Fixed** | Infrastructure | Domain name | ~$1 |
| **Fixed** | Storage | Cloudflare R2 (20GB) | ~$0.50 |
| **Fixed** | Optional | Redis (Upstash free tier) | $0 |
| **Variable** | API | Claude API usage | $50-500+ |
| **Variable** | Storage | R2 Class A ops (writes) | ~$0.50/million |
| **Variable** | Bandwidth | Railway egress (if heavy) | Usually $0 |

**The big variable: Claude API costs ($3/MTok input, $15/MTok output for Sonnet)**

---

## Tracking Options

### Option 1: Langfuse (Recommended)

**Open-source LLM observability with automatic cost tracking.**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         YOUR APPLICATION                                │
│                                                                         │
│   User Query → Agent → Claude API → Response                           │
│                    │                                                    │
│                    └──────────────────┐                                │
│                                       ▼                                │
│                              Langfuse SDK                              │
│                              (traces every call)                       │
└─────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      LANGFUSE DASHBOARD                                 │
│                                                                         │
│   📊 Traces    │  💰 Cost      │  ⏱️ Latency   │  👥 Users            │
│   ─────────    │  ─────────    │  ──────────   │  ─────────           │
│   1,234 today  │  $12.45 MTD   │  2.3s avg     │  45 active           │
│                │               │               │                      │
│   By model:    │  By day:      │  By endpoint: │  By session:         │
│   - Sonnet: 95%│  - Mon: $3.20 │  - /chat: 89% │  - Queries/user: 8   │
│   - Haiku: 5%  │  - Tue: $4.10 │  - /query: 11%│  - Avg cost: $0.28   │
└─────────────────────────────────────────────────────────────────────────┘
```

**Pricing:**
- **Self-hosted**: Free (open source)
- **Cloud free tier**: 50k events/month, 30-day retention
- **Cloud paid**: $59/month for 100k events

---

### Option 2: Built-in Usage Tracking

**Lightweight tracking without external dependencies.**

```python
# backend/src/pyfia_api/services/usage_tracker.py
import os
import json
import logging
from datetime import datetime, date
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
import asyncio

logger = logging.getLogger(__name__)

# Claude Sonnet 4.5 pricing (as of Dec 2024)
PRICING = {
    "claude-sonnet-4-5-20250929": {
        "input": 3.00 / 1_000_000,   # $3 per million input tokens
        "output": 15.00 / 1_000_000,  # $15 per million output tokens
    },
    "claude-haiku-3-5-20241022": {
        "input": 0.80 / 1_000_000,
        "output": 4.00 / 1_000_000,
    },
}

@dataclass
class UsageRecord:
    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    tool_calls: int = 0
    latency_ms: int = 0
    
class UsageTracker:
    """Track Claude API usage and costs."""
    
    def __init__(self, storage_dir: str = "./data/usage"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
    
    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate cost for a request."""
        pricing = PRICING.get(model, PRICING["claude-sonnet-4-5-20250929"])
        return (
            input_tokens * pricing["input"] +
            output_tokens * pricing["output"]
        )
    
    async def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        user_id: str | None = None,
        session_id: str | None = None,
        tool_calls: int = 0,
        latency_ms: int = 0,
    ):
        """Record a usage event."""
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        
        record = UsageRecord(
            timestamp=datetime.utcnow().isoformat(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            user_id=user_id,
            session_id=session_id,
            tool_calls=tool_calls,
            latency_ms=latency_ms,
        )
        
        # Append to daily log file
        today = date.today().isoformat()
        log_file = self.storage_dir / f"{today}.jsonl"
        
        async with self._lock:
            with open(log_file, "a") as f:
                f.write(json.dumps(asdict(record)) + "\n")
        
        logger.debug(
            f"Usage: {input_tokens} in, {output_tokens} out, ${cost:.4f}"
        )
        
        return record
    
    def get_daily_summary(self, day: date | None = None) -> dict:
        """Get usage summary for a day."""
        day = day or date.today()
        log_file = self.storage_dir / f"{day.isoformat()}.jsonl"
        
        if not log_file.exists():
            return {
                "date": day.isoformat(),
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_cost_usd": 0,
                "unique_users": 0,
            }
        
        requests = 0
        input_tokens = 0
        output_tokens = 0
        total_cost = 0
        users = set()
        
        with open(log_file) as f:
            for line in f:
                record = json.loads(line)
                requests += 1
                input_tokens += record["input_tokens"]
                output_tokens += record["output_tokens"]
                total_cost += record["cost_usd"]
                if record.get("user_id"):
                    users.add(record["user_id"])
        
        return {
            "date": day.isoformat(),
            "requests": requests,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_cost_usd": round(total_cost, 4),
            "unique_users": len(users),
        }
    
    def get_monthly_summary(self, year: int, month: int) -> dict:
        """Get usage summary for a month."""
        from calendar import monthrange
        
        _, days_in_month = monthrange(year, month)
        
        total = {
            "year": year,
            "month": month,
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost_usd": 0,
            "daily": [],
        }
        
        for day in range(1, days_in_month + 1):
            d = date(year, month, day)
            daily = self.get_daily_summary(d)
            total["requests"] += daily["requests"]
            total["input_tokens"] += daily["input_tokens"]
            total["output_tokens"] += daily["output_tokens"]
            total["total_cost_usd"] += daily["total_cost_usd"]
            total["daily"].append(daily)
        
        total["total_cost_usd"] = round(total["total_cost_usd"], 2)
        
        return total


# Singleton
usage_tracker = UsageTracker(
    storage_dir=os.getenv("USAGE_STORAGE_DIR", "./data/usage")
)
```

---

### Option 3: Anthropic Admin API (Direct)

**Query your usage directly from Anthropic's API.**

```python
import httpx
from datetime import datetime

async def get_anthropic_usage(
    starting_at: datetime,
    ending_at: datetime,
    admin_key: str,
) -> dict:
    """
    Fetch usage from Anthropic Admin API.
    Requires ANTHROPIC_ADMIN_API_KEY (different from regular API key).
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.anthropic.com/v1/organizations/usage_report/messages",
            params={
                "starting_at": starting_at.isoformat() + "Z",
                "ending_at": ending_at.isoformat() + "Z",
                "bucket_width": "1d",
                "group_by[]": "model",
            },
            headers={
                "anthropic-version": "2023-06-01",
                "x-api-key": admin_key,
            },
        )
        response.raise_for_status()
        return response.json()
```

---

## Recommended Setup

### For Development / Low Volume

Use **built-in tracking** (Option 2):
- Zero external dependencies
- Stores usage in local JSONL files
- Add `/api/v1/usage` endpoints
- Export to CSV/spreadsheet monthly

### For Production / Scaling

Use **Langfuse** (Option 1):
- Start with free cloud tier (50k events/month)
- Automatic cost calculation
- Beautiful dashboards
- User-level attribution
- Self-host when you hit limits

---

## Cost Optimization Tips

### 1. Use Prompt Caching

Claude supports prompt caching for repeated system prompts:

```python
# Save ~90% on repeated system prompt tokens
response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}  # Cache this!
        }
    ],
    messages=messages,
)
```

### 2. Right-size Your Model

| Use Case | Model | Cost Ratio |
|----------|-------|------------|
| Simple queries | Haiku 3.5 | 1x (baseline) |
| Complex analysis | Sonnet 4.5 | ~4x |
| Research/reports | Opus 4 | ~15x |

### 3. Cache Query Results

FIA data doesn't change frequently. Cache results for 1 hour:

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def cached_fia_query(query_hash: str):
    """Cache FIA query results."""
    pass
```

### 4. Set Usage Limits

```python
# Limit tokens per request
MAX_OUTPUT_TOKENS = 2000  # ~$0.03 max per response

# Limit requests per user per day
USER_DAILY_LIMIT = 50  # ~$1.50/user/day max
```

---

## Environment Variables

```bash
# Built-in usage tracking
USAGE_STORAGE_DIR=./data/usage

# Langfuse (optional but recommended)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Anthropic Admin API (optional)
ANTHROPIC_ADMIN_API_KEY=sk-ant-admin-...
```

---

## Recommendation

**Start with built-in tracking, migrate to Langfuse when you need dashboards.**

1. Add `usage_tracker.py` now (5 minutes)
2. Add Langfuse when you have real users (30 minutes)  
3. Set up alerts when costs hit $50/month

The variable cost is almost entirely Claude API usage. Everything else is negligible at your scale.
