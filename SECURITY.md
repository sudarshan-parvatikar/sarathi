# Security model

## Retained locally

Sarathi stores task IDs, short titles, workspace paths, agent/provider names,
native session identifiers, redacted evidence summaries, and compact handoffs.
Registry files are created mode `0600`.

## Not retained

Sarathi does not retain raw agent transcripts, terminal output, credentials,
source code, clipboard content, raw Slack/Jira/calendar content, or unredacted
commands. Explicit evidence capture accepts a short derived summary and source
references only.

## Permissions

- Claude: `--permission-mode auto`.
- Codex: `approvalPolicy=never` with `workspaceWrite` sandbox.
- Agy: `--sandbox --mode accept-edits`.

`--dangerously-skip-permissions`,
`--dangerously-bypass-approvals-and-sandbox`, `--yolo`, and equivalent flags
are rejected. A caller must provide the controller's per-launch
`allow_unsafe_once` switch; it is not persisted.

## Remote boundary

The Smriti endpoint is optional and must be supplied explicitly. Bearer tokens
are read from an environment variable named by configuration and are never
written to the registry. A failed sync is queued as derived JSON, not retried
with broadened permissions.

Report vulnerabilities privately to the repository owner before public
disclosure.
