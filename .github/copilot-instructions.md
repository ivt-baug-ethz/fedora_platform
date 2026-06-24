# Copilot Repository Instructions

## Repository Overview

TODO - needs to be created

## Hard Requirements

These rules apply to **every task** and must never be skipped.

### Scratchpad

Always maintain a `scratchpad.md` file at the **root of the repository**. Update it at the start of every task and continuously throughout. Do not delete it between sessions — accumulate knowledge over time. However, when the file becomes too long, please also remove outdated tasks, outdated information and compress its content to the necessary.

ESSENTIAL: Before returning and completing a task, ensure that all completed tasks in the scratchpad are marked as done, and that the learnings, decisions, dead ends, and open questions are up to date. This is critical for maintaining continuity and knowledge transfer across sessions.

Record the following in `scratchpad.md`:

- **Task**: Current task description with sub-tasks as checkboxes. Update progress as you go and mark them as completed when done.
- **Learnings**: Discoveries, surprising behavior, gotchas (with date)
- **Decisions**: Choices made and the rationale behind them
- **Dead Ends**: Approaches tried and why they were abandoned
- **Open Questions**: Unresolved items or follow-ups
- **Commands**: Useful one-liners, debug snippets, and environment notes

Use this structure:

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

### Python Virtual Environment

Always check for a virtual environment before running any Python command.

- If `venv/` exists at the project root, activate it first:
  ```bash
  source venv/bin/activate
  ```
- If no virtual environment exists and one is needed, create it with Python 3.13:
  ```bash
  python3.13 -m venv venv    # or: python3 -m venv venv if 3.13 is the default
  source venv/bin/activate
  pip install -r requirements.txt
  ```
- Never install packages globally. Always install into the active virtual environment.
- After installing new packages, update `requirements.txt` with pinned versions:
  ```bash
  pip freeze > requirements.txt
  ```

---

## Code Quality

- Follow the existing code style and naming conventions exactly — do not diverge without instruction.
- Obey the lint rules in `.pylintrc`. Run `pylint src/` and fix all warnings before committing.
- Write docstrings for all public functions, classes, and modules.
- Add inline comments only when the _why_ is not obvious from the code.
- Keep functions small and single-purpose (target ≤ 30 lines).
- Avoid magic numbers and strings — use named constants.
- Validate inputs at all system boundaries (file I/O, CLI args, algorithm entry points).
- Prefer explicit over implicit; readable over clever.
- Use type annotations on all new function signatures.

## Testing

- Write tests for every non-trivial function, covering edge cases and numerical edge cases (empty regions, degenerate geometry, zero-area cells).
- Place tests in `src/tests/`, mirroring the module structure (e.g., tests for `src/partitions/foo.py` go in `src/tests/test_partitions_foo.py`).
- Run the full test suite before and after every change: `pytest src/tests/ -v`
- Do not consider a task complete until all tests pass.
- Use `pytest` — it is already pinned in `requirements.txt`.

## Security & Data Integrity

- Never hardcode file paths as absolute paths — use `pathlib.Path` and relative paths.
- Never commit generated output files (plots, images, result CSVs) — add patterns to `.gitignore`.
- Sanitize all external inputs (file contents, CLI arguments) before passing them to algorithms.

## Communication & Reasoning

- Think step-by-step before writing code or making changes, especially for geometric/numerical algorithms.
- If requirements are ambiguous, ask one focused clarifying question before proceeding.
- When proposing a non-obvious algorithmic approach, briefly explain the reasoning and complexity.
- If multiple valid approaches exist, list them with trade-offs (numerical stability, performance, correctness) before choosing.
- Flag potential risks explicitly — especially numerical precision issues, degenerate geometry cases, or `cvxpy` solver failures.
- At the end of each task, summarize what was changed and why.
- Do not hallucinate APIs for `cvxpy`, `polytope`, `numpy`, or `matplotlib` — verify method signatures before using.
