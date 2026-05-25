# AIL 3.0 Project Init

## Project

AIL 3.0 - portable Assistant Instruction Layer for controlled AI-assisted project execution.

This repository defines a reusable workflow layer that can be copied into any software project. AIL coordinates task intake, project context, execution rules, validation, logging, and result handoff for agents such as Codex, Continue, Roo, Cline, and other AI development tools.

AIL is not only a President/OpenCode/OpenClaw system. Those AIL 2.0 concepts remain as historical and architectural references, but AIL 3.0 generalizes the useful parts into a practical project protocol.

## Current Repo Purpose

- Define AIL 3.0 workflow rules and documentation.
- Provide reusable `.ail/` starter templates.
- Provide AutoTasks GitHub Issue intake templates.
- Preserve useful AIL 2.0 concepts: deterministic startup, task state, session log, validation, no-repeat memory, and owner authority.
- Keep historical prototype code as reference without making it the required architecture for new projects.

## AIL 3.0 Architecture

```text
Owner / Architect AI
-> GitHub Issues or local task source
-> .ail/inbox/current-task.md
-> Execution agent under .ail/AGENTS.md rules
-> minimal patch + validation
-> .ail/outbox/last-result.md
-> .ail/ailog.md
-> GitHub issue comment / close when complete
```

## Key Files

| File | Purpose |
|---|---|
| `README.md` | Public AIL 3.0 overview |
| `docs/AIL-3.0.md` | Detailed AIL 3.0 workflow documentation |
| `templates/ail-3.0/` | Copyable starter pack for projects |
| `project.init.md` | This AI entry point |
| `ailog.md` | Repository session log |
| `task.todo.json` | Local task state |
| `snapshot.success.md` | Stable checkpoint record |
| `ail.errors.md` | Project no-repeat error register |
| `ail.errors.common.template.md` | Reusable no-repeat error template |
| `ai-system/` | Historical AIL 2.0 prototype and engine reference |

## Startup Protocol

Before changing this repository:

1. Read `project.init.md`.
2. Read `ail.errors.md`.
3. Read `ailog.md`.
4. Read `task.todo.json`.
5. Inspect relevant repository structure.
6. Create a short execution plan.
7. Patch minimally.
8. Validate changed docs/scripts/templates.
9. Update `ailog.md`.
10. Comment result in the source GitHub issue when applicable.

## AutoTasks Protocol

AutoTasks imports tasks. It does not execute them automatically.

```text
GitHub Issue labeled ail-task
-> watcher writes .ail/inbox/current-task.md
-> watcher stores .ail/state metadata
-> user asks agent to execute
-> agent validates and writes .ail/outbox/last-result.md
-> result is commented back to GitHub
```

Reusable watcher:

```text
templates/ail-3.0/.ail/scripts/ail-watch-issues.sh
```

VS Code task template:

```text
templates/ail-3.0/.vscode/tasks.json
```

## Version Status

Current direction: AIL 3.0 documentation and reusable templates.

Historical prototype status: the older `ai-system/` runtime remains in the repo as reference, but it is not the required execution model for AIL 3.0 projects.

## Migration Note From AIL 2.0

AIL 2.0 introduced useful principles:

- deterministic startup;
- project init entry point;
- session log;
- task state;
- stable snapshots;
- no-repeat error memory;
- validation before success;
- owner approval for architecture changes.

AIL 3.0 keeps those principles and adds:

- GitHub Issues as task queue;
- `.ail/inbox/current-task.md`;
- `.ail/outbox/last-result.md`;
- AutoTasks watcher;
- VS Code task integration;
- agent-neutral execution rules.

## Fundamental Principle

The owner remains the final authority. AIL controls workflow. Agents execute under explicit project rules.
