# AI Tracking System (how project knowledge is split)

To avoid duplicating the same facts in two places, project knowledge is split:

- **Serena memories** (this store, `.serena/memories/`, **committed** to git) = **reference
  knowledge**, the single source of truth: `mem:project_overview`, `mem:codebase_structure`,
  `mem:system_patterns`, `mem:integrations`, `mem:code_style_and_conventions`,
  `mem:suggested_commands`, `mem:task_completion_checklist`, `mem:tools_and_skills`, and
  `mem:architectural_decisions`. Read via serena's `read_memory` / `list_memories`, or directly as
  `.serena/memories/*.md` if serena is unavailable. Update with `write_memory` when facts change.

- **Architectural decisions are committed**: the ADR log — the explicit design *discussions*
  (context / decision / rationale / consequences) — lives in the `mem:architectural_decisions`
  memory, **not** in `.ai/`. This keeps the decision history version-controlled and shared. Append
  new ADRs there via `write_memory`; never delete past entries.

- **`.ai/`** (git-ignored, local only) = the ephemeral **progress** log the user asked to keep
  local, not committed:
  - `.ai/PROGRESS.md` — dated progress/changelog; append every session.
  - `.ai/README.md` — describes this split.

- **`AGENTS.md`** (repo root) = the **working protocol**, read by all AI tools (Claude Code via
  `CLAUDE.md` → AGENTS.md, plus Copilot/Codex/others directly). It says what to read before a task
  and update after; it points here and does **not** duplicate the reference content.

This repo is **not** a pip package, so — unlike the reference setup it was modelled on — there is
no `ai-docs/` / `context7.json` doc set. Only the user-facing MkDocs `docs/` site exists.

A `Stop` hook (`.claude/hooks/ai-tracking-reminder.sh`) nudges you to update tracking when work
changed but neither `.ai/` nor `.serena/memories/` was touched this session.
