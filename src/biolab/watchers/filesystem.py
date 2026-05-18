"""Filesystem watcher for tracking project file changes."""

import hashlib
from pathlib import Path
from typing import Set, Optional
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from ..models import FileEvent
from ..database import BioLabDB
from ..config import load_config
import logging
import os

logger = logging.getLogger(__name__)


def _should_track(path: Path, config=None) -> bool:
    """Determine if a file should be tracked."""
    if config is None:
        config = load_config()

    path_str = str(path)
    for pattern in config.watchers.ignored_patterns:
        if pattern.startswith("*"):
            if path_str.endswith(pattern[1:]):
                return False
        elif pattern in path_str:
            return False

    if path.suffix.lower() in [ext.lower() for ext in config.watchers.tracked_extensions]:
        return True
    return False


def _quick_hash(path: Path) -> Optional[str]:
    """Compute MD5 hash for files under 50MB."""
    try:
        if not path.exists() or path.stat().st_size > 50 * 1024 * 1024:
            return None
        h = hashlib.md5()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None


class BioLabFileHandler(FileSystemEventHandler):
    """Handle filesystem events and log them to the database."""

    def __init__(self, db: BioLabDB, project_id: str):
        self.db = db
        self.project_id = project_id
        self.config = load_config()

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if not _should_track(path, self.config):
            return
        try:
            file_event = FileEvent(
                project_id=self.project_id,
                event_type="created",
                file_path=str(path),
                file_size=path.stat().st_size if path.exists() else None,
                file_hash=_quick_hash(path),
            )
            self.db.add_file_event(file_event)
            logger.debug(f"Tracked new file: {path.name}")
        except Exception as e:
            logger.warning(f"Error tracking file creation: {e}")

    def on_modified(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if not _should_track(path, self.config):
            return
        try:
            file_event = FileEvent(
                project_id=self.project_id,
                event_type="modified",
                file_path=str(path),
                file_size=path.stat().st_size if path.exists() else None,
                file_hash=_quick_hash(path),
            )
            self.db.add_file_event(file_event)
        except Exception as e:
            logger.warning(f"Error tracking file modification: {e}")

    def on_deleted(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if not _should_track(path, self.config):
            return
        try:
            file_event = FileEvent(
                project_id=self.project_id,
                event_type="deleted",
                file_path=str(path),
            )
            self.db.add_file_event(file_event)
        except Exception as e:
            logger.warning(f"Error tracking file deletion: {e}")


class ProjectWatcher:
    """Watch project directories for file changes."""

    def __init__(self, db: BioLabDB, use_polling: bool = False):
        self.db = db
        # Use polling on NFS/Lustre (HPC shared filesystems)
        if use_polling:
            self.observer = PollingObserver(timeout=5)
        else:
            self.observer = Observer()
        self._watches = {}

    def watch_project(self, project_id: str, path: str):
        """Start watching a project directory."""
        if not Path(path).exists():
            logger.warning(f"Path does not exist: {path}")
            return
        handler = BioLabFileHandler(self.db, project_id)
        watch = self.observer.schedule(handler, path, recursive=True)
        self._watches[project_id] = watch
        logger.info(f"Watching: {path}")

    def start(self):
        """Start the observer thread."""
        self.observer.start()
        logger.info("Filesystem watcher started")

    def stop(self):
        """Stop the observer thread."""
        self.observer.stop()
        self.observer.join()
        logger.info("Filesystem watcher stopped")