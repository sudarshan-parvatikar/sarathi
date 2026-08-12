# Agent instructions

Sarathi is public controller code. Never add credentials, real task content,
session transcripts, terminal output, employer identifiers, or private Smriti
records.

- Keep runtime behavior agent-neutral; product-specific adapters belong under
  `src/sarathi/adapters.py` and must use supported CLIs or APIs.
- Never inject terminal keystrokes.
- Reject dangerous permission-bypass flags by default.
- Preserve immutable task IDs and native agent session IDs.
- External writes require approval in Smriti; Sarathi must not grow a shortcut.
- Use only the Python standard library in the controller foundation.
- Run `PYTHONPATH=src python3 -m unittest discover -s tests -v` before handoff.
