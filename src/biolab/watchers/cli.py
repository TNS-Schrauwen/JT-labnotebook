"""CLI interface for JT-labnotebook using Typer."""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
from datetime import datetime
import subprocess
import os

app = typer.Typer(
    name="biolab",
    help="JT Lab Notebook — Bioinformatics Project Intelligence System",
    no_args_is_help=True,
)
console = Console()

# Sub-command groups
project_app = typer.Typer(help="Manage projects")
note_app = typer.Typer(help="Create and manage notes")
experiment_app = typer.Typer(help="Manage experiments")
run_app = typer.Typer(help="Track pipeline runs")
sync_app = typer.Typer(help="Sync external data")
search_app = typer.Typer(help="Search knowledge base")
build_app = typer.Typer(help="Build documentation")

app.add_typer(project_app, name="project")
app.add_typer(note_app, name="note")
app.add_typer(experiment_app, name="exp")
app.add_typer(run_app, name="run")
app.add_typer(sync_app, name="sync")
app.add_typer(search_app, name="search")
app.add_typer(build_app, name="build")


def _get_db():
    """Get database instance."""
    from .database import BioLabDB
    from .config import load_config
    config = load_config()
    return BioLabDB(Path(config.database_path))


def _get_generator():
    """Get markdown generator."""
    from .generators.markdown import MarkdownGenerator
    from .config import load_config
    config = load_config()
    db = _get_db()
    return MarkdownGenerator(db, Path(config.docs.output_dir))


# ─── Init Command ─────────────────────────────────────────────────────

@app.command()
def init(
    name: str = typer.Option("JT Lab Notebook", help="Notebook name"),
    author: str = typer.Option("", help="Your name"),
):
    """Initialize a new lab notebook in the current directory."""
    from .config import NotebookConfig, save_config

    config = NotebookConfig(name=name, author=author)
    save_config(config)

    dirs = [
        "docs/experiments", "docs/runs/nextflow", "docs/runs/slurm",
        "docs/notes/debugging", "docs/notes/ideas",
        "docs/notes/observations", "docs/notes/todo",
        "docs/notes/general", "docs/projects", "docs/datasets",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)

    index_content = f"""# {name}

Welcome to your lab notebook.

- [Dashboard](dashboard.md)
- [Notes](notes/index.md)
- [Experiments](experiments/index.md)
- [Runs](runs/index.md)

*Initialized: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
    Path("docs/index.md").write_text(index_content)
    Path("docs/dashboard.md").write_text("# Dashboard\n\nRun `biolab build site` to generate.\n")

    # Create mkdocs.yml
    _create_mkdocs_yml(name)

    # Initialize database
    _get_db()

    # Create .gitignore additions
    gitignore_entries = """
# BioLab Notebook
.biolab/biolab.db
.biolab/biolab.db-wal
.biolab/biolab.db-shm
site/
"""
    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        existing = gitignore_path.read_text()
        if ".biolab/biolab.db" not in existing:
            gitignore_path.write_text(existing + gitignore_entries)
    else:
        gitignore_path.write_text(gitignore_entries)

    console.print(Panel.fit(
        f"[green]✅ Notebook initialized: {name}[/green]\n\n"
        f"Next steps:\n"
        f"  biolab project add <name> <path>\n"
        f"  biolab note add 'My first note'\n"
        f"  biolab build site",
        title="🧬 JT-labnotebook",
    ))


# ─── Status Command ────────────────────────────────────────────────────

@app.command()
def status():
    """Show notebook status overview."""
    from .config import load_config
    config = load_config()
    db = _get_db()

    projects = db.list_projects()
    notes = db.list_notes()
    todos = db.list_notes(category="todo")
    experiments = db.list_experiments()
    runs = db.list_nextflow_runs()

    console.print(Panel.fit(
        f"[bold]{config.name}[/bold]\n"
        f"Author: {config.author}\n\n"
        f"Projects: {len(projects)}\n"
        f"Experiments: {len(experiments)}\n"
        f"Runs: {len(runs)}\n"
        f"Notes: {len(notes)}\n"
        f"Active TODOs: {len(todos)}",
        title="Status",
    ))


# ─── Project Commands ──────────────────────────────────────────────────

@project_app.command("add")
def project_add(
    name: str = typer.Argument(..., help="Project name"),
    path: str = typer.Argument(..., help="Project directory path"),
    description: str = typer.Option("", "--desc", "-d", help="Description"),
    tags: str = typer.Option("", "--tags", "-t", help="Comma-separated tags"),
):
    """Register a project directory for tracking."""
    from .models import Project
    db = _get_db()

    project = Project(
        name=name,
        path=str(Path(path).resolve()),
        description=description if description else None,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
    )
    db.add_project(project)
    console.print(f"[green]✅ Project added: {name}[/green] ({project.path})")


@project_app.command("list")
def project_list():
    """List all tracked projects."""
    db = _get_db()
    projects = db.list_projects()

    if not projects:
        console.print("[yellow]No projects yet. Add one with: biolab project add <name> <path>[/yellow]")
        return

    table = Table(title="Projects")
    table.add_column("Name", style="bold")
    table.add_column("Path")
    table.add_column("Tags")
    table.add_column("Created")

    for p in projects:
        table.add_row(
            p.name, p.path,
            ", ".join(p.tags) if p.tags else "",
            p.created_at.strftime("%Y-%m-%d"),
        )
    console.print(table)


# ─── Note Commands ─────────────────────────────────────────────────────

@note_app.command("add")
def note_add(
    title: str = typer.Argument(..., help="Note title"),
    category: str = typer.Option("general", "--cat", "-c",
        help="Category: general, debugging, idea, observation, todo, experiment"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project name"),
    tags: str = typer.Option("", "--tags", "-t", help="Comma-separated tags"),
    content: str = typer.Option("", "--content", "-m", help="Note content"),
    editor: bool = typer.Option(False, "--edit", "-e", help="Open in $EDITOR"),
):
    """Add a note to the knowledge base."""
    from .models import Note, NoteCategory
    db = _get_db()
    gen = _get_generator()

    # Resolve project ID
    project_id = None
    if project:
        proj = db.get_project(project)
        if proj:
            project_id = proj.id

    # Get content from editor if requested
    if editor:
        content = _open_editor(f"# {title}\n\n")
    elif not content:
        content = typer.prompt("Content")

    note = Note(
        title=title,
        content=content,
        category=NoteCategory(category),
        project_id=project_id,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
    )

    db.add_note(note)
    gen.generate_note_page(note)
    gen.generate_notes_index()

    console.print(f"[green]✅ Note added:[/green] {title} [dim](id: {note.id})[/dim]")


@note_app.command("quick")
def note_quick(
    message: str = typer.Argument(..., help="Quick note content"),
    category: str = typer.Option("general", "--cat", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-p"),
):
    """Add a quick one-line note (title auto-generated from content)."""
    from .models import Note, NoteCategory
    db = _get_db()
    gen = _get_generator()

    project_id = None
    if project:
        proj = db.get_project(project)
        if proj:
            project_id = proj.id

    # Auto-generate title from first 60 chars
    title = message[:60] + ("..." if len(message) > 60 else "")

    note = Note(
        title=title,
        content=message,
        category=NoteCategory(category),
        project_id=project_id,
    )
    db.add_note(note)
    gen.generate_note_page(note)

    console.print(f"[green] Quick note saved[/green] [dim](id: {note.id})[/dim]")


@note_app.command("list")
def note_list(
    category: Optional[str] = typer.Option(None, "--cat", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    status: str = typer.Option("active", "--status", "-s"),
    limit: int = typer.Option(20, "--limit", "-n"),
):
    """List notes."""
    db = _get_db()

    project_id = None
    if project:
        proj = db.get_project(project)
        if proj:
            project_id = proj.id

    notes = db.list_notes(category=category, project_id=project_id, status=status)

    if not notes:
        console.print("[yellow]No notes found.[/yellow]")
        return

    table = Table(title=f"Notes ({status})")
    table.add_column("ID", style="dim")
    table.add_column("Category")
    table.add_column("Title", style="bold")
    table.add_column("Date")
    table.add_column("Tags")

    for note in notes[:limit]:
        cat_icon = {"debugging": "🐛", "idea": "💡", "todo": "✅",
                    "observation": "👁️", "general": "📝"}.get(
            note.category.value if hasattr(note.category, 'value') else note.category, "📝"
        )
        table.add_row(
            note.id,
            f"{cat_icon} {note.category.value if hasattr(note.category, 'value') else note.category}",
            note.title[:50],
            note.created_at.strftime("%Y-%m-%d"),
            ", ".join(note.tags) if note.tags else "",
        )
    console.print(table)


@note_app.command("cancel")
def note_cancel(
    note_id: str = typer.Argument(..., help="Note ID to cancel"),
    reason: str = typer.Option("", "--reason", "-r", help="Reason for cancellation"),
):
    """Cancel/archive a note or idea."""
    db = _get_db()
    gen = _get_generator()

    note = db.get_note(note_id)
    if not note:
        console.print(f"[red]Note not found: {note_id}[/red]")
        raise typer.Exit(1)

    update_content = note.content
    if reason:
        update_content += f"\n\n---\n**Cancelled:** {reason} ({datetime.now().strftime('%Y-%m-%d')})"

    db.update_note(note_id, status="cancelled", content=update_content)
    updated_note = db.get_note(note_id)
    if updated_note:
        gen.generate_note_page(updated_note)
        gen.generate_notes_index()

    console.print(f"[yellow]❌ Note cancelled: {note.title}[/yellow]")


@note_app.command("update")
def note_update(
    note_id: str = typer.Argument(..., help="Note ID"),
    content: str = typer.Option(None, "--content", "-m", help="New content to append"),
    tags: str = typer.Option(None, "--tags", "-t", help="New tags (replaces)"),
    title: str = typer.Option(None, "--title", help="New title"),
    editor: bool = typer.Option(False, "--edit", "-e", help="Open in editor"),
):
    """Update an existing note."""
    db = _get_db()
    gen = _get_generator()

    note = db.get_note(note_id)
    if not note:
        console.print(f"[red]Note not found: {note_id}[/red]")
        raise typer.Exit(1)

    kwargs = {}
    if title:
        kwargs["title"] = title
    if tags:
        kwargs["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if content:
        kwargs["content"] = note.content + f"\n\n---\n*Update ({datetime.now().strftime('%Y-%m-%d %H:%M')}):*\n\n{content}"
    if editor:
        new_content = _open_editor(note.content)
        kwargs["content"] = new_content

    if kwargs:
        db.update_note(note_id, **kwargs)
        updated = db.get_note(note_id)
        if updated:
            gen.generate_note_page(updated)
            gen.generate_notes_index()
        console.print(f"[green]✅ Note updated: {note.title}[/green]")
    else:
        console.print("[yellow]Nothing to update.[/yellow]")


# ─── Experiment Commands ───────────────────────────────────────────────

@experiment_app.command("add")
def exp_add(
    name: str = typer.Argument(..., help="Experiment name"),
    project: str = typer.Option(..., "--project", "-p", help="Project name"),
    hypothesis: str = typer.Option("", "--hyp", "-h", help="Hypothesis"),
    description: str = typer.Option("", "--desc", "-d", help="Description"),
    tags: str = typer.Option("", "--tags", "-t", help="Tags"),
):
    """Create a new experiment."""
    from .models import Experiment
    db = _get_db()
    gen = _get_generator()

    proj = db.get_project(project)
    if not proj:
        console.print(f"[red]Project not found: {project}[/red]")
        raise typer.Exit(1)

    exp = Experiment(
        project_id=proj.id,
        name=name,
        hypothesis=hypothesis if hypothesis else None,
        description=description if description else None,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
    )
    db.add_experiment(exp)
    gen.generate_experiment_page(exp)

    console.print(f"[green]✅ Experiment created: {name}[/green] [dim](id: {exp.id})[/dim]")


@experiment_app.command("list")
def exp_list(project: Optional[str] = typer.Option(None, "--project", "-p")):
    """List experiments."""
    db = _get_db()

    project_id = None
    if project:
        proj = db.get_project(project)
        if proj:
            project_id = proj.id

    experiments = db.list_experiments(project_id=project_id)

    table = Table(title="Experiments")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Status")
    table.add_column("Date")

    for exp in experiments:
        status_color = {"completed": "green", "failed": "red",
                       "running": "yellow"}.get(exp.status.value, "white")
        table.add_row(
            exp.id, exp.name,
            f"[{status_color}]{exp.status.value}[/{status_color}]",
            exp.created_at.strftime("%Y-%m-%d"),
        )
    console.print(table)


# ─── Run Commands ──────────────────────────────────────────────────────

@run_app.command("track")
def run_track(
    path: str = typer.Argument(..., help="Nextflow run directory"),
    project: str = typer.Option(..., "--project", "-p", help="Project name"),
    experiment: Optional[str] = typer.Option(None, "--exp", "-e", help="Experiment ID"),
):
    """Track a completed Nextflow run."""
    from .watchers.nextflow import NextflowTracker
    db = _get_db()
    gen = _get_generator()

    proj = db.get_project(project)
    if not proj:
        console.print(f"[red]Project not found: {project}[/red]")
        raise typer.Exit(1)

    tracker = NextflowTracker(db)
    run = tracker.track_run(proj.id, Path(path), experiment_id=experiment)

    # Generate run page
    run_data = {
        "run_name": run.run_name, "pipeline": run.pipeline,
        "status": run.status.value, "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "duration_seconds": run.duration_seconds, "cpu_hours": run.cpu_hours,
        "peak_memory_gb": run.peak_memory_gb, "exit_code": run.exit_code,
        "work_dir": run.work_dir, "command": run.command,
        "error_message": run.error_message,
    }
    gen.generate_run_page(run_data)

    console.print(
        f"[green]✅ Run tracked: {run.run_name}[/green] "
        f"[dim]({run.status.value})[/dim]"
    )


# ─── Sync Commands ────────────────────────────────────────────────────

@sync_app.command("slurm")
def sync_slurm(
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    days: int = typer.Option(7, "--days", "-d", help="Days to look back"),
):
    """Sync SLURM job history from sacct."""
    from .watchers.slurm import SlurmTracker
    db = _get_db()

    project_id = None
    if project:
        proj = db.get_project(project)
        if proj:
            project_id = proj.id

    tracker = SlurmTracker(db)
    count = tracker.sync_jobs(project_id=project_id, days=days)
    console.print(f"[green]✅ Synced {count} SLURM jobs[/green]")


# ─── Search Commands ───────────────────────────────────────────────────

@search_app.command("query")
def search_query(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(20, "--limit", "-n"),
):
    """Search the knowledge base."""
    db = _get_db()
    results = db.search(query, limit=limit)

    if not results:
        console.print(f"[yellow]No results for: {query}[/yellow]")
        return

    table = Table(title=f"Search: '{query}'")
    table.add_column("Type")
    table.add_column("Title")
    table.add_column("Snippet")

    for r in results:
        table.add_row(
            r.get("entity_type", ""),
            r.get("title", "")[:40],
            r.get("snippet", "")[:80],
        )
    console.print(table)


# ─── Build Commands ────────────────────────────────────────────────────

@build_app.command("site")
def build_site():
    """Build the MkDocs documentation site."""
    gen = _get_generator()
    gen.rebuild_all()

    # Run mkdocs build
    try:
        result = subprocess.run(
            ["mkdocs", "build"], capture_output=True, text=True
        )
        if result.returncode == 0:
            console.print("[green]✅ Site built successfully → ./site/[/green]")
        else:
            console.print(f"[red]Build error: {result.stderr[:200]}[/red]")
    except FileNotFoundError:
        console.print("[red]mkdocs not found. Install with: pip install mkdocs-material[/red]")


@build_app.command("serve")
def build_serve(port: int = typer.Option(8000, help="Port number")):
    """Serve the docs locally for preview."""
    gen = _get_generator()
    gen.rebuild_all()
    console.print(f"[green]Serving at http://localhost:{port}[/green]")
    subprocess.run(["mkdocs", "serve", "--dev-addr", f"localhost:{port}"])


@build_app.command("deploy")
def build_deploy():
    """Deploy to GitHub Pages."""
    gen = _get_generator()
    gen.rebuild_all()

    result = subprocess.run(
        ["mkdocs", "gh-deploy", "--force"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        console.print("[green]✅ Deployed to GitHub Pages![/green]")
    else:
        console.print(f"[red]Deploy error: {result.stderr[:200]}[/red]")


# ─── Helper Functions ─────────────────────────────────────────────────

def _open_editor(initial_content: str = "") -> str:
    """Open $EDITOR and return the content."""
    import tempfile
    editor = os.environ.get("EDITOR", "nano")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(initial_content)
        f.flush()
        subprocess.call([editor, f.name])
        f.seek(0)
    with open(f.name) as f:
        content = f.read()
    os.unlink(f.name)
    return content


def _create_mkdocs_yml(name: str):
    """Create the mkdocs.yml configuration file."""
    content = f"""site_name: "{name}"
site_description: "Personal Bioinformatics Lab Notebook"

theme:
  name: material
  palette:
    - scheme: default
      primary: teal
      accent: cyan
      toggle:
        icon: material/brightness-7
        name: Dark mode
    - scheme: slate
      primary: teal
      accent: cyan
      toggle:
        icon: material/brightness-4
        name: Light mode
  features:
    - navigation.instant
    - navigation.tracking
    - navigation.tabs
    - navigation.sections
    - search.suggest
    - search.highlight
    - content.code.copy

plugins:
  - search:
      separator: '[\\s\\-\\.]+'

markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.tasklist:
      custom_checkbox: true
  - attr_list
  - tables
  - toc:
      permalink: true
  - pymdownx.highlight:
      anchor_linenums: true

nav:
  - Home: index.md
  - Dashboard: dashboard.md
  - Notes: notes/index.md
  - Experiments: experiments/index.md
  - Runs: runs/index.md
"""
    Path("mkdocs.yml").write_text(content)


if __name__ == "__main__":
    app()