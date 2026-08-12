from __future__ import annotations

import re

_STOP_WORDS = {
    "a", "an", "and", "for", "from", "in", "into", "of", "on", "or",
    "the", "to", "with", "work", "working", "please", "task",
}


def normalize_title(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9._+-]*", value)
    words = [word for word in words if word.lower() not in _STOP_WORDS]
    if len(words) < 3:
        words.extend(["focused", "work", "task"][: 3 - len(words)])
    return " ".join(words[:6])


def infer_title(intent: str, short_id: str) -> str:
    if not intent.strip():
        return f"task-{short_id} focused work"
    return normalize_title(intent)


def emacs_label(task_id: str, title: str) -> str:
    return f"{title} [{task_id[:8]}]"
