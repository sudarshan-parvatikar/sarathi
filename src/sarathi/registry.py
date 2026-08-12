from __future__ import annotations

import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import Task, utc_now

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows is not a V1 target.
    fcntl = None


def default_state_dir() -> Path:
    override = os.environ.get("SARATHI_STATE_DIR")
    if override:
        return Path(override).expanduser()
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sarathi"


class Registry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_state_dir() / "registry.json"
        self.lock_path = self.path.with_suffix(".lock")

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            os.chmod(self.lock_path, 0o600)
            if fcntl:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _read_unlocked(self) -> dict[str, Task]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return {key: Task.from_dict(value) for key, value in payload.get("tasks", {}).items()}

    def _write_unlocked(self, tasks: dict[str, Task]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 1, "tasks": {key: task.to_dict() for key, task in tasks.items()}}
        fd, tmp_name = tempfile.mkstemp(prefix="registry-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp_name, 0o600)
            os.replace(tmp_name, self.path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def list(self) -> list[Task]:
        with self._lock():
            return sorted(self._read_unlocked().values(), key=lambda task: task.updated_at, reverse=True)

    def get(self, task_id: str) -> Task:
        with self._lock():
            tasks = self._read_unlocked()
            if task_id in tasks:
                return tasks[task_id]
            matches = [task for task in tasks.values() if task.short_id == task_id or task.id.startswith(task_id)]
            if len(matches) != 1:
                raise KeyError(f"unknown or ambiguous task: {task_id}")
            return matches[0]

    def create(self, workspace: Path) -> Task:
        with self._lock():
            tasks = self._read_unlocked()
            existing = next((task for task in tasks.values() if Path(task.workspace) == workspace.resolve()), None)
            if existing:
                return existing
            task_id = str(uuid.uuid4())
            short_id = task_id.split("-", 1)[0]
            task = Task(id=task_id, short_id=short_id, title=f"task-{short_id}", workspace=str(workspace.resolve()))
            tasks[task.id] = task
            self._write_unlocked(tasks)
            return task

    def save(self, task: Task) -> Task:
        with self._lock():
            tasks = self._read_unlocked()
            task.updated_at = utc_now()
            tasks[task.id] = task
            self._write_unlocked(tasks)
        return task
