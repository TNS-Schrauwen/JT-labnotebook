"""CLI interface for JT-labnotebook -- Professional Project Intelligence Tracker."""
import typer
from pathlib import Path
from typing import Optional
from datetime import datetime
import subprocess
import os
import re
import json
import hashlib
import time

app = typer.Typer(
    name="biolab",
    help="JT Lab Notebook -- Bioinformatics Project Intelligence Tracker",
    no_args_is_help=True,
)


# ===================================================================
# FILE TRACKING ENGINE
# ===================================================================

class FileTracker:
    """
    Tracks all files in project directories using content hashing.
    Detects new files, modified files, and deleted files.
    Similar to git's approach of hashing file contents to detect changes.
    """

    TRACKED_EXTENSIONS = {
        # Scripts
        ".py", ".R", ".r", ".sh", ".bash", ".nf", ".config", ".pl", ".rb",
        # Config
        ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf",
        # Data/metadata
        ".csv", ".tsv", ".txt", ".md", ".rst",
        # Bioinformatics
        ".bed", ".gff", ".gtf", ".vcf", ".fasta", ".fa",
        # Logs and outputs
        ".log", ".out", ".err", ".stderr", ".stdout",
        # Reports
        ".html", ".pdf", ".png", ".svg",
        # Job scripts
        ".slurm", ".sbatch", ".pbs", ".sge",
        # Nextflow specific
        ".nf", ".config",
        # Snakemake
        "Snakefile",
        # Make
        "Makefile",
    }

    SKIP_DIRS = {
        ".git", "__pycache__", ".nextflow", "work",
        ".snakemake", "node_modules", ".conda", ".cache",
        ".biolab", "site", ".venv", "venv",
    }

    # Large binary files to skip content hashing (track existence only)
    LARGE_BINARY_EXTENSIONS = {
        ".fastq", ".fastq.gz", ".fq", ".fq.gz",
        ".bam", ".sam", ".cram", ".bai",
        ".bcf", ".sra", ".h5", ".hdf5",
        ".tar", ".tar.gz", ".zip", ".gz", ".bz2",
    }

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.state_dir = Path(".biolab/state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.annotations_file = Path(".biolab/annotations.json")

    def _get_state_file(self, project_name: str) -> Path:
        return self.state_dir / f"{project_name}_state.json"

    def _load_state(self, project_name: str) -> dict:
        state_file = self._get_state_file(project_name)
        if state_file.exists():
            return json.loads(state_file.read_text())
        return {"files": {}, "last_scan": None}

    def _save_state(self, project_name: str, state: dict):
        state_file = self._get_state_file(project_name)
        state_file.write_text(json.dumps(state, indent=2, default=str))

    def _load_annotations(self) -> dict:
        if self.annotations_file.exists():
            return json.loads(self.annotations_file.read_text())
        return {}

    def _save_annotations(self, annotations: dict):
        self.annotations_file.parent.mkdir(parents=True, exist_ok=True)
        self.annotations_file.write_text(json.dumps(annotations, indent=2, default=str))

    def _should_track(self, path: Path) -> bool:
        """Determine if file should be tracked."""
        # Skip hidden files
        for part in path.parts:
            if part.startswith(".") and part not in (".nextflow.log",):
                if any(skip in str(path) for skip in self.SKIP_DIRS):
                    return False

        # Check directory exclusions
        for skip in self.SKIP_DIRS:
            if f"/{skip}/" in str(path) or str(path).endswith(f"/{skip}"):
                return False

        # Check if extension is tracked
        suffix = path.suffix.lower()
        name = path.name

        # Special filenames
        if name in ("Snakefile", "Makefile", "Dockerfile", "nextflow.config",
                    ".nextflow.log", "samplesheet.csv"):
            return True

        if suffix in self.TRACKED_EXTENSIONS:
            return True

        # Track any file in specific directories
        rel_path = str(path)
        if any(d in rel_path for d in ["/log/", "/logs/", "/results/",
                                        "/output/", "/reports/", "/pipeline_info/"]):
            return True

        return False

    def _is_large_binary(self, path: Path) -> bool:
        """Check if file is a large binary that should only be tracked by metadata."""
        name = path.name.lower()
        for ext in self.LARGE_BINARY_EXTENSIONS:
            if name.endswith(ext):
                return True
        return False

    def _compute_hash(self, path: Path) -> Optional[str]:
        """Compute MD5 hash for file content detection."""
        try:
            if not path.exists() or path.is_dir():
                return None
            if self._is_large_binary(path):
                return f"size:{path.stat().st_size}"
            if path.stat().st_size > 100 * 1024 * 1024:  # Skip >100MB
                return f"size:{path.stat().st_size}"
            h = hashlib.md5()
            with open(path, "rb") as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            return h.hexdigest()
        except (OSError, PermissionError):
            return None

    def _get_file_metadata(self, path: Path) -> dict:
        """Collect file metadata."""
        try:
            stat = path.stat()
            return {
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "extension": path.suffix,
                "name": path.name,
                "relative_path": str(path.relative_to(self.project_path)),
                "absolute_path": str(path),
                "is_binary": self._is_large_binary(path),
            }
        except (OSError, PermissionError):
            return {}

    def scan(self, project_name: str) -> dict:
        """
        Full scan of project directory.
        Returns dict with new, modified, deleted files.
        """
        old_state = self._load_state(project_name)
        old_files = old_state.get("files", {})

        current_files = {}
        new_files = []
        modified_files = []

        # Walk the project directory
        for path in self.project_path.rglob("*"):
            if path.is_dir():
                continue
            if not self._should_track(path):
                continue

            rel_path = str(path.relative_to(self.project_path))
            file_hash = self._compute_hash(path)
            metadata = self._get_file_metadata(path)

            current_files[rel_path] = {
                "hash": file_hash,
                "metadata": metadata,
                "first_seen": old_files.get(rel_path, {}).get(
                    "first_seen", datetime.now().isoformat()
                ),
                "last_seen": datetime.now().isoformat(),
            }

            if rel_path not in old_files:
                new_files.append(rel_path)
            elif old_files[rel_path].get("hash") != file_hash:
                modified_files.append(rel_path)

        # Detect deleted files
        deleted_files = [f for f in old_files if f not in current_files]

        # Save new state
        new_state = {
            "files": current_files,
            "last_scan": datetime.now().isoformat(),
        }
        self._save_state(project_name, new_state)

        return {
            "new": new_files,
            "modified": modified_files,
            "deleted": deleted_files,
            "total_tracked": len(current_files),
            "current_files": current_files,
        }


# ===================================================================
# LOG AND RUN DETECTOR
# ===================================================================

class RunDetector:
    """
    Detects pipeline runs from log files, output files, and directory structures.
    Parses Nextflow logs, SLURM outputs, and generic log files.
    """

    def __init__(self, project_path: Path):
        self.project_path = project_path

    def detect_nextflow_runs(self) -> list:
        """Detect Nextflow runs from .nextflow.log files."""
        runs = []
        for log_file in self.project_path.rglob(".nextflow.log"):
            run_data = self._parse_nextflow_log(log_file)
            if run_data:
                runs.append(run_data)
        return runs

    def detect_slurm_outputs(self) -> list:
        """Detect SLURM job outputs from slurm-*.out files."""
        jobs = []
        for out_file in self.project_path.rglob("slurm-*.out"):
            job_data = self._parse_slurm_output(out_file)
            if job_data:
                jobs.append(job_data)
        # Also check .err files
        for err_file in self.project_path.rglob("slurm-*.err"):
            if err_file not in [j.get("_source") for j in jobs]:
                job_data = self._parse_slurm_err(err_file)
                if job_data:
                    jobs.append(job_data)
        return jobs

    def detect_log_files(self) -> list:
        """Detect any .log, .out, .err files."""
        logs = []
        patterns = ["*.log", "*.out", "*.err", "*.stderr", "*.stdout"]
        for pattern in patterns:
            for log_file in self.project_path.rglob(pattern):
                # Skip work directories
                if "work/" in str(log_file) or "/.nextflow/" in str(log_file):
                    continue
                logs.append(self._parse_generic_log(log_file))
        return logs

    def _parse_nextflow_log(self, log_path: Path) -> dict:
        """Parse .nextflow.log for run metadata."""
        try:
            content = log_path.read_text(errors="ignore")
        except (OSError, PermissionError):
            return {}

        data = {
            "type": "nextflow",
            "log_file": str(log_path),
            "run_dir": str(log_path.parent),
            "detected_at": datetime.now().isoformat(),
        }

        # Run name
        match = re.search(r"\[([a-z]+_[a-z]+)\]", content)
        if match:
            data["run_name"] = match.group(1)

        # Pipeline
        match = re.search(r"Launching `(.+?)`", content)
        if match:
            data["pipeline"] = match.group(1)

        # Command
        match = re.search(r"Command line: (.+?)$", content, re.MULTILINE)
        if match:
            data["command"] = match.group(1).strip()

        # Nextflow version
        match = re.search(r"nextflow version (\S+)", content, re.IGNORECASE)
        if match:
            data["nextflow_version"] = match.group(1)

        # Work directory
        match = re.search(r"work-dir\s*[:=]\s*(.+)", content)
        if match:
            data["work_dir"] = match.group(1).strip()

        # Config files
        data["config_files"] = re.findall(r"User config file: (.+)", content)

        # Status
        if "Execution complete" in content or "pipeline completed" in content.lower():
            data["status"] = "completed"
        elif "ERROR" in content or "execution failed" in content.lower():
            data["status"] = "failed"
            error_lines = [l for l in content.split("\n") if "ERROR" in l]
            if error_lines:
                data["error"] = error_lines[-1][:500]
        else:
            data["status"] = "running"

        # Duration
        match = re.search(r"Duration\s*:\s*(.+?)$", content, re.MULTILINE)
        if match:
            data["duration"] = match.group(1).strip()

        # Timestamps
        timestamps = re.findall(r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})", content)
        if timestamps:
            data["started_at"] = timestamps[0]
            data["last_activity"] = timestamps[-1]

        # Parse trace if available
        trace_path = self._find_trace(log_path.parent)
        if trace_path:
            data["trace"] = self._parse_trace(trace_path)

        return data

    def _find_trace(self, run_dir: Path) -> Optional[Path]:
        """Find trace file."""
        candidates = list(run_dir.rglob("trace*.txt"))
        candidates = [c for c in candidates if "work/" not in str(c)]
        return candidates[0] if candidates else None

    def _parse_trace(self, trace_path: Path) -> dict:
        """Parse trace file for resource stats."""
        import csv
        stats = {"total_tasks": 0, "completed": 0, "failed": 0,
                 "cpu_hours": 0.0, "peak_memory_gb": 0.0, "processes": {}}
        try:
            with open(trace_path) as f:
                first_line = f.readline()
                f.seek(0)
                delimiter = "\t" if "\t" in first_line else ","
                reader = csv.DictReader(f, delimiter=delimiter)
                for row in reader:
                    stats["total_tasks"] += 1
                    status = row.get("status", "").upper()
                    if status == "COMPLETED":
                        stats["completed"] += 1
                    elif status == "FAILED":
                        stats["failed"] += 1

                    process = row.get("name", row.get("process", "unknown"))
                    base = process.split("(")[0].strip()
                    if base not in stats["processes"]:
                        stats["processes"][base] = 0
                    stats["processes"][base] += 1

                    # CPU
                    realtime = row.get("realtime", "")
                    cpus = int(row.get("cpus", 1) or 1)
                    if realtime:
                        ms = self._duration_ms(str(realtime))
                        stats["cpu_hours"] += (ms / 3_600_000) * cpus

                    # Memory
                    peak = row.get("peak_rss", "")
                    if peak:
                        gb = self._mem_gb(str(peak))
                        stats["peak_memory_gb"] = max(stats["peak_memory_gb"], gb)
        except Exception:
            pass
        return stats

    def _parse_slurm_output(self, path: Path) -> dict:
        """Parse slurm output file."""
        match = re.search(r"slurm-(\d+)", path.name)
        if not match:
            return {}

        job_id = match.group(1)
        data = {
            "type": "slurm",
            "job_id": job_id,
            "output_file": str(path),
            "detected_at": datetime.now().isoformat(),
        }

        # Try sacct
        try:
            result = subprocess.run(
                ["sacct", "-j", job_id,
                 "--format=JobName%60,State,Elapsed,MaxRSS,NCPUS,Partition,ExitCode,Start,End",
                 "--parsable2", "--noheader", "-X"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                fields = result.stdout.strip().split("\n")[0].split("|")
                if len(fields) >= 9:
                    data["job_name"] = fields[0].strip()
                    data["status"] = fields[1].split()[0].lower()
                    data["elapsed"] = fields[2]
                    data["max_rss"] = fields[3]
                    data["cpus"] = fields[4]
                    data["partition"] = fields[5]
                    data["exit_code"] = fields[6]
                    data["start_time"] = fields[7]
                    data["end_time"] = fields[8]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Parse from file content
            try:
                content = path.read_text(errors="ignore")[:2000]
                if "error" in content.lower() or "FAILED" in content:
                    data["status"] = "failed"
                else:
                    data["status"] = "unknown"
            except Exception:
                data["status"] = "unknown"

        data["_source"] = path
        return data

    def _parse_slurm_err(self, path: Path) -> dict:
        match = re.search(r"slurm-(\d+)", path.name)
        if not match:
            return {}
        return {
            "type": "slurm_error",
            "job_id": match.group(1),
            "error_file": str(path),
            "detected_at": datetime.now().isoformat(),
        }

    def _parse_generic_log(self, path: Path) -> dict:
        """Parse any log/out/err file for basic metadata."""
        try:
            stat = path.stat()
            return {
                "type": "log",
                "path": str(path),
                "relative_path": str(path.relative_to(self.project_path))
                    if str(path).startswith(str(self.project_path)) else str(path),
                "name": path.name,
                "extension": path.suffix,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        except (OSError, PermissionError):
            return {"type": "log", "path": str(path)}

    @staticmethod
    def _duration_ms(s: str) -> float:
        total = 0.0
        for m in re.finditer(r"(\d+\.?\d*)\s*(d|h|m|s|ms)", str(s)):
            val = float(m.group(1))
            unit = m.group(2)
            mult = {"d": 86_400_000, "h": 3_600_000, "m": 60_000, "s": 1000, "ms": 1}
            total += val * mult.get(unit, 0)
        return total or 0.0

    @staticmethod
    def _mem_gb(s: str) -> float:
        s = str(s).strip().upper()
        for suffix, mult in [("TB", 1000), ("GB", 1), ("MB", 0.001), ("KB", 1e-6), ("B", 1e-9)]:
            if s.endswith(suffix):
                try:
                    return float(s[:-len(suffix)].strip()) * mult
                except ValueError:
                    return 0.0
        try:
            return float(s) / (1024**3)
        except ValueError:
            return 0.0


# ===================================================================
# MARKDOWN GENERATOR -- PROFESSIONAL DASHBOARD
# ===================================================================

class DashboardGenerator:
    """Generate professional, detailed, interactive MkDocs pages."""

    def __init__(self, docs_dir: Path = Path("docs")):
        self.docs_dir = docs_dir

    def generate_file_registry(self, project_name: str, scan_result: dict,
                               annotations: dict) -> Path:
        """Generate the file registry page with all tracked files."""
        reg_dir = self.docs_dir / "registry"
        reg_dir.mkdir(parents=True, exist_ok=True)

        files = scan_result.get("current_files", {})
        new = scan_result.get("new", [])
        modified = scan_result.get("modified", [])
        deleted = scan_result.get("deleted", [])

        now = datetime.now()
        content = f"""---
title: "File Registry -- {project_name}"
date: {now.strftime('%Y-%m-%d %H:%M')}
tags:
  - registry
  - {project_name}
---

# File Registry: {project_name}

**Scan Date:** {now.strftime('%Y-%m-%d %H:%M')}
**Total Tracked Files:** {len(files)}
**New Since Last Scan:** {len(new)}
**Modified Since Last Scan:** {len(modified)}
**Deleted Since Last Scan:** {len(deleted)}

---

"""
        # Changes summary
        if new or modified or deleted:
            content += "## Changes Detected\n\n"

            if new:
                content += "### New Files\n\n"
                content += "| File | Type | Size | Modified |\n"
                content += "|------|------|------|----------|\n"
                for f in sorted(new):
                    meta = files.get(f, {}).get("metadata", {})
                    size = self._format_size(meta.get("size", 0))
                    mod = meta.get("modified", "")[:16]
                    ext = meta.get("extension", "")
                    ann = annotations.get(f, {})
                    tags_str = ", ".join(ann.get("tags", []))
                    content += f"| `{f}` | {ext} | {size} | {mod} |\n"
                content += "\n"

            if modified:
                content += "### Modified Files\n\n"
                content += "| File | Type | Size | Modified |\n"
                content += "|------|------|------|----------|\n"
                for f in sorted(modified):
                    meta = files.get(f, {}).get("metadata", {})
                    size = self._format_size(meta.get("size", 0))
                    mod = meta.get("modified", "")[:16]
                    ext = meta.get("extension", "")
                    content += f"| `{f}` | {ext} | {size} | {mod} |\n"
                content += "\n"

            if deleted:
                content += "### Deleted Files\n\n"
                content += "| File |\n|------|\n"
                for f in sorted(deleted):
                    content += f"| `{f}` |\n"
                content += "\n"

        # Full file inventory grouped by directory
        content += "---\n\n## Complete File Inventory\n\n"
        dirs = {}
        for f, data in sorted(files.items()):
            parts = f.split("/")
            dir_name = "/".join(parts[:-1]) if len(parts) > 1 else "."
            dirs.setdefault(dir_name, []).append((f, data))

        for dir_name in sorted(dirs.keys()):
            dir_files = dirs[dir_name]
            content += f"### `{dir_name}/`\n\n"
            content += "| File | Extension | Size | Hash | First Seen | Tags | Context |\n"
            content += "|------|-----------|------|------|------------|------|--------|\n"
            for f, data in sorted(dir_files, key=lambda x: x[0]):
                meta = data.get("metadata", {})
                name = meta.get("name", f.split("/")[-1])
                ext = meta.get("extension", "")
                size = self._format_size(meta.get("size", 0))
                h = (data.get("hash", "") or "")[:8]
                first = data.get("first_seen", "")[:10]
                ann = annotations.get(f, {})
                tags = ", ".join(ann.get("tags", []))
                context = ann.get("context", "")[:40]
                content += f"| `{name}` | {ext} | {size} | {h} | {first} | {tags} | {context} |\n"
            content += "\n"

        filepath = reg_dir / f"{self._slugify(project_name)}.md"
        filepath.write_text(content)
        return filepath

    def generate_runs_page(self, project_name: str, nf_runs: list,
                           slurm_jobs: list, log_files: list) -> Path:
        """Generate pipeline runs and jobs page."""
        runs_dir = self.docs_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        content = f"""---
title: "Pipeline Runs -- {project_name}"
date: {now.strftime('%Y-%m-%d %H:%M')}
tags:
  - runs
  - {project_name}
---

# Pipeline Runs: {project_name}

**Last Scanned:** {now.strftime('%Y-%m-%d %H:%M')}

---

"""
        # Nextflow runs
        if nf_runs:
            content += "## Nextflow Runs\n\n"
            for run in nf_runs:
                status = run.get("status", "unknown")
                name = run.get("run_name", "unnamed")
                pipeline = run.get("pipeline", "unknown")
                duration = run.get("duration", "N/A")
                started = run.get("started_at", "N/A")

                content += f"### {name}\n\n"
                content += "| Field | Value |\n|-------|-------|\n"
                content += f"| Pipeline | `{pipeline}` |\n"
                content += f"| Status | {status} |\n"
                content += f"| Started | {started} |\n"
                content += f"| Duration | {duration} |\n"

                if run.get("command"):
                    content += f"| Command | `{run['command'][:80]}` |\n"
                if run.get("work_dir"):
                    content += f"| Work Dir | `{run['work_dir']}` |\n"
                if run.get("nextflow_version"):
                    content += f"| NF Version | {run['nextflow_version']} |\n"

                # Trace stats
                trace = run.get("trace", {})
                if trace:
                    content += f"| Total Tasks | {trace.get('total_tasks', 0)} |\n"
                    content += f"| Completed | {trace.get('completed', 0)} |\n"
                    content += f"| Failed | {trace.get('failed', 0)} |\n"
                    content += f"| CPU Hours | {trace.get('cpu_hours', 0):.2f} |\n"
                    content += f"| Peak Memory | {trace.get('peak_memory_gb', 0):.2f} GB |\n"

                    if trace.get("processes"):
                        content += "\n**Processes:**\n\n"
                        content += "| Process | Tasks |\n|---------|-------|\n"
                        for proc, count in sorted(trace["processes"].items()):
                            content += f"| {proc} | {count} |\n"

                if run.get("error"):
                    content += f"\n**Error:**\n```\n{run['error'][:300]}\n```\n"

                content += "\n---\n\n"

        # SLURM jobs
        if slurm_jobs:
            content += "## SLURM Jobs\n\n"
            content += "| Job ID | Name | Status | Elapsed | CPUs | Partition | Exit |\n"
            content += "|--------|------|--------|---------|------|-----------|------|\n"
            for job in slurm_jobs:
                if job.get("type") == "slurm_error":
                    continue
                content += (
                    f"| {job.get('job_id', '')} "
                    f"| {job.get('job_name', '')[:30]} "
                    f"| {job.get('status', '')} "
                    f"| {job.get('elapsed', '')} "
                    f"| {job.get('cpus', '')} "
                    f"| {job.get('partition', '')} "
                    f"| {job.get('exit_code', '')} |\n"
                )
            content += "\n"

        # Log files
        if log_files:
            content += "## Log Files\n\n"
            content += "| File | Size | Modified |\n"
            content += "|------|------|----------|\n"
            seen = set()
            for log in sorted(log_files, key=lambda x: x.get("modified", ""), reverse=True):
                path = log.get("relative_path", log.get("path", ""))
                if path in seen:
                    continue
                seen.add(path)
                size = self._format_size(log.get("size", 0))
                mod = log.get("modified", "")[:16]
                content += f"| `{path}` | {size} | {mod} |\n"
            content += "\n"

        filepath = runs_dir / f"{self._slugify(project_name)}.md"
        filepath.write_text(content)
        return filepath

    def generate_dashboard(self, config: dict, scan_results: dict) -> Path:
        """Generate the main dashboard with comprehensive statistics."""
        now = datetime.now()
        projects = config.get("projects", {})

        content = f"""---
title: "Dashboard"
date: {now.strftime('%Y-%m-%d %H:%M')}
---

# Project Intelligence Dashboard

**Last Updated:** {now.strftime('%Y-%m-%d %H:%M')}

---

## Watched Projects

| Project | Path | Tracked Files | New | Modified | Status |
|---------|------|---------------|-----|----------|--------|
"""
        for name, info in projects.items():
            path = info.get("path", "")
            result = scan_results.get(name, {})
            total = result.get("total_tracked", 0)
            new = len(result.get("new", []))
            modified = len(result.get("modified", []))
            exists = "Active" if Path(path).exists() else "Unreachable"
            content += f"| [{name}](registry/{self._slugify(name)}.md) | `{path}` | {total} | {new} | {modified} | {exists} |\n"

        content += "\n---\n\n"

        # Aggregate stats
        total_files = sum(r.get("total_tracked", 0) for r in scan_results.values())
        total_new = sum(len(r.get("new", [])) for r in scan_results.values())
        total_mod = sum(len(r.get("modified", [])) for r in scan_results.values())
        total_del = sum(len(r.get("deleted", [])) for r in scan_results.values())

        content += f"""## Summary

| Metric | Value |
|--------|-------|
| Total Tracked Files | {total_files} |
| New Files (this scan) | {total_new} |
| Modified Files (this scan) | {total_mod} |
| Deleted Files (this scan) | {total_del} |
| Projects | {len(projects)} |

---

## Quick Navigation

| Section | Description |
|---------|-------------|
| [File Registry](registry/) | All tracked files with metadata and annotations |
| [Pipeline Runs](runs/) | Nextflow runs, SLURM jobs, log files |
| [Notes](notes/) | Manual notes, debugging entries, observations |
| [Annotations](annotations.md) | File tags and context annotations |

---

## How to Add Context

To annotate files detected by the scanner, use:

biolab annotate <relative-file-path> --tags "tag1,tag2" --context "description"

Or edit `docs/annotations.md` directly on GitHub to add tags and context
to any tracked file.

"""

        filepath = self.docs_dir / "dashboard.md"
        filepath.write_text(content)
        return filepath

    def generate_annotations_page(self, annotations: dict) -> Path:
        """Generate the annotations page showing all tagged files."""
        content = """---
title: "File Annotations"
tags:
  - annotations
---

# File Annotations

This page lists all files that have been annotated with tags and context.
Use `biolab annotate` to add annotations, or edit this data in `.biolab/annotations.json`.

---

"""
        if not annotations:
            content += "*No annotations yet. Use `biolab annotate <path> --tags ... --context ...` to add context to tracked files.*\n"
        else:
            # Group by tag
            tags_index = {}
            for filepath, ann in annotations.items():
                for tag in ann.get("tags", []):
                    tags_index.setdefault(tag, []).append((filepath, ann))

            content += "## By Tag\n\n"
            for tag in sorted(tags_index.keys()):
                content += f"### {tag}\n\n"
                content += "| File | Context | Annotated |\n"
                content += "|------|---------|----------|\n"
                for fp, ann in tags_index[tag]:
                    ctx = ann.get("context", "")[:60]
                    dt = ann.get("annotated_at", "")[:10]
                    content += f"| `{fp}` | {ctx} | {dt} |\n"
                content += "\n"

            content += "---\n\n## All Annotations\n\n"
            content += "| File | Tags | Context | Date |\n"
            content += "|------|------|---------|------|\n"
            for fp, ann in sorted(annotations.items()):
                tags = ", ".join(ann.get("tags", []))
                ctx = ann.get("context", "")[:60]
                dt = ann.get("annotated_at", "")[:10]
                content += f"| `{fp}` | {tags} | {ctx} | {dt} |\n"

        filepath = self.docs_dir / "annotations.md"
        filepath.write_text(content)
        return filepath

    def generate_index(self, config: dict) -> Path:
        """Generate the home page."""
        name = config.get("name", "Lab Notebook")
        author = config.get("author", "")
        content = f"""---
title: "Home"
---

# {name}

**Author:** {author}
**System:** Automated Project Intelligence Tracker

---

## Overview

This system automatically monitors registered project directories and tracks:

- All new, modified, and deleted files
- Nextflow pipeline runs (parsed from `.nextflow.log` and trace files)
- SLURM job outputs (parsed from `slurm-*.out` and `sacct`)
- Log files (`.log`, `.out`, `.err`)
- Configuration files and scripts
- File content hashes for change detection

## Navigation

| Page | Purpose |
|------|---------|
| [Dashboard](dashboard.md) | Statistics and project overview |
| [File Registry](registry/) | Complete file inventory per project |
| [Pipeline Runs](runs/) | Detected runs with resource usage |
| [Annotations](annotations.md) | File tags and context |
| [Notes](notes/) | Manual notes and observations |

## Usage
biolab scan -- Scan all projects, detect changes
biolab annotate -- Add tags and context to files
biolab sync -- Scan + commit + push
biolab note -- Add a manual note

"""
        filepath = self.docs_dir / "index.md"
        filepath.write_text(content)
        return filepath

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024*1024):.1f} MB"
        else:
            return f"{size_bytes / (1024**3):.2f} GB"

    @staticmethod
    def _slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "-", text)
        return text[:50].rstrip("-")


# ===================================================================
# CLI COMMANDS
# ===================================================================

@app.command()
def init(
    name: str = typer.Option("JT Lab Notebook", help="Notebook name"),
    author: str = typer.Option("", help="Author name"),
):
    """Initialize the project intelligence tracker."""
    dirs = [
        ".biolab", ".biolab/state",
        "docs", "docs/registry", "docs/runs", "docs/notes",
        "docs/notes/debugging", "docs/notes/general",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)

    config = {
        "name": name, "author": author,
        "projects": {}, "last_scan": None,
    }
    Path(".biolab/config.json").write_text(json.dumps(config, indent=2))
    Path(".biolab/annotations.json").write_text("{}")
    Path(".biolab/scan_state.json").write_text("{}")

    # Create mkdocs.yml
    _create_mkdocs_config(name)

    # Generate initial pages
    gen = DashboardGenerator()
    gen.generate_index(config)
    gen.generate_dashboard(config, {})
    gen.generate_annotations_page({})

    typer.echo(f"Initialized: {name}")
    typer.echo("Next: biolab watch /path/to/project --name my-project")


@app.command()
def watch(
    path: str = typer.Argument(..., help="Project directory to track"),
    name: str = typer.Option("", "--name", "-n", help="Project name"),
):
    """Register a project directory for tracking."""
    project_path = Path(path).resolve()
    project_name = name if name else project_path.name

    config = _load_config()
    config["projects"][project_name] = {
        "path": str(project_path),
        "registered_at": datetime.now().isoformat(),
    }
    _save_config(config)

    typer.echo(f"Watching: {project_name} at {project_path}")
    typer.echo("Run 'biolab scan' to detect files.")


@app.command()
def scan(
    project_name: Optional[str] = typer.Argument(None, help="Specific project (all if empty)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Scan all project directories. Detect new files, runs, changes."""
    config = _load_config()
    projects = config.get("projects", {})

    if not projects:
        typer.echo("No projects registered. Use: biolab watch /path --name myproject")
        raise typer.Exit(1)

    scan_targets = (
        {project_name: projects[project_name]}
        if project_name and project_name in projects
        else projects
    )

    gen = DashboardGenerator()
    all_results = {}

    for proj_name, proj_info in scan_targets.items():
        proj_path = Path(proj_info["path"])
        if not proj_path.exists():
            typer.echo(f"  [skip] {proj_name} -- path not found")
            continue

        typer.echo(f"  Scanning: {proj_name}")

        # File tracking
        tracker = FileTracker(proj_path)
        result = tracker.scan(proj_name)
        all_results[proj_name] = result

        typer.echo(f"    Tracked: {result['total_tracked']} files")
        typer.echo(f"    New: {len(result['new'])}")
        typer.echo(f"    Modified: {len(result['modified'])}")
        typer.echo(f"    Deleted: {len(result['deleted'])}")

        if verbose:
            for f in result["new"][:10]:
                typer.echo(f"      + {f}")
            for f in result["modified"][:10]:
                typer.echo(f"      ~ {f}")

        # Run detection
        detector = RunDetector(proj_path)
        nf_runs = detector.detect_nextflow_runs()
        slurm_jobs = detector.detect_slurm_outputs()
        log_files = detector.detect_log_files()

        typer.echo(f"    Nextflow runs: {len(nf_runs)}")
        typer.echo(f"    SLURM jobs: {len(slurm_jobs)}")
        typer.echo(f"    Log files: {len(log_files)}")

        # Generate pages
        annotations = json.loads(Path(".biolab/annotations.json").read_text())
        gen.generate_file_registry(proj_name, result, annotations)
        gen.generate_runs_page(proj_name, nf_runs, slurm_jobs, log_files)

    # Generate dashboard and index
    gen.generate_dashboard(config, all_results)
    gen.generate_annotations_page(
        json.loads(Path(".biolab/annotations.json").read_text())
    )

    # Update config
    config["last_scan"] = datetime.now().isoformat()
    _save_config(config)

    typer.echo("")
    typer.echo("Scan complete. Run 'biolab build' to compile the site.")


@app.command()
def annotate(
    filepath: str = typer.Argument(..., help="Relative file path to annotate"),
    tags: str = typer.Option("", "--tags", "-t", help="Comma-separated tags"),
    context: str = typer.Option("", "--context", "-c", help="Context description"),
):
    """Add tags and context to a tracked file."""
    annotations = json.loads(Path(".biolab/annotations.json").read_text())

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    if filepath in annotations:
        # Merge tags
        existing_tags = annotations[filepath].get("tags", [])
        merged = list(set(existing_tags + tag_list))
        annotations[filepath]["tags"] = merged
        if context:
            old_ctx = annotations[filepath].get("context", "")
            if old_ctx:
                annotations[filepath]["context"] = old_ctx + " | " + context
            else:
                annotations[filepath]["context"] = context
        annotations[filepath]["updated_at"] = datetime.now().isoformat()
    else:
        annotations[filepath] = {
            "tags": tag_list,
            "context": context,
            "annotated_at": datetime.now().isoformat(),
        }

    Path(".biolab/annotations.json").write_text(json.dumps(annotations, indent=2))

    # Regenerate annotations page
    gen = DashboardGenerator()
    gen.generate_annotations_page(annotations)

    typer.echo(f"Annotated: {filepath}")
    typer.echo(f"  Tags: {tag_list}")
    if context:
        typer.echo(f"  Context: {context}")


@app.command()
def sync(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Scan all projects, rebuild site, and git commit."""
    # Scan
    config = _load_config()
    projects = config.get("projects", {})
    gen = DashboardGenerator()
    all_results = {}

    for proj_name, proj_info in projects.items():
        proj_path = Path(proj_info["path"])
        if not proj_path.exists():
            continue

        tracker = FileTracker(proj_path)
        result = tracker.scan(proj_name)
        all_results[proj_name] = result

        detector = RunDetector(proj_path)
        nf_runs = detector.detect_nextflow_runs()
        slurm_jobs = detector.detect_slurm_outputs()
        log_files = detector.detect_log_files()

        annotations = json.loads(Path(".biolab/annotations.json").read_text())
        gen.generate_file_registry(proj_name, result, annotations)
        gen.generate_runs_page(proj_name, nf_runs, slurm_jobs, log_files)

    gen.generate_dashboard(config, all_results)
    gen.generate_annotations_page(
        json.loads(Path(".biolab/annotations.json").read_text())
    )
    gen.generate_index(config)

    config["last_scan"] = datetime.now().isoformat()
    _save_config(config)

    # Git commit
    try:
        result = subprocess.run(["git", "status", "--porcelain"],
                               capture_output=True, text=True)
        if result.stdout.strip():
            subprocess.run(["git", "add", "-A"])
            msg = f"sync: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            subprocess.run(["git", "commit", "-m", msg])
            typer.echo(f"Committed: {msg}")
        else:
            typer.echo("No changes to commit.")
    except Exception as e:
        typer.echo(f"Git error: {e}")


@app.command()
def note(
    message: str = typer.Argument(..., help="Note content"),
    category: str = typer.Option("general", "--cat", "-c",
                                 help="Category: general, debugging, observation"),
    title: Optional[str] = typer.Option(None, "--title", "-t"),
    project_name: Optional[str] = typer.Option(None, "--project", "-p"),
    tags: str = typer.Option("", "--tags"),
):
    """Add a manual note."""
    now = datetime.now()
    note_title = title if title else message[:60]
    slug = re.sub(r"[^\w-]", "", note_title.lower().replace(" ", "-"))[:40]
    filename = f"{now.strftime('%Y-%m-%d')}_{slug}.md"
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    cat_dir = Path(f"docs/notes/{category}")
    cat_dir.mkdir(parents=True, exist_ok=True)

    tag_yaml = "\n".join(f"  - {t}" for t in tag_list) if tag_list else ""
    content = f"""---
title: "{note_title}"
date: {now.strftime('%Y-%m-%d %H:%M')}
category: {category}
{"tags:" if tag_list else ""}
{tag_yaml}
---

# {note_title}

{message}

"""
    if project_name:
        content += f"**Project:** {project_name}\n"
    content += f"\n---\n*{now.strftime('%Y-%m-%d %H:%M')}*\n"

    filepath = cat_dir / filename
    filepath.write_text(content)
    typer.echo(f"Note saved: {filepath}")


@app.command()
def status():
    """Show tracker status."""
    config = _load_config()
    typer.echo(f"\n{config.get('name', 'Lab Notebook')}")
    typer.echo(f"Author: {config.get('author', '')}")
    typer.echo(f"Last Scan: {config.get('last_scan', 'Never')}")
    typer.echo("")

    projects = config.get("projects", {})
    typer.echo(f"Watched Projects: {len(projects)}")
    for name, info in projects.items():
        exists = "OK" if Path(info["path"]).exists() else "NOT FOUND"
        typer.echo(f"  {name}: {info['path']} [{exists}]")

    annotations = json.loads(Path(".biolab/annotations.json").read_text())
    typer.echo(f"\nAnnotated Files: {len(annotations)}")


@app.command()
def build():
    """Build the MkDocs site."""
    result = subprocess.run(["mkdocs", "build"], capture_output=True, text=True)
    if result.returncode == 0:
        typer.echo("Site built: ./site/")
    else:
        typer.echo(f"Build error: {result.stderr[:300]}")


@app.command()
def serve(port: int = typer.Option(8000)):
    """Serve the site locally."""
    typer.echo(f"http://localhost:{port}")
    subprocess.run(["mkdocs", "serve", "--dev-addr", f"localhost:{port}"])


@app.command()
def deploy():
    """Scan, build, and deploy to GitHub Pages."""
    # Run sync first
    config = _load_config()
    projects = config.get("projects", {})
    gen = DashboardGenerator()
    all_results = {}

    for proj_name, proj_info in projects.items():
        proj_path = Path(proj_info["path"])
        if not proj_path.exists():
            continue
        tracker = FileTracker(proj_path)
        result = tracker.scan(proj_name)
        all_results[proj_name] = result
        detector = RunDetector(proj_path)
        annotations = json.loads(Path(".biolab/annotations.json").read_text())
        gen.generate_file_registry(proj_name, result, annotations)
        gen.generate_runs_page(proj_name, detector.detect_nextflow_runs(),
                               detector.detect_slurm_outputs(),
                               detector.detect_log_files())

    gen.generate_dashboard(config, all_results)
    gen.generate_annotations_page(
        json.loads(Path(".biolab/annotations.json").read_text())
    )
    gen.generate_index(config)

    result = subprocess.run(["mkdocs", "gh-deploy", "--force"],
                           capture_output=True, text=True)
    if result.returncode == 0:
        typer.echo("Deployed to GitHub Pages.")
    else:
        typer.echo(f"Deploy error: {result.stderr[:300]}")


@app.command()
def search(query: str = typer.Argument(...), limit: int = typer.Option(20, "-n")):
    """Search across all tracked content."""
    query_lower = query.lower()
    results = []
    for md_file in Path("docs").rglob("*.md"):
        if md_file.name == "index.md":
            continue
        try:
            content = md_file.read_text()
            if query_lower in content.lower():
                title_m = re.search(r'^#\s+(.+)', content, re.MULTILINE)
                title = title_m.group(1) if title_m else md_file.stem
                for line in content.split('\n'):
                    if query_lower in line.lower():
                        ctx = line.strip()[:80]
                        break
                else:
                    ctx = ""
                results.append((str(md_file), title, ctx))
        except Exception:
            continue

    if not results:
        typer.echo(f"No results for: '{query}'")
        return
    typer.echo(f"\nResults for '{query}' ({len(results)} found):\n")
    for fp, title, ctx in results[:limit]:
        typer.echo(f"  {title}")
        typer.echo(f"    {fp}")
        if ctx:
            typer.echo(f"    > {ctx}")
        typer.echo("")


# ===================================================================
# HELPERS
# ===================================================================

def _load_config() -> dict:
    p = Path(".biolab/config.json")
    if p.exists():
        return json.loads(p.read_text())
    typer.echo("No notebook found. Run: biolab init")
    raise typer.Exit(1)


def _save_config(config: dict):
    Path(".biolab/config.json").write_text(json.dumps(config, indent=2, default=str))


def _create_mkdocs_config(name: str):
    """Create mkdocs.yml with tags support and professional styling."""
    content = f"""site_name: "{name}"
site_description: "Automated Project Intelligence Tracker"

theme:
  name: material
  palette:
    - scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: Dark mode
    - scheme: slate
      primary: indigo
      accent: indigo
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
    - content.tabs.link
  font:
    text: Roboto
    code: Roboto Mono

plugins:
  - search:
      separator: '[\\s\\-\\.]+'
  - tags:
      tags_file: tags.md

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
  - File Registry: registry/
  - Pipeline Runs: runs/
  - Annotations: annotations.md
  - Notes: notes/
  - Tags: tags.md
"""
    Path("mkdocs.yml").write_text(content)

    # Create tags page
    Path("docs/tags.md").write_text("""---
title: Tags
---

# Tags Index

<!-- material/tags -->
""")


if __name__ == "__main__":
    app()

