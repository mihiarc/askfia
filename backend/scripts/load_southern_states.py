"""Load remaining southern states to MotherDuck.

Downloads each state using pyfia, uploads to MotherDuck, then cleans up local files.
"""

import os
import sys
from pathlib import Path

from rich.console import Console

console = Console()

# States to load - update this list as needed
# Already loaded: GA, SC, NC, FL, AL, MS, TN, VA, KY, LA, AR, WV (southern states)
# Already loaded: ME, NH, VT, MA, RI, CT, NY, NJ, PA, DE, MD (northeast states)
# Already loaded: OH, IN, IL, MI, WI, MN, IA, MO, ND, SD, NE, KS (midwest states)
# Already loaded: WA, OR, CA, ID, MT, WY, NV, UT, CO, AZ, NM (western states)
# Remaining states to complete all 50
STATES_TO_LOAD = ["AK", "HI", "OK", "TX"]


def download_state(state: str, data_dir: Path) -> Path:
    """Download a state's FIA data using pyfia."""
    from pyfia import download

    console.print(f"\n[bold blue]Downloading {state}...[/bold blue]")

    # Download using pyfia's download function
    # This downloads from FIA DataMart and converts to DuckDB
    db_path = download(state, dir=data_dir, common=True, force=True)

    size_mb = db_path.stat().st_size / 1e6
    console.print(f"  [green]File size: {size_mb:.1f} MB[/green]")

    return db_path


def upload_state(db_path: Path, state: str, motherduck_token: str) -> str:
    """Upload a state to MotherDuck."""
    from upload_to_motherduck import upload_state as do_upload

    return do_upload(db_path, state, motherduck_token)


def cleanup(db_path: Path, state: str):
    """Remove local database file and its directory."""
    import shutil

    if db_path.exists():
        db_path.unlink()

    # Also remove the state directory if it's empty
    state_dir = db_path.parent
    if state_dir.exists() and not any(state_dir.iterdir()):
        state_dir.rmdir()

    # Clean up cache for this state too
    cache_dir = state_dir.parent / ".cache"
    if cache_dir.exists():
        for cache_file in cache_dir.glob(f"*{state.lower()}*"):
            cache_file.unlink()

    console.print(f"  [dim]Cleaned up local files for {state}[/dim]")


def main():
    """Main entry point."""
    motherduck_token = os.environ.get("MOTHERDUCK_TOKEN")

    if not motherduck_token and len(sys.argv) > 1:
        motherduck_token = sys.argv[1]

    if not motherduck_token:
        console.print("[red]Error: MOTHERDUCK_TOKEN not set[/red]")
        console.print("Usage: MOTHERDUCK_TOKEN=<token> uv run python scripts/load_southern_states.py")
        sys.exit(1)

    data_dir = Path(__file__).parent.parent / "data" / "fia"
    data_dir.mkdir(parents=True, exist_ok=True)

    uploaded_dbs = []
    failed_states = []

    console.print(f"[bold]Loading {len(STATES_TO_LOAD)} states to MotherDuck[/bold]")
    console.print(f"States: {', '.join(STATES_TO_LOAD)}")

    for state in STATES_TO_LOAD:
        try:
            # Download
            db_path = download_state(state, data_dir)

            # Upload
            db_name = upload_state(db_path, state, motherduck_token)
            uploaded_dbs.append(db_name)

            # Cleanup
            cleanup(db_path, state)

        except Exception as e:
            console.print(f"[red]Error processing {state}: {e}[/red]")
            failed_states.append((state, str(e)))
            # Clean up on error too
            db_path = data_dir / f"{state}.duckdb"
            if db_path.exists():
                db_path.unlink()

    # Summary
    console.print("\n" + "=" * 50)
    console.print("[bold green]Upload Summary[/bold green]")
    console.print(f"Successfully uploaded: {len(uploaded_dbs)}")
    for db_name in uploaded_dbs:
        console.print(f"  - md:{db_name}")

    if failed_states:
        console.print(f"\n[bold red]Failed: {len(failed_states)}[/bold red]")
        for state, error in failed_states:
            console.print(f"  - {state}: {error}")

    console.print("\nView your data at https://app.motherduck.com")


if __name__ == "__main__":
    main()
