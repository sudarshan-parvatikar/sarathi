# Sarathi

Sarathi is a public, local-first work controller: one durable task identity,
one Emacs workspace, and resumable Claude, Codex, and Agy sessions. It keeps
terminal control on the desktop and synchronizes only compact, redacted task
state with an optional private Smriti instance.

## What works in this foundation

- `sarathi open` starts or focuses a named Emacs daemon and returns immediately.
- Every task has an immutable UUID and a three-to-six-word mutable title.
- Titles propagate to Emacs, registered agent sessions, and Smriti. Codex names
  are updated through the documented `thread/name/set` app-server method;
  Claude receives `--name` before launch; Agy names live in Sarathi's registry.
- Claude defaults to `--permission-mode auto`; Codex defaults to
  `--ask-for-approval never --sandbox workspace-write`; Agy uses its sandbox.
  Unsafe bypass flags are rejected unless a single command explicitly opts in.
- Task directories hold context, handoff, and derived evidence files—never raw
  terminal output or transcripts. Failed Smriti writes remain as replayable,
  per-event outbox files and `sarathi sync` retries them.
- The repository is also a Codex/Claude plugin with one canonical agent-neutral
  skill and a small Smriti MCP bridge.
- Linux systemd-user and macOS LaunchAgent definitions are included but are not
  installed or enabled automatically.
- Optional Bash/Zsh helpers (`sr`, `sarathi_here`, and `sarathi_done`) reuse the
  canonical CLI; source `integrations/shell/sarathi.sh` only if those names do
  not conflict with an existing shell setup.
- [`BOOTSTRAP.md`](BOOTSTRAP.md) is the stable, provider-neutral machine setup
  entry point. The bootstrap script is dry-run by default and idempotent.

## Local development

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m sarathi.cli --help
scripts/bootstrap --identity neutral --roles base --dry-run
```

Install into an isolated environment with `pipx install .`, or use
`python -m pip install --user .`. Then load `emacs/sarathi.el` from the Emacs
daemon init file. Installation, service enablement, plugin enrollment, remote
repository access, and Smriti authentication remain explicit operator actions.

## Data and authority boundary

Sarathi is safe to publish because it contains controller code and schemas, not
work data. It never sends Slack messages, edits Jira, writes calendars, acts on
pull requests, or triggers builds. Those actions are outside Sarathi and must
pass Smriti's approval ledger. See [`SECURITY.md`](SECURITY.md).

## Repository layout

- `src/sarathi/` — registry, controller, CLI, safe agent adapters and MCP bridge
- `emacs/` — workspace UI and daemon integration
- `integrations/codex/sarathi/` — shared Codex/Claude plugin and skill
- `services/` — opt-in login service definitions
- `integrations/shell/` — opt-in reusable shell alias and functions
- `scripts/` — bootstrap and integration installers
- `tests/` — synthetic acceptance tests

License: Apache-2.0.
