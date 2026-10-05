from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .controller import Controller
from .profiles import PROFILES, resolve_profile, workspace_profile


def _task_json(task: Any) -> str:
    return json.dumps(task.to_dict(), indent=2, sort_keys=True)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="sarathi", description="Local task workspace controller")
    root.add_argument(
        "--profile",
        choices=PROFILES,
        help="isolated personal, work, or neutral context (default: SARATHI_PROFILE or neutral)",
    )
    sub = root.add_subparsers(dest="command", required=True)

    profile_cmd = sub.add_parser("profile", help="show the selected isolated context")
    profile_cmd.add_argument("--json", action="store_true")

    open_cmd = sub.add_parser("open", help="create or reuse a task workspace")
    open_cmd.add_argument("workspace", nargs="?", default=".")
    open_cmd.add_argument("--intent", default="")
    open_cmd.add_argument("--agent", choices=("claude", "codex", "agy"))
    open_ui = open_cmd.add_mutually_exclusive_group()
    open_ui.add_argument(
        "--emacs",
        action="store_true",
        help="explicitly open or focus the task in Emacs",
    )
    open_ui.add_argument(
        "--no-emacs",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    open_cmd.add_argument("--json", action="store_true")

    list_cmd = sub.add_parser("list", help="list registered tasks")
    list_cmd.add_argument("--json", action="store_true")

    show_cmd = sub.add_parser("show", help="show one task")
    show_cmd.add_argument("task_id")

    rename_cmd = sub.add_parser("rename", help="rename a task and lock manual naming")
    rename_cmd.add_argument("task_id")
    rename_cmd.add_argument("title")
    rename_cmd.add_argument("--automatic", action="store_true")
    rename_cmd.add_argument("--major-intent-change", action="store_true")

    refresh_names_cmd = sub.add_parser(
        "refresh-names", help="reapply current task titles to registered native sessions"
    )
    refresh_names_cmd.add_argument("task_id", nargs="?")

    agent_cmd = sub.add_parser("agent-command", help="prepare a safe native agent session")
    agent_cmd.add_argument("task_id")
    agent_cmd.add_argument("agent", choices=("claude", "codex", "agy"))
    agent_cmd.add_argument("--extra-arg", action="append", default=[])
    agent_cmd.add_argument("--allow-unsafe-once", action="store_true")
    agent_cmd.add_argument("--json", action="store_true")

    resume_cmd = sub.add_parser("resume-command", help="return a safe command for a known session")
    resume_cmd.add_argument("task_id")
    resume_cmd.add_argument("session_id")
    resume_cmd.add_argument("--json", action="store_true")

    capture_cmd = sub.add_parser("capture", help="capture a derived evidence summary")
    capture_cmd.add_argument("task_id")
    capture_cmd.add_argument("kind", choices=("change", "solution", "workaround", "learning", "decision", "feedback", "result"))
    capture_cmd.add_argument("summary")
    capture_cmd.add_argument("--source", action="append", default=[])

    complete_cmd = sub.add_parser("complete", help="finish a task only after an immediate resolution capture")
    complete_cmd.add_argument("task_id")
    complete_cmd.add_argument("--approach", required=True)
    complete_cmd.add_argument("--result", required=True)
    complete_cmd.add_argument("--workaround", action="append", default=[])
    complete_cmd.add_argument("--workflow-step", action="append", default=[])
    complete_cmd.add_argument("--command-summary", action="append", default=[])
    complete_cmd.add_argument("--learning", action="append", default=[])
    complete_cmd.add_argument("--link", action="append", default=[])

    restore_cmd = sub.add_parser("restore", help="sync registered tasks after restart")
    restore_ui = restore_cmd.add_mutually_exclusive_group()
    restore_ui.add_argument(
        "--emacs",
        action="store_true",
        help="explicitly recreate the registered task frames in Emacs",
    )
    restore_ui.add_argument(
        "--no-emacs",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    sync_cmd = sub.add_parser("sync", help="retry durable Smriti task and evidence outboxes")
    sync_cmd.add_argument("task_id", nargs="?")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        requested_profile = args.profile
        if args.command == "open" and not requested_profile:
            requested_profile = workspace_profile(Path(args.workspace))
        profile = resolve_profile(requested_profile)
        controller = Controller(profile=profile)
        if args.command == "profile":
            payload = {
                "profile": profile,
                "state": str(controller.registry.path.parent),
                "smriti_configured": controller.smriti is not None,
            }
            print(json.dumps(payload, indent=2, sort_keys=True) if args.json else profile)
        elif args.command == "open":
            task = controller.create_task(Path(args.workspace), args.intent)
            if args.emacs:
                controller.open_emacs(task, agent=args.agent)
            print(_task_json(task) if args.json else f"{task.id}\t{task.title}\t{task.workspace}")
        elif args.command == "list":
            tasks = controller.registry.list()
            if args.json:
                print(json.dumps([task.to_dict() for task in tasks], indent=2, sort_keys=True))
            else:
                for task in tasks:
                    print(f"{task.short_id}\t{task.title}\t{task.workspace}")
        elif args.command == "show":
            print(_task_json(controller.registry.get(args.task_id)))
        elif args.command == "rename":
            task = controller.rename(
                args.task_id,
                args.title,
                manual=not args.automatic,
                major_intent_change=args.major_intent_change,
            )
            print(_task_json(task))
        elif args.command == "refresh-names":
            print(json.dumps(controller.refresh_session_names(args.task_id), sort_keys=True))
        elif args.command == "agent-command":
            plan = controller.prepare_agent(
                args.task_id,
                args.agent,
                extra_args=tuple(args.extra_arg),
                allow_unsafe_once=args.allow_unsafe_once,
            )
            payload = {
                "command": list(plan.command),
                "environment": plan.environment,
                "session": plan.session.__dict__ if hasattr(plan.session, "__dict__") else {
                    field: getattr(plan.session, field) for field in plan.session.__dataclass_fields__
                },
            }
            print(json.dumps(payload, sort_keys=True) if args.json else plan.shell_preview())
        elif args.command == "resume-command":
            plan = controller.resume_agent(args.task_id, args.session_id)
            print(
                json.dumps({"command": list(plan.command), "environment": plan.environment}, sort_keys=True)
                if args.json else plan.shell_preview()
            )
        elif args.command == "capture":
            print(json.dumps(controller.capture_evidence(args.task_id, args.kind, args.summary, args.source), indent=2, sort_keys=True))
        elif args.command == "complete":
            print(json.dumps(controller.complete_task(
                args.task_id,
                approach=args.approach,
                result=args.result,
                workarounds=args.workaround,
                workflow_steps=args.workflow_step,
                command_summaries=args.command_summary,
                learnings=args.learning,
                reference_links=args.link,
            ), indent=2, sort_keys=True))
        elif args.command == "restore":
            tasks = controller.registry.list()
            controller.sync_pending()
            if args.emacs:
                for task in reversed(tasks):
                    controller.open_emacs(task)
            print(json.dumps({"restored": len(tasks)}))
        elif args.command == "sync":
            print(json.dumps(controller.sync_pending(args.task_id), sort_keys=True))
    except (KeyError, ValueError, RuntimeError, OSError) as exc:
        print(f"sarathi: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
