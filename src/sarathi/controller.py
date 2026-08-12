from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from .adapters import LaunchPlan, build_launch_plan, build_resume_plan
from .codex_app_server import CodexAppServer
from .models import Task, utc_now
from .naming import infer_title, normalize_title
from .profiles import resolve_profile, workspace_profile
from .registry import Registry
from .smriti_client import SmritiClient, SmritiUnavailable


class RenameLimitError(ValueError):
    pass


class Controller:
    def __init__(
        self,
        registry: Registry | None = None,
        smriti: SmritiClient | None = None,
        codex: CodexAppServer | None = None,
        profile: str | None = None,
    ) -> None:
        self.profile = registry.profile if registry is not None else resolve_profile(profile)
        self.registry = registry or Registry(profile=self.profile)
        self.smriti = smriti if smriti is not None else SmritiClient.from_environment(self.profile)
        self.codex = codex or CodexAppServer()

    def create_task(self, workspace: Path, intent: str = "") -> Task:
        existing_profile = workspace_profile(workspace)
        if existing_profile and existing_profile != self.profile:
            raise ValueError(
                f"workspace belongs to {existing_profile!r}, not {self.profile!r}; "
                "use a separate workspace instead of crossing profiles"
            )
        workspace.mkdir(parents=True, exist_ok=True)
        task = self.registry.create(workspace)
        self.ensure_workspace_files(task)
        if intent and task.automatic_renames == 0 and not task.manual_name_locked:
            task.intent = intent
            task.title = infer_title(intent, task.short_id)
            task.automatic_renames = 1
            self._sync_task(task)
        saved = self.registry.save(task)
        self.ensure_workspace_files(saved)
        return saved

    def ensure_workspace_files(self, task: Task) -> None:
        root = Path(task.workspace) / ".sarathi"
        root.mkdir(parents=True, exist_ok=True)
        profile_path = root / "profile"
        if profile_path.exists() and profile_path.read_text(encoding="utf-8").strip() != task.profile:
            raise ValueError("workspace profile cannot be changed")
        profile_path.write_text(task.profile + "\n", encoding="utf-8")
        defaults = {
            "context.md": (
                f"# {task.title}\n\nTask ID: `{task.id}`\n\nProfile: `{task.profile}`\n\n## Context\n\n"
            ),
            "handoff.md": (
                f"# Handoff — {task.title}\n\nProfile: `{task.profile}`\n\n"
                "## Done\n\n## Next\n\n## Risks\n\n"
            ),
        }
        for name, content in defaults.items():
            path = root / name
            if not path.exists():
                path.write_text(content, encoding="utf-8")
        task_path = root / "task.json"
        task_path.write_text(json.dumps(task.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def rename(self, task_id: str, title: str, *, manual: bool = False, major_intent_change: bool = False) -> Task:
        task = self.registry.get(task_id)
        if not manual:
            if task.manual_name_locked:
                raise RenameLimitError("manual naming locked this task")
            allowed = task.automatic_renames == 0 or (major_intent_change and task.automatic_renames == 1)
            if not allowed:
                raise RenameLimitError("automatic rename allowance exhausted")
            task.automatic_renames += 1
        else:
            task.manual_name_locked = True
        task.title = normalize_title(title)
        for session in task.sessions.values():
            session.title = task.title
            if session.agent == "codex" and session.native_id:
                try:
                    self.codex.set_name(session.native_id, task.title)
                except (OSError, TimeoutError, RuntimeError):
                    task.sync_pending = True
        self.ensure_workspace_files(task)
        self._sync_task(task)
        return self.registry.save(task)

    def prepare_agent(
        self,
        task_id: str,
        agent: str,
        *,
        extra_args: tuple[str, ...] = (),
        allow_unsafe_once: bool = False,
    ) -> LaunchPlan:
        task = self.registry.get(task_id)
        native_id = self.codex.start_thread(task.workspace) if agent.lower() == "codex" else None
        plan = build_launch_plan(
            task,
            agent,
            native_id=native_id,
            extra_args=extra_args,
            allow_unsafe_once=allow_unsafe_once,
        )
        task.sessions[plan.session.registry_id] = plan.session
        if plan.session.agent == "codex" and plan.session.native_id:
            self.codex.set_name(plan.session.native_id, task.title)
        self.registry.save(task)
        return plan

    def resume_agent(self, task_id: str, session_id: str) -> LaunchPlan:
        task = self.registry.get(task_id)
        session = task.sessions.get(session_id)
        if not session:
            matches = [value for value in task.sessions.values() if value.native_id == session_id]
            if len(matches) != 1:
                raise KeyError(f"unknown session: {session_id}")
            session = matches[0]
        return build_resume_plan(task, session)

    def capture_evidence(self, task_id: str, kind: str, summary: str, sources: list[str]) -> dict[str, Any]:
        if not summary.strip():
            raise ValueError("evidence summary cannot be empty")
        task = self.registry.get(task_id)
        event = {
            "id": str(uuid4()),
            "schema_version": 1,
            "task_id": task.id,
            "profile": task.profile,
            "kind": kind,
            "summary": summary.strip(),
            "source_refs": sources,
            "occurred_at": utc_now(),
            "redaction_state": "derived-no-raw-content",
            "confidence": 1.0,
            "provenance": {"producer": "sarathi", "method": "explicit-user-capture"},
        }
        path = Path(task.workspace) / ".sarathi" / "evidence.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
        self._queue_and_sync_evidence(task, event)
        return event

    def complete_task(
        self,
        task_id: str,
        *,
        approach: str,
        result: str,
        workarounds: list[str],
        workflow_steps: list[str],
        command_summaries: list[str],
        learnings: list[str],
        reference_links: list[str],
    ) -> dict[str, Any]:
        if not approach.strip() or not result.strip():
            raise ValueError("completion requires both approach and result")
        task = self.registry.get(task_id)
        completed_at = utc_now()
        resolution = {
            "schema_version": 1,
            "task_id": task.id,
            "profile": task.profile,
            "title": task.title,
            "completed_at": completed_at,
            "approach": approach.strip(),
            "result": result.strip(),
            "workarounds": [value.strip() for value in workarounds if value.strip()],
            "workflow_steps": [value.strip() for value in workflow_steps if value.strip()],
            "command_summaries": [value.strip() for value in command_summaries if value.strip()],
            "learnings": [value.strip() for value in learnings if value.strip()],
            "reference_links": reference_links,
            "redaction_state": "derived-no-raw-content",
            "provenance": {"producer": "sarathi", "method": "synchronous-task-completion-gate"},
        }
        root = Path(task.workspace) / ".sarathi"
        lines = [
            f"# Resolution — {task.title}", "", f"Completed: {completed_at}", "",
            "## How it worked", "", resolution["approach"], "", "## Result", "", resolution["result"], "",
        ]
        for heading, key in (
            ("Workarounds", "workarounds"),
            ("Workflow and debugging path", "workflow_steps"),
            ("Redacted command summaries", "command_summaries"),
            ("Learning", "learnings"),
            ("References", "reference_links"),
        ):
            lines.extend([f"## {heading}", ""])
            lines.extend(f"- {value}" for value in resolution[key])
            lines.append("")
        (root / "resolution.md").write_text("\n".join(lines), encoding="utf-8")
        event = {
            "id": str(uuid4()),
            "schema_version": 1,
            "task_id": task.id,
            "profile": task.profile,
            "kind": "result",
            "summary": result.strip(),
            "action": approach.strip(),
            "result": result.strip(),
            "workarounds": resolution["workarounds"],
            "workflow_steps": resolution["workflow_steps"],
            "command_summaries": resolution["command_summaries"],
            "learnings": resolution["learnings"],
            "reference_links": reference_links,
            "source_refs": reference_links,
            "occurred_at": completed_at,
            "redaction_state": "derived-no-raw-content",
            "confidence": 1.0,
            "provenance": resolution["provenance"],
        }
        with (root / "evidence.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
        task.status = "done"
        task.completed_at = completed_at
        self._queue_and_sync_evidence(task, event)
        self.ensure_workspace_files(task)
        return resolution

    def _queue_and_sync_evidence(self, task: Task, event: dict[str, Any]) -> None:
        outbox = Path(task.workspace) / ".sarathi" / "outbox"
        outbox.mkdir(parents=True, exist_ok=True)
        pending = outbox / f"{event['id']}.json"
        pending.write_text(json.dumps(event, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        task.sync_pending = True
        self.registry.save(task)
        if not self.smriti:
            return
        try:
            self.smriti.capture_evidence(event)
        except SmritiUnavailable:
            return
        pending.unlink()
        task.sync_pending = any(outbox.glob("*.json"))
        self.registry.save(task)

    def sync_pending(self, task_id: str | None = None) -> dict[str, int]:
        tasks = [self.registry.get(task_id)] if task_id else self.registry.list()
        attempted = synced = remaining = 0
        for task in tasks:
            if self.smriti:
                self._sync_task(task)
            outbox = Path(task.workspace) / ".sarathi" / "outbox"
            task_remaining = 0
            for pending in sorted(outbox.glob("*.json")) if outbox.exists() else []:
                attempted += 1
                if not self.smriti:
                    remaining += 1
                    task_remaining += 1
                    continue
                event = json.loads(pending.read_text(encoding="utf-8"))
                try:
                    self.smriti.capture_evidence(event)
                except SmritiUnavailable:
                    remaining += 1
                    task_remaining += 1
                    continue
                pending.unlink()
                synced += 1
            task.sync_pending = bool(task.sync_pending or task_remaining or (outbox.exists() and any(outbox.glob("*.json"))))
            self.registry.save(task)
        return {"attempted": attempted, "synced": synced, "remaining": remaining}

    def _sync_task(self, task: Task) -> None:
        if not self.smriti:
            return
        try:
            self.smriti.upsert_task(task)
            task.sync_pending = False
        except SmritiUnavailable:
            task.sync_pending = True

    def open_emacs(self, task: Task, *, agent: str | None = None) -> None:
        expression = (
            "(progn (require 'sarathi) "
            f"(sarathi-open-task {json.dumps(task.id)} {json.dumps(task.workspace)} "
            f"{json.dumps(task.title)} {json.dumps(task.profile)})"
            + (f" (sarathi-launch-agent {json.dumps(task.id)} {json.dumps(agent)}))" if agent else ")")
        )
        command = ["emacsclient", "--socket-name=sarathi", "--create-frame", "--no-wait", "--eval", expression]
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError as exc:
            raise RuntimeError("emacsclient is not installed") from exc
