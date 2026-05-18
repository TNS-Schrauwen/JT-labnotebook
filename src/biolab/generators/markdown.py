"""Generate markdown files from database content."""

from pathlib import Path
from datetime import datetime, date
from typing import List, Optional
from jinja2 import Environment, FileSystemLoader, BaseLoader
from ..database import BioLabDB
from ..models import Note, NoteCategory
import logging

logger = logging.getLogger(__name__)

# Inline templates (no external template files needed initially)
NOTE_TEMPLATE = """---
title: "{{ note.title }}"
date: {{ note.created_at.strftime('%Y-%m-%d %H:%M') }}
category: {{ note.category.value if note.category.value else note.category }}
tags: {{ note.tags }}
status: {{ note.status }}
{% if note.project_id %}project: {{ note.project_id }}{% endif %}
{% if note.experiment_id %}experiment: {{ note.experiment_id }}{% endif %}
---

# {{ note.title }}

{{ note.content }}

{% if note.status == 'cancelled' %}
!!! warning "Cancelled"
    This item has been cancelled.
{% endif %}

---
*Created: {{ note.created_at.strftime('%Y-%m-%d %H:%M') }}{% if note.updated_at %} | Updated: {{ note.updated_at.strftime('%Y-%m-%d %H:%M') }}{% endif %}*
"""

EXPERIMENT_TEMPLATE = """---
title: "{{ exp.name }}"
date: {{ exp.created_at.strftime('%Y-%m-%d') }}
status: {{ exp.status.value if exp.status.value else exp.status }}
tags: {{ exp.tags }}
---

# {{ exp.name }}

**Status:** {{ exp.status.value if exp.status.value else exp.status }}
**Project:** {{ exp.project_id }}
**Created:** {{ exp.created_at.strftime('%Y-%m-%d %H:%M') }}

{% if exp.hypothesis %}
## Hypothesis

{{ exp.hypothesis }}
{% endif %}

{% if exp.description %}
## Description

{{ exp.description }}
{% endif %}

{% if exp.parameters %}
## Parameters

| Parameter | Value |
|-----------|-------|
{% for key, value in exp.parameters.items() %}| {{ key }} | {{ value }} |
{% endfor %}
{% endif %}

{% if exp.results_summary %}
## Results

{{ exp.results_summary }}
{% endif %}

{% if exp.conclusion %}
## Conclusion

{{ exp.conclusion }}
{% endif %}
"""

RUN_TEMPLATE = """---
title: "{{ run.run_name }}"
date: {{ run.started_at }}
pipeline: {{ run.pipeline }}
status: {{ run.status }}
---

# Nextflow Run: {{ run.run_name }}

| Field | Value |
|-------|-------|
| **Pipeline** | `{{ run.pipeline }}` |
| **Status** | {{ run.status }} |
| **Started** | {{ run.started_at }} |
| **Completed** | {{ run.completed_at or 'N/A' }} |
| **Duration** | {{ run.duration_seconds or 'N/A' }}s |
| **CPU Hours** | {{ '%.2f'|format(run.cpu_hours) if run.cpu_hours else 'N/A' }} |
| **Peak Memory** | {{ '%.2f'|format(run.peak_memory_gb) if run.peak_memory_gb else 'N/A' }} GB |
| **Exit Code** | {{ run.exit_code if run.exit_code is not none else 'N/A' }} |
| **Work Dir** | `{{ run.work_dir }}` |

{% if run.command %}
## Command

```bash
{{ run.command }}
```

{% endif %}

{% if run.error_message %}
## Error

{% endif %}
"""

DASHBOARD_TEMPLATE = """---
title: Dashboard
Lab Notebook Dashboard
Last updated: {{ now.strftime('%Y-%m-%d %H:%M') }}

Quick Stats
METRIC
COUNT
Projects
{{ stats.projects }}
Experiments
{{ stats.experiments }}
Nextflow Runs
{{ stats.runs }}
Notes
{{ stats.notes }}
Active TODOs
{{ stats.todos }}


Recent Activity
{% for item in recent %}

{{ item.type }} {{ item.title }} ({{ item.date }})
{% endfor %}
Active TODOs
{% for todo in todos %}


{{ todo.title }} {% if todo.project_id %}({{ todo.project_id }}){% endif %}
{% endfor %}
Active Ideas
{% for idea in ideas %}

 {{ idea.title }} {% if idea.project_id %}({{ idea.project_id }}){% endif %}
{% endfor %}
"""
class MarkdownGenerator:
    """Generate markdown files from database content."""

    def __init__(self, db: BioLabDB, docs_dir: Path):
        self.db = db
        self.docs_dir = docs_dir
        self.env = Environment(loader=BaseLoader())

    def generate_note_page(self, note: Note) -> Path:
        """Generate a markdown file for a note."""
        template = self.env.from_string(NOTE_TEMPLATE)
        content = template.render(note=note)

        # Determine subdirectory
        cat = note.category.value if hasattr(note.category, 'value') else note.category
        category_dir = self.docs_dir / "notes" / cat
        category_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{note.created_at.strftime('%Y-%m-%d')}_{note.id}_{self._slugify(note.title)}.md"
        filepath = category_dir / filename

        filepath.write_text(content)
        logger.info(f"Generated note page: {filepath}")
        return filepath

    def generate_experiment_page(self, exp) -> Path:
        """Generate a markdown file for an experiment."""
        template = self.env.from_string(EXPERIMENT_TEMPLATE)
        content = template.render(exp=exp)

        exp_dir = self.docs_dir / "experiments"
        exp_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{exp.created_at.strftime('%Y-%m-%d')}_{exp.id}_{self._slugify(exp.name)}.md"
        filepath = exp_dir / filename

        filepath.write_text(content)
        return filepath

    def generate_run_page(self, run_data: dict) -> Path:
        """Generate a markdown page for a Nextflow run."""
        template = self.env.from_string(RUN_TEMPLATE)
        content = template.render(run=run_data)

        run_dir = self.docs_dir / "runs" / "nextflow"
        run_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{run_data.get('started_at', 'unknown')[:10]}_{run_data.get('run_name', 'unknown')}.md"
        filepath = run_dir / filename

        filepath.write_text(content)
        return filepath

    def generate_dashboard(self) -> Path:
        """Generate the main dashboard page."""
        template = self.env.from_string(DASHBOARD_TEMPLATE)

        # Gather stats
        projects = self.db.list_projects()
        experiments = self.db.list_experiments()
        runs = self.db.list_nextflow_runs()
        notes = self.db.list_notes()
        todos = self.db.list_notes(category="todo", status="active")
        ideas = self.db.list_notes(category="idea", status="active")

        stats = {
            "projects": len(projects),
            "experiments": len(experiments),
            "runs": len(runs),
            "notes": len(notes),
            "todos": len(todos),
        }

        # Recent activity (combine and sort)
        recent = []
        for n in notes[:5]:
            cat = n.category.value if hasattr(n.category, 'value') else n.category
            recent.append({
                "type": f" [{cat}]",
                "title": n.title,
                "date": n.created_at.strftime("%Y-%m-%d"),
            })
        for r in runs[:5]:
            recent.append({
                "type": " [run]",
                "title": r.get("run_name", ""),
                "date": r.get("started_at", "")[:10],
            })

        recent.sort(key=lambda x: x["date"], reverse=True)

        content = template.render(
            now=datetime.now(),
            stats=stats,
            recent=recent[:10],
            todos=todos,
            ideas=ideas,
        )

        filepath = self.docs_dir / "dashboard.md"
        filepath.write_text(content)
        return filepath

    def generate_notes_index(self) -> Path:
        """Generate an index page for all notes."""
        notes = self.db.list_notes()
        lines = ["#  Notes\n\n"]

        # Group by category
        categories = {}
        for note in notes:
            cat = note.category.value if hasattr(note.category, 'value') else note.category
            categories.setdefault(cat, []).append(note)

        for category, cat_notes in sorted(categories.items()):
            lines.append(f"## {category.title()}\n\n")
            for note in cat_notes:
                status_icon = "✅" if note.status == "active" else "❌"
                lines.append(
                    f"- {status_icon} [{note.title}]"
                    f"({category}/{note.created_at.strftime('%Y-%m-%d')}_{note.id}_{self._slugify(note.title)}.md)"
                    f" *({note.created_at.strftime('%Y-%m-%d')})*\n"
                )
            lines.append("\n")

        filepath = self.docs_dir / "notes" / "index.md"
        filepath.write_text("".join(lines))
        return filepath

    def rebuild_all(self):
        """Rebuild all generated markdown pages."""
        # Dashboard
        self.generate_dashboard()

        # Notes
        notes = self.db.list_notes()
        for note in notes:
            self.generate_note_page(note)
        self.generate_notes_index()

        # Experiments
        experiments = self.db.list_experiments()
        for exp in experiments:
            self.generate_experiment_page(exp)

        # Runs
        runs = self.db.list_nextflow_runs()
        for run in runs:
            self.generate_run_page(run)

        logger.info("Rebuilt all markdown pages")

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to URL-friendly slug."""
        import re
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "-", text)
        return text[:50]
