"""Built-in usage tracking for Claude API costs."""

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional
import asyncio
import aiofiles

logger = logging.getLogger(__name__)

# Claude pricing (as of December 2024)
PRICING = {
    "claude-sonnet-4-5-20250929": {
        "input": 3.00 / 1_000_000,   # $3 per million input tokens
        "output": 15.00 / 1_000_000,  # $15 per million output tokens
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.00 / 1_000_000,
        "output": 15.00 / 1_000_000,
    },
    "claude-3-5-haiku-20241022": {
        "input": 0.80 / 1_000_000,
        "output": 4.00 / 1_000_000,
    },
    "claude-3-opus-20240229": {
        "input": 15.00 / 1_000_000,
        "output": 75.00 / 1_000_000,
    },
}


@dataclass
class UsageRecord:
    """Single API usage record."""

    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    tool_calls: int = 0
    latency_ms: int = 0
    query_type: Optional[str] = None  # e.g., "forest_area", "timber_volume"


class UsageTracker:
    """Track Claude API usage and costs.

    Stores usage records in daily JSONL files for easy analysis.
    Thread-safe with async lock for concurrent writes.
    """

    def __init__(self, storage_dir: str = "./data/usage"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        logger.info(f"Usage tracker initialized: {self.storage_dir}")

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate cost for a request."""
        # Find matching pricing (handle model version suffixes)
        pricing = None
        for model_key, model_pricing in PRICING.items():
            if model.startswith(model_key.rsplit("-", 1)[0]):
                pricing = model_pricing
                break

        if pricing is None:
            # Default to Sonnet pricing
            pricing = PRICING["claude-sonnet-4-5-20250929"]
            logger.warning(f"Unknown model {model}, using Sonnet pricing")

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
        query_type: str | None = None,
    ) -> UsageRecord:
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
            query_type=query_type,
        )

        # Append to daily log file
        today = date.today().isoformat()
        log_file = self.storage_dir / f"{today}.jsonl"

        async with self._lock:
            async with aiofiles.open(log_file, "a") as f:
                await f.write(json.dumps(asdict(record)) + "\n")

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
                "total_cost_usd": 0.0,
                "unique_users": 0,
                "by_query_type": {},
            }

        requests = 0
        input_tokens = 0
        output_tokens = 0
        total_cost = 0.0
        users = set()
        by_query_type: dict[str, int] = {}

        with open(log_file) as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                requests += 1
                input_tokens += record["input_tokens"]
                output_tokens += record["output_tokens"]
                total_cost += record["cost_usd"]
                if record.get("user_id"):
                    users.add(record["user_id"])
                query_type = record.get("query_type", "unknown")
                by_query_type[query_type] = by_query_type.get(query_type, 0) + 1

        return {
            "date": day.isoformat(),
            "requests": requests,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_cost_usd": round(total_cost, 4),
            "unique_users": len(users),
            "by_query_type": by_query_type,
        }

    def get_monthly_summary(self, year: int | None = None, month: int | None = None) -> dict:
        """Get usage summary for a month."""
        from calendar import monthrange

        today = date.today()
        year = year or today.year
        month = month or today.month
        _, days_in_month = monthrange(year, month)

        total = {
            "year": year,
            "month": month,
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost_usd": 0.0,
            "unique_users": set(),
            "daily": [],
        }

        for day_num in range(1, days_in_month + 1):
            d = date(year, month, day_num)
            if d > today:
                break
            daily = self.get_daily_summary(d)
            total["requests"] += daily["requests"]
            total["input_tokens"] += daily["input_tokens"]
            total["output_tokens"] += daily["output_tokens"]
            total["total_cost_usd"] += daily["total_cost_usd"]
            if daily["requests"] > 0:
                total["daily"].append(daily)

        total["total_cost_usd"] = round(total["total_cost_usd"], 2)
        total["unique_users"] = len(total["unique_users"]) if isinstance(total["unique_users"], set) else 0

        return total

    def get_recent_records(self, limit: int = 100) -> list[dict]:
        """Get the most recent usage records."""
        records = []

        # Get files sorted by date descending
        log_files = sorted(
            self.storage_dir.glob("*.jsonl"),
            key=lambda f: f.stem,
            reverse=True
        )

        for log_file in log_files:
            with open(log_file) as f:
                file_records = []
                for line in f:
                    if line.strip():
                        file_records.append(json.loads(line))
                # Reverse to get newest first within file
                records.extend(reversed(file_records))
                if len(records) >= limit:
                    break

        return records[:limit]


def get_usage_tracker() -> UsageTracker:
    """Get the configured UsageTracker instance."""
    from ..config import settings

    storage_dir = getattr(settings, 'usage_storage_dir', './data/usage')
    return UsageTracker(storage_dir=storage_dir)


# Singleton instance
usage_tracker = get_usage_tracker()
