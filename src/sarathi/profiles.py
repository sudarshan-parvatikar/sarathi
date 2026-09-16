from __future__ import annotations

import os
from pathlib import Path


PROFILES = ("personal", "work", "neutral")


def resolve_profile(value: str | None = None) -> str:
    profile = (value or os.environ.get("SARATHI_PROFILE") or "neutral").strip().lower()
    if profile not in PROFILES:
        raise ValueError(f"profile must be one of: {', '.join(PROFILES)}")
    return profile


def workspace_profile(workspace: Path) -> str | None:
    marker = workspace.expanduser().resolve() / ".sarathi" / "profile"
    if not marker.is_file():
        return None
    return resolve_profile(marker.read_text(encoding="utf-8").strip())


def profile_environment(profile: str) -> dict[str, str]:
    return {"SARATHI_PROFILE": resolve_profile(profile)}
