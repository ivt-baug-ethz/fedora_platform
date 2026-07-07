# AGENTS.md — FEDORA Platform Agent Instructions

> **Compatibility:** This file is the single source of truth for AI-agent work on this
> repository. It is read automatically by Claude Code (via `CLAUDE.md`), GitHub Copilot,
> OpenAI Codex, and other agents. All agents operating here MUST follow every rule below.
> You never need to commit changes — the maintainer commits manually. You are responsible
> for following the rules and keeping project tracking current.

---

## Repository overview

The **FEDORA Platform** is a Python **3.13** modular orchestration framework for multimodal
traffic management: pluggable **logic modules** (signal controllers, demand models) connected to
swappable execution **environments** (SUMO today, real-world pilots later) via an **Orchestrator**
over JSON-line TCP. The shipped demonstrator is traffic signal control (Fixed-Cycle, Max-Pressure,
Urban Priority Pass, plus a SUMO-default baseline). Full detail is in the serena memories below.

---

## Working protocol (read first, every session)

Project knowledge is split to avoid duplication, and keeping it current is part of every task:

- **Serena memories** (`.serena/memories/`, committed) — the reference knowledge and **primary
  source of truth**: `project_overview`, `codebase_structure`, `system_patterns`, `integrations`,
  `code_style_and_conventions`, `suggested_commands`, `task_completion_checklist`,
  `tools_and_skills`, `architectural_decisions`, `ai_tracking_system`. The **architectural
  decisions** (the explicit design *discussions* / ADRs — context, decision, rationale,
  consequences) are **committed** in the `architectural_decisions` memory, not in `.ai/`.
- **`.ai/`** (git-ignored, local) — only the ephemeral progress log: `PROGRESS.md` (dated
  changelog). See `.ai/README.md`.
- **This file** — the protocol and pointers only; it deliberately does **not** restate the content
  in the memories.

**Before starting a task**
1. Read the relevant **serena memories** — use serena's `list_memories` / `read_memory` (or read
   `.serena/memories/*.md` directly if serena is unavailable). Start with `project_overview`, then
   `codebase_structure`, `system_patterns`, `code_style_and_conventions`, `suggested_commands`,
   `tools_and_skills`.
2. Read the `architectural_decisions` memory — the committed ADRs / design decisions and
   constraints that bind your work.
3. Check `.ai/PROGRESS.md` — in-flight work and recent changes.

**While working** — follow the `code_style_and_conventions` memory; use the tools in
`tools_and_skills` (serena for code navigation/editing, context7 for library docs). If you deviate
from a recorded decision, record why in the `architectural_decisions` memory.

**Before finishing a task (definition of done)** — run the `task_completion_checklist` memory and
update whichever apply:
- **serena memory** — update `codebase_structure`, `system_patterns`,
  `code_style_and_conventions`, `integrations`, or `suggested_commands` (via `write_memory`) if
  structure, architecture, conventions, or commands changed.
- **User docs** — keep the MkDocs `docs/` pages and `README.md` in sync when a change touches
  components, setup, interfaces, configuration, entry points, or architecture. (This repo is **not**
  a pip package — there is no `ai-docs/`/Context7 doc set to maintain.)
- `architectural_decisions` memory — add an ADR (committed, via `write_memory`) when you made a
  non-obvious or systematic choice: context, decision, rationale, consequences.
- `.ai/PROGRESS.md` — **always** append a dated entry summarizing what changed and why (local).

**A stale tracking file is a bug** — fix it in the same task. A `Stop` hook
(`.claude/hooks/ai-tracking-reminder.sh`) reminds you if work changed but tracking (`.ai/` **or**
`.serena/memories/`) wasn't updated.

---

## Do NOT create worktrees (hard rule)

**Never create a git worktree in this repository.** Do not call the `EnterWorktree` tool, do not
run `git worktree add`, and do not otherwise isolate work into a separate working copy — not even
for background jobs. Apply **all** changes directly to the branch currently checked out in the main
working copy. Background-job isolation is disabled via `worktree.bgIsolation: "none"` and
`EnterWorktree` is denied in `.claude/settings.json`. Worktrees under `.claude/worktrees/` split the
local `.ai/` tracking across working copies and cause `Stop`-hook false positives — edit in place.

---

## Hard requirements

- **Virtual environment** — always activate `venv` before running Python:
  `source venv/bin/activate`. Create with `python3.13 -m venv venv && source venv/bin/activate &&
  pip install -r requirements.txt` if missing. Never install globally; after adding a package,
  `pip freeze > requirements.txt` with pinned versions.
- **Type annotations** on all function signatures.
- **Docstrings** on all public functions, classes, and modules.
- **Code quality** — run `pylint src/` (fix all warnings) and `black src/ tests/` before finishing.
  Keep functions small and single-purpose; avoid magic numbers/strings; one class per file in `src/`.
- **No absolute paths** — use `pathlib.Path`, relative to the project root.
- **Security** — validate/sanitize all external inputs (JSON config, file contents, CLI args)
  before passing them to algorithms. Never commit generated output (`logs/`, `results/`).

## Testing

- Write tests for every non-trivial function, covering edge and numerical cases.
- Tests live in the **root-level `tests/`** directory.
- Run the full suite before and after every change: `pytest tests/ -v`. Do not consider a task
  complete until all tests pass.

## Communication & reasoning

- Think step-by-step before changing traffic-management algorithms. If requirements are ambiguous,
  ask one focused clarifying question first. When proposing a non-obvious approach, briefly explain
  the reasoning and trade-offs. Flag numerical-precision or SUMO/TraCI failure risks explicitly.
- Do not hallucinate `numpy` / `sumolib` / `traci` / `matplotlib` APIs — verify via context7.
- At the end of each task, summarize what changed and why.
