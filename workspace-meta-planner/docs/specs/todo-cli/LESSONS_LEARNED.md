# LESSONS_LEARNED.md — Todo CLI

**Last updated:** 2026-04-07

## 1. Common Failure Modes
1. **Forgetting to initialize schema**
   - Fix: always run `CREATE TABLE IF NOT EXISTS ...` at startup.

2. **Printing tracebacks for expected errors**
   - Fix: catch `sqlite3.Error` and argument errors; print concise stderr messages.

3. **SQL injection / string formatting**
   - Fix: parameterized queries only.

4. **Ambiguous list output**
   - Fix: always show IDs and a done marker.

5. **Accidental deletes**
   - Fix: `rm` is explicit; never auto-delete.

## 2. Design Guardrails
- Keep commands minimal until a real use-case appears.
- Prefer clarity over cleverness in output formatting.
- Keep the data model tiny.
