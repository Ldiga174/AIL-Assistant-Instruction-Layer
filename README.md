# AIL 3.0 - Assistant Instruction Layer

AIL 3.0 is a portable workflow layer for controlled AI-assisted project execution.

It gives owners and AI agents a deterministic operating protocol: task intake, project context, planning, minimal patching, validation, logging, and result handoff. AIL can be copied into any repository and used with VS Code, GitHub Issues, Codex, Continue, Roo, Cline, or other execution agents.

AIL is not tied to OpenClaw, OpenCode, DPA Compute, or any single IDE. Older AIL 2.0 ideas are preserved as reusable workflow principles, while AIL 3.0 focuses on practical project execution.

## Why It Exists

AI agents are useful only when they work inside stable project rules. Without an orchestration layer they can skip context, repeat errors, rewrite unrelated architecture, forget validation, or lose task state between sessions.

AIL exists to make AI-assisted work reproducible:

```text
Owner defines the task
-> GitHub Issue or local inbox stores the task
-> agent reads project state
-> agent inspects architecture
-> agent creates a short plan
-> agent patches minimally
-> agent validates
-> agent documents the result
-> AIL log preserves what happened
```

## Core Principle

AIL is the orchestration layer. Agents are execution layers.

The owner remains the final authority. Agents may inspect, plan, patch, test, and report, but they should not rewrite architecture, run destructive actions, or declare success without validation.

## Roles

| Role | Responsibility |
|---|---|
| Owner | Defines goals, approves risky changes, decides final direction |
| Architect AI / ChatGPT | Breaks goals into issues, clarifies scope, reviews strategy |
| GitHub Issues | External task queue and audit trail |
| VS Code | Local execution environment and task runner |
| Execution Agents | Codex, Continue, Roo, Cline, or other tools that execute AIL tasks |
| AIL | Deterministic workflow, memory, safety rules, and result protocol |

## Standard `.ail/` Structure

```text
.ail/
├── AGENTS.md
├── bootstrap.md
├── project.init.md
├── ailog.md
├── task.todo.json
├── memory.md
├── snapshot.success.md
├── inbox/
│   └── current-task.md
├── outbox/
│   └── last-result.md
├── state/
│   ├── .gitkeep
│   ├── last_issue_number
│   ├── current_issue_number
│   └── current_issue_url
└── scripts/
    └── ail-watch-issues.sh

.vscode/
└── tasks.json
```

## File Roles

| File | Purpose |
|---|---|
| `.ail/AGENTS.md` | Agent rules for the local project |
| `.ail/bootstrap.md` | Mandatory startup workflow |
| `.ail/project.init.md` | Project purpose, architecture, stack, and current state |
| `.ail/ailog.md` | Append-only work log and validation record |
| `.ail/task.todo.json` | Deterministic local task state |
| `.ail/memory.md` | Durable project memory and no-repeat lessons |
| `.ail/snapshot.success.md` | Last known stable checkpoint |
| `.ail/inbox/current-task.md` | Active task from GitHub or owner |
| `.ail/outbox/last-result.md` | Latest validated result for owner/GitHub |
| `.ail/state/` | AutoTasks metadata |
| `.ail/scripts/ail-watch-issues.sh` | GitHub Issue intake watcher |

## GitHub Issues Workflow

AIL uses GitHub Issues as a task queue when a project needs shared, durable task state.

1. Owner or Architect AI creates an issue.
2. Add label `ail-task`.
3. AutoTasks watcher imports the newest open `ail-task` issue into `.ail/inbox/current-task.md`.
4. The owner asks an execution agent to process the inbox task.
5. The agent follows AIL workflow: inspect, analyze, plan, patch, validate, document.
6. Result goes to `.ail/outbox/last-result.md`.
7. The result is posted as a GitHub issue comment.
8. The issue is closed only after completion.

## AutoTasks Workflow

AutoTasks is automatic task intake, not unsafe autonomous execution.

```text
GitHub Issue labeled ail-task
-> watcher detects the issue
-> watcher writes .ail/inbox/current-task.md
-> watcher stores metadata in .ail/state/
-> watcher optionally opens VS Code or sends a desktop notification
-> owner asks an agent to execute
```

Required tools:

- `gh`
- `jq`
- optional `code`
- optional `notify-send`

Run:

```bash
AIL_REPO="owner/repo" .ail/scripts/ail-watch-issues.sh 20
```

## Recommended Codex Command

```text
Read .ail/inbox/current-task.md and execute it under AIL workflow.

After completion:
- update .ail/outbox/last-result.md
- update .ail/ailog.md
- commit changes if appropriate
- push to GitHub if appropriate
- comment result in the source GitHub issue
- close the issue if completed
```

## Task Lifecycle

```text
inspect
-> analyze
-> plan
-> confirm if architectural/risky
-> patch minimally
-> validate
-> document
-> log
```

## Safety Rules

- Read AIL context before editing.
- Prefer minimal diffs.
- Do not modify unrelated files.
- Do not hardcode secrets.
- Do not commit `.env`.
- Do not remove logs or comments without reason.
- Do not rewrite architecture without owner approval.
- Stop and ask when requirements conflict.
- Preserve reproducibility.

## Validation Rules

Every task should define validation before success. Validation may include:

- syntax checks;
- unit tests;
- build checks;
- route/API registration checks;
- local smoke tests;
- manual verification notes when automation is unavailable.

Success means the requested behavior was implemented and validated, not just that files were edited.

## Minimal Install / Copy Pack

Copy the starter pack into a project:

```bash
cp -R templates/ail-3.0/. /path/to/project/
```

Then edit:

- `.ail/project.init.md`
- `.ail/task.todo.json`
- `.vscode/tasks.json` if needed

Start AutoTasks:

```bash
cd /path/to/project
AIL_REPO="owner/repo" .ail/scripts/ail-watch-issues.sh 20
```

## AIL 2.0 vs AIL 3.0

| AIL 2.0 | AIL 3.0 |
|---|---|
| President/OpenCode/OpenClaw centered | Portable across Codex, Continue, Roo, Cline, and other agents |
| More tied to one execution architecture | Copyable workflow layer for any repo |
| Internal task queues and runtime engine focus | GitHub Issues, inbox/outbox, VS Code, local project memory |
| Useful no-repeat and validation concepts | Preserved as project memory, prestart, and validation rules |
| Architecture-heavy | Practical daily execution protocol |

## Preserved From AIL 2.0

- deterministic startup protocol;
- `project.init.md` as entry point;
- `ailog.md` as session log;
- `task.todo.json` as task state;
- `snapshot.success.md` as stable checkpoint;
- prestart/checklist mindset;
- no-repeat errors and durable memory;
- validation before success;
- no architecture changes without approval;
- owner remains final authority.

## Repository Contents

This repository includes:

- current AIL 3.0 documentation;
- reusable AIL 3.0 templates;
- historical AIL 2.0 / AI-system prototype files;
- dashboard and older execution-engine experiments.

Historical files are kept for continuity. New projects should start from `templates/ail-3.0/`.

## Roadmap

- Finish AIL 3.0 documentation and starter templates.
- Add attribution and NOTICE files.
- Add more project templates.
- Add optional issue result posting helpers.
- Add validation examples for common stacks.
- Keep AutoTasks intake safe and user-approved.
