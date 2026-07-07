# Copilot Repository Instructions

**Read [`AGENTS.md`](../AGENTS.md) at the repository root — it is the single source of truth for
all agent work on this repository, GitHub Copilot included.** Follow every rule there.

In short:

- **Project knowledge** lives in the committed **Serena memories** under `.serena/memories/`
  (reference truth: overview, structure, system patterns, integrations, conventions, commands, and
  the `architectural_decisions` ADR log — the committed design *discussions*) plus the git-ignored
  **`.ai/PROGRESS.md`** progress log. Read them before starting; keep them current when finishing
  (new decisions go in the `architectural_decisions` memory). See the `ai_tracking_system` memory
  for the split.
- **Environment / quality:** activate the `venv` (Python 3.13) before running Python; type hints and
  docstrings everywhere; `pylint src/` and `black src/ tests/` clean; `pytest tests/ -v` green;
  no absolute paths (`pathlib`, relative to root); sanitize external inputs; never commit generated
  output.
- **Never create git worktrees** — edit in place on the checked-out branch.

All the detail (working protocol, definition of done, testing, worktree ban) is in `AGENTS.md`.
