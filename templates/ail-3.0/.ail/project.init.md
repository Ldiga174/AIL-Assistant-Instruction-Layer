# Project Init

## Project

Describe the project name, purpose, stack, and owner priorities here.

## Architecture

Document the important modules, services, data flow, and integration boundaries.

## AIL Workflow

This project uses AIL 3.0:

- `.ail/bootstrap.md` defines startup workflow.
- `.ail/AGENTS.md` defines agent rules.
- `.ail/ailog.md` records completed work and validation.
- `.ail/task.todo.json` tracks local tasks.
- `.ail/inbox/current-task.md` stores the active task.
- `.ail/outbox/last-result.md` stores the latest result.

## Startup Protocol

1. Read `.ail/bootstrap.md`.
2. Read `.ail/AGENTS.md`.
3. Read `.ail/project.init.md`.
4. Read `.ail/ailog.md`.
5. Read `.ail/task.todo.json`.
6. Inspect architecture before editing.
7. Plan, patch, validate, document.

## AutoTasks

GitHub issues labeled `ail-task` can be imported by:

```bash
AIL_REPO="owner/repo" .ail/scripts/ail-watch-issues.sh 20
```
