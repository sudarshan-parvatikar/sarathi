from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .profiles import resolve_profile


class SmritiUnavailable(RuntimeError):
    pass


@dataclass(slots=True)
class SmritiClient:
    base_url: str
    token_env: str = "SMRITI_TOKEN"
    timeout: float = 3.0
    profile: str = "neutral"

    @classmethod
    def from_environment(cls, profile: str | None = None) -> "SmritiClient | None":
        selected = resolve_profile(profile)
        if selected == "neutral":
            return None
        prefix = f"SMRITI_{selected.upper()}"
        value = os.environ.get(f"{prefix}_URL", "").strip()
        token_env = os.environ.get(f"{prefix}_TOKEN_ENV", f"{prefix}_TOKEN")
        return cls(value.rstrip("/"), token_env, profile=selected) if value else None

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
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
            {
                "id": task.id,
                "title": task.title,
                "workspace": task.workspace,
                "profile": task.profile,
                "source": "sarathi",
            },
        )

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self.request("GET", f"/api/v1/tasks/{task_id}")

    def capture_evidence(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/api/v1/evidence-events", {**payload, "profile": self.profile})

    def put_handoff(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request(
            "PUT",
            f"/api/v1/tasks/{task_id}/handoff",
            {**payload, "profile": self.profile},
        )

    def publish_context(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request(
            "POST", "/api/v1/context-messages", {**payload, "profile": self.profile},
        )

    def consume_context(
        self,
        *,
        consumer_id: str,
        topic: str | None = None,
        kinds: list[str] | None = None,
        task_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "consumer_id": consumer_id,
            "profile": self.profile,
            "limit": limit,
        }
        if topic:
            query["topic"] = topic
        if kinds:
            query["kinds"] = kinds
        if task_id:
            query["task_id"] = task_id
        return self.request(
            "GET", f"/api/v1/context-messages?{urllib.parse.urlencode(query, doseq=True)}",
        )

    def acknowledge_context(
        self,
        message_id: str,
        *,
        consumer_id: str,
        status: str = "acknowledged",
        note: str | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            f"/api/v1/context-messages/{message_id}/ack",
            {
                "consumer_id": consumer_id,
                "status": status,
                "note": note,
                "profile": self.profile,
            },
        )
