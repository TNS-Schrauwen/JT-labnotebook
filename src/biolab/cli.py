"""CLI interface for JT-labnotebook."""
import typer
from pathlib import Path
from typing import Optional
from datetime import datetime
import subprocess
import os
import re

app = typer.Typer(
    name="biolab",
    help="JT Lab Notebook — Bioinformatics Project Intelligence System",
    no_args_is_help=True,
)

@app.command()
def init(
    name: str = typer.Option("JT Lab Notebook", help="Notebook name"),
    author: str = typer.Option("", help="Your name"),
):
    """Initialize a new lab notebook in the current directory."""
    # Create directories
    dirs = [
        ".biolab",
        "docs", "docs/experiments", "docs/runs/nextflow", "docs/runs/slurm",
        "docs/notes/debugging", "docs/notes/ideas",
        "docs/notes/observations", "docs/notes/todo",
        "docs/notes/general", "docs/projects", "docs/datasets",
        "docs/scripts",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)

    # Create config
    config_content = f"""version: "1.0"
name: "{name}"
author: "{author}"
institution: ""
database_path: ".biolab/biolab.db"
retention_days: 90
"""
    Path(".biolab/config.yaml").write_text(config_content)

    # Create docs/index.md
    now = datetime.now()
    index_content = f"""# {name}

**Author:** {author}  
**Last Updated:** {now.strftime('%Y-%m-%d')}

---

## Navigation

| Section | Description |
|---------|-------------|
| [Dashboard](dashboard.md) | Overview of all activity |
| [Projects](projects/index.md) | Registered project directories |
| [Experiments](experiments/index.md) | Tracked experiments |
| [Runs](runs/index.md) | Pipeline execution history |
| [Notes](notes/index.md) | All notes by category |
| [Datasets](datasets/index.md) | Dataset registry |

## Quick Links

- [Active TODOs](notes/todo/index.md)
- [Ideas](notes/ideas/index.md)
- [Debugging Journal](notes/debugging/index.md)

---
*Initialized: {now.strftime('%Y-%m-%d %H:%M')}*
"""
    Path("docs/index.md").write_text(index_content)
    Path("docs/dashboard.md").write_text("# Dashboard\n\n*Run `biolab build` to generate.*\n")

    # Create index files for each section
    Path("docs/notes/index.md").write_text("# Notes\n\n## Categories\n\n- [General](general/index.md)\n- [Debugging](debugging/index.md)\n- [Ideas](ideas/index.md)\n- [TODOs](todo/index.md)\n- [Observations](observations/index.md)\n")
    Path("docs/notes/general/index.md").write_text("# General Notes\n\n*No notes yet.*\n")
    Path("docs/notes/debugging/index.md").write_text("# Debugging Notes\n\n*No notes yet.*\n")
    Path("docs/notes/ideas/index.md").write_text("# Ideas\n\n*No ideas yet.*\n")
    Path("docs/notes/todo/index.md").write_text("# TODOs\n\n## Active\n\n*No TODOs yet.*\n\n## Completed\n\n*None.*\n")
    Path("docs/notes/observations/index.md").write_text("# Observations\n\n*No observations yet.*\n")
    Path("docs/experiments/index.md").write_text("# Experiments\n\n*No experiments yet.*\n")
    Path("docs/runs/index.md").write_text("# Pipeline Runs\n\n- [Nextflow Runs](nextflow/index.md)\n- [SLURM Jobs](slurm/index.md)\n")
    Path("docs/runs/nextflow/index.md").write_text("jects\n\n*No projects registered yet.*\n")
    Path("docs/datasets/index.md").write_text("# Datasets\n\n*No datasets registered yet.*\n")

    # Create mkdocs.yml if it doesn't exist
    if not Path("mkdocs.yml").exists():
        _create_mkdocs_yml(name)

    typer.echo(f"Notebook initialized: {name}")
    typer.echo(f"   Author: {author}")
    typer.echo(f"   Config: .biolab/config.yaml")
    typer.echo(f"   Docs:   docs/")
    typer.echo("")
    typer.echo("Next steps:")
    typer.echo("  biolab status")
    typer.echo("  biolab project <name> <path>")
    typer.echo("  biolab note 'My first note'")
    typer.echo("  biolab build")


# ═══════════════════════════════════════════════════════════════════════
# STATUS COMMAND
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def status():
    """Show notebook status overview."""
    config_path = Path(".biolab/config.yaml")
    if not config_path.exists():
        typer.echo("Error: No notebook found here. Run: biolab init")
        raise typer.Exit(1)

    import yaml
    config = yaml.safe_load(config_path.read_text())

    typer.echo(f"\n {config.get('name', 'Lab Notebook')}")
    typer.echo(f"   Author: {config.get('author', 'Unknown')}")
    typer.echo("")

    # Count files
    projects = _count_md_files("docs/projects")
    notes_debug = _count_md_files("docs/notes/debugging")
    notes_ideas = _count_md_files("docs/notes/ideas")
    notes_todo = _count_md_files("docs/notes/todo")
    notes_general = _count_md_files("docs/notes/general")
    notes_obs = _count_md_files("docs/notes/observations")
    experiments = _count_md_files("docs/experiments")
    runs_nf = _count_md_files("docs/runs/nextflow")
    runs_slurm = _count_md_files("docs/runs/slurm")
    datasets = _count_md_files("docs/datasets")

    total_notes = notes_debug + notes_ideas + notes_todo + notes_general + notes_obs

    typer.echo(f"  Projects:     {projects}")
    typer.echo(f"  Datasets:     {datasets}")
    typer.echo(f"  Experiments:  {experiments}")
    typer.echo(f"  Nextflow Runs: {runs_nf}")
    typer.echo(f"  SLURM Jobs:   {runs_slurm}")
    typer.echo(f"  Notes:        {total_notes}")
    typer.echo(f"  Debugging: {notes_debug}")
    typer.echo(f"  Ideas:     {notes_ideas}")
    typer.echo(f"  TODOs:     {notes_todo}")
    typer.echo(f"  Observations: {notes_obs}")
    typer.echo(f"  General:   {notes_general}")
    typer.echo("")

@app.command()
def project(
    name: str = typer.Argument(..., help="Project name"),
    path: str = typer.Argument(..., help="Path to project directory"),
    description: str = typer.Option("", "--desc", "-d", help="Project description"),
    tags: str = typer.Option("", "--tags", "-t", help="Comma-separated tags"),
    organism: str = typer.Option("", "--organism", "-o", help="Organism (e.g., Homo sapiens)"),
    pipeline: str = typer.Option("", "--pipeline", help="Pipeline tool (e.g., nextflow, snakemake)"),
):
    """Register a project directory for tracking."""
    project_path = Path(path).resolve()

    # Check if path exists
    if not project_path.exists():
        typer.echo(f" Warning: Path does not exist: {project_path}")
        create = typer.confirm("Register anyway?")
        if not create:
            raise typer.Exit()

    # Create project page
    projects_dir = Path("docs/projects")
    projects_dir.mkdir(parents=True, exist_ok=True)

    slug = _slugify(name)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    now = datetime.now()

    content = f"""---
title: "{name}"
path: "{project_path}"
created: {now.strftime('%Y-%m-%d')}
tags: {tag_list}
status: active
organism: "{organism}"
pipeline: "{pipeline}"
---

# {name}

| Field | Value |
|-------|-------|
| **Path** | `{project_path}` |
| **Created** | {now.strftime('%Y-%m-%d')} |
| **Status** | Active |
| **Description** | {description if description else 'N/A'} |
| **Organism** | {organism if organism else 'N/A'} |
| **Pipeline** | {pipeline if pipeline else 'N/A'} |
| **Tags** | {', '.join(tag_list) if tag_list else 'None'} |

## Description

{description if description else '*Add project description here.*'}

## Directory Structure

```
{project_path}/
├── (update with actual structure)
```

## Pipeline Configuration

*Add key parameters, config files, and pipeline details here.*

## Runs

| Date | Run Name | Status | Duration | Notes |
|------|----------|--------|----------|-------|
| | | | | |

## Datasets

| Name | Path | Format | Samples | Size |
|------|------|--------|---------|------|
| | | | | |

## Related Notes

- 

---
*Registered: {now.strftime('%Y-%m-%d %H:%M')}*
"""

    filepath = projects_dir / f"{slug}.md"
    filepath.write_text(content)

    # Update projects index
    _rebuild_projects_index()

    typer.echo(f"Project registered: {name}")
    typer.echo(f"   Path: {project_path}")
    typer.echo(f"   Page: {filepath}")



@app.command()
def projects():
    """List all registered projects."""
    projects_dir = Path("docs/projects")
    project_files = sorted(projects_dir.glob("*.md"))
    project_files = [f for f in project_files if f.name != "index.md"]

    if not project_files:
        typer.echo(" No projects registered yet.")
        typer.echo("  Add one with: biolab project <name> <path>")
        return

    typer.echo("\n Registered Projects:\n")
    for pf in project_files:
        content = pf.read_text()
        title_match = re.search(r'title:\s*"(.+?)"', content)
        path_match = re.search(r'path:\s*"(.+?)"', content)
        status_match = re.search(r'status:\s*(\S+)', content)

        title = title_match.group(1) if title_match else pf.stem
        path = path_match.group(1) if path_match else "unknown"
        status = status_match.group(1) if status_match else "active"

        typer.echo(f"  [{status}] {title}")
        typer.echo(f"    {path}")
        typer.echo("")


# ═══════════════════════════════════════════════════════════════════════
# NOTE COMMAND
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def note(
    message: str = typer.Argument(..., help="Note content"),
    category: str = typer.Option("general", "--cat", "-c",
        help="Category: general, debugging, ideas, todo, observations"),
    title: Optional[str] = typer.Option(None, "--title", help="Link to project"),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags"),
    editor: bool = typer.Option(False, "--edit", "-e", help="Open in $EDITOR"),
):
    """Add a note to the notebook."""
    now = datetime.now()
    note_title = title if title else message[:60]
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Get content
    if editor:
        content_body = _open_editor(f"{message}\n\n")
    else:
        content_body = message

    # Category icon
    icons = {
        "debugging": "🐛", "ideas": "💡", "todo": "✅",
        "observations": "👁️", "general": "📝",
    }
    # Build markdown
    slug = _slugify(note_title)
    filename = f"{now.strftime('%Y-%m-%d')}_{slug}.md"

    cat_dir = Path(f"docs/notes/{category}")
    cat_dir.mkdir(parents=True, exist_ok=True)

    content = f"""---
title: "{note_title}"
date: {now.strftime('%Y-%m-%d %H:%M')}
category: {category}
tags: {tag_list}
status: active
project: "{project_name or ''}"
---

# {note_title}

{content_body}

"""
    if project_name:
        content += f"\n**Project:** {project_name}\n"

    content += f"""
---
*Created: {now.strftime('%Y-%m-%d %H:%M')}*
"""

    filepath = cat_dir / filename
    filepath.write_text(content)

    # Rebuild category index
    _rebuild_notes_index(category)

    typer.echo(f"Note saved: {filepath}")


# ═══════════════════════════════════════════════════════════════════════
# IDEA COMMAND (shortcut)
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def idea(
    message: str = typer.Argument(..., help="Idea description"),
    project_name: Optional[str] = typer.Option(None, "--project", "-p", help="Link to project"),
    tags: str = typer.Option("", "--tags", "-t", help="Comma-separated tags"),
):
    """Quick shortcut to add an idea."""
    now = datetime.now()
    slug = _slugify(message[:40])
    filename = f"{now.strftime('%Y-%m-%d')}_{slug}.md"
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    idea_dir = Path("docs/notes/ideas")
    idea_dir.mkdir(parents=True, exist_ok=True)

    content = f"""---
title: "{message[:60]}"
date: {now.strftime('%Y-%m-%d %H:%M')}
category: idea
status: active
tags: {tag_list}
project: "{project_name or ''}"
---

# {message[:60]}

{message}

## Why

*Explain rationale here.*

## Plan

*How would you implement this?*

## Priority

*Low / Medium / High*

---
*Created: {now.strftime('%Y-%m-%d %H:%M')}*
"""
    filepath = idea_dir / filename
    filepath.write_text(content)
    _rebuild_notes_index("ideas")

    typer.echo(f"Idea saved: {filepath}")


# ═══════════════════════════════════════════════════════════════════════
# TODO COMMAND (shortcut)
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def todo(
    message: str = typer.Argument(..., help="TODO item"),
    project_name: Optional[str] = typer.Option(None, "--project", "-p", help="Link to project"),
    priority: str = typer.Option("medium", "--priority", help="Priority: low, medium, high"),
):
    """Quick shortcut to add a TODO."""
    now = datetime.now()
    slug = _slugify(message[:40])
    filename = f"{now.strftime('%Y-%m-%d')}_{slug}.md"

    todo_dir = Path("docs/notes/todo")
    todo_dir.mkdir(parents=True, exist_ok=True)

    content = f"""---
title: "{message[:60]}"
date: {now.strftime('%Y-%m-%d %H:%M')}
category: todo
status: active
priority: {priority}
project: "{project_name or ''}"
---

# {message[:60]}

- [ ] {message}

**Priority:** {priority}
"""
    if project_name:
        content += f"**Project:** {project_name}\n"

    content += f"""
---
*Created: {now.strftime('%Y-%m-%d %H:%M')}*
"""
    filepath = todo_dir / filename
    filepath.write_text(content)
    _rebuild_notes_index("todo")

    typer.echo(f"TODO saved: {filepath}")


# ═══════════════════════════════════════════════════════════════════════
# DEBUG COMMAND (shortcut)
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def debug(
    message: str = typer.Argument(..., help="Debugging note"),
    project_name: Optional[str] = typer.Option(None, "--project", "-p", help="Link to project"),
    error: str = typer.Option("", "--error", help="Error message"),
    fix: str = typer.Option("", "--fix", help="The fix/solution"),
    tags: str = typer.Option("", "--tags", "-t", help="Comma-separated tags"),
):
    """Add a debugging note with optional error and fix."""
    now = datetime.now()
    slug = _slugify(message[:40])
    filename = f"{now.strftime('%Y-%m-%d')}_{slug}.md"
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    debug_dir = Path("docs/notes/debugging")
    debug_dir.mkdir(parents=True, exist_ok=True)

    content = f"""---
title: "{message[:60]}"
date: {now.strftime('%Y-%m-%d %H:%M')}
category: debugging
status: {"resolved" if fix else "investigating"}
tags: {tag_list}
project: "{project_name or ''}"
---

# {message[:60]}

**Status:** {"Resolved" if fix else "Investigating"}
"""
    if project_name:
        content += f"**Project:** {project_name}\n"

    content += f"\n## Problem\n\n{message}\n"

    if error:
        content += f"\n## Error\n\n```\n{error}\n```\n"

    if fix:
        content += f"\n## Solution\n\n{fix}\n"
    else:
        content += "\n## Solution\n\n*Pending...*\n"

    content += f"""
---
*Created: {now.strftime('%Y-%m-%d %H:%M')}*
"""
    filepath = debug_dir / filename
    filepath.write_text(content)
    _rebuild_notes_index("debugging")

    typer.echo(f"Debug note saved: {filepath}")


# ═══════════════════════════════════════════════════════════════════════
# OBSERVE COMMAND
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def observe(
    message: str = typer.Argument(..., help="Observation"),
    project_name: Optional[str] = typer.Option(None, "--project", "-p", help="Link to project"),
):
    """Add an observation note."""
    now = datetime.now()
    slug = _slugify(message[:40])
    filename = f"{now.strftime('%Y-%m-%d')}_{slug}.md"

    obs_dir = Path("docs/notes/observations")
    obs_dir.mkdir(parents=True, exist_ok=True)

    content = f"""---
title: "{message[:60]}"
date: {now.strftime('%Y-%m-%d %H:%M')}
category: observation
status: active
project: "{project_name or ''}"
---

# {message[:60]}

{message}

---
*Created: {now.strftime('%Y-%m-%d %H:%M')}*
"""
    filepath = obs_dir / filename
    filepath.write_text(content)
    _rebuild_notes_index("observations")

    typer.echo(f"Observation saved: {filepath}")


# ═══════════════════════════════════════════════════════════════════════
# EXPERIMENT COMMAND
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def experiment(
    name: str = typer.Argument(..., help="Experiment name"),
    project_name: str = typer.Option(..., "--project", "-p", help="Project name"),
    hypothesis: str = typer.Option("", "--hyp", "-h", help="Hypothesis"),
    description: str = typer.Option("", "--desc", "-d", help="Description"),
    tags: str = typer.Option("", "--tags", "-t", help="Comma-separated tags"),
):
    """Create a new experiment."""
    now = datetime.now()
    slug = _slugify(name)
    filename = f"{now.strftime('%Y-%m-%d')}_{slug}.md"
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    exp_dir = Path("docs/experiments")
    exp_dir.mkdir(parents=True, exist_ok=True)

    content = f"""---
title: "{name}"
date: {now.strftime('%Y-%m-%d')}
project: "{project_name}"
status: active
tags: {tag_list}
---

# {name}

| Field | Value |
|-------|-------|
| **Date** | {now.strftime('%Y-%m-%d')} |
| **Project** | {project_name} |
| **Status** | In Progress |

## Hypothesis

{hypothesis if hypothesis else '*State your hypothesis here.*'}

## Description

{description if description else '*Describe the experimental setup.*'}

## Parameters

| Parameter | Value |
|-----------|-------|
| | |

## Methods

*Describe the methods used.*

## Results

*Pending...*

## Conclusion

*Pending...*

---
*Created: {now.strftime('%Y-%m-%d %H:%M')}*
"""
    filepath = exp_dir / filename
    filepath.write_text(content)
    _rebuild_experiments_index()

    typer.echo(f"Experiment created: {filepath}")


# ═══════════════════════════════════════════════════════════════════════
# RUN COMMAND (Nextflow tracking)
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def run(
    name: str = typer.Argument(..., help="Run name or identifier"),
    project_name: str = typer.Option(..., "--project", "-p", help="Project name"),
    pipeline: str = typer.Option("", "--pipeline", help="Pipeline file or name"),
    status_val: str = typer.Option("completed", "--status", "-s", help="Status: completed, failed, running"),
    duration: str = typer.Option("", "--duration", help="Duration (e.g., '23m', '2h 15m')"),
    command: str = typer.Option("", "--cmd", help="Command that was run"),
    work_dir: str = typer.Option("", "--workdir", "-w", help="Working directory"),
    output_dir: str = typer.Option("", "--outdir", "-o", help="Output directory"),
    error_msg: str = typer.Option("", "--error", help="Error message if failed"),
    notes: str = typer.Option("", "--notes", "-n", help="Additional notes"),
    cpu_hours: float = typer.Option(0.0, "--cpu", help="CPU hours used"),
    memory_gb: float = typer.Option(0.0, "--mem", help="Peak memory in GB"),
):
    """Track a pipeline run (Nextflow, Snakemake, etc.)."""
    now = datetime.now()
    slug = _slugify(name)
    filename = f"{now.strftime('%Y-%m-%d')}_{slug}.md"

    run_dir = Path("docs/runs/nextflow")
    run_dir.mkdir(parents=True, exist_ok=True)

    content = f"""---
title: "{name}"
date: {now.strftime('%Y-%m-%d %H:%M')}
project: "{project_name}"
pipeline: "{pipeline}"
status: {status_val}
---

# Run: {name}

| Field | Value |
|-------|-------|
| **Run Name** | {name} |
| **Project** | {project_name} |
| **Pipeline** | `{pipeline}` |
| **Status** | {status_val} |
| **Date** | {now.strftime('%Y-%m-%d %H:%M')} |
| **Duration** | {duration if duration else 'N/A'} |
| **CPU Hours** | {cpu_hours if cpu_hours else 'N/A'} |
| **Peak Memory** | {f'{memory_gb} GB' if memory_gb else 'N/A'} |
| **Work Dir** | `{work_dir}` |
| **Output Dir** | `{output_dir}` |
"""

    if command:
        content += f"""
## Command

```bash
{command}
```
"""

    if error_msg:
        content += f"""
## Error

```
{error_msg}
```
"""

    if notes:
        content += f"""
## Notes

{notes}
"""

    content += f"""
---
*Tracked: {now.strftime('%Y-%m-%d %H:%M')}*
"""

    filepath = run_dir / filename
    filepath.write_text(content)
    _rebuild_runs_index()

    typer.echo(f"Run tracked: {filepath}")


# ═══════════════════════════════════════════════════════════════════════
# SLURM COMMAND
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def slurm(
    job_id: str = typer.Argument(..., help="SLURM Job ID"),
    project_name: str = typer.Option("", "--project", "-p", help="Project name"),
    job_name: str = typer.Option("", "--name", "-n", help="Job name"),
    status_val: str = typer.Option("completed", "--status", "-s", help="Status"),
    partition: str = typer.Option("", "--partition", help="SLURM partition"),
    cpus: int = typer.Option(0, "--cpus", help="CPUs requested"),
    memory: str = typer.Option("", "--mem", help="Memory requested"),
    duration: str = typer.Option("", "--duration", help="Wall time"),
    notes: str = typer.Option("", "--notes", help="Notes"),
):
    """Track a SLURM job."""
    now = datetime.now()
    filename = f"{now.strftime('%Y-%m-%d')}_job-{job_id}.md"

    slurm_dir = Path("docs/runs/slurm")
    slurm_dir.mkdir(parents=True, exist_ok=True)

    content = f"""---
title: "SLURM Job {job_id}"
date: {now.strftime('%Y-%m-%d %H:%M')}
job_id: "{job_id}"
project: "{project_name}"
status: {status_val}
---

# SLURM Job: {job_id}

| Field | Value |
|-------|-------|
| **Job ID** | {job_id} |
| **Job Name** | {job_name if job_name else 'N/A'} |
| **Project** | {project_name if project_name else 'N/A'} |
| **Status** | {status_val} |
| **Partition** | {partition if partition else 'N/A'} |
| **CPUs** | {cpus if cpus else 'N/A'} |
| **Memory** | {memory if memory else 'N/A'} |
| **Duration** | {duration if duration else 'N/A'} |
"""

    if notes:
        content += f"\n## Notes\n\n{notes}\n"

    content += f"""
---
*Tracked: {now.strftime('%Y-%m-%d %H:%M')}*
"""

    filepath = slurm_dir / filename
    filepath.write_text(content)

    _rebuild_runs_index()

    typer.echo(f"SLURM job tracked: {filepath}")


# ═══════════════════════════════════════════════════════════════════════
# DATASET COMMAND
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def dataset(
    name: str = typer.Argument(..., help="Dataset name"),
    path: str = typer.Argument(..., help="Path to dataset"),
    project_name: str = typer.Option(..., "--project", "-p", help="Project name"),
    description: str = typer.Option("", "--desc", "-d", help="Description"),
    organism: str = typer.Option("", "--organism", "-o", help="Organism"),
    fmt: str = typer.Option("", "--format", "-f", help="Format (FASTQ, BAM, VCF, etc.)"),
    samples: int = typer.Option(0, "--samples", "-n", help="Number of samples"),
    accession: str = typer.Option("", "--accession", help="Accession number (GEO, SRA, etc.)"),
):
    """Register a dataset (metadata only - not the actual files)."""
    now = datetime.now()
    slug = _slugify(name)
    filename = f"{slug}.md"

    ds_dir = Path("docs/datasets")
    ds_dir.mkdir(parents=True, exist_ok=True)

    dataset_path = Path(path).resolve()

    content = f"""---
title: "{name}"
date: {now.strftime('%Y-%m-%d')}
project: "{project_name}"
path: "{dataset_path}"
organism: "{organism}"
format: "{fmt}"
accession: "{accession}"
samples: {samples}
---

# Dataset: {name}

| Field | Value |
|-------|-------|
| **Path** | `{dataset_path}` |
| **Project** | {project_name} |
| **Format** | {fmt if fmt else 'N/A'} |
| **Organism** | {organism if organism else 'N/A'} |
| **Samples** | {samples if samples else 'N/A'} |
| **Accession** | {accession if accession else 'N/A'} |
| **Registered** | {now.strftime('%Y-%m-%d')} |

## Description

{description if description else '*Add description.*'}

## Files

*List key files here.*

## Provenance

*How was this dataset obtained? QC status?*

---
*Registered: {now.strftime('%Y-%m-%d %H:%M')}*
"""

    filepath = ds_dir / filename
    filepath.write_text(content)

    _rebuild_datasets_index()

    typer.echo(f"Dataset registered: {filepath}")


# ═══════════════════════════════════════════════════════════════════════
# CANCEL COMMAND
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def cancel(
    filepath: str = typer.Argument(..., help="Path to the note/idea/todo file to cancel"),
    reason: str = typer.Option("", "--reason", "-r", help="Reason for cancellation"),
):
    """Cancel/archive a note, idea, or TODO."""
    path = Path(filepath)
    if not path.exists():
        # Try to find it in docs/notes
        possible = list(Path("docs/notes").rglob(f"*{filepath}*"))
        if possible:
            path = possible[0]
            typer.echo(f"Found: {path}")
        else:
            typer.echo(f"Error: File not found: {filepath}")
            raise typer.Exit(1)

    content = path.read_text()

    # Update status in frontmatter
    content = content.replace("status: active", "status: cancelled")

    # Add cancellation notice
    now = datetime.now()
    cancel_notice = f"\n\n---\n\n!!! warning \"Cancelled ({now.strftime('%Y-%m-%d')})\"\n"
    if reason:
        cancel_notice += f"    **Reason:** {reason}\n"
    else:
        cancel_notice += "    This item has been cancelled.\n"

    content += cancel_notice
    path.write_text(content)

    # Determine category and rebuild index
    category = path.parent.name
    _rebuild_notes_index(category)

    typer.echo(f"Cancelled: {path}")
    if reason:
        typer.echo(f"   Reason: {reason}")


# ═══════════════════════════════════════════════════════════════════════
# DONE COMMAND (mark TODO as done)
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def done(
    filepath: str = typer.Argument(..., help="Path to the TODO file to mark as done"),
    result: str = typer.Option("", "--result", "-r", help="Result or outcome"),
):
    """Mark a TODO as completed."""
    path = Path(filepath)
    if not path.exists():
        possible = list(Path("docs/notes/todo").rglob(f"*{filepath}*"))
        if possible:
            path = possible[0]
            typer.echo(f"Found: {path}")
        else:
            typer.echo(f"Error: File not found: {filepath}")
            raise typer.Exit(1)

    content = path.read_text()
    now = datetime.now()

    # Update status
    content = content.replace("status: active", "status: completed")
    content = content.replace("- [ ]", "- [x]")

    # Add completion notice
    done_notice = f"\n\n---\n\n!!! success \"Completed ({now.strftime('%Y-%m-%d')})\"\n"
    if result:
        done_notice += f"    **Result:** {result}\n"

    content += done_notice
    path.write_text(content)
    _rebuild_notes_index("todo")

    typer.echo(f"Marked as done: {path}")


# ═══════════════════════════════════════════════════════════════════════
# UPDATE COMMAND
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def update(
    filepath: str = typer.Argument(..., help="Path to the file to update"),
    message: str = typer.Option("", "--msg", "-m", help="Update message to append"),
    editor: bool = typer.Option(False, "--edit", "-e", help="Open in $EDITOR"),
    new_status: str = typer.Option("", "--status", "-s", help="New status"),
):
    """Update an existing note, experiment, or run."""
    path = Path(filepath)
    if not path.exists():
        # Search for it
        possible = list(Path("docs").rglob(f"*{filepath}*"))
        if possible:
            path = possible[0]
            typer.echo(f"Found: {path}")
        else:
            typer.echo(f"Error: File not found: {filepath}")
            raise typer.Exit(1)

    content = path.read_text()
    now = datetime.now()

    # Update status if provided
    if new_status:
        content = re.sub(r'status:\s*\S+', f'status: {new_status}', content)

    # Append update
    if message:
        update_text = f"\n\n---\n\n**Update ({now.strftime('%Y-%m-%d %H:%M')}):**\n\n{message}\n"
        content += update_text

    if editor:
        content = _open_editor(content)

    path.write_text(content)
    typer.echo(f"Updated: {path}")


# ═══════════════════════════════════════════════════════════════════════
# SEARCH COMMAND
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def search(
    query: str = typer.Argument(..., help="Search term"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
):
    """Search across all notebook content."""
    query_lower = query.lower()
    results = []

    # Search all markdown files
    for md_file in Path("docs").rglob("*.md"):
        if md_file.name == "index.md":
            continue
        try:
            content = md_file.read_text()
            if query_lower in content.lower():
                # Extract title
                title_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
                title = title_match.group(1) if title_match else md_file.stem

                # Find matching line for context
                for line in content.split('\n'):
                    if query_lower in line.lower():
                        context = line.strip()[:80]
                        break
                else:
                    context = ""

                results.append((str(md_file), title, context))
        except Exception:
            continue

    if not results:
        typer.echo(f"No results for: '{query}'")
        return

    typer.echo(f"\nResults for '{query}' ({len(results)} found):\n")
    for filepath, title, context in results[:limit]:
        typer.echo(f"  {title}")
        typer.echo(f"     {filepath}")
        if context:
            typer.echo(f"     → {context}")
        typer.echo("")


# ═══════════════════════════════════════════════════════════════════════
# BUILD COMMAND
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def build():
    """Build the MkDocs documentation site."""
    mkdocs_yml = Path("mkdocs.yml")
    if not mkdocs_yml.exists():
        typer.echo("Error: mkdocs.yml not found. Run: biolab init")
        raise typer.Exit(1)

    # Rebuild all indexes first
    _rebuild_projects_index()
    _rebuild_experiments_index()
    _rebuild_runs_index()
    _rebuild_datasets_index()
    for cat in ["general", "debugging", "ideas", "todo", "observations"]:
        _rebuild_notes_index(cat)
    _rebuild_dashboard()

    # Run mkdocs build
    result = subprocess.run(["mkdocs", "build"], capture_output=True, text=True)
    if result.returncode == 0:
        typer.echo("Site built → ./site/")
    else:
        typer.echo(f"Build error: {result.stderr[:300]}")


# ═══════════════════════════════════════════════════════════════════════
# SERVE COMMAND
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def serve(
    port: int = typer.Option(8000, help="Port number"),
):
    """Serve docs locally for preview."""
    _rebuild_dashboard()
    typer.echo(f"Serving at http://localhost:{port} (Ctrl+C to stop)")
    subprocess.run(["mkdocs", "serve", "--dev-addr", f"localhost:{port}"])


# ═══════════════════════════════════════════════════════════════════════
# DEPLOY COMMAND
# ═══════════════════════════════════════════════════════════════════════

@app.command()
def deploy():
    """Deploy to GitHub Pages."""
    # Rebuild everything first
    _rebuild_projects_index()
    _rebuild_experiments_index()
    _rebuild_runs_index()
    _rebuild_datasets_index()
    for cat in ["general", "debugging", "ideas", "todo", "observations"]:
        _rebuild_notes_index(cat)
    _rebuild_dashboard()

    result = subprocess.run(
        ["mkdocs", "gh-deploy", "--force"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        typer.echo("Deployed to GitHub Pages!")
    else:
        typer.echo(f"Deploy failed: {result.stderr[:300]}")


# ═══════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text[:50].rstrip("-")


def _count_md_files(directory: str) -> int:
    """Count markdown files in a directory (excluding index.md)."""
    d = Path(directory)
    if not d.exists():
        return 0
    return len([f for f in d.glob("*.md") if f.name != "index.md"])


def _open_editor(initial_content: str = "") -> str:
    """Open $EDITOR and return content."""
    import tempfile
    editor = os.environ.get("EDITOR", "nano")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(initial_content)
        tmppath = f.name
    subprocess.call([editor, tmppath])
    with open(tmppath) as f:
        content = f.read()
    os.unlink(tmppath)
    return content


def _rebuild_projects_index():
    """Rebuild docs/projects/index.md from project files."""
    projects_dir = Path("docs/projects")
    if not projects_dir.exists():
        return

    project_files = sorted(projects_dir.glob("*.md"))
    project_files = [f for f in project_files if f.name != "index.md"]

    lines = ["# Projects\n\n"]

    if not project_files:
        lines.append("*No projects registered yet.*\n\n")
        lines.append("Add one with:\n```bash\nbiolab project <name> <path>\n```\n")
    else:
        lines.append("| Project | Path | Status | Created |\n")
        lines.append("|---------|------|--------|--------|\n")

        for pf in project_files:
            content = pf.read_text()
            title_match = re.search(r'title:\s*"(.+?)"', content)
            path_match = re.search(r'path:\s*"(.+?)"', content)
            created_match = re.search(r'created:\s*(\S+)', content)
            status_match = re.search(r'status:\s*(\S+)', content)

            title = title_match.group(1) if title_match else pf.stem
            path = path_match.group(1) if path_match else ""
            created = created_match.group(1) if created_match else ""
            status = status_match.group(1) if status_match else "active"

            # Truncate long paths
            display_path = path if len(path) < 50 else "..." + path[-47:]
            lines.append(f"| {title} | `{display_path}` | {status} | {created} |\n")

    (projects_dir / "index.md").write_text("".join(lines))


def _rebuild_notes_index(category: str):
    """Rebuild index for a specific notes category."""
    cat_dir = Path(f"docs/notes/{category}")
    if not cat_dir.exists():
        return

    note_files = sorted(cat_dir.glob("*.md"), reverse=True)
    note_files = [f for f in note_files if f.name != "index.md"]

    lines = [f"# {category.title()}\n\n"]

    if not note_files:
        lines.append("*No entries yet.*\n")
    else:
        lines.append("| Date | Title | Status |\n")
        lines.append("|------|-------|--------|\n")

        for nf in note_files:
            content = nf.read_text()
            title_match = re.search(r'title:\s*"(.+?)"', content)
            date_match = re.search(r'date:\s*(\S+)', content)
            status_match = re.search(r'status:\s*(\S+)', content)

            title = title_match.group(1) if title_match else nf.stem
            date = date_match.group(1) if date_match else ""
            status = status_match.group(1) if status_match else "active"

            lines.append(f"| {date} | [{title[:50]}]({nf.name}) | {status} |\n")

    (cat_dir / "index.md").write_text("".join(lines))


def _rebuild_experiments_index():
    """Rebuild docs/experiments/index.md."""
    exp_dir = Path("docs/experiments")
    if not exp_dir.exists():
        return

    exp_files = sorted(exp_dir.glob("*.md"), reverse=True)
    exp_files = [f for f in exp_files if f.name != "index.md"]

    lines = ["# Experiments\n\n"]

    if not exp_files:
        lines.append("*No experiments yet.*\n")
    else:
        lines.append("| Date | Experiment | Project | Status |\n")
        lines.append("|------|-----------|---------|--------|\n")

        for ef in exp_files:
            content = ef.read_text()
            title_match = re.search(r'title:\s*"(.+?)"', content)
            date_match = re.search(r'date:\s*(\S+)', content)
            project_match = re.search(r'project:\s*"(.+?)"', content)
            status_match = re.search(r'status:\s*(\S+)', content)

            title = title_match.group(1) if title_match else ef.stem
            date = date_match.group(1) if date_match else ""
            proj = project_match.group(1) if project_match else ""
            status = status_match.group(1) if status_match else "active"

            lines.append(f"| {date} | [{title[:40]}]({ef.name}) | {proj} | {status} |\n")

    (exp_dir / "index.md").write_text("".join(lines))


def _rebuild_runs_index():
    """Rebuild docs/runs/index.md and sub-indexes."""
    # Nextflow runs
    nf_dir = Path("docs/runs/nextflow")
    if nf_dir.exists():
        nf_files = sorted(nf_dir.glob("*.md"), reverse=True)
        nf_files = [f for f in nf_files if f.name != "index.md"]

        lines = ["# Nextflow Runs\n\n"]
        if not nf_files:
            lines.append("*No runs tracked yet.*\n")
        else:
            lines.append("| Date | Run | Pipeline | Status |\n")
            lines.append("|------|-----|----------|--------|\n")
            for rf in nf_files:
                content = rf.read_text()
                title_match = re.search(r'title:\s*"(.+?)"', content)
                date_match = re.search(r'date:\s*(\S+)', content)
                pipeline_match = re.search(r'pipeline:\s*"(.+?)"', content)
                status_match = re.search(r'status:\s*(\S+)', content)

                title = title_match.group(1) if title_match else rf.stem
                date = date_match.group(1) if date_match else ""
                pipeline = pipeline_match.group(1) if pipeline_match else ""
                status = status_match.group(1) if status_match else ""

                lines.append(f"| {date} | [{title[:30]}]({rf.name}) | {pipeline[:20]} | {status} |\n")

        (nf_dir / "index.md").write_text("".join(lines))

    # SLURM Jobs
    slurm_dir = Path("docs/runs/slurm")
    if slurm_dir.exists():
        slurm_files = sorted(slurm_dir.glob("*.md"), reverse=True)
        slurm_files = [f for f in slurm_files if f.name != "index.md"]

        lines = ["# SLURM Jobs\n\n"]
        if not slurm_files:
            lines.append("*No jobs tracked yet.*\n")
        else:
            lines.append("| Date | Job ID | Project | Status |\n")
            lines.append("|------|--------|---------|--------|\n")
            for sf in slurm_files:
                content = sf.read_text()
                id_match = re.search(r'job_id:\s*"(.+?)"', content)
                date_match = re.search(r'date:\s*(\S+)', content)
                proj_match = re.search(r'project:\s*"(.+?)"', content)
                status_match = re.search(r'status:\s*(\S+)', content)

                job_id = id_match.group(1) if id_match else sf.stem
                date = date_match.group(1) if date_match else ""
                proj = proj_match.group(1) if proj_match else ""
                status = status_match.group(1) if status_match else ""

                lines.append(f"| {date} | {job_id} | {proj[:20]} | {status} |\n")

        (slurm_dir / "index.md").write_text("".join(lines))

    # Main runs index
    runs_dir = Path("docs/runs")
    if runs_dir.exists():
        nf_count = _count_md_files("docs/runs/nextflow")
        slurm_count = _count_md_files("docs/runs/slurm")
        main_lines = [
            "# Pipeline Runs\n\n",
            f"- [Nextflow Runs](nextflow/index.md) ({nf_count} tracked)\n",
            f"- [SLURM Jobs](slurm/index.md) ({slurm_count} tracked)\n",
        ]
        (runs_dir / "index.md").write_text("".join(main_lines))


def _rebuild_dashboard():
    """Rebuild the main dashboard with current stats."""
    now = datetime.now()

    projects_count = _count_md_files("docs/projects")
    experiments_count = _count_md_files("docs/experiments")
    nf_runs_count = _count_md_files("docs/runs/nextflow")
    slurm_count = _count_md_files("docs/runs/slurm")
    datasets_count = _count_md_files("docs/datasets")
    notes_debug = _count_md_files("docs/notes/debugging")
    notes_ideas = _count_md_files("docs/notes/ideas")
    notes_todo = _count_md_files("docs/notes/todo")
    notes_obs = _count_md_files("docs/notes/observations")
    notes_general = _count_md_files("docs/notes/general")
    total_notes = notes_debug + notes_ideas + notes_todo + notes_general + notes_obs

    content = f"""# Dashboard

**Last Updated:** {now.strftime('%Y-%m-%d %H:%M')}

## Quick Stats

| Metric | Count |
|--------|-------|
| Projects | {projects_count} |
| Experiments | {experiments_count} |
| Nextflow Runs | {nf_runs_count} |
| SLURM Jobs | {slurm_count} |
| Datasets | {datasets_count} |
| Total Notes | {total_notes} |
| Debugging | {notes_debug} |
| Ideas | {notes_ideas} |
| TODOs | {notes_todo} |
| Observations | {notes_obs} |

## Sections

| Section | Link |
|---------|------|
| Projects | [View all projects](projects/index.md) |
| Experiments | [View all experiments](experiments/index.md) |
| Pipeline Runs | [View all runs](runs/index.md) |
| Datasets | [View all datasets](datasets/index.md) |
| Debugging Notes | [View debugging](notes/debugging/index.md) |
| Ideas | [View ideas](notes/ideas/index.md) |
| TODOs | [View TODOs](notes/todo/index.md) |
| Observations | [View observations](notes/observations/index.md) |

"""
    Path("docs/dashboard.md").write_text(content)


def _create_mkdocs_yml(name: str):
    """Create mkdocs.yml configuration."""
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
    - navigation.expand
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
  - md_in_html
  - tables
  - toc:
      permalink: true
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite

nav:
  - Home: index.md
  - Dashboard: dashboard.md
  - Projects: projects/index.md
  - Experiments: experiments/index.md
  - Runs: runs/index.md
  - Notes:
    - All Notes: notes/index.md
    - General: notes/general/index.md
    - Debugging: notes/debugging/index.md
    - Ideas: notes/ideas/index.md
    - TODOs: notes/todo/index.md
    - Observations: notes/observations/index.md
  - Datasets: datasets/index.md
"""
    Path("mkdocs.yml").write_text(content)


def _rebuild_datasets_index():
    """Rebuild docs/datasets/index.md."""
    ds_dir = Path("docs/datasets")
    if not ds_dir.exists():
        return

    ds_files = sorted(ds_dir.glob("*.md"), reverse=True)
    ds_files = [f for f in ds_files if f.name != "index.md"]

    lines = ["# Datasets\n\n"]

    if not ds_files:
        lines.append("*No datasets registered yet.*\n")
    else:
        lines.append("| Date | Dataset | Project | Format | Samples |\n")
        lines.append("|------|---------|---------|--------|---------|\n")

        for df in ds_files:
            content = df.read_text()
            title_match = re.search(r'title:\s*"(.+?)"', content)
            date_match = re.search(r'date:\s*(\S+)', content)
            proj_match = re.search(r'project:\s*"(.+?)"', content)
            fmt_match = re.search(r'format:\s*"(.+?)"', content)
            samples_match = re.search(r'samples:\s*(\d+)', content)

            title = title_match.group(1) if title_match else df.stem
            date = date_match.group(1) if date_match else ""
            proj = proj_match.group(1) if proj_match else ""
            fmt = fmt_match.group(1) if fmt_match else ""
            samples = samples_match.group(1) if samples_match else "N/A"

            lines.append(f"| {date} | [{title[:40]}]({df.name}) | {proj[:20]} | {fmt} | {samples} |\n")

    (ds_dir / "index.md").write_text("".join(lines))


if __name__ == "__main__":
    app()
