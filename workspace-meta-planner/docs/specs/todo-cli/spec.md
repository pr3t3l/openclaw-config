

# MODULE_SPEC — Todo CLI

**Version:** 1.0.0
**Date:** 2026-04-07
**Status:** Draft — ready for implementation review

---

## 1. Purpose

Todo CLI is a tiny, local-first command-line todo application for a single user. Its sole job is fast task capture and completion tracking. All data is stored in a local SQLite database under the user's control. The application uses only the Python standard library, requires no network access, and targets developers or power users who prefer managing tasks from their terminal.

**Primary value proposition:** zero-friction task management — a user can add a task in under two seconds, list outstanding work, mark items done, or remove items, all from the shell with no configuration required.

---

## 2. Scope

### In Scope (MVP)

| Capability | Detail |
|---|---|
| Add a task | Capture free-form text as a new pending task |
| List tasks | Show pending tasks by default; optionally show done or all tasks |
| Complete a task | Mark a task as done by its numeric ID |
| Remove a task | Permanently delete a task by its numeric ID |
| Auto-provision DB | Create the SQLite file and schema on first use |
| Override DB path | Global `--db` flag to point at a non-default database file |

### Out of Scope (MVP)

- Editing task text after creation
- Priorities, due dates, tags, or projects
- Sync, cloud storage, or remote APIs
- Multi-user support or authentication
- TUI / interactive mode
- Background daemons or watchers
- Export or import of data

---

## 3. CLI

### 3.1 Executable

The application is invoked as `todo` (installed via `pipx`) or `python -m todo_cli`. Both invocations behave identically.

### 3.2 Global Flags

| Flag | Type | Default | Description |
|---|---|---|---|
| `--db` | File path (string) | `~/.todo.sqlite3` | Override the path to the SQLite database file. The path is expanded via `os.path.expanduser`. |

### 3.3 Commands

#### `todo add <text...>`

Concatenates all positional arguments after `add` into a single task description string (joined with spaces). Creates a new pending task with that text.

| Aspect | Detail |
|---|---|
| Arguments | One or more positional strings forming the task text |
| Validation | Text must be non-empty after stripping whitespace; exit code 1 with message `error: task text cannot be empty` to stderr otherwise |
| Output (stdout) | `Added task <id>: <text>` |
| Exit code | 0 on success, 1 on validation error, 2 on DB error |

#### `todo list [--all | --done]`

Prints a table of tasks. By default, only pending (not-done) tasks are shown.

| Flag | Behaviour |
|---|---|
| *(no flag)* | Show tasks where `done = 0` |
| `--done` | Show tasks where `done = 1` |
| `--all` | Show all tasks regardless of status |

`--all` and `--done` are mutually exclusive. If both are supplied, exit code 1 with message `error: --all and --done are mutually exclusive` to stderr.

**Output format** (stdout, one header line then one line per task):

```
ID  Status  Created              Text
 1  [ ]     2025-07-09 08:30:00  Buy milk
 3  [x]     2025-07-08 14:12:00  Write spec
```

- Columns are left-aligned and separated by two spaces minimum.
- `Status` is `[ ]` for pending and `[x]` for done.
- `Created` is the `created_at` timestamp truncated to seconds (`YYYY-MM-DD HH:MM:SS`).
- When no tasks match the filter, print only the header line (no rows) and exit 0.

| Aspect | Detail |
|---|---|
| Exit code | 0 on success, 1 on invalid flags, 2 on DB error |

#### `todo done <id>`

Marks the task identified by the integer `<id>` as completed. Sets `done = 1` and `done_at` to the current UTC timestamp.

| Aspect | Detail |
|---|---|
| Arguments | Exactly one positional integer (the task ID) |
| Validation — non-integer | Exit code 1, message `error: id must be an integer` to stderr |
| Validation — ID not found | Exit code 1, message `error: task <id> not found` to stderr |
| Validation — already done | Succeeds (idempotent); does not modify `done_at` |
| Output (stdout) | `Completed task <id>: <text>` |
| Exit code | 0 on success, 1 on validation error, 2 on DB error |

#### `todo rm <id>`

Permanently deletes the task identified by the integer `<id>`.

| Aspect | Detail |
|---|---|
| Arguments | Exactly one positional integer (the task ID) |
| Validation — non-integer | Exit code 1, message `error: id must be an integer` to stderr |
| Validation — ID not found | Exit code 1, message `error: task <id> not found` to stderr |
| Output (stdout) | `Removed task <id>: <text>` (prints the text of the deleted task for confirmation) |
| Exit code | 0 on success, 1 on validation error, 2 on DB error |

### 3.4 No-Command / Unknown-Command Behaviour

| Situation | Behaviour |
|---|---|
| No command supplied (`todo` alone) | Print usage summary to stderr, exit code 1 |
| Unknown command (`todo foo`) | Print `error: unknown command 'foo'` to stderr, exit code 1 |

### 3.5 Argument Parsing

Use a custom `argparse.ArgumentParser` subclass to ensure user/validation errors exit with code 1 (not argparse's default 2) and to keep error messages stable (see §5.4).

Use `argparse` from the standard library. Subparsers handle each command. `--db` is attached to the top-level parser so it is available to every subcommand.

---

## 4. Data Model

### 4.1 Database Engine

SQLite 3 via Python's built-in `sqlite3` module. WAL journal mode is enabled at connection time for safer concurrent reads (e.g., a user running `list` while another shell does `add`).

### 4.2 Database File

Default location: `~/.todo.sqlite3`. Overridden by the `--db` global flag. The directory must already exist; the application does not create parent directories. If the directory does not exist, exit code 2 with message `error: directory '<dir>' does not exist` to stderr.

### 4.3 Schema

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY,
    text       TEXT    NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL,
    done_at    TEXT
);
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique task identifier, monotonically increasing |
| `text` | TEXT | NOT NULL | User-supplied task description |
| `done` | INTEGER | NOT NULL, DEFAULT 0 | 0 = pending, 1 = completed |
| `created_at` | TEXT | NOT NULL | UTC timestamp in ISO 8601 format (`YYYY-MM-DDTHH:MM:SS`) set at insertion time |
| `done_at` | TEXT | nullable | UTC timestamp in ISO 8601 format set when task is marked done; NULL while pending |

### 4.4 Schema Provisioning

On every invocation the application calls `CREATE TABLE IF NOT EXISTS` to ensure the table exists. No migration system is needed for MVP — the schema is single-version.

### 4.5 Connection Management

A single `sqlite3.Connection` is opened at the start of the command, used for all queries within that invocation, and closed before exit. All mutations are committed immediately after the relevant INSERT / UPDATE / DELETE via `connection.commit()`. Connections set `connection.execute("PRAGMA journal_mode=WAL")` immediately after opening.

### 4.6 Query Safety

All queries use parameterized placeholders (`?`). String interpolation or f-string injection into SQL is forbidden.

### 4.7 Queries by Command

**add:**
```sql
INSERT INTO tasks (text, done, created_at) VALUES (?, 0, ?);
```
`created_at` is set to `datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")`.

**list (pending):**
```sql
SELECT id, text, done, created_at FROM tasks WHERE done = 0 ORDER BY id ASC;
```

**list (done):**
```sql
SELECT id, text, done, created_at FROM tasks WHERE done = 1 ORDER BY id ASC;
```

**list (all):**
```sql
SELECT id, text, done, created_at FROM tasks ORDER BY id ASC;
```

**done:**
```sql
SELECT id, text FROM tasks WHERE id = ?;
UPDATE tasks SET done = 1, done_at = ? WHERE id = ?;
```

**rm:**
```sql
SELECT id, text FROM tasks WHERE id = ?;
DELETE FROM tasks WHERE id = ?;
```

The SELECT before UPDATE/DELETE is used to (a) verify the ID exists and (b) retrieve the task text for the confirmation message.

---

## 5. Error Handling

### 5.1 Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | User / input error (bad arguments, missing ID, mutually exclusive flags) |
| 2 | System / database error (file permissions, corrupt DB, I/O failure) |

### 5.2 Error Output Convention

All error messages are written to **stderr** via `sys.stderr.write()`. Messages follow the pattern `error: <lowercase description>\n`. Normal output goes to **stdout**.

### 5.3 Traceback Suppression

The `main()` entry point wraps all logic in a try/except block:

- `sqlite3.Error` → print `error: database error — <sqlite3 exception message>` to stderr, exit 2.
- `KeyboardInterrupt` → print nothing, exit 130 (standard Unix convention).
- `Exception` (catch-all safety net) → print `error: unexpected failure — <message>` to stderr, exit 2.

No Python traceback is ever printed during normal or expected-error operation.

### 5.4 Specific Error Messages

| Condition | Stderr Message | Exit Code |
|---|---|---|
| No command given | `usage: todo <add|list|done|rm> [options]` | 1 |
| Unknown command | `error: unknown command '<cmd>'` | 1 |
| `add` with empty text | `error: task text cannot be empty` | 1 |
| `done`/`rm` with non-integer id | `error: id must be an integer` | 1 |
| `done`/`rm` with non-existent id | `error: task <id> not found` | 1 |
| `list` with both `--all` and `--done` | `error: --all and --done are mutually exclusive` | 1 |
| DB directory missing | `error: directory '<dir>' does not exist` | 2 |
| SQLite operational error | `error: database error — <details>` | 2 |

---

## 6. Testing

### 6.1 Framework

`unittest` from the Python standard library. Tests are discovered and run via `python -m unittest discover -s tests -p "test_*.py"`. Compatibility with `pytest` is maintained (pytest auto-discovers `unittest.TestCase` subclasses) but pytest is not a dependency.

### 6.2 Test Database Strategy

Every test method creates a temporary SQLite file using `tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)`. The file is deleted in `tearDown`. This ensures complete isolation between tests with no in-memory shortcuts — the on-disk behaviour matches production.

### 6.3 Test Module: `tests/test_db.py`

Tests exercise the internal database-layer functions directly (not via subprocess). The DB layer exposes pure functions or a thin class that accepts a database path.

| Test Name | What It Verifies |
|---|---|
| `test_schema_auto_created` | Opening a connection to a non-existent file creates the file and the `tasks` table with the correct columns |
| `test_add_task` | Inserting a task returns a positive integer ID; the task appears in a subsequent SELECT with `done = 0` and a valid `created_at` |
| `test_add_task_empty_text_raises` | Attempting to add a task with empty or whitespace-only text raises `ValueError` |
| `test_list_pending_only` | After adding 3 tasks and completing 1, listing pending returns exactly 2 rows |
| `test_list_done_only` | After adding 3 tasks and completing 2, listing done returns exactly 2 rows |
| `test_list_all` | After adding 3 tasks and completing 1, listing all returns exactly 3 rows |
| `test_list_empty` | Listing tasks on a fresh DB returns an empty list |
| `test_done_sets_fields` | Marking a task done sets `done = 1` and `done_at` to a non-null ISO 8601 UTC timestamp |
| `test_done_idempotent` | Marking an already-done task done again succeeds without error and updates `done_at` |
| `test_done_nonexistent_id` | Marking a non-existent ID raises `KeyError` |
| `test_rm_deletes_task` | Removing a task by ID results in that ID being absent from a subsequent SELECT |
| `test_rm_nonexistent_id` | Removing a non-existent ID raises `KeyError` |
| `test_parameterized_queries` | Adding a task with text containing SQL injection characters (`'; DROP TABLE tasks;--`) succeeds and the text is stored literally |

### 6.4 Test Module: `tests/test_cli.py`

Integration-level tests that invoke the CLI entry point programmatically (calling `main()` with patched `sys.argv` and capturing stdout/stderr via `io.StringIO`).

| Test Name | What It Verifies |
|---|---|
| `test_add_prints_confirmation` | `todo add Buy milk` prints `Added task 1: Buy milk` to stdout and exits 0 |
| `test_list_default_shows_pending` | After adding two tasks and completing one, `todo list` shows only the pending task |
| `test_list_done_flag` | `todo list --done` shows only completed tasks |
| `test_list_all_flag` | `todo list --all` shows all tasks |
| `test_list_mutual_exclusion` | `todo list --all --done` exits 1 with the mutual-exclusion error on stderr |
| `test_done_prints_confirmation` | `todo done 1` prints `Completed task 1: Buy milk` to stdout and exits 0 |
| `test_rm_prints_confirmation` | `todo rm 1` prints `Removed task 1: Buy milk` to stdout and exits 0 |
| `test_no_command_exits_1` | Invoking `todo` with no arguments exits 1 and writes usage to stderr |
| `test_unknown_command_exits_1` | `todo foo` exits 1 with `error: unknown command 'foo'` on stderr |
| `test_db_flag_overrides_path` | `todo --db /tmp/custom.sqlite3 add Test` creates the DB at the specified path |

---

## 7. Non-Goals

The following are explicitly out of scope and must not be implemented, even partially, in MVP:

| Non-Goal | Rationale |
|---|---|
| User accounts or authentication | Single-user, local-first by design (Constitution §2) |
| Multi-user or concurrent-user workflows | Complexity disproportionate to value; WAL mode handles incidental concurrency from the same OS user |
| Network calls, sync, or cloud storage | Local-first principle (Constitution §2) |
| TUI or interactive mode | Constitution §2 explicitly defers this |
| Background daemons, file watchers, or schedulers | Out of scope for a synchronous CLI tool |
| Telemetry or analytics | Constitution §8 forbids telemetry |
| Third-party dependencies | stdlib-only constraint (Constitution §3) |
| Task editing after creation | MVP captures and completes; editing deferred to future enhancement |
| Priorities, due dates, tags, or projects | Feature creep; deferred to future enhancement |
| Data export or import | Deferred to future enhancement |

---

## 8. Future Enhancements

The following features may be considered **after MVP is stable and tested**. Each would require its own MODULE_SPEC before implementation.

| Enhancement | Description | Prerequisite |
|---|---|---|
| `edit <id> <new_text>` command | Modify the text of an existing task in place | Stable MVP |
| Priority levels | Add a `priority` column (integer 1–3); `list` sorts by priority then ID; `add --priority 1` flag | Stable MVP, schema migration strategy |
| Due dates | Add a `due_at TEXT` column; `add --due 2025-08-01` flag; `list --overdue` filter | Stable MVP, schema migration strategy |
| Tags | Add a `tags` table with many-to-many relation; `add --tag work` flag; `list --tag work` filter | Stable MVP, schema migration strategy |
| Full-text search | `todo search <query>` using SQLite FTS5 extension | Tags or sufficient task volume |
| Archive command | `todo archive` moves done tasks to an `archive` table instead of deleting | Stable MVP |
| Export / Import | `todo export --format json` and `todo import <file>` for backup and portability | Stable MVP |
| Shell completions | Auto-generate Bash/Zsh/Fish completions from argparse | Stable MVP |
| Colour output | Coloured status indicators using ANSI escape codes (with `--no-color` flag) | Stable MVP, detect TTY |