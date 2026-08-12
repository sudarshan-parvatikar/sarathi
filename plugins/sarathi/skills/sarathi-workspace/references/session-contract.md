# Session contract

## Identity and profile

- Task `id` is an immutable UUID.
- `short_id` is a display-only prefix and may not be used as durable identity
  when ambiguous.
- `profile` is exactly `personal`, `work`, or `neutral` and never changes for a
  task or workspace.
- Agent session `registry_id` identifies Sarathi's record.
- `native_id` is the provider's resumable session/thread identifier and is
  never rewritten.

Registries live under profile-specific state directories. `personal` and
`work` use only their matching `SMRITI_<PROFILE>_URL` and token environment;
`neutral` never syncs to Smriti.

## Naming state machine

1. New task: `task-<short-id>`.
2. First intent: automatic three-to-six-word title; counter becomes one.
3. Major intent change: one optional automatic rename; counter becomes two.
4. Manual rename: normalize the title and lock automatic naming permanently.

Renaming updates display labels only. It never changes task, profile, or native
session identity.

## Adapter requirements

- Claude new: pass `--name`, `--permission-mode auto`, and a valid
  `--session-id` before launch. Resume with `--resume`.
- Codex new: start through app-server using `approvalPolicy: never` and
  `sandbox: workspaceWrite`, record the returned thread ID, set the title with
  `thread/name/set`, then open the TUI by resuming that thread.
- Agy: launch with `--sandbox --mode accept-edits`; preserve an observed
  conversation ID when available and otherwise retain the registry ID.
- Pass the selected profile in the child process environment so plugin and MCP
  processes use the same isolated context.
- Reject dangerous bypass flags unless the caller explicitly opts into one
  launch. Never persist that opt-in.

## Retention

Allowed: profile, IDs, short title, workspace path, provider, timestamps,
compact handoff, derived evidence summary, opaque source reference.

Prohibited: raw transcript, terminal stream, raw message/email/calendar body,
credential, source-code copy, clipboard, or unredacted command.
