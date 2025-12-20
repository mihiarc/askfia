#!/usr/bin/env python
"""Build FIA DuckDB cache and upload to S3/R2.

This script downloads FIA data for specified states (or all states),
builds DuckDB files, and uploads them to S3-compatible storage.

Usage:
    # Build all states
    uv run python scripts/build_fia_cache.py --all

    # Build specific states
    uv run python scripts/build_fia_cache.py --states GA NC SC VA

    # Dry run (don't upload)
    uv run python scripts/build_fia_cache.py --states GA --dry-run
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

# Load environment variables from .env
load_dotenv()
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

console = Console()

# All US states with FIA data
ALL_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_s3_client():
    """Create S3 client from environment variables."""
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
        region_name=os.getenv("S3_REGION", "auto"),
    )


def download_state(state: str, output_dir: Path) -> Path | None:
    """Download FIA data for a state and return the DB path."""
    from pyfia import download

    try:
        db_path = download(state, dir=str(output_dir))
        return Path(db_path)
    except Exception as e:
        logger.error(f"Failed to download {state}: {e}")
        return None


def upload_to_s3(
    s3_client,
    local_path: Path,
    bucket: str,
    prefix: str,
    state: str,
) -> bool:
    """Upload a file to S3."""
    s3_key = f"{prefix}/{state}.duckdb"
    try:
        s3_client.upload_file(str(local_path), bucket, s3_key)
        return True
    except Exception as e:
        logger.error(f"Failed to upload {state}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Build and upload FIA cache")
    parser.add_argument(
        "--states",
        nargs="+",
        help="States to process (e.g., GA NC SC)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all US states",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./data/fia-build"),
        help="Local directory for downloads",
    )
    parser.add_argument(
        "--bucket",
        default=os.getenv("FIA_S3_BUCKET"),
        help="S3 bucket name",
    )
    parser.add_argument(
        "--prefix",
        default=os.getenv("FIA_S3_PREFIX", "fia-duckdb"),
        help="S3 prefix for files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download only, don't upload",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip states that already exist in S3",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        default=True,
        help="Clean up local files after upload (default: True)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_false",
        dest="cleanup",
        help="Keep local files after upload",
    )

    args = parser.parse_args()

    # Determine states to process
    if args.all:
        states = ALL_STATES
    elif args.states:
        states = [s.upper() for s in args.states]
    else:
        console.print("[red]Error: Must specify --states or --all[/red]")
        sys.exit(1)

    # Validate S3 config if not dry run
    s3_client = None
    if not args.dry_run:
        if not args.bucket:
            console.print("[red]Error: S3 bucket not configured[/red]")
            console.print("Set FIA_S3_BUCKET env var or use --bucket")
            sys.exit(1)

        try:
            s3_client = get_s3_client()
        except Exception as e:
            console.print(f"[red]Error: Failed to create S3 client: {e}[/red]")
            sys.exit(1)

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold]Building FIA cache for {len(states)} states[/bold]")
    console.print(f"Output: {args.output_dir}")
    if not args.dry_run:
        console.print(f"Bucket: {args.bucket}/{args.prefix}")
    console.print()

    # Track results
    results = {"downloaded": [], "uploaded": [], "failed": [], "skipped": []}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing states...", total=len(states))

        for state in states:
            progress.update(task, description=f"Processing {state}...")

            # Check if already exists in S3
            if args.skip_existing and s3_client:
                try:
                    s3_key = f"{args.prefix}/{state}.duckdb"
                    s3_client.head_object(Bucket=args.bucket, Key=s3_key)
                    results["skipped"].append(state)
                    progress.advance(task)
                    continue
                except Exception:
                    pass  # File doesn't exist, proceed

            # Download
            db_path = download_state(state, args.output_dir)
            if db_path:
                results["downloaded"].append(state)
                size_mb = db_path.stat().st_size / 1e6

                # Upload
                if not args.dry_run and s3_client:
                    if upload_to_s3(s3_client, db_path, args.bucket, args.prefix, state):
                        results["uploaded"].append(state)
                        console.print(f"  [green]✓[/green] {state}: {size_mb:.1f} MB uploaded")

                        # Cleanup local files to save disk space
                        if args.cleanup:
                            try:
                                # Remove the duckdb file
                                db_path.unlink()
                                # Remove the state directory if it exists and is empty
                                state_dir = db_path.parent
                                if state_dir != args.output_dir:
                                    import shutil
                                    shutil.rmtree(state_dir, ignore_errors=True)
                                console.print(f"  [dim]Cleaned up local files for {state}[/dim]")
                            except Exception as e:
                                console.print(f"  [yellow]Warning: Cleanup failed: {e}[/yellow]")
                    else:
                        results["failed"].append(state)
                        console.print(f"  [red]✗[/red] {state}: upload failed")
                else:
                    console.print(f"  [green]✓[/green] {state}: {size_mb:.1f} MB downloaded")
            else:
                results["failed"].append(state)
                console.print(f"  [red]✗[/red] {state}: download failed")

            progress.advance(task)

    # Summary table
    console.print("\n[bold]Summary[/bold]")
    table = Table()
    table.add_column("Status", style="bold")
    table.add_column("Count")
    table.add_column("States")

    if results["downloaded"]:
        table.add_row(
            "[green]Downloaded[/green]",
            str(len(results["downloaded"])),
            ", ".join(results["downloaded"][:10]) + ("..." if len(results["downloaded"]) > 10 else ""),
        )
    if results["uploaded"]:
        table.add_row(
            "[blue]Uploaded[/blue]",
            str(len(results["uploaded"])),
            ", ".join(results["uploaded"][:10]) + ("..." if len(results["uploaded"]) > 10 else ""),
        )
    if results["skipped"]:
        table.add_row(
            "[yellow]Skipped[/yellow]",
            str(len(results["skipped"])),
            ", ".join(results["skipped"][:10]) + ("..." if len(results["skipped"]) > 10 else ""),
        )
    if results["failed"]:
        table.add_row(
            "[red]Failed[/red]",
            str(len(results["failed"])),
            ", ".join(results["failed"]),
        )

    console.print(table)

    # Exit with error if any failures
    if results["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
