# Sarathi one-URL machine setup

This file is the stable, provider-neutral entry point for a capable agent or a
human. Read it from:

`https://raw.githubusercontent.com/sudarshan-parvatikar/sarathi/main/BOOTSTRAP.md`

The procedure is deliberately dry-run-first and identity-aware.

## 1. Inspect without changing the machine

Record the OS and architecture; presence and versions of Git, GitHub CLI,
Python 3.11+, Emacs 29+, Claude, Codex, and Agy; applicable employer policy;
and the active `gh api user --jq .login`. Do not print tokens or environment
dumps.

Run:

```sh
scripts/bootstrap --identity neutral --roles base --dry-run
```

## 2. Select the identity and roles

- `personal`: personal GitHub identity and its private versioned allowlist.
- `work`: employer-approved identity and allowlist in employer-approved storage.
- `neutral`: public Sarathi client tooling only; no private repositories.
- `base`: Sarathi CLI, skill/plugin links, and Emacs integration.
- `dev`: approved development repositories and developer checks.
- `server`: service definitions and server verification; never enable them
  implicitly.

Use comma-separated roles, for example `--roles base,dev`.

## 3. Verify authentication before retrieval

Switch GitHub accounts only after the operator confirms the selected identity.
Verify the resulting login exactly. A mismatch is a hard stop; never clone a
private allowlist using the wrong identity.

For `personal` or `work`, provide an allowlist document with a version and rows
containing repository, roles, destination, and optional artifact URL. The
bootstrap validates its shape before proposing actions. Credentials never
belong in the document.

## 4. Review the dry-run

Run the exact intended selection with `--manifest PATH` and no `--apply`.
Review identity, roles, existing paths, proposed clones/updates, plugin links,
Emacs load path, and service files. On managed machines, reject personal source
repositories unless policy explicitly permits them; use a reviewed offline
release artifact when personal source is prohibited.

## 5. Apply only after approval

Re-run the same command with `--apply`. The script installs no OS packages,
changes no GitHub authentication, enables no services, starts no tunnels, and
connects no employer system. It copies only the selected public client files
and clones only exact allowlisted repositories into unoccupied destinations.

## 6. Prove idempotence

Run the same dry-run again. Success is zero proposed mutations and all
verification checks passing. Test Linux and macOS separately; validate wrong
account, cancellation, missing tools, conflicting destinations, and repeated
installation.
