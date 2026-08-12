from __future__ import annotations

import shlex
import uuid
from dataclasses import dataclass

from .models import AgentSession, Task


UNSAFE_FLAGS = {
    "--dangerously-skip-permissions",
    "--allow-dangerously-skip-permissions",
    "--dangerously-bypass-approvals-and-sandbox",
    "--yolo",
    "--no-sandbox",
}


@dataclass(frozen=True, slots=True)
class LaunchPlan:
    command: tuple[str, ...]
    session: AgentSession

    def shell_preview(self) -> str:
        return shlex.join(self.command)


def ensure_safe_args(args: list[str] | tuple[str, ...], allow_unsafe_once: bool = False) -> None:
    present = UNSAFE_FLAGS.intersection(args)
    if present and not allow_unsafe_once:
        raise ValueError(f"unsafe bypass flags rejected: {', '.join(sorted(present))}")


def build_launch_plan(
    task: Task,
    agent: str,
    *,
    native_id: str | None = None,
    extra_args: tuple[str, ...] = (),
    allow_unsafe_once: bool = False,
) -> LaunchPlan:
    ensure_safe_args(extra_args, allow_unsafe_once)
    agent = agent.lower()
    registry_id = str(uuid.uuid4())
    if agent == "claude":
        native_id = native_id or str(uuid.uuid4())
        command = (
            "claude", "--name", task.title, "--permission-mode", "auto",
            "--session-id", native_id, *extra_args,
        )
    elif agent == "codex":
        if not native_id:
            raise ValueError("Codex launch requires a prepared native thread id")
        command = (
            "codex", "--ask-for-approval", "never", "--sandbox", "workspace-write",
            "resume", native_id, *extra_args,
        )
    elif agent == "agy":
        command = ("agy", "--sandbox", "--mode", "accept-edits", *extra_args)
    else:
        raise ValueError(f"unsupported agent: {agent}")
    return LaunchPlan(
        command=command,
        session=AgentSession(
            agent=agent,
            registry_id=registry_id,
            native_id=native_id,
            title=task.title,
        ),
    )


def build_resume_plan(task: Task, session: AgentSession) -> LaunchPlan:
    if session.agent == "claude" and session.native_id:
        command = ("claude", "--permission-mode", "auto", "--resume", session.native_id)
    elif session.agent == "codex" and session.native_id:
        command = (
            "codex", "--ask-for-approval", "never", "--sandbox", "workspace-write",
            "resume", session.native_id,
        )
    elif session.agent == "agy" and session.native_id:
        command = ("agy", "--sandbox", "--mode", "accept-edits", "--conversation", session.native_id)
    elif session.agent == "agy":
        command = ("agy", "--sandbox", "--mode", "accept-edits")
    else:
        raise ValueError(f"session {session.registry_id} cannot be resumed")
    return LaunchPlan(command=command, session=session)
