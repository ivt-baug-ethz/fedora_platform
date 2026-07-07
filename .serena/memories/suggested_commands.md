# Suggested Commands

Dev environment: macOS (darwin), zsh. Required interpreter: **Python 3.13**.

## Setup (always activate the venv first)
```bash
source venv/bin/activate
# create it if missing:
python3.13 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

## Test / lint / format
```bash
pytest tests/ -v          # full test suite (root-level tests/)
pylint src/               # lint — fix all warnings
black src/ tests/         # format;  black --check src/ tests/  in CI
```
If `pytest` aborts before collecting (global Anaconda plugin autoload), prefix with
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. Other failure modes: see `mem:integrations`.

## Run scenarios (SUMO must be installed; SUMO_HOME set)
```bash
python run.py                                                    # default: demo priority-pass
python run.py configurations/demo_sumo_fixed_cycle_config.json  # any config
python run.py configurations/demo_sumo_baseline_config.json     # baseline (SUMO default plans)
python run.py CONFIG_FILE --skip-evaluation                     # skip the post-run Evaluator
python run.py --help
```
Config naming: `{scenario}_sumo_{controller}_config.json` (demo|vienna × baseline|fixed_cycle|
max_pressure|priority_pass). Run logs → `logs/{scenario}_{controller}/`; evaluation output →
`results/{scenario}/{controller}/`.

## Post-processing (manual; auto-run for Priority Pass configs)
```bash
python src/post_processing/priority_pass_analysis.py CONFIG_FILE
python src/post_processing/vehicle_count_comparison.py CONFIG_FILE [CONFIG_FILE ...]
```

## Docs (user-facing MkDocs Material → GitHub Pages)
```bash
mkdocs serve         # live preview
mkdocs build         # build the static site (CI builds/deploys via docs.yml)
```

## CI gates (`.github/workflows/`)
`python_testing.yml` (pytest), `lint.yml` (pylint), `format_check.yml` (black --check),
`docs.yml` (MkDocs), `sumo_scenarios.yml` (end-to-end pipeline simulation).

Read-only serena/context7 tools and the pytest/pylint/black commands are pre-approved in
`.claude/settings.json`, so they run without permission prompts. `git worktree` and
`EnterWorktree` are denied — edit in place on the checked-out branch.
