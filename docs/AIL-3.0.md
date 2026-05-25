# AIL 3.0 - Assistant Instruction Layer

## What AIL 3.0 Is

AIL 3.0 is a practical AI workflow layer for real development work with VS Code, Codex, Continue, Roo, Cline, GitHub Issues, and local project memory.

AIL 3.0 is not a project-specific OpenClaw architecture.
It is a reusable project workflow protocol.

The main goal is simple:

```text
Owner creates or receives a task
-> AIL stores the task in a deterministic place
-> agent reads project state
-> agent plans
-> agent patches minimally
-> agent validates
-> agent logs result
-> result is pushed/commented back when needed
```

## Core Principle

AIL is the orchestration layer.
Agents are execution layers.

Agents must not randomly rewrite architecture, skip logs, or work without reading project state.

## Roles

| Role | Responsibility |
|---|---|
| Owner | Sets goals, approves risky changes, owns final decisions |
| Architect AI / ChatGPT | Helps split work into issues and clarify scope |
| GitHub Issues | Durable task queue and audit trail |
| VS Code | Local execution surface and background task runner |
| Execution Agents | Codex, Continue, Roo, Cline, or other tools that perform the work |
| AIL | Workflow rules, memory, inbox/outbox protocol, and validation discipline |

## AIL 3.0 Project Layout

Recommended layout inside any project:

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
| `.ail/bootstrap.md` | Session startup protocol |
| `.ail/AGENTS.md` | Agent behavior rules |
| `.ail/project.init.md` | Project description, stack, status, priorities |
| `.ail/ailog.md` | Session and change log |
| `.ail/task.todo.json` | Current task state |
| `.ail/memory.md` | Durable project memory |
| `.ail/snapshot.success.md` | Last known stable milestone |
| `.ail/inbox/current-task.md` | Current task pulled from GitHub or user |
| `.ail/outbox/last-result.md` | Last agent result |
| `.ail/state/*` | AutoTasks metadata |

## Standard Agent Startup

Every agent session must start with:

```text
Read .ail/bootstrap.md, .ail/AGENTS.md, .ail/project.init.md and .ail/ailog.md.
If .ail/inbox/current-task.md contains an active task, execute that task under AIL workflow.
```

## Standard Task Lifecycle

```text
inspect
-> analyze
-> plan
-> confirm if architectural or risky
-> patch minimally
-> validate
-> document
-> update ailog
-> update outbox
-> comment/push when required
```

## GitHub Issues Workflow

AIL 3.0 can use GitHub Issues as the external queue:

```text
Owner creates issue
-> issue gets label ail-task
-> watcher imports it to .ail/inbox/current-task.md
-> agent executes after user approval
-> result is written to .ail/outbox/last-result.md
-> result is commented back to GitHub
-> issue closes only after completion
```

## Why AIL Uses GitHub Issues From the Main LLM

AIL separates reasoning from execution.

The main LLM may know the long project history, owner preferences, previous
decisions, constraints, and why a specific technical direction was chosen.
Execution agents may not have that memory. Multiple executors can also
interpret broad requests differently when they do not share the same context.

Therefore the main LLM produces a precise GitHub Issue as an execution
contract. The executor should not reinterpret the whole project. It should
execute the bounded task, validate it, and return the result.

This contract reduces confusion between different LLMs/agents and saves tokens.
The executor only needs:

- current project state from `.ail/`;
- the precise task from GitHub Issue or `.ail/inbox/current-task.md`;
- allowed scope;
- rules and constraints;
- validation steps;
- expected output.

The issue should include goal, context, scope, rules, validation, and expected
result. `.ail/inbox/current-task.md` is the local execution copy of the issue.
`.ail/outbox/last-result.md` is how the executor returns the result.

## AutoTasks

AIL 3.0 introduces AutoTasks.

AutoTasks is automatic task intake, not unsafe autonomous execution.

```text
GitHub Issue labeled ail-task
-> local watcher detects it
-> watcher writes it to .ail/inbox/current-task.md
-> watcher stores metadata in .ail/state/
-> watcher opens task file in VS Code if available
-> user/agent executes it under AIL workflow
```

AutoTasks solves one practical problem: the owner can create work in GitHub,
while local execution remains controlled by AIL rules and explicit user review.
The watcher only moves task text into the local inbox.

## Required Tools for AutoTasks

- GitHub CLI: `gh`
- JSON processor: `jq`
- Optional: VS Code `code` CLI
- Optional: `notify-send` on Linux

Auth check:

```bash
gh auth status
```

## AutoTasks State Files

AutoTasks stores lightweight metadata in `.ail/state/`:

| File | Purpose |
|---|---|
| `.ail/state/last_issue_number` | Last issue number observed by the watcher |
| `.ail/state/current_issue_number` | Issue number currently written to inbox |
| `.ail/state/current_issue_url` | GitHub URL for the active inbox task |

The active task body is written to:

```text
.ail/inbox/current-task.md
```

The agent writes the latest execution result to:

```text
.ail/outbox/last-result.md
```

## AutoTasks Watcher

Reusable watcher template:

```text
templates/ail-3.0/.ail/scripts/ail-watch-issues.sh
```

Usage:

```bash
AIL_REPO="owner/repo" .ail/scripts/ail-watch-issues.sh 20
```

Or:

```bash
.ail/scripts/ail-watch-issues.sh 20 owner/repo
```

Defaults:

- label: `ail-task`
- polling interval: `20` seconds
- task inbox: `.ail/inbox/current-task.md`

The watcher:

- fetches open GitHub issues with the `ail-task` label;
- selects the most recently updated issue;
- writes issue title, URL, and body into `.ail/inbox/current-task.md`;
- writes issue metadata into `.ail/state/`;
- sends a desktop notification when `notify-send` is available;
- opens the inbox file when the VS Code `code` CLI is available;
- keeps retrying on temporary GitHub or network errors.

## VS Code AutoTasks Task

Reusable VS Code task template:

```text
templates/ail-3.0/.vscode/tasks.json
```

Example:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "AIL: Watch GitHub Issues",
      "type": "shell",
      "command": ".ail/scripts/ail-watch-issues.sh 20",
      "isBackground": true,
      "problemMatcher": [],
      "presentation": {
        "reveal": "always",
        "panel": "dedicated",
        "clear": false
      }
    }
  ]
}
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

This command is intentionally a user-approved execution step. AutoTasks does
not run Codex, Cline, Roo, Continue, shell commands, or code edits by itself.

## Safety Rules

AutoTasks must not auto-execute destructive operations.

It may:

- pull task text from GitHub;
- write inbox files;
- notify the user;
- open VS Code task file.

It must not:

- execute Codex automatically without user approval;
- store tokens in repo;
- modify unrelated project files;
- close issues without task completion.

## Creator Attribution Rule

AI agents are execution tools, not project creators.

AI tools must not add themselves as creators, authors, owners, or co-creators
unless the owner explicitly requests that wording. Names such as Cursor,
cursoragent, Codex, ChatGPT, OpenAI, Roo, Continue, Cline, or other tools must
not be presented as project creators or project authors.

Official creator attribution for Rodion's projects:

```text
Created by Rodion Lebedev / Ldiga.
```

Recommended AIL attribution:

```text
Based on AIL - Assistant Instruction Layer by Rodion Lebedev / Ldiga.
```

Tools may be listed separately only as development tools, for example:

```text
Development tools used: VS Code, Codex, Cursor, ChatGPT.
```

## Validation Rules

Every task should define validation before completion. Validation may include:

- syntax checks;
- tests;
- builds;
- API route checks;
- local smoke tests;
- manual verification notes when automation is not available.

If validation cannot run, the result must state why.

## Difference from AIL 2.0

AIL 2.0 was more tied to a specific President/OpenCode/OpenClaw structure.

AIL 3.0 is more practical and portable:

- works with VS Code + Codex;
- works with GitHub Issues;
- uses inbox/outbox task protocol;
- keeps deterministic markdown state;
- can be copied into any project;
- avoids forcing OpenClaw-specific architecture.

## AIL 2.0 Concepts Preserved

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

## Minimal Install / Copy Pack

Copy the starter pack into a project:

```bash
cp -R templates/ail-3.0/. /path/to/project/
```

Then edit `.ail/project.init.md` and `.ail/task.todo.json`.

Optional AutoTasks command:

```bash
AIL_REPO="owner/repo" .ail/scripts/ail-watch-issues.sh 20
```

## Roadmap

- Publish complete AIL 3.0 starter pack.
- Add attribution and NOTICE files.
- Add example project integrations.
- Add validation recipes for common stacks.
- Add optional helpers for issue comments and result upload.
- Keep AutoTasks as intake-only unless owner explicitly approves stronger automation.

## Minimal Success Criteria

A project uses AIL 3.0 successfully when:

- every task has a deterministic source;
- agent reads `.ail/` before editing;
- changes are minimal and validated;
- results are logged;
- GitHub Issues can act as task source;
- project state can be resumed later without context loss.
