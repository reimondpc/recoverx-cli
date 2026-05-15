from __future__ import annotations

import json
import os
import tempfile

import typer
from rich.console import Console
from rich.table import Table

from recoverx.core.cases import CaseManager
from recoverx.core.indexing.storage import StorageBackend

case_app = typer.Typer(
    name="case",
    help="Create and manage forensic investigation cases.",
    rich_markup_mode="rich",
)

DEFAULT_DB = os.path.join(tempfile.gettempdir(), "recoverx_cases.db")


def _get_manager(db: str = "") -> CaseManager:
    storage = StorageBackend(db or DEFAULT_DB, read_only=False)
    storage.open()
    return CaseManager(storage)


@case_app.command()
def create(
    name: str = typer.Argument(..., help="Case name."),
    description: str = typer.Option("", "--description", "-d", help="Case description."),
    examiner: str = typer.Option("", "--examiner", "-e", help="Examiner name."),
    db: str = typer.Option("", "--db", help="Case database path."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Create a new investigation case."""
    console = Console()
    mgr = _get_manager(db)
    case = mgr.create_case(name=name, description=description, examiner=examiner)
    if json_output:
        console.print(json.dumps(case.to_dict(), indent=2, default=str))
    else:
        console.print(f"[green]Case created:[/green] {case.case_id}")
        console.print(f"  Name:       {case.metadata.name}")
        console.print(f"  Examiner:   {case.metadata.examiner}")
        console.print(f"  Status:     {case.metadata.status}")


@case_app.command()
def open(
    case_id: str = typer.Argument(..., help="Case ID to open."),
    db: str = typer.Option("", "--db", help="Case database path."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Open an existing case and show its metadata."""
    console = Console()
    mgr = _get_manager(db)
    case = mgr.get_case(case_id)
    if case is None:
        console.print(f"[red]Case not found:[/red] {case_id}")
        raise typer.Exit(code=1)
    if json_output:
        console.print(json.dumps(case.to_dict(), indent=2, default=str))
    else:
        console.print(f"\n[bold cyan]Case:[/bold cyan] {case.metadata.name}")
        console.print(f"  ID:          {case.case_id}")
        console.print(f"  Description: {case.metadata.description}")
        console.print(f"  Examiner:    {case.metadata.examiner}")
        console.print(f"  Status:      {case.metadata.status}")
        bm = case.get_bookmarks()
        sq = case.get_saved_queries()
        console.print(f"  Bookmarks:   {len(bm)}")
        console.print(f"  Saved queries: {len(sq)}")


@case_app.command()
def list(
    status: str = typer.Option("", "--status", "-s", help="Filter by status (open/closed)."),
    db: str = typer.Option("", "--db", help="Case database path."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List all investigation cases."""
    console = Console()
    mgr = _get_manager(db)
    cases = mgr.list_cases(status=status if status else None)
    if not cases:
        console.print("[yellow]No cases found.[/yellow]")
        return
    if json_output:
        console.print(json.dumps([c.to_dict() for c in cases], indent=2, default=str))
    else:
        table = Table(title=f"Cases ({len(cases)})")
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("Examiner")
        table.add_column("Status")
        table.add_column("Created")
        for c in cases:
            table.add_row(
                c.case_id[:12],
                c.name or "",
                c.examiner or "",
                c.status,
                c.created_at.isoformat() if c.created_at else "",
            )
        console.print(table)


@case_app.command()
def close(
    case_id: str = typer.Argument(..., help="Case ID to close."),
    db: str = typer.Option("", "--db", help="Case database path."),
) -> None:
    """Close an investigation case."""
    console = Console()
    mgr = _get_manager(db)
    mgr.close_case(case_id)
    console.print(f"[green]Case closed:[/green] {case_id}")


@case_app.command()
def delete(
    case_id: str = typer.Argument(..., help="Case ID to delete."),
    db: str = typer.Option("", "--db", help="Case database path."),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation."),
) -> None:
    """Permanently delete a case and all its data."""
    console = Console()
    if not force:
        console.print("[yellow]Use --force to confirm deletion.[/yellow]")
        raise typer.Exit(code=1)
    mgr = _get_manager(db)
    mgr.delete_case(case_id)
    console.print(f"[red]Case deleted:[/red] {case_id}")
