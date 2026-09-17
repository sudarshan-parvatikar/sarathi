# Sarathi

Sarathi is a public, local-first work controller: one durable task identity,
one Emacs workspace, and resumable Claude, Codex, and Agy sessions. The same
plugin package works in Codex and Claude. It keeps terminal control on the
desktop and synchronizes only compact, redacted task state with the matching
optional private Smriti instance.

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
- The Smriti MCP bridge exposes audited producer/consumer context channels for
  redacted issues, fixes, workarounds, decisions, requests, and results. Each
  consumer acknowledges independently; messages never authorize external work.
- The repository is a marketplace for both Codex and Claude. Both install one
  canonical agent-neutral plugin, skill, and small Smriti MCP bridge from
  `plugins/sarathi`; there are no provider-specific copies to drift.
- `personal`, `work`, and `neutral` profiles have separate registries, evidence
  outboxes, child-agent environments, and Smriti configuration. A workspace is
  permanently bound to one profile and cross-profile reuse is rejected.
- Linux systemd-user and macOS LaunchAgent definitions are included but are not
  installed or enabled automatically.
- The optional `sarathi-smriti-sync.timer` retries Work task and evidence
  outboxes every five minutes; it never redirects Personal or Neutral state.
- Optional Bash/Zsh helpers include `sr`, `srp`, `srw`, `srn`, role functions,
  `sarathi_here`, and `sarathi_done`. They reuse the canonical CLI; source
  `integrations/shell/sarathi.sh` only if those names do not conflict.
- [`BOOTSTRAP.md`](BOOTSTRAP.md) is the stable, provider-neutral machine setup
  entry point. The bootstrap script is dry-run by default and idempotent.

## Local development

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m sarathi.cli --help
scripts/bootstrap --identity neutral --roles base --dry-run
scripts/agent-host-bootstrap --group core --group python --dry-run
```

Install into an isolated environment with `pipx install .`, or use
`python -m pip install --user .`. Then load `emacs/sarathi.el` from the Emacs
daemon init file. `scripts/bootstrap --apply` installs the local client,
registers this repository's marketplace in installed Codex and Claude CLIs,
and installs the shared plugin at user scope. Pass `--skip-agent-plugins` when
machine policy prohibits plugin enrollment. Start a new Codex thread or
restart/reload Claude after installation so the new skill is loaded.

## Profiles

Select the context explicitly when it is not the machine default:

```sh
sarathi --profile personal open ~/workspace/my-project --intent "Fix release notes"
sarathi --profile work open ~/work/approved-project --intent "Investigate build failure"
sarathi --profile neutral profile --json
```

The bootstrap identity becomes the installed wrapper's default, while
`SARATHI_PROFILE` or `--profile` can select another context per command. Work
sync uses only `SMRITI_WORK_URL` and `SMRITI_WORK_TOKEN`; personal sync uses
only `SMRITI_PERSONAL_URL` and `SMRITI_PERSONAL_TOKEN`. Neutral mode never
syncs to Smriti. Credentials stay in the environment or an approved secret
store, never in this repository.

## Data and authority boundary

Sarathi is safe to publish because it contains controller code and schemas, not
work data. It never sends Slack messages, edits Jira, writes calendars, acts on
pull requests, or triggers builds. Those actions are outside Sarathi and must
pass Smriti's approval ledger. See [`SECURITY.md`](SECURITY.md).

## Repository layout

- `src/sarathi/` — registry, controller, CLI, safe agent adapters and MCP bridge
- `emacs/` — workspace UI and daemon integration
- `plugins/sarathi/` — shared Codex/Claude plugin, skill, and Smriti MCP bridge
- `.agents/plugins/marketplace.json` — Codex marketplace catalog
- `.claude-plugin/marketplace.json` — Claude marketplace catalog
- `services/` — opt-in login service definitions
- `integrations/shell/` — opt-in reusable shell alias and functions
- `scripts/` — Sarathi bootstrap, host-tool planning, and integration installers
- `tests/` — synthetic acceptance tests

License: Apache-2.0.
