"""SQLite database operations for JT-labnotebook."""

import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from datetime import datetime

from .models import (
    Project, Experiment, NextflowRun, SlurmJob,
    FileEvent, Note, Dataset, RunStatus
)


class BioLabDB:
    """SQLite database manager."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database schema."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    tags TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}',
                    active INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    hypothesis TEXT,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    parameters TEXT DEFAULT '{}',
                    results_summary TEXT,
                    tags TEXT DEFAULT '[]',
                    conclusion TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                );

                CREATE TABLE IF NOT EXISTS nextflow_runs (
                    id TEXT PRIMARY KEY,
                    experiment_id TEXT,
                    project_id TEXT NOT NULL,
                    run_name TEXT NOT NULL,
                    pipeline TEXT NOT NULL,
                    revision TEXT,
                    work_dir TEXT NOT NULL,
                    output_dir TEXT,
                    config_files TEXT DEFAULT '[]',
                    params TEXT DEFAULT '{}',
                    status TEXT DEFAULT 'pending',
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    duration_seconds REAL,
                    nextflow_log TEXT,
                    trace_file TEXT,
                    timeline_file TEXT,
                    dag_file TEXT,
                    error_message TEXT,
                    cpu_hours REAL,
                    peak_memory_gb REAL,
                    exit_code INTEGER,
                    command TEXT,
                    git_commit TEXT,
                    container TEXT,
                    nextflow_version TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
                );

                CREATE TABLE IF NOT EXISTS slurm_jobs (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    job_name TEXT,
                    project_id TEXT,
                    nextflow_run_id TEXT,
                    partition TEXT,
                    nodes INTEGER,
                    cpus INTEGER,
                    memory_mb INTEGER,
                    time_limit TEXT,
                    status TEXT DEFAULT 'pending',
                    submitted_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    exit_code INTEGER,
                    work_dir TEXT,
                    stdout_path TEXT,
                    stderr_path TEXT,
                    script_path TEXT,
                    account TEXT,
                    qos TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    FOREIGN KEY (nextflow_run_id) REFERENCES nextflow_runs(id)
                );

                CREATE TABLE IF NOT EXISTS file_events (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    file_hash TEXT,
                    timestamp TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                );

                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    project_id TEXT,
                    experiment_id TEXT,
                    tags TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    status TEXT DEFAULT 'active',
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
                );

                CREATE TABLE IF NOT EXISTS datasets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    description TEXT,
                    format TEXT,
                    size_bytes INTEGER,
                    num_samples INTEGER,
                    organism TEXT,
                    source TEXT,
                    accession TEXT,
                    checksum TEXT,
                    created_at TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                );

                -- Full-text search
                CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
                    entity_type, entity_id, title, content, tags
                );

                -- Performance indexes
                CREATE INDEX IF NOT EXISTS idx_experiments_project
                    ON experiments(project_id);
                CREATE INDEX IF NOT EXISTS idx_nf_runs_project
                    ON nextflow_runs(project_id);
                CREATE INDEX IF NOT EXISTS idx_nf_runs_status
                    ON nextflow_runs(status);
                CREATE INDEX IF NOT EXISTS idx_slurm_project
                    ON slurm_jobs(project_id);
                CREATE INDEX IF NOT EXISTS idx_file_events_project
                    ON file_events(project_id);
                CREATE INDEX IF NOT EXISTS idx_file_events_ts
                    ON file_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_notes_category
                    ON notes(category);
                CREATE INDEX IF NOT EXISTS idx_notes_status
                    ON notes(status);
            """)

    # ─── Project Operations ───────────────────────────────────────────

    def add_project(self, project: Project) -> Project:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO projects 
                   (id, name, path, description, created_at, tags, metadata, active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (project.id, project.name, project.path,
                 project.description, project.created_at.isoformat(),
                 json.dumps(project.tags), json.dumps(project.metadata),
                 int(project.active))
            )
            self._index_entity(conn, "project", project.id,
                             project.name, project.description or "",
                             project.tags)
        return project

    def get_project(self, name_or_id: str) -> Optional[Project]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ? OR name = ?",
                (name_or_id, name_or_id)
            ).fetchone()
            if row:
                return self._row_to_project(row)
        return None

    def list_projects(self, active_only: bool = True) -> List[Project]:
        with self._conn() as conn:
            query = "SELECT * FROM projects"
            if active_only:
                query += " WHERE active = 1"
            query += " ORDER BY created_at DESC"
            rows = conn.execute(query).fetchall()
            return [self._row_to_project(r) for r in rows]

    # ─── Note Operations ──────────────────────────────────────────────

    def add_note(self, note: Note) -> Note:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO notes
                   (id, title, content, category, project_id, experiment_id,
                    tags, created_at, updated_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (note.id, note.title, note.content, note.category.value,
                 note.project_id, note.experiment_id,
                 json.dumps(note.tags), note.created_at.isoformat(),
                 note.updated_at.isoformat() if note.updated_at else None,
                 note.status)
            )
            self._index_entity(conn, "note", note.id,
                             note.title, note.content, note.tags)
        return note

    def update_note(self, note_id: str, **kwargs) -> Optional[Note]:
        with self._conn() as conn:
            note_row = conn.execute(
                "SELECT * FROM notes WHERE id = ?", (note_id,)
            ).fetchone()
            if not note_row:
                return None
            
            updates = []
            values = []
            for key, value in kwargs.items():
                if key == "tags":
                    updates.append(f"{key} = ?")
                    values.append(json.dumps(value))
                elif key == "category":
                    updates.append(f"{key} = ?")
                    values.append(value.value if hasattr(value, 'value') else value)
                else:
                    updates.append(f"{key} = ?")
                    values.append(value)
            
            updates.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(note_id)
            
            conn.execute(
                f"UPDATE notes SET {', '.join(updates)} WHERE id = ?",
                values
            )
        return self.get_note(note_id)

    def get_note(self, note_id: str) -> Optional[Note]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM notes WHERE id = ?", (note_id,)
            ).fetchone()
            if row:
                return self._row_to_note(row)
        return None

    def list_notes(self, category: Optional[str] = None,
                   project_id: Optional[str] = None,
                   status: str = "active") -> List[Note]:
        with self._conn() as conn:
            query = "SELECT * FROM notes WHERE status = ?"
            params: list = [status]
            if category:
                query += " AND category = ?"
                params.append(category)
            if project_id:
                query += " AND project_id = ?"
                params.append(project_id)
            query += " ORDER BY created_at DESC"
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_note(r) for r in rows]

    # ─── Experiment Operations ────────────────────────────────────────

    def add_experiment(self, exp: Experiment) -> Experiment:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO experiments
                   (id, project_id, name, hypothesis, description, status,
                    created_at, completed_at, parameters, results_summary,
                    tags, conclusion)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (exp.id, exp.project_id, exp.name, exp.hypothesis,
                 exp.description, exp.status.value,
                 exp.created_at.isoformat(),
                 exp.completed_at.isoformat() if exp.completed_at else None,
                 json.dumps(exp.parameters), exp.results_summary,
                 json.dumps(exp.tags), exp.conclusion)
            )
            self._index_entity(conn, "experiment", exp.id,
                             exp.name, exp.description or "", exp.tags)
        return exp

    def list_experiments(self, project_id: Optional[str] = None) -> List[Experiment]:
        with self._conn() as conn:
            if project_id:
                rows = conn.execute(
                    "SELECT * FROM experiments WHERE project_id = ? ORDER BY created_at DESC",
                    (project_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM experiments ORDER BY created_at DESC"
                ).fetchall()
            return [self._row_to_experiment(r) for r in rows]

    # ─── Nextflow Run Operations ──────────────────────────────────────

    def add_nextflow_run(self, run: NextflowRun) -> NextflowRun:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO nextflow_runs
                   (id, experiment_id, project_id, run_name, pipeline,
                    revision, work_dir, output_dir, config_files, params,
                    status, started_at, completed_at, duration_seconds,
                    nextflow_log, trace_file, timeline_file, dag_file,
                    error_message, cpu_hours, peak_memory_gb, exit_code,
                    command, git_commit, container, nextflow_version)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (run.id, run.experiment_id, run.project_id, run.run_name,
                 run.pipeline, run.revision, run.work_dir, run.output_dir,
                 json.dumps(run.config_files), json.dumps(run.params),
                 run.status.value, run.started_at.isoformat(),
                 run.completed_at.isoformat() if run.completed_at else None,
                 run.duration_seconds, run.nextflow_log, run.trace_file,
                 run.timeline_file, run.dag_file, run.error_message,
                 run.cpu_hours, run.peak_memory_gb, run.exit_code,
                 run.command, run.git_commit, run.container,
                 run.nextflow_version)
            )
            self._index_entity(conn, "nextflow_run", run.id,
                             run.run_name, run.pipeline, [])
        return run

    def list_nextflow_runs(self, project_id: Optional[str] = None) -> List[Dict]:
        with self._conn() as conn:
            if project_id:
                rows = conn.execute(
                    "SELECT * FROM nextflow_runs WHERE project_id = ? ORDER BY started_at DESC",
                    (project_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM nextflow_runs ORDER BY started_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    # ─── SLURM Job Operations ────────────────────────────────────────

    def upsert_slurm_job(self, job: SlurmJob) -> SlurmJob:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO slurm_jobs
                   (id, job_id, job_name, project_id, nextflow_run_id,
                    partition, nodes, cpus, memory_mb, time_limit, status,
                    submitted_at, started_at, completed_at, exit_code,
                    work_dir, stdout_path, stderr_path, script_path,
                    account, qos)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (job.id, job.job_id, job.job_name, job.project_id,
                 job.nextflow_run_id, job.partition, job.nodes,
                 job.cpus, job.memory_mb, job.time_limit, job.status.value,
                 job.submitted_at.isoformat() if job.submitted_at else None,
                 job.started_at.isoformat() if job.started_at else None,
                 job.completed_at.isoformat() if job.completed_at else None,
                 job.exit_code, job.work_dir, job.stdout_path,
                 job.stderr_path, job.script_path, job.account, job.qos)
            )
        return job

    # ─── File Event Operations ────────────────────────────────────────

    def add_file_event(self, event: FileEvent) -> FileEvent:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO file_events
                   (id, project_id, event_type, file_path, file_size,
                    file_hash, timestamp, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (event.id, event.project_id, event.event_type,
                 event.file_path, event.file_size, event.file_hash,
                 event.timestamp.isoformat(), json.dumps(event.metadata))
            )
        return event

    # ─── Search ───────────────────────────────────────────────────────

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT entity_type, entity_id, title,
                          snippet(search_index, 3, '<mark>', '</mark>', '...', 30) as snippet
                   FROM search_index
                   WHERE search_index MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    # ─── Helper Methods ───────────────────────────────────────────────

    def _index_entity(self, conn, entity_type: str, entity_id: str,
                      title: str, content: str, tags: List[str]):
        conn.execute(
            "DELETE FROM search_index WHERE entity_type = ? AND entity_id = ?",
            (entity_type, entity_id)
        )
        conn.execute(
            "INSERT INTO search_index (entity_type, entity_id, title, content, tags) VALUES (?,?,?,?,?)",
            (entity_type, entity_id, title, content, " ".join(tags))
        )

    @staticmethod
    def _row_to_project(row) -> Project:
        return Project(
            id=row["id"], name=row["name"], path=row["path"],
            description=row["description"],
            created_at=datetime.fromisoformat(row["created_at"]),
            tags=json.loads(row["tags"]),
            metadata=json.loads(row["metadata"]),
            active=bool(row["active"]),
        )

    @staticmethod
    def _row_to_note(row) -> Note:
        return Note(
            id=row["id"], title=row["title"], content=row["content"],
            category=row["category"],
            project_id=row["project_id"],
            experiment_id=row["experiment_id"],
            tags=json.loads(row["tags"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
            status=row["status"],
        )

    @staticmethod
    def _row_to_experiment(row) -> Experiment:
        return Experiment(
            id=row["id"], project_id=row["project_id"],
            name=row["name"], hypothesis=row["hypothesis"],
            description=row["description"], status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            parameters=json.loads(row["parameters"]),
            results_summary=row["results_summary"],
            tags=json.loads(row["tags"]),
            conclusion=row["conclusion"],
        )