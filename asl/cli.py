"""CLI interface for ASL."""

import click
from rich.console import Console
from rich.markup import escape

from .recorder import Recorder
from .searcher import Searcher
from .indexer import Indexer

console = Console()


@click.group()
@click.version_option(version=__import__("asl").__version__)
def cli():
    """Agent Session Logger — Record, index, and search AI agent sessions."""
    pass


@cli.command()
@click.argument("session_id")
@click.option("--agent", default="claude-code", help="Agent type (claude-code, codex, cursor)")
@click.option("--project", default=".", help="Project path")
def record(session_id: str, agent: str, project: str):
    """Record a new session."""
    recorder = Recorder(session_id=session_id, agent=agent, project=project)
    recorder.start()
    console.print(f"[green]Recording session '{session_id}'[/green]")
    console.print("[yellow]Press Ctrl+C to stop recording[/yellow]")
    try:
        recorder.wait()
    except KeyboardInterrupt:
        recorder.stop()
        console.print(f"[green]Session saved: {recorder.session_file}[/green]")


@cli.command()
@click.argument("query")
@click.option("--limit", default=10, help="Max results")
@click.option("--project", default=".", help="Project path")
def search(query: str, limit: int, project: str):
    """Search across recorded sessions."""
    searcher = Searcher(project=project)
    results = searcher.search(query, limit=limit)
    if not results:
        console.print("[yellow]No results found[/yellow]")
        return
    for r in results:
        console.print(f"[bold cyan]{escape(r['session_id'])}[/bold cyan]  [dim]{r['timestamp']}[/dim]")
        console.print(f"  {escape(r['snippet'])}", highlight=False, soft_wrap=True)
        console.print()


@cli.command()
@click.argument("session_id")
@click.option("--project", default=".", help="Project path")
def export(session_id: str, project: str):
    """Export a session as markdown."""
    from .exporter import export_session
    md = export_session(session_id, project)
    console.print(md)


@cli.command()
@click.option("--project", default=".", help="Project path")
def list(project: str):
    """List all recorded sessions."""
    from .store import Store
    store = Store(project)
    sessions = store.list_sessions()
    if not sessions:
        console.print("[yellow]No sessions recorded yet[/yellow]")
        return
    for s in sessions:
        console.print(f"[cyan]{escape(s['id'])}[/cyan]  [dim]{s['agent']}  {s['started_at']}[/dim]")


@cli.command()
@click.option("--project", default=".", help="Project path")
def init(project: str):
    """Initialize ASL in a project."""
    from .store import Store
    store = Store(project)
    store.init_db()
    console.print(f"[green]Initialized ASL in {project}[/green]")
    console.print(f"Database: {store.db_path}")

if __name__ == '__main__':
    cli()
