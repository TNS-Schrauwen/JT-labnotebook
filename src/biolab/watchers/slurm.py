"""SLURM job tracking and metadata extraction."""

import subprocess
from datetime import datetime
from typing import List, Optional, Dict
from ..models import SlurmJob, RunStatus
from ..database import BioLabDB
import logging

logger = logging.getLogger(__name__)


class SlurmTracker:
    """Track SLURM jobs and sync metadata."""

    def __init__(self, db: BioLabDB):
        self.db = db

    def sync_jobs(self, project_id: Optional[str] = None,
                  days: int = 7, user: Optional[str] = None):
        """Sync recent SLURM jobs into the database."""
        jobs = self._fetch_jobs(days=days, user=user)
        count = 0
        for job_data in jobs:
            if "." in job_data.get("job_id", ""):
                continue  # Skip sub-steps

            slurm_job = SlurmJob(
                job_id=job_data["job_id"],
                job_name=job_data.get("job_name"),
                project_id=project_id,
                partition=job_data.get("partition"),
                cpus=self._safe_int(job_data.get("ncpus")),
                nodes=self._safe_int(job_data.get("nnodes")),
                memory_mb=self._parse_memory_mb(job_data.get("reqmem", "")),
                time_limit=job_data.get("timelimit"),
                status=self._map_state(job_data.get("state", "")),
                submitted_at=self._parse_time(job_data.get("submit")),
                started_at=self._parse_time(job_data.get("start")),
                completed_at=self._parse_time(job_data.get("end")),
                exit_code=self._parse_exit_code(job_data.get("exitcode")),
                work_dir=job_data.get("workdir"),
                account=job_data.get("account"),
            )
            self.db.upsert_slurm_job(slurm_job)
            count += 1

        logger.info(f"Synced {count} SLURM jobs")
        return count

    def _fetch_jobs(self, days: int = 7, user: Optional[str] = None) -> List[Dict]:
        """Fetch jobs from sacct."""
        if user is None:
            try:
                user = subprocess.getoutput("whoami").strip()
            except Exception:
                user = ""

        cmd = [
            "sacct",
            "-u", user,
            "--starttime", f"now-{days}days",
            "--format", "JobID,JobName%30,Partition,State,ExitCode,"
                       "Submit,Start,End,Elapsed,MaxRSS,NCPUS,NNodes,"
                       "Account,WorkDir%100,TimelimitRaw,ReqMem",
            "--parsable2", "--noheader",
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                logger.warning(f"sacct error: {result.stderr[:200]}")
                return []
        except FileNotFoundError:
            logger.warning("sacct not found — not on a SLURM system?")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("sacct timed out")
            return []

        fields = [
            "job_id", "job_name", "partition", "state", "exitcode",
            "submit", "start", "end", "elapsed", "maxrss", "ncpus",
            "nnodes", "account", "workdir", "timelimit", "reqmem",
        ]

        jobs = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            values = line.split("|")
            if len(values) >= len(fields):
                jobs.append(dict(zip(fields, values)))
        return jobs

    @staticmethod
    def _map_state(state: str) -> RunStatus:
        state = state.upper().split(" ")[0]  # Handle "CANCELLED by ..."
        mapping = {
            "COMPLETED": RunStatus.COMPLETED,
            "FAILED": RunStatus.FAILED,
            "CANCELLED": RunStatus.CANCELLED,
            "RUNNING": RunStatus.RUNNING,
            "PENDING": RunStatus.PENDING,
            "TIMEOUT": RunStatus.FAILED,
            "NODE_FAIL": RunStatus.FAILED,
            "OUT_OF_MEMORY": RunStatus.FAILED,
        }
        return mapping.get(state, RunStatus.PENDING)

    @staticmethod
    def _parse_time(time_str: Optional[str]) -> Optional[datetime]:
        if not time_str or time_str in ("Unknown", "None"):
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_exit_code(code_str: Optional[str]) -> Optional[int]:
        if not code_str:
            return None
        try:
            return int(code_str.split(":")[0])
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _safe_int(val) -> Optional[int]:
        if val is None or val == "":
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_memory_mb(mem_str: str) -> Optional[int]:
        if not mem_str:
            return None
        mem_str = mem_str.strip().upper()
        try:
            if mem_str.endswith("G") or mem_str.endswith("GN") or mem_str.endswith("GC"):
                return int(float(mem_str.rstrip("GNC")) * 1024)
            elif mem_str.endswith("M") or mem_str.endswith("MN") or mem_str.endswith("MC"):
                return int(float(mem_str.rstrip("MNC")))
            return int(float(mem_str))
        except ValueError:
            return None