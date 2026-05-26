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

## Future Transport Options

GitHub Issues remain the default AIL 3.0 task queue. AIL may later support
optional decentralized transports such as Nostr, where tasks and results are
represented as signed events from trusted owner public keys.

Nostr relays would be transport only, not authority. Executors must not run
arbitrary events from public relays, and any future implementation must preserve
AIL boundaries: trusted signer verification, bounded scope, validation, owner
approval or trusted-key policy, and secure private key handling outside the
repository.

See `docs/nostr-transport.md` for the future Nostr transport concept.

## Why AIL Uses GitHub Issues From the Main LLM

AIL separates reasoning from execution.

The main conversational LLM that the owner talks to can hold the long project
history: previous decisions, owner preferences, constraints, and why a
technical direction was chosen. Local execution agents inside VS Code, Codex,
Continue, Roo, or Cline may not have that full memory. There can also be many
executors, and each one can interpret a broad request differently.

AIL uses the main LLM as the task-shaping and strategy layer. The main LLM
turns discussion into a precise GitHub Issue. That issue becomes the execution
contract for the executor.

The executor should not reinterpret the whole project. It should read current
project state from `.ail/`, execute the bounded issue, validate the result, and
return the result through `.ail/outbox/last-result.md`.

A good AIL issue includes:

- goal;
- context;
- allowed scope;
- rules and constraints;
- validation steps;
- expected result.

This reduces confusion between different LLMs/agents and saves tokens because
the full historical conversation does not need to be repeated to every
executor. `.ail/inbox/current-task.md` is the local execution copy of the
issue. `.ail/outbox/last-result.md` is how the executor returns the result.

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

## Attribution

AIL was created by Rodion Lebedev / Ldiga.

If you use AIL, its workflow, templates, AutoTasks, GitHub Issue task protocol,
inbox/outbox structure, watcher scripts, or documentation in your own tool,
product, AI IDE, SaaS, internal workflow, or public repository, please credit
the original project:

**Based on AIL - Assistant Instruction Layer by Rodion Lebedev / Ldiga.**

Repository: https://github.com/Ldiga174/AIL-Assistant-Instruction-Layer

This project is licensed under Apache-2.0. When redistributing derivative work
that includes substantial AIL materials, preserve the attribution notices in
`NOTICE.md` as required by the license.

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

## Roadmap

- Finish AIL 3.0 documentation and starter templates.
- Add more attribution examples for downstream templates.
- Add more project templates.
- Add optional issue result posting helpers.
- Add validation examples for common stacks.
- Keep AutoTasks intake safe and user-approved.
