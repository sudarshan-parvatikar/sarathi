# Agent host bootstrap

`scripts/agent-host-bootstrap` prepares a small, agent-neutral command-line
toolset. It is dry-run first, idempotent by command discovery, and never reads
or creates credentials.

```sh
# Default: core search/navigation, Python workflow, and quality tools.
scripts/agent-host-bootstrap --dry-run

# Include database/container clients used when operating Smriti.
scripts/agent-host-bootstrap --group core --group python --group quality \
  --group services --dry-run

# Apply the reviewed plan; omit --yes to retain package-manager prompts.
scripts/agent-host-bootstrap --group core --group python --apply
```

The core group installs Git, curl, ripgrep, jq, fd, fzf, tmux, direnv, and
ShellCheck. The Python group installs Python, pipx, and uv; the quality group
adds Ruff and pre-commit in isolated pipx environments. The services group
adds PostgreSQL, Redis, and SQLite clients. Docker is detected but deliberately
left as a manual install because its supported setup and privilege model are
platform-specific.

The script supports apt, dnf, pacman, and Homebrew. It installs packages but
does not enable daemons, start containers, edit shell startup files, add users
to privileged groups, or run `docker compose`. Review those steps separately.

Primary installation references:

- <https://docs.astral.sh/uv/getting-started/installation/>
- <https://pipx.pypa.io/latest/how-to/install-pipx.html>
- <https://github.com/BurntSushi/ripgrep#installation>
- <https://docs.docker.com/engine/install/>
