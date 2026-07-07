# Tools & Skills (Claude Code)

Prefer these over ad-hoc approaches:

- **serena MCP** — semantic, LSP-backed code intelligence for Python. Use it to read/navigate and
  edit code by symbol: `get_symbols_overview`, `find_symbol`, `find_referencing_symbols`,
  `find_implementations`, `search_for_pattern`, and symbol-level edits
  (`replace_symbol_body`, `rename_symbol`, `insert_after_symbol`, `safe_delete_symbol`). Read
  reference knowledge via `list_memories` / `read_memory`; record it via `write_memory`.
- **context7 MCP** — up-to-date library docs. Call `resolve-library-id` then `query-docs` before
  using any unfamiliar or version-sensitive API (`numpy`, `sumolib`/`traci`, `matplotlib`,
  tooling). Do not code library calls from memory.
- **Claude Code skills** (ship by default, no install): use **code-review** / **simplify** on the
  working diff; a **verify**/**run** skill to exercise a scenario end-to-end before finishing;
  visualization skills before producing plots of model output.

Read-only serena/context7 tools are pre-approved in `.claude/settings.json`. See
`mem:suggested_commands` for pre-approved shell commands and `mem:ai_tracking_system` for the
knowledge-tracking workflow.
