from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class SmritiUnavailable(RuntimeError):
    pass


@dataclass(slots=True)
class SmritiClient:
    base_url: str
    token_env: str = "SMRITI_TOKEN"
    timeout: float = 3.0

    @classmethod
    def from_environment(cls) -> "SmritiClient | None":
        value = os.environ.get("SMRITI_URL", "").strip()
        return cls(value.rstrip("/"), os.environ.get("SMRITI_TOKEN_ENV", "SMRITI_TOKEN")) if value else None

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        token = os.environ.get(self.token_env)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SmritiUnavailable(str(exc)) from exc
        return json.loads(body) if body else {}

    def upsert_task(self, task: Task) -> dict[str, Any]:
        from .models import Task

        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        return self.request(
            "PUT",
            f"/api/v1/tasks/{task.id}",
            {"id": task.id, "title": task.title, "workspace": task.workspace, "source": "sarathi"},
        )

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self.request("GET", f"/api/v1/tasks/{task_id}")

    def capture_evidence(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/api/v1/evidence-events", payload)

    def put_handoff(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/api/v1/tasks/{task_id}/handoff", payload)
