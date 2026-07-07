# Code Style & Conventions

- **Python 3.13** is the required/dev version (`python3.13 -m venv venv`). Packaging metadata in
  `pyproject.toml` uses a `src/`-discovered layout (`setuptools`); import name unchanged.
- **Type hints** on all function signatures.
- **Docstrings** on every public function, class, and module — concise (purpose, args, returns).
- **Comments** explain the *why*, not the *what*, and only where non-obvious.
- **Formatting:** `black`. **Lint:** `pylint src/` — fix all warnings before finishing. (No custom
  `.pylintrc`/pylint config in the repo currently; run `black` + `pylint` with defaults.)
- **Structure conventions:** one class per file in `src/`; keep functions small and
  single-purpose; avoid magic numbers/strings (named constants); prefer explicit over clever.
- **FSM discipline:** every `src/` component uses explicit state constants + transition maps
  (see `mem:system_patterns`). Do not add hidden state outside the FSM.
- **Paths:** never hardcode absolute paths — use `pathlib.Path`, relative to the project root.
- **Security / boundaries:** validate and sanitize all external inputs (JSON config, file
  contents, CLI args) before passing them to algorithms.
- **Naming:** files `snake_case`, classes `PascalCase`; follow existing conventions exactly.
- **Do not commit generated output** (plots, result JSON/CSV, run logs) — `logs/` and `results/`
  are git-ignored.

Runtime deps (`requirements.txt`, pinned): `numpy`, `sumolib==1.19.0`, `traci==1.19.0`,
`matplotlib`; dev/tooling: `pytest`, `pylint`, `black`.
