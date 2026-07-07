# CLAUDE.md

**Read [`AGENTS.md`](AGENTS.md) first — it is the single source of truth for all agent work on
this repository.** This file only points Claude Code at it; the full working protocol, hard
requirements, testing rules, and the worktree ban all live in `AGENTS.md`.

## Where project knowledge lives

- **Serena memories** (`.serena/memories/`, committed) — reference knowledge / primary source of
  truth. Read with serena's `list_memories` / `read_memory`; update with `write_memory`. Start with
  `project_overview`, then `codebase_structure`, `system_patterns`, `code_style_and_conventions`,
  `suggested_commands`, `tools_and_skills`. Architectural decisions (the design *discussions* /
  ADRs) are the committed `architectural_decisions` memory.
- **`.ai/`** (git-ignored, local) — only `PROGRESS.md` (dated changelog). Read it before starting;
  append every session. (Decisions are **not** here — they live in the `architectural_decisions`
  memory so they stay committed.)

See the `ai_tracking_system` serena memory for how the knowledge is split.

## Hard rule: no worktrees

Never create a git worktree here — do not call `EnterWorktree`, do not run `git worktree add`.
Edit directly on the checked-out branch. (Enforced via `.claude/settings.json`:
`worktree.bgIsolation: "none"` and `EnterWorktree` denied.) See `AGENTS.md` for the rationale.

## Quick reference (authoritative details in `AGENTS.md`)

- Activate the venv first: `source venv/bin/activate` (Python **3.13**).
- Tests: `pytest tests/ -v` (root-level `tests/`). Lint/format: `pylint src/`, `black src/ tests/`.
- Keep the user-facing MkDocs `docs/` and `README.md` in sync with code changes.
- Update tracking before finishing: `.ai/PROGRESS.md` always; the relevant serena memory when
  structure/conventions change, and the `architectural_decisions` memory for notable choices.
  A `Stop` hook reminds you.
