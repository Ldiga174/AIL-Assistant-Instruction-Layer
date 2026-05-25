# AIL Agent Rules

## Mandatory Startup

Before starting any task:

1. Read `.ail/bootstrap.md`.
2. Read `.ail/project.init.md`.
3. Read `.ail/ailog.md`.
4. Read `.ail/task.todo.json`.
5. Inspect the current architecture before making changes.
6. Create a short execution plan before patching.

## Never

- Rewrite architecture without owner approval.
- Modify unrelated files.
- Generate placeholder code as a finished result.
- Remove logs or comments without reason.
- Commit secrets or `.env` files.
- Perform massive refactors without confirmation.

## Always

- Prefer minimal diffs.
- Fix root causes over symptoms.
- Validate changes after edits.
- Document modified files.
- Update `.ail/ailog.md` after task completion.
- Keep workflow deterministic and reproducible.

## Task Lifecycle

```text
inspect
-> analyze
-> plan
-> patch minimally
-> validate
-> document
-> log
```
