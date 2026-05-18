"""Pydantic models for all notebook entities."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid


def _new_id() -> str:
    return str(uuid.uuid4())[:8]


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NoteCategory(str, Enum):
    GENERAL = "general"
    DEBUGGING = "debugging"
    IDEA = "idea"
    OBSERVATION = "observation"
    TODO = "todo"
    EXPERIMENT = "experiment"
    ARCHITECTURE = "architecture"


class Project(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    path: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
    active: bool = True


class Experiment(BaseModel):
    id: str = Field(default_factory=_new_id)
    project_id: str
    name: str
    hypothesis: Optional[str] = None
    description: Optional[str] = None
    status: RunStatus = RunStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    parameters: Dict[str, Any] = {}
    results_summary: Optional[str] = None
    tags: List[str] = []
    conclusion: Optional[str] = None


class NextflowRun(BaseModel):
    id: str = Field(default_factory=_new_id)
    experiment_id: Optional[str] = None
    project_id: str
    run_name: str
    pipeline: str
    revision: Optional[str] = None
    work_dir: str
    output_dir: Optional[str] = None
    config_files: List[str] = []
    params: Dict[str, Any] = {}
    status: RunStatus = RunStatus.PENDING
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    nextflow_log: Optional[str] = None
    trace_file: Optional[str] = None
    timeline_file: Optional[str] = None
    dag_file: Optional[str] = None
    error_message: Optional[str] = None
    cpu_hours: Optional[float] = None
    peak_memory_gb: Optional[float] = None
    exit_code: Optional[int] = None
    command: Optional[str] = None
    git_commit: Optional[str] = None
    container: Optional[str] = None
    nextflow_version: Optional[str] = None


class SlurmJob(BaseModel):
    id: str = Field(default_factory=_new_id)
    job_id: str
    job_name: Optional[str] = None
    project_id: Optional[str] = None
    nextflow_run_id: Optional[str] = None
    partition: Optional[str] = None
    nodes: Optional[int] = None
    cpus: Optional[int] = None
    memory_mb: Optional[int] = None
    time_limit: Optional[str] = None
    status: RunStatus = RunStatus.PENDING
    submitted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    work_dir: Optional[str] = None
    stdout_path: Optional[str] = None
    stderr_path: Optional[str] = None
    script_path: Optional[str] = None
    account: Optional[str] = None
    qos: Optional[str] = None


class FileEvent(BaseModel):
    id: str = Field(default_factory=_new_id)
    project_id: str
    event_type: str  # created, modified, deleted, moved
    file_path: str
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = {}


class Note(BaseModel):
    id: str = Field(default_factory=_new_id)
    title: str
    content: str
    category: NoteCategory = NoteCategory.GENERAL
    project_id: Optional[str] = None
    experiment_id: Optional[str] = None
    tags: List[str] = []
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    status: str = "active"  # active, archived, cancelled


class Dataset(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    project_id: str
    path: str
    description: Optional[str] = None
    format: Optional[str] = None
    size_bytes: Optional[int] = None
    num_samples: Optional[int] = None
    organism: Optional[str] = None
    source: Optional[str] = None
    accession: Optional[str] = None
    checksum: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = {}