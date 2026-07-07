# Task Completion Checklist

When finishing a coding task:

1. **Tests:** `pytest tests/ -v` — add/adjust tests for new behaviour; all must pass.
2. **Lint + format:** `pylint src/` (fix all warnings) and `black --check src/ tests/`.
3. **User docs — keep in sync:** if the change touches components, setup, interfaces,
   configuration, entry points, or architecture, update the **MkDocs `docs/`** pages
   (`index`, `getting-started`, `architecture`, `components`, `configuration`, `evaluation`)
   **and** `README.md` where run/architecture details changed. A stale doc is a bug.
   *(This repo is not a pip package — there is no `ai-docs/`/Context7 doc set to maintain.)*
4. **Update tracking:**
   - **serena memory** — update `mem:codebase_structure` (structure), `mem:system_patterns`
     (architecture), `mem:code_style_and_conventions` (style/tooling), `mem:integrations`, or
     `mem:suggested_commands` if the reference facts changed (via serena's `write_memory`).
   - **`mem:architectural_decisions`** — add an ADR (committed) for any non-obvious or systematic
     choice, with its context / decision / rationale / consequences.
   - **`.ai/PROGRESS.md`** — **always** append a dated entry summarizing what changed and why
     (local, not committed).

A `Stop` hook (`.claude/hooks/ai-tracking-reminder.sh`) reminds you if work changed but neither
`.ai/` nor `.serena/memories/` was updated. See `mem:ai_tracking_system` for how knowledge is split.
