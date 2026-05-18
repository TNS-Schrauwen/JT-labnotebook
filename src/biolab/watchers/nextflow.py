"""Nextflow run tracking and metadata extraction."""

import re
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from ..models import NextflowRun, RunStatus
from ..database import BioLabDB
import logging

logger = logging.getLogger(__name__)


class NextflowTracker:
    """Parse and track Nextflow run metadata."""

    def __init__(self, db: BioLabDB):
        self.db = db

    def track_run(self, project_id: str, run_dir: Path,
                  experiment_id: Optional[str] = None) -> NextflowRun:
        """Track a Nextflow run from its directory."""
        run_dir = Path(run_dir)

        # Find log file
        log_path = run_dir / ".nextflow.log"
        if not log_path.exists():
            # Try parent directory
            log_path = run_dir.parent / ".nextflow.log"

        log_meta = self._parse_log(log_path) if log_path.exists() else {}

        # Find trace file
        trace_path = self._find_file(run_dir, "trace*.txt")
        trace_stats = self._parse_trace(trace_path) if trace_path else {}

        # Find other report files
        timeline_path = self._find_file(run_dir, "timeline*.html")
        dag_path = self._find_file(run_dir, "dag*")

        run = NextflowRun(
            project_id=project_id,
            experiment_id=experiment_id,
            run_name=log_meta.get("run_name", run_dir.name),
            pipeline=log_meta.get("pipeline", "unknown"),
            work_dir=log_meta.get("work_dir", str(run_dir / "work")),
            output_dir=str(run_dir),
            status=log_meta.get("status", RunStatus.COMPLETED),
            started_at=log_meta.get("started_at", datetime.now()),
            completed_at=log_meta.get("completed_at"),
            duration_seconds=log_meta.get("duration_seconds"),
            nextflow_log=str(log_path) if log_path.exists() else None,
            trace_file=str(trace_path) if trace_path else None,
            timeline_file=str(timeline_path) if timeline_path else None,
            dag_file=str(dag_path) if dag_path else None,
            cpu_hours=trace_stats.get("total_cpu_hours"),
            peak_memory_gb=trace_stats.get("peak_memory_gb"),
            command=log_meta.get("command"),
            error_message=log_meta.get("error_message"),
            nextflow_version=log_meta.get("nextflow_version"),
        )

        self.db.add_nextflow_run(run)
        logger.info(f"Tracked Nextflow run: {run.run_name} ({run.status.value})")
        return run

    def _parse_log(self, log_path: Path) -> Dict[str, Any]:
        """Extract metadata from .nextflow.log."""
        meta: Dict[str, Any] = {}
        try:
            content = log_path.read_text(errors="ignore")
        except (OSError, PermissionError):
            return meta

        # Run name
        match = re.search(r"\[([a-z]+_[a-z]+)\]", content)
        if match:
            meta["run_name"] = match.group(1)

        # Pipeline
        match = re.search(r"Launching `(.+?)`", content)
        if match:
            meta["pipeline"] = match.group(1)

        # Work directory
        match = re.search(r"work-dir\s*[:=]\s*(.+)", content)
        if match:
            meta["work_dir"] = match.group(1).strip()

        # Nextflow version
        match = re.search(r"nextflow version (\S+)", content, re.IGNORECASE)
        if match:
            meta["nextflow_version"] = match.group(1)

        # Command
        match = re.search(r"Command line: (.+)", content)
        if match:
            meta["command"] = match.group(1).strip()

        # Status
        if "Execution complete" in content or "pipeline completed" in content.lower():
            meta["status"] = RunStatus.COMPLETED
        elif "ERROR" in content or "execution failed" in content.lower():
            meta["status"] = RunStatus.FAILED
            # Extract error
            error_match = re.search(r"ERROR.*?(?=\n\n|\Z)", content, re.DOTALL)
            if error_match:
                meta["error_message"] = error_match.group(0)[:500]
        else:
            meta["status"] = RunStatus.RUNNING

        # Duration
        match = re.search(r"Duration\s*:\s*(.+)", content)
        if match:
            meta["duration_seconds"] = self._parse_duration(match.group(1).strip())

        return meta

    def _parse_trace(self, trace_path: Path) -> Dict[str, Any]:
        """Parse trace.txt for resource usage."""
        stats = {"total_cpu_hours": 0.0, "peak_memory_gb": 0.0, "total_tasks": 0}
        try:
            with open(trace_path) as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    stats["total_tasks"] += 1
                    # CPU time
                    if "realtime" in row and row["realtime"]:
                        ms = self._duration_to_ms(row["realtime"])
                        cpus = int(row.get("cpus", 1) or 1)
                        stats["total_cpu_hours"] += (ms / 3_600_000) * cpus
                    # Memory
                    if "peak_rss" in row and row["peak_rss"]:
                        mem_gb = self._mem_to_gb(row["peak_rss"])
                        stats["peak_memory_gb"] = max(stats["peak_memory_gb"], mem_gb)
        except (OSError, csv.Error) as e:
            logger.warning(f"Error parsing trace: {e}")
        return stats

    def _find_file(self, directory: Path, pattern: str) -> Optional[Path]:
        """Find a file matching a glob pattern."""
        matches = list(directory.rglob(pattern))
        return matches[0] if matches else None

    @staticmethod
    def _parse_duration(duration_str: str) -> float:
        """Parse duration string like '2h 30m 15s' to seconds."""
        total = 0.0
        for match in re.finditer(r"(\d+\.?\d*)\s*(d|h|m|s|ms)", duration_str):
            value = float(match.group(1))
            unit = match.group(2)
            multipliers = {"d": 86400, "h": 3600, "m": 60, "s": 1, "ms": 0.001}
            total += value * multipliers.get(unit, 0)
        return total

    @staticmethod
    def _duration_to_ms(s: str) -> float:
        """Convert Nextflow duration to milliseconds."""
        s = s.strip()
        total = 0.0
        for match in re.finditer(r"(\d+\.?\d*)\s*(h|m|s|ms)", s):
            val = float(match.group(1))
            unit = match.group(2)
            mult = {"h": 3_600_000, "m": 60_000, "s": 1000, "ms": 1}
            total += val * mult.get(unit, 0)
        if total == 0:
            try:
                total = float(s)
            except ValueError:
                pass
        return total

    @staticmethod
    def _mem_to_gb(s: str) -> float:
        """Convert memory string to GB."""
        s = s.strip().upper()
        multipliers = {"B": 1e-9, "KB": 1e-6, "MB": 1e-3, "GB": 1, "TB": 1000}
        for suffix, mult in multipliers.items():
            if s.endswith(suffix):
                try:
                    return float(s[:-len(suffix)].strip()) * mult
                except ValueError:
                    return 0.0
        try:
            return float(s) / (1024**3)
        except ValueError:
            return 0.0