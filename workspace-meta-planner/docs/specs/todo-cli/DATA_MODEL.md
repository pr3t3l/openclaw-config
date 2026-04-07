# DATA_MODEL.md — Todo CLI

**Last updated:** 2026-04-07

## 1. Storage Overview
- Storage engine: SQLite
- Default DB path: `~/.todo.sqlite3`
- Override path: `todo --db /path/to/file.sqlite3 ...`

## 2. Schema (MVP)
### 2.1 `tasks`
| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY | Sequential rowid-style ID |
| text | TEXT | NOT NULL | Task description |
| done | INTEGER | NOT NULL DEFAULT 0 | 0=false, 1=true |
| created_at | TEXT | NOT NULL | ISO-8601 UTC timestamp |
| done_at | TEXT | NULL | ISO-8601 UTC timestamp |

DDL:
```sql
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY,
  text TEXT NOT NULL,
  done INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  done_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks(done);
```

## 3. Queries (MVP)
- Insert task: `INSERT INTO tasks(text, done, created_at) VALUES (?, 0, ?)`
- List open: `SELECT id, text, done, created_at, done_at FROM tasks WHERE done = 0 ORDER BY id ASC`
- List done: `... WHERE done = 1 ...`
- List all: no WHERE clause
- Mark done: `UPDATE tasks SET done = 1, done_at = ? WHERE id = ? AND done = 0`
- Remove: `DELETE FROM tasks WHERE id = ?`

## 4. Migration Policy
- MVP has no migrations; schema changes require a bump + migration plan later.
