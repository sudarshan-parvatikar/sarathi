from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class AgentSession:
    agent: str
    registry_id: str
    native_id: str | None = None
    title: str = ""
    state: str = "prepared"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AgentSession":
        return cls(**value)


@dataclass(slots=True)
class Task:
    id: str
    short_id: str
    title: str
    workspace: str
    profile: str = "neutral"
    intent: str = ""
    automatic_renames: int = 0
    manual_name_locked: bool = False
    status: str = "active"
    completed_at: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    sessions: dict[str, AgentSession] = field(default_factory=dict)
    sync_pending: bool = False

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Task":
        data = dict(value)
        data["sessions"] = {
            key: AgentSession.from_dict(session)
            for key, session in data.get("sessions", {}).items()
        }
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
