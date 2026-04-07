# CONSTITUTION.md — Todo CLI

**Last updated:** 2026-04-07

## 1. Principles
1. **Minimal by default**: do not add features beyond add/list/done/rm unless explicitly requested.
2. **Local-first**: no network calls; everything works offline.
3. **Zero dependencies**: Python standard library only.
4. **Predictable CLI**: stable command names and flags; helpful error messages.
5. **Data safety**: never delete data without explicit user action (rm).

## 2. Non-Goals (Hard Constraints)
- No user accounts, auth, or multi-user support
- No sync, cloud storage, or remote APIs
- No TUI/interactive mode in MVP

## 3. CLI Contract
- Executable name: `todo` (install via `pipx` or `python -m todo_cli` is acceptable)
- Commands:
  - `add <text...>`
  - `list` with flags: `--all` and `--done`
  - `done <id>`
  - `rm <id>`
- Global flags:
  - `--db PATH` to override DB file location

## 4. Output Rules
- `list` prints a stable, script-friendly table-like output.
- IDs are always shown.
- Done tasks are clearly marked (e.g., `[x]`).

## 5. Error Handling Rules
- Non-zero exit code on invalid arguments or DB errors.
- Human-readable error messages to stderr.
- Never print Python tracebacks for expected errors (handle them).

## 6. Storage Rules
- Use SQLite with a single table in MVP.
- Auto-create the DB and schema if missing.
- Use parameterized queries only.

## 7. Testing Rules (MVP)
- Include at least a small unit test suite for DB operations.
- Tests should run against a temporary SQLite file.

## 8. Security & Privacy
- No PII collection.
- No telemetry.
- DB stays on disk under user control.
