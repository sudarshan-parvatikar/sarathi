from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sarathi.adapters import UNSAFE_FLAGS, build_launch_plan
from sarathi.controller import Controller, RenameLimitError
from sarathi.registry import Registry
from sarathi.smriti_client import SmritiClient
from sarathi.smriti_mcp import handle
from sarathi.smriti_client import SmritiUnavailable


class FakeCodex:
    def __init__(self) -> None:
        self.names: list[tuple[str, str]] = []

    def start_thread(self, cwd: str) -> str:
        return "thr_synthetic"

    def set_name(self, thread_id: str, name: str) -> None:
        self.names.append((thread_id, name))


class FakeSmriti:
    def __init__(self) -> None:
        self.tasks: list[tuple[str, str]] = []
        self.evidence: list[dict] = []

    def upsert_task(self, task):
        self.tasks.append((task.id, task.title))
        return {}

    def capture_evidence(self, payload):
        self.evidence.append(payload)
        return payload


class FailingSmriti(FakeSmriti):
    def capture_evidence(self, payload):
        raise SmritiUnavailable("synthetic outage")


class RegistryAndNamingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.registry = Registry(root / "state" / "registry.json")
        self.codex = FakeCodex()
        self.smriti = FakeSmriti()
        self.controller = Controller(self.registry, self.smriti, self.codex)
        self.workspace = root / "project"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_task_id_is_immutable_and_titles_follow_two_step_policy(self) -> None:
        task = self.controller.create_task(self.workspace, "Fix Jenkins deployment failure quickly")
        original_id = task.id
        self.assertEqual("Fix Jenkins deployment failure quickly", task.title)
        renamed = self.controller.rename(task.id, "Repair release verification pipeline", major_intent_change=True)
        self.assertEqual(original_id, renamed.id)
        self.assertEqual(2, renamed.automatic_renames)
        with self.assertRaises(RenameLimitError):
            self.controller.rename(task.id, "Another automatic title")
        manual = self.controller.rename(task.id, "Manual locked incident review", manual=True)
        self.assertTrue(manual.manual_name_locked)
        with self.assertRaises(RenameLimitError):
            self.controller.rename(task.id, "Major change still blocked", major_intent_change=True)

    def test_workspace_contains_compact_files_not_transcripts(self) -> None:
        task = self.controller.create_task(self.workspace, "Investigate flaky release tests")
        root = self.workspace / ".sarathi"
        self.assertTrue((root / "context.md").exists())
        self.assertTrue((root / "handoff.md").exists())
        self.assertFalse((root / "transcript.jsonl").exists())
        payload = json.loads((root / "task.json").read_text())
        self.assertEqual(task.title, payload["title"])
        self.assertEqual("neutral", payload["profile"])
        self.assertEqual("neutral", (root / "profile").read_text().strip())
        self.assertEqual(0o600, self.registry.path.stat().st_mode & 0o777)

    def test_workspace_cannot_cross_personal_and_work_profiles(self) -> None:
        personal_registry = Registry(Path(self.temp.name) / "personal.json", profile="personal")
        personal = Controller(personal_registry, self.smriti, self.codex)
        task = personal.create_task(self.workspace, "Keep personal work isolated")
        self.assertEqual("personal", task.profile)
        work_registry = Registry(Path(self.temp.name) / "work.json", profile="work")
        work = Controller(work_registry, self.smriti, self.codex)
        with self.assertRaisesRegex(ValueError, "workspace belongs to 'personal'"):
            work.create_task(self.workspace, "Do not cross the boundary")

    def test_codex_session_preserves_thread_and_receives_rename(self) -> None:
        task = self.controller.create_task(self.workspace, "Build exact cache validation")
        plan = self.controller.prepare_agent(task.id, "codex")
        self.assertEqual("thr_synthetic", plan.session.native_id)
        self.assertIn("workspace-write", plan.command)
        self.assertEqual({"SARATHI_PROFILE": "neutral"}, plan.environment)
        self.assertIn(("thr_synthetic", task.title), self.codex.names)
        changed = self.controller.rename(task.id, "Validate unchanged inference cache", major_intent_change=True)
        self.assertIn(("thr_synthetic", changed.title), self.codex.names)

    def test_unsafe_bypass_flags_are_rejected(self) -> None:
        task = self.controller.create_task(self.workspace, "Run safe agent workspace")
        for flag in UNSAFE_FLAGS:
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                build_launch_plan(task, "claude", extra_args=(flag,))

    def test_evidence_is_derived_and_syncs_without_raw_fields(self) -> None:
        task = self.controller.create_task(self.workspace, "Capture useful debugging result")
        event = self.controller.capture_evidence(task.id, "result", "Reduced runtime by five minutes", ["jenkins:42"])
        self.assertEqual("derived-no-raw-content", event["redaction_state"])
        self.assertNotIn("terminal_output", event)
        self.assertEqual(event, self.smriti.evidence[0])

    def test_completion_is_gated_on_immediate_resolution_capture(self) -> None:
        task = self.controller.create_task(self.workspace, "Repair failing integration build")
        with self.assertRaises(ValueError):
            self.controller.complete_task(
                task.id, approach="", result="green", workarounds=[], workflow_steps=[],
                command_summaries=[], learnings=[], reference_links=[],
            )
        resolution = self.controller.complete_task(
            task.id,
            approach="Traced the failure to an expired fixture and regenerated it",
            result="Integration build passed",
            workarounds=["Ran the isolated fixture target first"],
            workflow_steps=["Reproduced", "Compared last green artifact", "Regenerated fixture"],
            command_summaries=["Ran the redacted fixture verification command"],
            learnings=["Fixture expiry should be checked before deployment"],
            reference_links=["https://confluence.example.invalid/display/TEAM/Fixture+Runbook"],
        )
        saved = self.registry.get(task.id)
        self.assertEqual("done", saved.status)
        self.assertEqual("synchronous-task-completion-gate", resolution["provenance"]["method"])
        text = (self.workspace / ".sarathi" / "resolution.md").read_text()
        self.assertIn("How it worked", text)
        self.assertIn("confluence", text.casefold())

    def test_failed_completion_sync_has_durable_replayable_outbox(self) -> None:
        self.controller.smriti = FailingSmriti()
        task = self.controller.create_task(self.workspace, "Preserve completion during outage")
        self.controller.complete_task(
            task.id, approach="Used the documented fallback", result="Task finished",
            workarounds=[], workflow_steps=[], command_summaries=[], learnings=[], reference_links=[],
        )
        pending = list((self.workspace / ".sarathi" / "outbox").glob("*.json"))
        self.assertEqual(1, len(pending))
        event_id = json.loads(pending[0].read_text())["id"]
        self.controller.smriti = self.smriti
        outcome = self.controller.sync_pending(task.id)
        self.assertEqual({"attempted": 1, "synced": 1, "remaining": 0}, outcome)
        self.assertEqual(event_id, self.smriti.evidence[-1]["id"])
        self.assertFalse(list((self.workspace / ".sarathi" / "outbox").glob("*.json")))


class McpTests(unittest.TestCase):
    def test_tools_are_described_before_smriti_is_configured(self) -> None:
        result = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, None)
        names = {tool["name"] for tool in result["result"]["tools"]}
        self.assertEqual({"smriti_task_get", "smriti_evidence_capture", "smriti_handoff_put"}, names)

    def test_write_fails_closed_without_endpoint(self) -> None:
        result = handle(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "smriti_evidence_capture", "arguments": {}}},
            None,
        )
        self.assertIn("error", result)

    def test_smriti_endpoints_are_selected_without_cross_profile_fallback(self) -> None:
        environment = {
            "SMRITI_WORK_URL": "https://work-smriti.invalid",
            "SMRITI_PERSONAL_URL": "https://personal-smriti.invalid",
            "SMRITI_NEUTRAL_URL": "https://neutral-smriti.invalid",
        }
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual("https://work-smriti.invalid", SmritiClient.from_environment("work").base_url)
            self.assertEqual(
                "SMRITI_WORK_TOKEN",
                SmritiClient.from_environment("work").token_env,
            )
            self.assertEqual(
                "https://personal-smriti.invalid",
                SmritiClient.from_environment("personal").base_url,
            )
            self.assertIsNone(SmritiClient.from_environment("neutral"))
        with patch.dict(os.environ, {"SMRITI_URL": "https://generic.invalid"}, clear=True):
            self.assertIsNone(SmritiClient.from_environment("work"))
            self.assertIsNone(SmritiClient.from_environment("personal"))


class BootstrapTests(unittest.TestCase):
    def test_neutral_dry_run_is_non_mutating_and_repeatable(self) -> None:
        script = Path(__file__).parents[1] / "scripts" / "bootstrap"
        env = dict(os.environ)
        env["PATH"] = ""
        command = [
            sys.executable, str(script), "--identity", "neutral", "--roles", "base",
            "--skip-agent-plugins", "--dry-run",
        ]
        first = subprocess.run(command, capture_output=True, text=True, env=env, check=True)
        second = subprocess.run(command, capture_output=True, text=True, env=env, check=True)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))
        self.assertEqual("dry-run", json.loads(first.stdout)["mode"])

    def test_neutral_apply_installs_managed_client_and_is_idempotent(self) -> None:
        script = Path(__file__).parents[1] / "scripts" / "bootstrap"
        with tempfile.TemporaryDirectory() as prefix:
            command = [
                sys.executable, str(script), "--identity", "neutral", "--roles", "base",
                "--prefix", prefix, "--skip-agent-plugins", "--apply",
            ]
            applied = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertEqual("installed", json.loads(applied.stdout)["actions"][0]["status"])
            wrapper = Path(prefix) / "bin" / "sarathi"
            self.assertTrue(wrapper.exists())
            self.assertEqual(0, subprocess.run([str(wrapper), "--help"], capture_output=True).returncode)
            selected = subprocess.run([str(wrapper), "profile"], capture_output=True, text=True, check=True)
            self.assertEqual("neutral", selected.stdout.strip())
            checked = subprocess.run(command[:-1] + ["--dry-run"], capture_output=True, text=True, check=True)
            self.assertEqual("present-current", json.loads(checked.stdout)["actions"][0]["status"])

    def test_one_shared_plugin_is_listed_in_both_marketplaces(self) -> None:
        root = Path(__file__).parents[1]
        plugin = root / "plugins" / "sarathi"
        codex_marketplace = json.loads((root / ".agents" / "plugins" / "marketplace.json").read_text())
        claude_marketplace = json.loads((root / ".claude-plugin" / "marketplace.json").read_text())
        self.assertTrue((plugin / ".codex-plugin" / "plugin.json").is_file())
        self.assertTrue((plugin / ".claude-plugin" / "plugin.json").is_file())
        self.assertEqual("./plugins/sarathi", codex_marketplace["plugins"][0]["source"]["path"])
        self.assertEqual("./plugins/sarathi", claude_marketplace["plugins"][0]["source"])


if __name__ == "__main__":
    unittest.main()
