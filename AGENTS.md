# AGENTS.md — FEDORA Platform Coding Agent Instructions

> **Compatibility:** This file is read automatically by OpenCode, OpenAI Codex, GitHub Copilot,
> Aider, and Claude Code. All agents operating on this repository MUST follow every rule here.

---

## Repository Overview

This repository implements the **FEDORA Platform** — a Python 3.13 research platform for
multimodal traffic management. It provides a reusable framework for traffic management pilots
with support for optimization, simulation, pilot systems, data storage, and communication.

**Primary language:** Python 3.13  
**Key dependencies:** numpy, sumolib, traci, cvxpy, pytest (see `requirements.txt`)

---

## Documentation Files — MANDATORY MAINTENANCE

The following files in `docs/` are the **single source of truth** for the repository's state.
Every agent **MUST** keep them up to date. Failure to do so is treated as an incomplete task.

| File                   | Purpose                                                  | Update trigger                           |
| ---------------------- | -------------------------------------------------------- | ---------------------------------------- |
| `docs/STRUCTURE.md`    | Annotated directory tree with module responsibilities    | Any file/folder added, moved, or removed |
| `docs/DECISIONS.md`    | Architectural Decision Records (ADRs)                    | Any non-trivial tech or design choice    |
| `docs/INTEGRATIONS.md` | External tools, simulators, and their config patterns    | When external dependency changes         |
| `docs/scratchpad.md`   | Per-session working memory (tasks, learnings, dead ends) | Continuously during every session        |

### Update Protocol (MANDATORY)

At the **end of every task**, before considering it complete, you MUST:

2. **`docs/STRUCTURE.md`** — Update the directory tree if any files or folders were added,
   removed, or had their responsibilities changed.
3. **`docs/DECISIONS.md`** — Add an ADR if a non-obvious architectural or algorithmic choice
   was made.
4. **`docs/scratchpad.md`** — Update task progress, mark completed sub-tasks, and record any
   learnings or dead ends encountered during the session.

> If you are unsure whether a change warrants a docs update, err on the side of updating.
> A one-line entry is always better than silence.

---

## Project Layout

```
fedora_platform/
├── src/
│   ├── __init__.py
│   ├── components.py          – Abstract FEDORA components and finite-state lifecycle
│   ├── communication.py       – Message bus and transport adapter templates
│   ├── storage.py             – Memory, JSON, and SQLite stores plus storage templates
│   ├── mtm_space.py           – Component container for one MTM Space
│   ├── priority_pass.py       – Vienna Priority Pass implementation
│   └── traffic_model_sumo/    – SUMO controller, recorder, and microscopic simulator code
│       └── tests/             – Co-located tests (test_*.py)
├── models/
│   ├── pilot_vienna/          – SUMO network, demand, route and phase files
│   ├── pilot_basque_country/
│   ├── pilot_nicosia/
│   ├── pilot_copenhagen/
│   ├── pilot_reggio_emilia/
│   └── pilot_budapest/
├── docs/                      – LLM-maintained documentation (see above)
│   ├── STRUCTURE.md
│   ├── DECISIONS.md
│   ├── INTEGRATIONS.md
│   └── scratchpad.md
├── figures/                   – Pilot images and repository banner
├── example/                   – Run scripts (e.g. run_priority_pass.py)
├── requirements.txt           – Pinned dependencies
├── .pylintrc                  – Pylint configuration
├── .gitignore
└── AGENTS.md                  – This file
```

- All source code lives under `src/`. Tests are co-located under `src/tests/`.
- Do **not** create new top-level directories without explicit instruction.
- Use relative imports within `src/`; use absolute imports across packages.
- After any structural change, update `docs/STRUCTURE.md` immediately.

---

## Hard Requirements

These rules apply to **every task** and must never be skipped.

### Python Virtual Environment

Always check for a virtual environment before running any Python command.

- If `venv/` exists at the project root, activate it first:
  ```bash
  source venv/bin/activate
  ```
- If no virtual environment exists and one is needed, create it with Python 3.13:
  ```bash
  python3.13 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```
- Never install packages globally. Always install into the active virtual environment.
- After installing new packages, update `requirements.txt` with pinned versions:
  ```bash
  pip freeze > requirements.txt
  ```

---

## Memory Bank — MANDATORY

All files in `memory-bank/` MUST be read at the start of every session and updated
at the end. They are the primary source of project context — treat them as your
persistent working memory across sessions.

- `projectbrief.md` — read-only unless scope changes
- `systemPatterns.md` — update when architecture changes
- `techContext.md` — update when dependencies or environment changes
- `activeContext.md` — update every session (current focus + recent changes)
- `progress.md` — update every session (what works, what's broken)

## Code Quality

- Follow existing code style and naming conventions exactly — do not diverge without instruction.
- Obey the lint rules in `.pylintrc`. Run `pylint src/` and fix all warnings before committing.
- Write docstrings for all public functions, classes, and modules.
- Add inline comments only when the _why_ is not obvious from the code.
- Keep functions small and single-purpose (target ≤ 30 lines).
- Avoid magic numbers and strings — use named constants.
- Validate inputs at all system boundaries (file I/O, CLI args, algorithm entry points).
- Prefer explicit over implicit; readable over clever.
- Use type annotations on all new function signatures.

---

## Testing

- Write tests for every non-trivial function, covering edge cases and numerical edge cases.
- Place tests in `src/tests/`, mirroring the module structure.
  - Example: tests for `src/partitions/foo.py` → `src/tests/test_partitions_foo.py`
- Run the full test suite before and after every change:
  ```bash
  pytest src/tests/ -v
  ```
- Do not consider a task complete until all tests pass.
- Use `pytest` — it is already pinned in `requirements.txt`.

---

## Security & Data Integrity

- Never hardcode absolute file paths — use `pathlib.Path` and relative paths.
- Never commit generated output files (plots, images, result CSVs) — add patterns to `.gitignore`.
- Sanitize all external inputs (file contents, CLI arguments) before passing them to algorithms.

---

## Communication & Reasoning

- Think step-by-step before writing code or making changes, especially for traffic management algorithms.
- If requirements are ambiguous, ask one focused clarifying question before proceeding.
- When proposing a non-obvious algorithmic approach, briefly explain the reasoning and complexity.
- If multiple valid approaches exist, list them with trade-offs (numerical stability, performance,
  correctness) before choosing.
- Flag potential risks explicitly — especially numerical precision issues, degenerate geometry
  cases, or `cvxpy` solver failures.
- At the end of each task, summarize what was changed and why.
- Do not hallucinate APIs for `cvxpy`, `numpy`, or `matplotlib` — verify method signatures before using.

---

## Scratchpad Format

When updating `docs/scratchpad.md`, use this structure for each session:

```markdown
## Task: <short description>

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

Do not delete previous entries between sessions — accumulate knowledge over time.