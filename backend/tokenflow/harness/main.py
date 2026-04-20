from __future__ import annotations

from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from tokenflow import __version__
from tokenflow.adapters.persistence import migrations as _migrations
from tokenflow.adapters.persistence import paths
from tokenflow.adapters.persistence.import_ccprophet import import_from_ccprophet
from tokenflow.adapters.persistence.repository import Repository

app = typer.Typer(
    name="tokenflow",
    help="Token Flow - Claude Code usage tracker.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.command()
def init() -> None:
    """Create ~/.tokenflow directories and run pending migrations."""
    paths.ensure_dirs()
    applied = _migrations.run_migrations()
    console.print(f"[green]ok[/green] home: {paths.tokenflow_dir()}")
    console.print(f"[green]ok[/green] db: {paths.db_path()}")
    if applied:
        console.print(f"[green]ok[/green] applied migrations: {applied}")
    else:
        console.print("[dim]no pending migrations[/dim]")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host. Locked to loopback by default."),
    port: int = typer.Option(8765, help="Bind port."),
    dev: bool = typer.Option(False, "--dev", help="Dev mode - skip static mount, expect Vite on :5173."),
) -> None:
    from tokenflow.adapters.web.app import create_app

    repo_root = Path(__file__).resolve().parents[3]
    frontend_dist = repo_root / "frontend" / "dist"
    app_instance = create_app(frontend_dist=None if dev else frontend_dist)

    console.print(f"[bold]Token Flow[/bold] v{__version__} on http://{host}:{port}")
    if dev:
        console.print("[dim]dev mode - frontend expected at http://localhost:5173[/dim]")
    uvicorn.run(app_instance, host=host, port=port, log_level="info")


def _ensure_db_lock_ok() -> bool:
    """Return True if we can hold the DB; False (and print a friendly message) if another process has it."""
    import duckdb as _duckdb

    # Windows and Linux/macOS surface "file busy" quite differently; catch broadly.
    contention_markers = ("lock", "already open", "being used", "another process")
    try:
        conn = _duckdb.connect(str(paths.db_path()))
    except (_duckdb.IOException, OSError, PermissionError) as e:
        msg = str(e).lower()
        if any(m in msg for m in contention_markers):
            console.print(
                "[red]DB is locked by another Token Flow process.[/red] "
                "Stop any running `tokenflow serve` and retry."
            )
            return False
        raise
    conn.close()
    return True


@app.command()
def doctor() -> None:
    """Report DB / hook / API key status."""
    paths.ensure_dirs()
    if not _ensure_db_lock_ok():
        raise typer.Exit(1)
    applied = _migrations.run_migrations()

    table = Table(title="Token Flow doctor", show_header=True, header_style="bold")
    table.add_column("check")
    table.add_column("status")
    table.add_column("detail")

    home = paths.tokenflow_dir()
    table.add_row("home", "ok", str(home))

    db = paths.db_path()
    table.add_row("db", "ok" if db.exists() else "missing", str(db))
    if applied:
        table.add_row("migrations (just applied)", "ok", str(applied))

    ndjson = paths.events_ndjson_path()
    if ndjson.exists() and ndjson.stat().st_size > 0:
        table.add_row("hook log", "ok", f"{ndjson} ({ndjson.stat().st_size} B)")
    else:
        table.add_row("hook log", "warn", "no events received yet")

    secret = paths.secret_path()
    table.add_row("api key", "ok" if secret.exists() else "none", "configured" if secret.exists() else "not configured")

    if db.exists():
        repo = Repository()
        try:
            cur = repo.get_current_session()
            table.add_row("active session", "ok" if cur else "-", cur["id"] if cur else "none")
        finally:
            repo.close()

    console.print(table)


@app.command("import")
def import_cmd(
    from_ccprophet: Path = typer.Option(..., "--from-ccprophet", help="Path to ccprophet events.duckdb"),
) -> None:
    """Import V1-V5 shared tables from a ccprophet DB (idempotent; PK conflicts skipped)."""
    paths.ensure_dirs()
    if not _ensure_db_lock_ok():
        raise typer.Exit(1)
    _migrations.run_migrations()
    repo = Repository()
    try:
        console.print(f"[bold]Importing[/bold] from {from_ccprophet} ...")
        counts = import_from_ccprophet(from_ccprophet, repo)
    finally:
        repo.close()

    table = Table(title="Import summary", show_header=True, header_style="bold")
    table.add_column("table")
    table.add_column("new rows", justify="right")
    total = 0
    for t, n in counts.items():
        table.add_row(t, str(n))
        total += n
    console.print(table)
    console.print(f"[green]done[/green] imported {total} rows total")


if __name__ == "__main__":
    app()
