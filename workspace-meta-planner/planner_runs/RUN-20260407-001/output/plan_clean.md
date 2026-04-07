# PLAN.md — Todo CLI

**Version:** 1.0.0
**Date:** 2026-04-07
**Derived from:** MODULE_SPEC v1.0.0
**Constitution:** CONSTITUTION.md (2026-04-07)

---

## Overview

This plan breaks the Todo CLI implementation into six sequential phases. Each phase produces a concrete deliverable and ends with a validation gate that must pass before proceeding. Dependencies flow strictly forward — no phase references work from a later phase.

---

## Phase 1 — Project Scaffold & Entry Point

### Goal
Establish the repository structure, packaging metadata, and a runnable entry point that prints a usage message and exits with code 1 (no-command behaviour per §3.4).

### Deliverables
| # | File / Artefact | Description |
|---|---|---|
| 1.1 | `pyproject.toml` | Minimal packaging config; `[project.scripts] todo = "todo_cli.__main__:main"` |
| 1.2 | `todo_cli/__init__.py` | Empty package init |
| 1.3 | `todo_cli/__main__.py` | `main()` function: sets up top-level `argparse.ArgumentParser` with `--db` global flag (default `~/.todo.sqlite3`), registers empty subparsers for `add`, `list`, `done`, `rm`. Prints usage to stderr and exits 1 when no command is given. Prints `error: unknown command '<cmd>'` to stderr and exits 1 for unrecognised commands. |
| 1.4 | `todo_cli/cli.py` | Custom `ArgumentParser` subclass that overrides `error()` to always exit with code 1 (not argparse's default 2) and prints stable error messages to stderr. |
| 1.5 | `tests/__init__.py` | Empty test package init |

### Dependencies
None — this is the first phase.

### Validation Gate
- [ ] `python -m todo_cli` (no args) prints usage to stderr and exits 1.
- [ ] `python -m todo_cli foo` prints `error: unknown command 'foo'` to stderr and exits 1.
- [ ] `python -m todo_cli --db /tmp/test.db` (no subcommand) still prints usage to stderr and exits 1.
- [ ] No third-party imports anywhere in the tree — stdlib only.

---

## Phase 2 — Database Layer

### Goal
Implement the SQLite storage module: connection management, schema provisioning, WAL mode, and all CRUD query functions. This phase contains **no CLI wiring** — it is a pure library layer.

### Deliverables
| # | File / Artefact | Description |
|---|---|---|
| 2.1 | `todo_cli/db.py` | Module exposing the following functions, all accepting a `sqlite3.Connection` as first argument: |
|     |                  | `init_db(conn)` — executes `PRAGMA journal_mode=WAL` and `CREATE TABLE IF NOT EXISTS tasks (…)` per §4.3. |
|     |                  | `add_task(conn, text: str) -> tuple[int, str]` — inserts a new pending task with UTC `created_at`; commits; returns `(id, text)`. |
|     |                  | `list_tasks(conn, filter: str) -> list[tuple]` — `filter` is one of `"pending"`, `"done"`, `"all"`; returns rows `(id, text, done, created_at)` ordered by id ASC. |
|     |                  | `complete_task(conn, task_id: int) -> tuple[int, str]` — SELECTs the task (raises `TaskNotFoundError` if missing); if already done, returns without updating `done_at` (idempotent); otherwise sets `done=1, done_at=<utcnow>`; commits; returns `(id, text)`. |
|     |                  | `remove_task(conn, task_id: int) -> tuple[int, str]` — SELECTs the task (raises `TaskNotFoundError` if missing); DELETEs; commits; returns `(id, text)`. |
|     |                  | `open_connection(db_path: str) -> sqlite3.Connection` — expands user path, validates parent directory exists (raises `DBError` if not), opens connection, calls `init_db`, returns connection. |
| 2.2 | `todo_cli/errors.py` | Custom exception classes: `TaskNotFoundError(task_id)`, `DBError(message)`. Both inherit from a common `TodoError` base. |

### Dependencies
Phase 1 (package structure must exist).

### Validation Gate
- [ ] `open_connection("/tmp/test_todo.sqlite3")` creates the file and the `tasks` table with correct schema.
- [ ] `PRAGMA journal_mode` returns `wal` on the opened connection.
- [ ] All five CRUD functions can be called in sequence against a temp DB without error.
- [ ] All queries use `?` parameterized placeholders — verified by code review (no f-strings or `%` formatting in SQL).
- [ ] `complete_task` on a non-existent ID raises `TaskNotFoundError`.
- [ ] `remove_task` on a non-existent ID raises `TaskNotFoundError`.
- [ ] `complete_task` on an already-done task succeeds and does **not** overwrite `done_at`.
- [ ] `open_connection` with a non-existent parent directory raises `DBError`.

---

## Phase 3 — Command Handlers

### Goal
Wire each CLI subcommand to the database layer. Each command is a thin function that parses its validated args, calls `db.py`, formats output, and handles errors with correct exit codes.

### Deliverables
| # | File / Artefact | Description |
|---|---|---|
| 3.1 | `todo_cli/commands.py` | Module with four handler functions, each accepting the parsed `argparse.Namespace`: |
|     |                        | `cmd_add(args)` — validates non-empty text (exit 1); calls `add_task`; prints `Added task <id>: <text>` to stdout; exits 0. |
|     |                        | `cmd_list(args)` — checks mutual exclusivity of `--all`/`--done` (exit 1); calls `list_tasks`; formats and prints the table per §3.3 output format (header always printed, rows only when present); exits 0. |
|     |                        | `cmd_done(args)` — validates integer ID (exit 1); calls `complete_task`; prints `Completed task <id>: <text>`; exits 0. Catches `TaskNotFoundError` → exit 1. |
|     |                        | `cmd_rm(args)` — validates integer ID (exit 1); calls `remove_task`; prints `Removed task <id>: <text>`; exits 0. Catches `TaskNotFoundError` → exit 1. |
| 3.2 | `todo_cli/__main__.py` | **Updated**: each subparser's `set_defaults(func=…)` now points to the corresponding handler in `commands.py`. Top-level `main()` opens the DB connection via `open_connection(args.db)`, wraps execution in try/except to catch `DBError` → stderr message + exit 2, and ensures `connection.close()` in a `finally` block. |

### Dependencies
Phase 1 (CLI scaffold), Phase 2 (database layer).

### Validation Gate
- [ ] `todo add Buy milk` → stdout `Added task 1: Buy milk`, exit 0, row exists in DB.
- [ ] `todo add "  "` → stderr `error: task text cannot be empty`, exit 1.
- [ ] `todo list` → prints header + pending tasks only, exit 0.
- [ ] `todo list --all --done` → stderr `error: --all and --done are mutually exclusive`, exit 1.
- [ ] `todo done 1` → stdout `Completed task 1: Buy milk`, exit 0, `done=1` in DB.
- [ ] `todo done 999` → stderr `error: task 999 not found`, exit 1.
- [ ] `todo done abc` → stderr `error: id must be an integer`, exit 1.
- [ ] `todo rm 1` → stdout `Removed task 1: Buy milk`, exit 0, row deleted from DB.
- [ ] `todo rm 999` → stderr `error: task 999 not found`, exit 1.
- [ ] All DB errors surface as exit 2 with human-readable message to stderr.
- [ ] No Python tracebacks appear for any expected error scenario.

---

## Phase 4 — Output Formatting

### Goal
Ensure the `list` command output matches the exact table format specified in §3.3: left-aligned columns, two-space minimum separation, correct status markers, and timestamp formatting.

### Deliverables
| # | File / Artefact | Description |
|---|---|---|
| 4.1 | `todo_cli/formatting.py` | `format_task_table(rows: list[tuple]) -> str` — accepts rows from `list_tasks`, returns the fully formatted table string. Computes per-column widths dynamically. Status renders as `[ ]` or `[x]`. Timestamps render as `YYYY-MM-DD HH:MM:SS` (space-separated, truncated to seconds). Always includes the header line `ID  Status  Created              Text`. |
| 4.2 | `todo_cli/commands.py` | **Updated**: `cmd_list` delegates formatting to `format_task_table`. |

### Dependencies
Phase 3 (command handlers must exist to integrate formatted output).

### Validation Gate
- [ ] `format_task_table([])` returns only the header line.
- [ ] A table with mixed pending/done tasks aligns columns correctly with ≥ 2 spaces between each column.
- [ ] Status column shows `[ ]` for `done=0` and `[x]` for `done=1`.
- [ ] Timestamps display as `YYYY-MM-DD HH:MM:SS` (space, not `T`).
- [ ] IDs of varying digit-lengths (1, 10, 100) produce correct alignment.
- [ ] End-to-end: `todo list --all` against a seeded DB matches the spec's example format.

---

## Phase 5 — Unit & Integration Tests

### Goal
Deliver a test suite that validates all DB operations and CLI behaviours against a temporary SQLite database. Tests must run with `python -m pytest` (or `python -m unittest`) using only the standard library (plus pytest if desired as the sole dev dependency).

### Deliverables
| # | File / Artefact | Description |
|---|---|---|
| 5.1 | `tests/test_db.py` | Unit tests for every function in `db.py`: |
|     |                    | • `test_init_db_creates_table` — verifies table existence and schema columns. |
|     |                    | • `test_add_task_returns_id_and_text` |
|     |                    | • `test_add_task_empty_text_rejected` (validation happens in command layer; here confirm DB stores non-empty text correctly) |
|     |                    | • `test_list_tasks_pending_only` / `_done_only` / `_all` |
|     |                    | • `test_complete_task_success` — verifies `done=1` and `done_at` is set. |
|     |                    | • `test_complete_task_idempotent` — second call does not change `done_at`. |
|     |                    | • `test_complete_task_not_found` — raises `TaskNotFoundError`. |
|     |                    | • `test_remove_task_success` — row no longer in DB. |
|     |                    | • `test_remove_task_not_found` — raises `TaskNotFoundError`. |
|     |                    | • `test_open_connection_bad_directory` — raises `DBError`. |
| 5.2 | `tests/test_formatting.py` | Unit tests for `format_task_table`: empty rows, single row, mixed statuses, column alignment, timestamp format. |
| 5.3 | `tests/test_cli.py` | Integration tests that invoke `main()` (or `subprocess.run(["python", "-m", "todo_cli", ...])`) against a temp DB (`--db` flag pointing to `tempfile`): |
|     |                    | • No-command → exit 1, usage on stderr. |
|     |                    | • Unknown command → exit 1, error on stderr. |
|     |                    | • Full add → list → done → list --done → rm cycle. |
|     |                    | • Validation errors for each command (empty text, non-integer id, missing id). |
|     |                    | • Mutually exclusive `--all --done` → exit 1. |

All tests use `tempfile.mkdtemp()` or `tempfile.NamedTemporaryFile` for DB paths and clean up after themselves.

### Dependencies
Phase 4 (all production code must be complete).

### Validation Gate
- [ ] `python -m pytest tests/ -v` (or `python -m unittest discover tests`) passes with 0 failures.
- [ ] Minimum 15 test cases across the three files.
- [ ] No test relies on a pre-existing DB file or mutates the user's home directory.
- [ ] Tests confirm exit codes (0, 1, 2) for each documented scenario.
- [ ] Tests confirm stderr vs stdout routing for error messages.

---

## Phase 6 — Packaging & Documentation

### Goal
Finalize packaging so the application installs cleanly via `pip install .` or `pipx install .`, and provide minimal user-facing documentation.

### Deliverables
| # | File / Artefact | Description |
|---|---|---|
| 6.1 | `pyproject.toml` | **Finalized**: includes `[project]` metadata (name, version `1.0.0`, description, python_requires `>=3.9`, license), `[project.scripts]` entry point, and optional `[project.optional-dependencies] dev = ["pytest"]`. |
| 6.2 | `README.md` | Sections: one-line description, installation (`pip install .` / `pipx`), usage examples for all four commands, `--db` flag, and a note on data location (`~/.todo.sqlite3`). |
| 6.3 | `LICENSE` | MIT license file (or as specified by project owner). |

### Dependencies
Phase 5 (tests must pass before declaring the package ready).

### Validation Gate
- [ ] `pip install .` in a fresh virtual environment succeeds with no network calls beyond pip itself.
- [ ] `todo add "test"` works after install (entry point resolves correctly).
- [ ] `python -m todo_cli add "test"` also works after install.
- [ ] `README.md` examples are copy-pasteable and produce the documented output.
- [ ] No files outside the specified deliverables are required for a working install.
- [ ] Zero third-party runtime dependencies confirmed in installed metadata.

---

## Dependency Graph

```
Phase 1 ─► Phase 2 ─► Phase 3 ─► Phase 4 ─► Phase 5 ─► Phase 6
Scaffold    DB Layer   Commands   Formatting   Tests      Packaging
```

All phases are strictly sequential. No phase may begin until the preceding phase's validation gate is fully satisfied.
