"""Usage tracking endpoints."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from ...auth import require_auth
from ...services.usage_tracker import usage_tracker

# All usage endpoints require authentication
router = APIRouter(prefix="/usage", tags=["usage"], dependencies=[require_auth])


@router.get("/today")
async def get_today_usage():
    """Get usage summary for today."""
    return usage_tracker.get_daily_summary()


@router.get("/daily")
async def get_daily_usage(
    day: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
):
    """Get usage summary for a specific day."""
    if day:
        try:
            target_date = date.fromisoformat(day)
        except ValueError:
            return {"error": "Invalid date format. Use YYYY-MM-DD"}
    else:
        target_date = date.today()

    return usage_tracker.get_daily_summary(target_date)


@router.get("/monthly")
async def get_monthly_usage(
    year: Optional[int] = Query(None, description="Year (defaults to current)"),
    month: Optional[int] = Query(None, description="Month (1-12, defaults to current)"),
):
    """Get usage summary for a month."""
    return usage_tracker.get_monthly_summary(year, month)


@router.get("/recent")
async def get_recent_usage(
    limit: int = Query(50, ge=1, le=500, description="Number of records to return"),
):
    """Get recent usage records."""
    records = usage_tracker.get_recent_records(limit)
    return {
        "count": len(records),
        "records": records,
    }


@router.get("/summary")
async def get_usage_summary():
    """Get comprehensive usage summary."""
    today = usage_tracker.get_daily_summary()
    monthly = usage_tracker.get_monthly_summary()

    return {
        "today": today,
        "month_to_date": {
            "requests": monthly["requests"],
            "input_tokens": monthly["input_tokens"],
            "output_tokens": monthly["output_tokens"],
            "total_cost_usd": monthly["total_cost_usd"],
        },
        "storage_dir": str(usage_tracker.storage_dir),
    }
