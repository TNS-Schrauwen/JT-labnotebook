"""Configuration management for JT-labnotebook."""

from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import yaml

class WatcherConfig(BaseModel):
    """Configuration for filesystem watchers."""
    enabled: bool = True
    poll_interval: int = 5
    ignored_patterns: List[str] = [
        ".git", "__pycache__", "work/", ".nextflow",
        "*.fastq.gz", "*.fastq", "*.bam", "*.sam",
        "*.bai", "*.cram", "*.bcf", "*.sra",
        "node_modules", ".venv", ".conda",
    ]
    tracked_extensions: List[str] = [
        ".py", ".R", ".r", ".sh", ".bash", ".nf", ".config",
        ".csv", ".tsv", ".json", ".yaml", ".yml", ".toml",
        ".bed", ".gff", ".gtf", ".vcf",
        ".md", ".rst", ".txt", ".log",
        ".html", ".pdf",
    ]


class NextflowConfig(BaseModel):
    """Configuration for Nextflow tracking."""
    auto_track: bool = True
    trace_enabled: bool = True
    report_dir: str = "results/pipeline_info"


class SlurmConfig(BaseModel):
    """Configuration for SLURM integration."""
    sync_enabled: bool = True
    sync_interval_minutes: int = 15
    account: str = ""


class DocsConfig(BaseModel):
    """Configuration for documentation generation."""
    output_dir: str = "docs"
    auto_build: bool = True


class GitConfig(BaseModel):
    """Configuration for git integration."""
    auto_commit: bool = True
    commit_interval_minutes: int = 30


class NotebookConfig(BaseModel):
    """Main configuration model."""
    version: str = "1.0"
    name: str = "JT Lab Notebook"
    author: str = ""
    institution: str = ""
    database_path: str = ".biolab/biolab.db"
    retention_days: int = 90
    watchers: WatcherConfig = WatcherConfig()
    nextflow: NextflowConfig = NextflowConfig()
    slurm: SlurmConfig = SlurmConfig()
    docs: DocsConfig = DocsConfig()
    git: GitConfig = GitConfig()
    plugins: List[str] = []


def get_config_path() -> Path:
    """Get path to config file."""
    return Path(".biolab/config.yaml")


def load_config() -> NotebookConfig:
    """Load configuration from YAML file."""
    config_path = get_config_path()
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return NotebookConfig(**data)
    return NotebookConfig()


def save_config(config: NotebookConfig) -> None:
    """Save configuration to YAML file."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(
            config.model_dump(),
            f,
            default_flow_style=False,
            sort_keys=False,
        )