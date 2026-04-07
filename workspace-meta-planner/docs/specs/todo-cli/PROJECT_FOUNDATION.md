# PROJECT_FOUNDATION.md — Todo CLI

**Last updated:** 2026-04-07

## 1. What This Is
A tiny, local-first command-line todo app written in Python that stores tasks in a single SQLite database file.

## 2. What Problem It Solves
Provides a fast, reliable way to capture and manage a personal task list from the terminal without accounts, sync, or external services.

## 3. What This Is NOT (Anti-Goals)
- Not a multi-user system
- Not a cloud-synced app
- Not a full project-management suite (no kanban, comments, attachments)

## 4. Who It’s For
- A single user on their own machine who wants minimal task tracking.

## 5. Competitive Differentiators
- Zero dependencies (stdlib only)
- Single-file SQLite storage
- Simple, memorable commands

## 6. Tech Stack
- Language: Python 3.x
- Storage: SQLite (via `sqlite3`)
- CLI parsing: `argparse`

## 7. Key Decisions
- IDs: sequential integers (SQLite INTEGER PRIMARY KEY)
- DB location: default `~/.todo.sqlite3` (override via `--db`)
- Minimal commands: add/list/done/rm

## 8. MVP Scope
### In-scope
- Add a task
- List tasks (open by default; optionally include done)
- Mark task done
- Remove task

### Out-of-scope (MVP)
- Editing task text
- Priorities, due dates, tags/projects
- Sorting/filtering beyond open vs done
- Sync

## 9. UX Summary (CLI)
- `todo add "Buy milk"`
- `todo list` (shows open tasks)
- `todo list --all` (shows open + done)
- `todo done 3`
- `todo rm 3`

## 10. Risks & Mitigations
- DB corruption: rely on SQLite durability; keep schema tiny.
- Confusing IDs: always display IDs in `list` output.

## 11. Doc Registry
- `CONSTITUTION.md` — rules & constraints
- `DATA_MODEL.md` — SQLite schema details
- `INTEGRATIONS.md` — none (local-only)
- `LESSONS_LEARNED.md` — pitfalls to avoid
- `spec.md` — module spec
- `plan.md` / `tasks.md` — build plan and execution tasks
