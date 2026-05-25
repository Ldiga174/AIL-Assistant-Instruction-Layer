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
- List AI tools or agents as project creators, authors, owners, or co-creators unless the owner explicitly requests it.

## Always

- Prefer minimal diffs.
- Fix root causes over symptoms.
- Validate changes after edits.
- Document modified files.
- Update `.ail/ailog.md` after task completion.
- Keep workflow deterministic and reproducible.
- Preserve creator attribution. For Rodion's projects, use: `Created by Rodion Lebedev / Ldiga.`

## Main LLM to Issue to Executor

AIL separates reasoning from execution.

The main LLM may hold the wider project history and strategy. The execution
agent should treat GitHub Issues and `.ail/inbox/current-task.md` as bounded
execution contracts, not as invitations to reinterpret the whole project.
Return results through `.ail/outbox/last-result.md`.

## Creator Attribution Rule

AI agents are execution tools, not project creators. Cursor, cursoragent,
Codex, ChatGPT, OpenAI, Roo, Continue, Cline, and other tools must not be
presented as project creators or authors. They may be listed separately as
development tools.

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
