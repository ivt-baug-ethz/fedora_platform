# CLAUDE.md — FEDORA Platform Coding Guidelines

This file provides quick reference guidance for working on the FEDORA Platform. For comprehensive
agent instructions, code quality requirements, and architectural decisions, always refer to **AGENTS.md**.
You NEVER need to commit your changes, this will be done manually by the project maintainer. You are only
responsible for following the rules and updating the documentation.

## Quick Reference

**Read these first:**

- `AGENTS.md` — Complete agent instructions (mandatory for all work)
- `memory-bank/` — Persistent context about the project state and decisions
- `.agent-docs/STRUCTURE.md` — Current directory structure and module responsibilities
- `.agent-docs/DECISIONS.md` — Architectural Decision Records (ADRs)

## Essential Rules

1. **Always activate the virtual environment:**

   ```bash
   source venv/bin/activate
   ```

   If it doesn't exist: `python3.13 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`

2. **Update documentation on every task:**
   - `README.md` — If code behavior, entry points, or scenario configs change (keep in sync!)
   - `.agent-docs/STRUCTURE.md` — After adding/moving/removing files or folders
   - `.agent-docs/DECISIONS.md` — After any non-trivial architectural choice
   - `.agent-docs/scratchpad.md` — Session progress and learnings (mandatory)
   - `docs/` — User-facing MkDocs pages (deployed to GitHub Pages); update when components, setup, interfaces, or architecture change

3. **Update memory-bank at session end:**
   - `memory-bank/activeContext.md` — Current focus and recent changes
   - `memory-bank/progress.md` — What works, what's broken
   - `memory-bank/systemPatterns.md` — When architecture changes

4. **Run tests before committing:**

   ```bash
   pytest tests/ -v
   ```

   All tests must pass.

5. **Follow the code style:**
   - Type annotations on all function signatures
   - Docstrings for public functions, classes, and modules
   - Inline comments only for the _why_, not the _what_
   - Follow existing naming conventions exactly
   - Run `pylint src/` and fix all warnings

## Project Structure

```
fedora_platform/
├── src/                    – Core application components
│   ├── environment_sumo.py – SUMO environment FSM (type: "sumo_simulation")
│   ├── orchestrator.py     – TCP message router and sole orchestrator
│   ├── recorder.py         – Communication logger
│   └── controller_*.py     – Fixed-cycle, Max-pressure, Priority Pass controllers
├── run.py                  – Entry point for scenarios
├── tests/                  – Test suite (root level)
├── configurations/         – JSON configuration files
├── scenarios/              – Scenario-specific SUMO files and metadata
│   ├── demo/sumo/          – Demo scenario SUMO files
│   ├── pilot_vienna/       – Vienna pilot scenario
│   └── pilot_*/            – Other pilot scenarios
├── logs/                   – Generated output logs
├── .agent-docs/            – LLM-maintained documentation
│   ├── STRUCTURE.md        – Directory tree and responsibilities
│   ├── DECISIONS.md        – Architectural Decision Records
│   ├── INTEGRATIONS.md     – External tools and integrations
│   └── scratchpad.md       – Per-session working memory
├── docs/                   – User-facing MkDocs documentation (GitHub Pages)
├── memory-bank/            – Persistent project context
├── requirements.txt        – Pinned dependencies
├── AGENTS.md               – Complete agent instructions
└── CLAUDE.md               – This file
```

## Common Tasks

### Add New Code

1. Create/modify files as needed
2. Add type annotations and docstrings
3. Update `.agent-docs/STRUCTURE.md` if adding new files/directories
4. Run `pytest tests/ -v` to verify

### Fix a Bug

1. Write a test that reproduces the bug
2. Fix the bug
3. Verify all tests pass
4. Update `.agent-docs/DECISIONS.md` if the fix involved non-obvious reasoning
5. Update `.agent-docs/scratchpad.md` with what you learned

### Refactor Code

1. Plan the refactor (use AGENTS.md for architectural guidance)
2. Preserve all existing behavior
3. Update `.agent-docs/STRUCTURE.md` if module responsibilities change
4. Run full test suite
5. Update `.agent-docs/DECISIONS.md` with the rationale

## Key Technologies

- **Python 3.13** — Required version
- **SUMO 1.19.0** — Traffic simulator (via `sumolib` and `traci`)
- **pytest 8.4.2** — Testing framework
- **cvxpy** — Optimization library (for planning algorithms)
- **JSON** — Configuration and scenario files
- **TCP/JSON** — Inter-component communication (localhost)

## Contact & Help

For issues with Claude Code itself, see `/help` or report at:
https://github.com/anthropics/claude-code/issues

For project-specific questions, refer to AGENTS.md or check the memory-bank context.

---

**Everything below this line is reference. For the authoritative source, see AGENTS.md.**

### From AGENTS.md: Hard Requirements

- **Virtual environment** — Always required. Create with `python3.13 -m venv venv`
- **Type annotations** — All function signatures must have type hints
- **Docstrings** — Required for all public functions, classes, and modules
- **Code quality** — Run `pylint src/` before committing, all warnings must be fixed
- **Testing** — Write tests for every non-trivial function; run `pytest src/tests/ -v` before committing
- **Documentation** — Keep `.agent-docs/STRUCTURE.md`, `.agent-docs/DECISIONS.md`, `.agent-docs/scratchpad.md`, and the `docs/` MkDocs pages up to date at task end
- **No absolute paths** — Always use `pathlib.Path` and relative paths
- **Security** — Sanitize all external inputs before passing to algorithms

### From AGENTS.md: Memory Bank Files

All files in `memory-bank/` MUST be read at the start of every session and updated at the end:

- `projectbrief.md` — Read-only (project scope and goals)
- `systemPatterns.md` — Update when architecture changes
- `techContext.md` — Update when dependencies or environment changes
- `activeContext.md` — Update every session (focus + recent changes)
- `progress.md` — Update every session (what works + what's broken)

### From AGENTS.md: Scratchpad Format

When updating `.agent-docs/scratchpad.md`, document each session with:

```markdown
## Task: <description>

### Plan

- [ ] Step 1
- [ ] Step 2

### Learnings

- YYYY-MM-DD: <learning>

### Decisions

- <decision>: <rationale>

### Dead Ends

- <approach>: <why it failed>

### Open Questions

- <question>
```

Do not delete previous entries — accumulate knowledge over time.
