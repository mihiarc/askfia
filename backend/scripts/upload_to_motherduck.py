"""Upload FIA DuckDB files to MotherDuck.

This script copies tables from local DuckDB files to MotherDuck,
creating a separate database for each state.

Can download from R2 first if needed.
"""

import os
import sys
from pathlib import Path

import duckdb
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def get_tables_from_local(local_path: Path) -> list[str]:
    """Get list of tables from a local DuckDB file."""
    local_conn = duckdb.connect(str(local_path), read_only=True)
    result = local_conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()
    local_conn.close()
    return [row[0] for row in result]


def download_from_r2(state: str, local_path: Path) -> bool:
    """Download a state's DuckDB file from R2."""
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        console.print("[red]boto3 not installed, cannot download from R2[/red]")
        return False

    # Get R2 credentials from environment
    endpoint = os.environ.get("S3_ENDPOINT_URL", "").strip()
    access_key = os.environ.get("S3_ACCESS_KEY", "").strip()
    secret_key = os.environ.get("S3_SECRET_KEY", "").strip()
    bucket = os.environ.get("FIA_S3_BUCKET", "").strip()
    prefix = os.environ.get("FIA_S3_PREFIX", "fia-duckdb").strip()

    if not all([endpoint, access_key, secret_key, bucket]):
        console.print("[yellow]R2 credentials not configured, skipping R2 download[/yellow]")
        return False

    console.print(f"  Downloading {state} from R2...")

    session = boto3.session.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name='us-east-1',
    )
    s3 = session.client(
        's3',
        endpoint_url=endpoint,
        config=Config(signature_version='s3v4'),
    )

    s3_key = f"{prefix}/{state}.duckdb"
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(bucket, s3_key, str(local_path))
        size_mb = local_path.stat().st_size / 1e6
        console.print(f"  [green]✓[/green] Downloaded {state} ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        console.print(f"  [red]Failed to download {state}: {e}[/red]")
        return False


def upload_state(
    local_path: Path,
    state: str,
    motherduck_token: str,
) -> None:
    """Upload a state's DuckDB file to MotherDuck."""
    console.print(f"\n[bold blue]Uploading {state}...[/bold blue]")

    # First, get tables from the local database
    tables = get_tables_from_local(local_path)
    console.print(f"  Found {len(tables)} tables to upload")

    # Connect to MotherDuck default database first
    md_db_name = f"fia_{state.lower()}"
    md_conn = duckdb.connect(f"md:?motherduck_token={motherduck_token}")

    # Create database if not exists
    md_conn.execute(f"CREATE DATABASE IF NOT EXISTS {md_db_name}")
    md_conn.execute(f"USE {md_db_name}")

    # Attach local database
    md_conn.execute(f"ATTACH '{local_path}' AS local_db (READ_ONLY)")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for table in tables:
            task = progress.add_task(f"  Copying {table}...", total=None)

            # Drop table if exists (for re-runs)
            md_conn.execute(f"DROP TABLE IF EXISTS {table}")

            # Copy table from local to MotherDuck
            md_conn.execute(f"CREATE TABLE {table} AS SELECT * FROM local_db.{table}")

            # Get row count
            count = md_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            progress.update(task, description=f"  [green]✓[/green] {table} ({count:,} rows)")
            progress.remove_task(task)
            console.print(f"  [green]✓[/green] {table} ({count:,} rows)")

    # Detach local database
    md_conn.execute("DETACH local_db")
    md_conn.close()

    console.print(f"[bold green]✓ {state} uploaded to md:{md_db_name}[/bold green]")


def main():
    """Main entry point."""
    # Get MotherDuck token from environment or argument
    motherduck_token = os.environ.get("MOTHERDUCK_TOKEN")

    if not motherduck_token and len(sys.argv) > 1:
        motherduck_token = sys.argv[1]

    if not motherduck_token:
        console.print("[red]Error: MOTHERDUCK_TOKEN not set[/red]")
        console.print("Usage: uv run python scripts/upload_to_motherduck.py <token>")
        console.print("   or: MOTHERDUCK_TOKEN=<token> uv run python scripts/upload_to_motherduck.py")
        sys.exit(1)

    # Find local DuckDB files
    data_dir = Path(__file__).parent.parent / "data" / "fia"

    if not data_dir.exists():
        console.print(f"[red]Error: Data directory not found: {data_dir}[/red]")
        sys.exit(1)

    # Find all .duckdb files
    db_files = list(data_dir.glob("*.duckdb"))

    # Also check for state subdirectories (like nc/fia.duckdb)
    for subdir in data_dir.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("."):
            for db_file in subdir.glob("*.duckdb"):
                db_files.append(db_file)

    if not db_files:
        console.print(f"[red]Error: No DuckDB files found in {data_dir}[/red]")
        sys.exit(1)

    console.print(f"[bold]Found {len(db_files)} DuckDB files to upload:[/bold]")
    for f in db_files:
        size_mb = f.stat().st_size / 1e6
        console.print(f"  - {f.name} ({size_mb:.1f} MB)")

    # Upload each file
    for db_file in db_files:
        # Extract state code from filename
        if db_file.stem.lower() == "fia":
            # File is named fia.duckdb, get state from parent dir
            state = db_file.parent.name.upper()
        else:
            state = db_file.stem.upper()

        upload_state(db_file, state, motherduck_token)

    console.print("\n[bold green]All uploads complete![/bold green]")
    console.print("\nYou can now query your data at https://app.motherduck.com")


if __name__ == "__main__":
    main()
