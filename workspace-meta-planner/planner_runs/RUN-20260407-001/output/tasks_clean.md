# TASKS.md — Todo CLI

**Version:** 1.0.0
**Date:** 2026-04-07
**Derived from:** PLAN.md v1.0.0, MODULE_SPEC v1.0.0

---

## TASK-001: Create pyproject.toml with packaging metadata

| Field | Detail |
|---|---|
| **Objective** | Create the `pyproject.toml` file with minimal packaging configuration, including the console script entry point `todo = "todo_cli.__main__:main"`. No third-party dependencies. |
| **Inputs** | PLAN §Phase 1, deliverable 1.1; SPEC §3.1 (executable invocation as `todo` and `python -m todo_cli`) |
| **Outputs** | A valid `pyproject.toml` at the repository root with `[project]` metadata, `[project.scripts]` entry point, and Python version requirement. |
| **Files touched** | `pyproject.toml` (create) |
| **Done when** | `pyproject.toml` parses without error (e.g., `python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"`), declares `todo` script entry point, and lists zero third-party dependencies. |
| **depends_on** | — |
| **if_blocked** | MINOR — skip and create a minimal stub; other tasks only need the package directory to exist. |
| **Estimated** | 5 min |

---

## TASK-002: Create package init and test package init

| Field | Detail |
|---|---|
| **Objective** | Create the `todo_cli/` package directory with an empty `__init__.py` and the `tests/` directory with an empty `__init__.py`, establishing the importable package structure. |
| **Inputs** | PLAN §Phase 1, deliverables 1.2 and 1.5 |
| **Outputs** | Two empty `__init__.py` files in the correct directories. |
| **Files touched** | `todo_cli/__init__.py` (create), `tests/__init__.py` (create) |
| **Done when** | `python -c "import todo_cli"` succeeds without error and both files exist on disk. |
| **depends_on** | TASK-001 |
| **if_blocked** | MINOR — create directories and files manually; no logic involved. |
| **Estimated** | 3 min |

---

## TASK-003: Implement custom ArgumentParser subclass in cli.py

| Field | Detail |
|---|---|
| **Objective** | Create `todo_cli/cli.py` with a custom `ArgumentParser` subclass that overrides the `error()` method to always exit with code 1 (instead of argparse's default 2) and prints stable error messages to stderr. |
| **Inputs** | PLAN §Phase 1, deliverable 1.4; SPEC §3.3 (exit code 1 for validation errors across all commands); SPEC §3.4 (no-command and unknown-command behaviour) |
| **Outputs** | `todo_cli/cli.py` containing a `TodoArgumentParser` class inheriting from `argparse.ArgumentParser` with overridden `error()` method that writes to stderr and calls `sys.exit(1)`. |
| **Files touched** | `todo_cli/cli.py` (create) |
| **Done when** | Instantiating `TodoArgumentParser` and triggering a parse error (e.g., unrecognized argument) results in exit code 1, not 2. Verified by unit test or manual invocation. |
| **depends_on** | TASK-002 |
| **if_blocked** | MINOR — can use standard `ArgumentParser` temporarily and patch exit codes in handlers. |
| **Estimated** | 10 min |

---

## TASK-004: Implement __main__.py entry point with argparse skeleton

| Field | Detail |
|---|---|
| **Objective** | Create `todo_cli/__main__.py` with a `main()` function that sets up the top-level argument parser using the custom `TodoArgumentParser` from `cli.py`, registers the `--db` global flag (default `~/.todo.sqlite3`), registers empty subparsers for `add`, `list`, `done`, and `rm`, prints usage to stderr and exits 1 when no command is given, and prints `error: unknown command '<cmd>'` to stderr and exits 1 for unrecognised commands. |
| **Inputs** | PLAN §Phase 1, deliverable 1.3; SPEC §3.2 (`--db` flag details); SPEC §3.4 (no-command and unknown-command behaviour) |
| **Outputs** | `todo_cli/__main__.py` with fully functional `main()` that handles no-command and unknown-command cases with correct exit codes and stderr messages. |
| **Files touched** | `todo_cli/__main__.py` (create) |
| **Done when** | (1) `python -m todo_cli` prints usage to stderr and exits 1. (2) `python -m todo_cli foo` prints `error: unknown command 'foo'` to stderr and exits 1. (3) `python -m todo_cli --db /tmp/test.db` with no subcommand prints usage to stderr and exits 1. (4) No third-party imports. |
| **depends_on** | TASK-003 |
| **if_blocked** | MODERATE — this is the application entry point; cannot proceed to command wiring without it. Use standard argparse as fallback for TASK-003 block. |
| **Estimated** | 20 min |

---

## TASK-005: Write tests for Phase 1 entry point behaviour

| Field | Detail |
|---|---|
| **Objective** | Write unit tests validating all Phase 1 validation gate criteria: no-args exits 1 with usage on stderr, unknown command exits 1 with error message, `--db` flag with no subcommand exits 1, and no third-party imports in the source tree. |
| **Inputs** | PLAN §Phase 1 Validation Gate (all four checkboxes); SPEC §3.4 |
| **Outputs** | Test file with at least four test functions covering each gate criterion using `subprocess.run` or equivalent to capture exit codes and stderr. |
| **Files touched** | `tests/test_cli_entry.py` (create) |
| **Done when** | All tests pass via `python -m pytest tests/test_cli_entry.py` and cover all four Phase 1 validation gate items. |
| **depends_on** | TASK-004 |
| **if_blocked** | MINOR — tests can be written speculatively and run once TASK-004 completes. |
| **Estimated** | 15 min |

---

## TASK-006: Create custom exception classes in errors.py

| Field | Detail |
|---|---|
| **Objective** | Create `todo_cli/errors.py` with a `TodoError` base exception, `TaskNotFoundError(task_id)` that stores the task ID and produces a meaningful `str()`, and `DBError(message)` for database-level errors. Both inherit from `TodoError`. |
| **Inputs** | PLAN §Phase 2, deliverable 2.2; SPEC §3.3 (error messages referencing task IDs: `error: task <id> not found`) |
| **Outputs** | `todo_cli/errors.py` with three exception classes: `TodoError`, `TaskNotFoundError`, `DBError`. |
| **Files touched** | `todo_cli/errors.py` (create) |
| **Done when** | (1) `TaskNotFoundError(42)` can be raised and caught; `str()` contains the ID. (2) `DBError("msg")` can be raised and caught. (3) Both are instances of `TodoError`. Verified by import and instantiation test. |
| **depends_on** | TASK-002 |
| **if_blocked** | MINOR — simple Python file with no external dependencies. |
| **Estimated** | 5 min |

---

## TASK-007: Implement open_connection and init_db in db.py

| Field | Detail |
|---|---|
| **Objective** | Create `todo_cli/db.py` with `open_connection(db_path: str) -> sqlite3.Connection` that expands the user path, validates the parent directory exists (raises `DBError` if not), opens a SQLite connection, calls `init_db(conn)`, and returns the connection. `init_db(conn)` executes `PRAGMA journal_mode=WAL` and `CREATE TABLE IF NOT EXISTS tasks` with the schema from SPEC §4.3 (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, done_at TEXT). |
| **Inputs** | PLAN §Phase 2, deliverable 2.1 (open_connection, init_db); SPEC §4.1 (SQLite, WAL mode); SPEC §4.3 (table schema) |
| **Outputs** | `todo_cli/db.py` with `open_connection` and `init_db` functions. |
| **Files touched** | `todo_cli/db.py` (create) |
| **Done when** | (1) `open_connection("/tmp/test_todo.sqlite3")` creates the file and the `tasks` table with correct columns. (2) `PRAGMA journal_mode` returns `wal`. (3) Non-existent parent directory raises `DBError`. |
| **depends_on** | TASK-006 |
| **if_blocked** | CRITICAL — all CRUD functions and command handlers depend on this. Escalate immediately. |
| **Estimated** | 15 min |

---

## TASK-008: Implement add_task function in db.py

| Field | Detail |
|---|---|
| **Objective** | Add the `add_task(conn, text: str) -> tuple[int, str]` function to `db.py`. It inserts a new row with `done=0`, `created_at` set to current UTC timestamp (ISO format truncated to seconds), commits the transaction, and returns `(lastrowid, text)`. Must use parameterized `?` placeholders — no string formatting in SQL. |
| **Inputs** | PLAN §Phase 2, deliverable 2.1 (add_task); SPEC §3.3 `todo add` (task creation semantics); SPEC §4.3 (column types and defaults) |
| **Outputs** | `add_task` function appended to `todo_cli/db.py`. |
| **Files touched** | `todo_cli/db.py` (modify) |
| **Done when** | Calling `add_task(conn, "Buy milk")` on a fresh DB returns `(1, "Buy milk")` and the row exists in the `tasks` table with `done=0` and a valid `created_at` timestamp. |
| **depends_on** | TASK-007 |
| **if_blocked** | CRITICAL — command handler for `add` depends on this. Escalate immediately. |
| **Estimated** | 10 min |

---

## TASK-009: Implement list_tasks function in db.py

| Field | Detail |
|---|---|
| **Objective** | Add the `list_tasks(conn, filter: str) -> list[tuple]` function to `db.py`. The `filter` parameter accepts `"pending"`, `"done"`, or `"all"`. Returns rows as `(id, text, done, created_at)` ordered by `id ASC`. Uses parameterized queries where applicable. |
| **Inputs** | PLAN §Phase 2, deliverable 2.1 (list_tasks); SPEC §3.3 `todo list` (filter semantics: pending=done 0, done=done 1, all=no filter) |
| **Outputs** | `list_tasks` function appended to `todo_cli/db.py`. |
| **Files touched** | `todo_cli/db.py` (modify) |
| **Done when** | (1) With mixed pending/done tasks, `list_tasks(conn, "pending")` returns only `done=0` rows. (2) `list_tasks(conn, "done")` returns only `done=1` rows. (3) `list_tasks(conn, "all")` returns all rows. (4) Results are ordered by `id ASC`. |
| **depends_on** | TASK-007 |
| **if_blocked** | CRITICAL — command handler for `list` depends on this. Escalate immediately. |
| **Estimated** | 10 min |

---

## TASK-010: Implement complete_task function in db.py

| Field | Detail |
|---|---|
| **Objective** | Add the `complete_task(conn, task_id: int) -> tuple[int, str]` function to `db.py`. It SELECTs the task by ID (raises `TaskNotFoundError` if missing). If the task is already done (`done=1`), it returns `(id, text)` without modifying `done_at` (idempotent). Otherwise, it sets `done=1` and `done_at` to current UTC timestamp, commits, and returns `(id, text)`. Uses parameterized queries. |
| **Inputs** | PLAN §Phase 2, deliverable 2.1 (complete_task); SPEC §3.3 `todo done` (idempotent behaviour, error on not found) |
| **Outputs** | `complete_task` function appended to `todo_cli/db.py`. |
| **Files touched** | `todo_cli/db.py` (modify) |
| **Done when** | (1) Non-existent ID raises `TaskNotFoundError`. (2) Pending task is marked done with `done_at` set. (3) Already-done task returns successfully without changing `done_at`. |
| **depends_on** | TASK-007, TASK-008 |
| **if_blocked** | CRITICAL — command handler for `done` depends on this. Escalate immediately. |
| **Estimated** | 15 min |

---

## TASK-011: Implement remove_task function in db.py

| Field | Detail |
|---|---|
| **Objective** | Add the `remove_task(conn, task_id: int) -> tuple[int, str]` function to `db.py`. It SELECTs the task by ID (raises `TaskNotFoundError` if missing), DELETEs the row, commits, and returns `(id, text)`. Uses parameterized queries. |
| **Inputs** | PLAN §Phase 2, deliverable 2.1 (remove_task); SPEC §3.3 `todo rm` (error on not found, success output) |
| **Outputs** | `remove_task` function appended to `todo_cli/db.py`. |
| **Files touched** | `todo_cli/db.py` (modify) |
| **Done when** | (1) Non-existent ID raises `TaskNotFoundError`. (2) Existing task is deleted and returned as `(id, text)`. (3) Row no longer exists in the table after deletion. |
| **depends_on** | TASK-007, TASK-008 |
| **if_blocked** | CRITICAL — command handler for `rm` depends on this. Escalate immediately. |
| **Estimated** | 10 min |

---

## TASK-012: Write tests for database layer (Phase 2)

| Field | Detail |
|---|---|
| **Objective** | Write comprehensive unit tests for all functions in `db.py` covering every Phase 2 validation gate criterion: schema creation, WAL mode, CRUD sequence, parameterized queries (code review assertion), `TaskNotFoundError` on invalid IDs, idempotent complete, and `DBError` on bad parent directory. |
| **Inputs** | PLAN §Phase 2 Validation Gate (all eight checkboxes); SPEC §4.3 (schema); all db.py functions from TASK-007 through TASK-011 |
| **Outputs** | Test file covering all db.py functions with at least one test per validation gate item. Tests use temporary in-memory or temp-file SQLite databases. |
| **Files touched** | `tests/test_db.py` (create) |
| **Done when** | All tests pass via `python -m pytest tests/test_db.py` and cover all eight Phase 2 validation gate items. |
| **depends_on** | TASK-008, TASK-009, TASK-010, TASK-011 |
| **if_blocked** | MINOR — tests can be written speculatively against the function signatures. |
| **Estimated** | 25 min |

---

## TASK-013: Implement cmd_add handler in commands.py

| Field | Detail |
|---|---|
| **Objective** | Create `todo_cli/commands.py` with the `cmd_add(args)` handler function. It validates that the task text (joined positional arguments) is non-empty after stripping whitespace (exit 1, `error: task text cannot be empty` to stderr). On success, calls `db.add_task`, prints `Added task <id>: <text>` to stdout, and exits 0. |
| **Inputs** | PLAN §Phase 3, deliverable 3.1 (cmd_add); SPEC §3.3 `todo add` (validation, output format, exit codes) |
| **Outputs** | `todo_cli/commands.py` with `cmd_add` function. |
| **Files touched** | `todo_cli/commands.py` (create) |
| **Done when** | (1) Empty text input produces `error: task text cannot be empty` on stderr and exit 1. (2) Valid text calls `add_task` and prints correct stdout message. |
| **depends_on** | TASK-008 |
| **if_blocked** | MODERATE — can stub `db.add_task` call and implement formatting; wire DB later. |
| **Estimated** | 10 min |

---

## TASK-014: Implement cmd_list handler in commands.py

| Field | Detail |
|---|---|
| **Objective** | Add the `cmd_list(args)` handler to `commands.py`. It checks mutual exclusivity of `--all` and `--done` (exit 1, `error: --all and --done are mutually exclusive` to stderr). Determines the filter string (`"pending"`, `"done"`, or `"all"`), calls `db.list_tasks`, and formats the output as a left-aligned table with columns `ID`, `Status`, `Created`, `Text` separated by two-space minimum padding. Status is `[ ]` or `[x]`. Header is always printed. Exits 0. |
| **Inputs** | PLAN §Phase 3, deliverable 3.1 (cmd_list); SPEC §3.3 `todo list` (output format, mutual exclusivity, exit codes) |
| **Outputs** | `cmd_list` function appended to `todo_cli/commands.py`. |
| **Files touched** | `todo_cli/commands.py` (modify) |
| **Done when** | (1) `--all` + `--done` together produces error on stderr and exit 1. (2) Table output matches SPEC format with correct alignment, status markers, and timestamp formatting. (3) Empty result set prints header only. |
| **depends_on** | TASK-009, TASK-013 |
| **if_blocked** | MODERATE — table formatting can be developed independently of DB results using mock data. |
| **Estimated** | 20 min |

---

## TASK-015: Implement cmd_done handler in commands.py

| Field | Detail |
|---|---|
| **Objective** | Add the `cmd_done(args)` handler to `commands.py`. It validates the ID is an integer (exit 1, `error: id must be an integer` to stderr). Calls `db.complete_task`. Prints `Completed task <id>: <text>` to stdout. Catches `TaskNotFoundError` and prints `error: task <id> not found` to stderr with exit 1. Exits 0 on success. |
| **Inputs** | PLAN §Phase 3, deliverable 3.1 (cmd_done); SPEC §3.3 `todo done` (validation, idempotent, output, exit codes) |
| **Outputs** | `cmd_done` function appended to `todo_cli/commands.py`. |
| **Files touched** | `todo_cli/commands.py` (modify) |
| **Done when** | (1) Non-integer ID produces correct error and exit 1. (2) Non-existent ID produces `error: task <id> not found` and exit 1. (3) Valid completion prints correct stdout message and exits 0. |
| **depends_on** | TASK-010, TASK-013 |
| **if_blocked** | MODERATE — can implement validation and formatting; stub DB call. |
| **Estimated** | 10 min |

---

## TASK-016: Implement cmd_rm handler in commands.py

| Field | Detail |
|---|---|
| **Objective** | Add the `cmd_rm(args)` handler to `commands.py`. It validates the ID is an integer (exit 1, `error: id must be an integer` to stderr). Calls `db.remove_task`. Prints `Removed task <id>: <text>` to stdout. Catches `TaskNotFoundError` and prints `error: task <id> not found` to stderr with exit 1. Exits 0 on success. |
| **Inputs** | PLAN §Phase 3, deliverable 3.1 (cmd_rm); SPEC §3.3 `todo rm` (validation, output, exit codes) |
| **Outputs** | `cmd_rm` function appended to `todo_cli/commands.py`. |
| **Files touched** | `todo_cli/commands.py` (modify) |
| **Done when** | (1) Non-integer ID produces correct error and exit 1. (2) Non-existent ID produces `error: task <id> not found` and exit 1. (3) Valid removal prints correct stdout message and exits 0. |
| **depends_on** | TASK-011, TASK-013 |
| **if_blocked** | MODERATE — can implement validation and formatting; stub DB call. |
| **Estimated** | 10 min |

---

## TASK-017: Wire command handlers into __main__.py and add DB lifecycle

| Field | Detail |
|---|---|
| **Objective** | Update `todo_cli/__main__.py` to (1) set each subparser's `set_defaults(func=…)` to point to the corresponding handler in `commands.py`, (2) open the DB connection via `db.open_connection(args.db)` before dispatching, (3) wrap execution in try/except to catch `DBError` → print message to stderr + exit 2, and (4) ensure `connection.close()` in a `finally` block. Pass the connection to handlers via `args.conn`. |
| **Inputs** | PLAN §Phase 3, deliverable 3.2; SPEC §3.3 (exit code 2 for DB errors); all cmd_* handlers from TASK-013 through TASK-016 |
| **Outputs** | Updated `__main__.py` with full command dispatch and DB lifecycle management. |
| **Files touched** | `todo_cli/__main__.py` (modify) |
| **Done when** | (1) `python -m todo_cli add "test"` creates a task and prints success. (2) DB errors produce exit code 2. (3) Connection is always closed (verified by code review of finally block). (4) Each subcommand dispatches to its correct handler. |
| **depends_on** | TASK-004, TASK-007, TASK-013, TASK-014, TASK-015, TASK-016 |
| **if_blocked** | CRITICAL — this is the integration point connecting CLI to DB. Escalate immediately. |
| **Estimated** | 15 min |

---

## TASK-018: Write tests for command handlers (Phase 3)

| Field | Detail |
|---|---|
| **Objective** | Write unit tests for all four command handlers in `commands.py`. Tests should use a temporary SQLite database and invoke handlers with constructed `argparse.Namespace` objects. Cover: add validation and success, list mutual exclusivity and table formatting, done validation/not-found/idempotent/success, rm validation/not-found/success. Capture stdout/stderr and verify exit codes. |
| **Inputs** | PLAN §Phase 3 Validation Gate; SPEC §3.3 (all command output formats and exit codes); TASK-013 through TASK-016 outputs |
| **Outputs** | Test file with tests for each handler covering validation errors, success paths, and error handling. |
| **Files touched** | `tests/test_commands.py` (create) |
| **Done when** | All tests pass via `python -m pytest tests/test_commands.py` and cover validation errors, success output, and error handling for all four commands. |
| **depends_on** | TASK-013, TASK-014, TASK-015, TASK-016, TASK-012 |
| **if_blocked** | MINOR — tests can be written against function signatures before implementation is finalized. |
| **Estimated** | 25 min |

---

## TASK-019: Write end-to-end integration tests (Phase 4)

| Field | Detail |
|---|---|
| **Objective** | Write integration tests that invoke the full CLI via `subprocess.run(["python", "-m", "todo_cli", ...])` against a temporary database (using `--db` flag with a temp file). Cover the full lifecycle: add multiple tasks → list pending → complete one → list done → list all → remove one → list all → verify final state. Also test edge cases: empty add text, unknown command, mutually exclusive list flags, done/rm on non-existent IDs. |
| **Inputs** | PLAN §Phase 4 (implied integration testing); SPEC §3.3 (all commands end-to-end); SPEC §3.4 (error behaviour) |
| **Outputs** | Test file with end-to-end tests exercising the full CLI through subprocess calls. |
| **Files touched** | `tests/test_integration.py` (create) |
| **Done when** | All integration tests pass via `python -m pytest tests/test_integration.py`. Tests verify correct stdout, stderr, and exit codes for the full task lifecycle and all error conditions. |
| **depends_on** | TASK-017 |
| **if_blocked** | MODERATE — integration tests require full wiring. Write test stubs and run once TASK-017 completes. |
| **Estimated** | 25 min |

---

## TASK-020: Add subparser argument definitions for all commands

| Field | Detail |
|---|---|
| **Objective** | Update `__main__.py` to add proper argument definitions to each subparser: `add` gets `nargs="+"` positional `text` argument; `list` gets `--all` and `--done` boolean flags; `done` gets positional `id` argument; `rm` gets positional `id` argument. This ensures argparse handles argument parsing correctly before handlers are invoked. |
| **Inputs** | SPEC §3.3 (argument definitions for each command); PLAN §Phase 1, deliverable 1.3 (subparser registration) |
| **Outputs** | Updated `__main__.py` with complete argument definitions on all four subparsers. |
| **Files touched** | `todo_cli/__main__.py` (modify) |
| **Done when** | (1) `python -m todo_cli add` with no text arg produces a usage error. (2) `python -m todo_cli list --all --done` parses both flags. (3) `python -m todo_cli done` with no ID produces a usage error. (4) `python -m todo_cli rm` with no ID produces a usage error. |
| **depends_on** | TASK-004 |
| **if_blocked** | MODERATE — command dispatch cannot work correctly without proper argument definitions. |
| **Estimated** | 10 min |

---

## TASK-021: Create README.md with usage documentation

| Field | Detail |
|---|---|
| **Objective** | Create a `README.md` at the repository root documenting installation (via `pipx` or `pip`), all four commands with example invocations and expected output, the `--db` global flag, and a note that only the Python standard library is required. |
| **Inputs** | SPEC §3.1 (invocation), §3.2 (global flags), §3.3 (all commands with examples) |
| **Outputs** | `README.md` with installation instructions, usage examples for all commands, and project description. |
| **Files touched** | `README.md` (create) |
| **Done when** | README contains: project description, installation steps, usage examples for `add`, `list`, `done`, `rm`, and `--db` flag documentation. Renders correctly as Markdown. |
| **depends_on** | TASK-017 |
| **if_blocked** | MINOR — documentation can be written at any time; does not block functionality. |
| **Estimated** | 15 min |
