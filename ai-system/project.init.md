# SYSTEM MODE

This is an AIL-controlled execution system.
All actions must go through: AIL -> Agents -> Validation -> Decision.
No direct execution is allowed outside the architecture.

---

# AIL System — Project Map (v1)

## 0. General Concept

The system is a **controlled AI execution pipeline**:

```
User -> AIL -> Agents -> Apply -> Execute -> Validate -> Decision
```

AIL (Assistant Instruction Layer) is the **sole decision-maker**.
Agents are executors. They do not set strategy, override validation, or act autonomously.

---

## 1. Architecture Layers

### 1.1 Core (Orchestration)

```
ai-system/core/
```

| Module | Purpose | Status |
|--------|---------|--------|
| `ail_controller.py` | Main orchestrator (President) | IMPLEMENTED |
| `planner.py` | Task decomposition into steps | IMPLEMENTED |
| `router.py` | Decides which agent executes | IMPLEMENTED |
| `validator.py` | Result validation + gates | IMPLEMENTED |
| `memory.py` | State persistence and logging | IMPLEMENTED |
| `policy.py` | Execution constraints (safe/dev/aggressive) | PLANNED |
| `capabilities.py` | Per-agent permission registry | PLANNED |

### 1.2 File Operations

| Module | Purpose | Status |
|--------|---------|--------|
| `file_reader.py` | Safe file reading with sandbox | PLANNED |
| `file_applier.py` | Full file writes | PLANNED |
| `patch_applier.py` | Targeted diffs/patches | PLANNED |
| `snapshot_manager.py` | Snapshot before change + rollback | PLANNED |

### 1.3 Agents

```
ai-system/agents/
```

| Agent | Role | Status |
|-------|------|--------|
| `opencode/` | Programmer — LLM-based code generation | IMPLEMENTED |
| `openclaw/` | Operator — safe shell execution | IMPLEMENTED |
| `shared/` | Base class + data models | IMPLEMENTED |

#### OpenCode (`agents/opencode/`)

| File | Purpose |
|------|---------|
| `adapter.py` | Bridge to LLM (OpenAI/Anthropic/Mock transports) |
| `executor.py` | Parses LLM JSON response into AgentResult |
| `prompts/system.md` | Model identity and constraints |

#### OpenClaw (`agents/openclaw/`)

| File | Purpose |
|------|---------|
| `adapter.py` | Extracts commands from task |
| `executor.py` | Safe subprocess runner with allowlist |
| `prompts/system.md` | Executor identity (no LLM) |

#### Shared (`agents/shared/`)

| File | Purpose |
|------|---------|
| `base_agent.py` | Abstract base with `execute(task) -> AgentResult` |
| `models.py` | Task, AgentResult, Artifacts, CommandResult, ErrorInfo, enums |

### 1.4 Contracts

```
ai-system/contracts/
```

| File | Purpose | Status |
|------|---------|--------|
| `task.schema.json` | Task format (task_id, goal, role, inputs, steps) | IMPLEMENTED |
| `result.schema.json` | Agent result format (artifacts, errors, status) | IMPLEMENTED |
| `validation.schema.json` | Validation check format | IMPLEMENTED |

### 1.5 System State

```
ai-system/state/
```

| File | Purpose |
|------|---------|
| `task.todo.json` | Task queue |
| `agents.state.json` | Agent readiness and status |
| `routing.state.json` | Current routing decisions |

### 1.6 Logs

```
ai-system/logs/
```

| Path | Purpose |
|------|---------|
| `ailog.md` | Session-level log |
| `tasks/` | Per-task execution logs |
| `snapshots/` | Pre-change snapshots (when snapshot_manager is implemented) |

### 1.7 Scripts (CLI)

```
ai-system/scripts/
```

| File | Purpose | Status |
|------|---------|--------|
| `run_task.py` | Run a task through the full pipeline | IMPLEMENTED |
| `replay_task.py` | Replay a failed/completed task | IMPLEMENTED |
| `export_logs.py` | Export logs to markdown report | IMPLEMENTED |

### 1.8 Validations

```
ai-system/validations/
```

| File | Purpose | Status |
|------|---------|--------|
| `code_checks.py` | Code quality checks (syntax, lint, tests) | IMPLEMENTED |
| `deploy_checks.py` | Deployment checks (port, process, docker) | IMPLEMENTED |
| `ui_checks.py` | UI checks (placeholder) | IMPLEMENTED |

Note: these modules are standalone helpers. The core `validator.py` runs its own generic checks; these are not wired into the main pipeline yet.

---

## 2. Task Lifecycle (Full)

```
 1. User -> Task (goal, constraints, repo)

 2. AIL Controller:
    - normalize task
    - assign task_id
    - select policy          [PLANNED]
    - check capabilities     [PLANNED]

 3. FileReader:              [PLANNED]
    - read context files

 4. Planner:
    - classify: code / exec / hybrid
    - generate steps

 5. Router:
    - assign agents to steps
    - dispatch in order: opencode -> openclaw

 6. OpenCode:
    - generate via LLM:
      - files_changed
      - commands
      - summary

 7. SnapshotManager:         [PLANNED]
    - save current state

 8. Apply:                   [PLANNED]
    - PatchApplier / FileApplier

 9. OpenClaw:
    - execute commands (subprocess, allowlist)
    - return exit codes, stdout, stderr

10. Validator:
    - check result validity
    - gates / handoff / capability / policy  [partially PLANNED]

11. Decision:
    - success -> done
    - partial -> retry (up to max_retries)
    - error   -> failed (+ rollback via SnapshotManager) [PLANNED]
```

---

## 3. Constraints

### 3.1 Capabilities (per-agent)

| Agent | Can | Cannot |
|-------|-----|--------|
| OpenCode | Generate code, suggest commands | Write files, execute commands |
| OpenClaw | Execute allowlisted commands | Generate code, set strategy |
| AIL | Orchestrate, validate, decide | Execute directly |

### 3.2 Policy Modes (PLANNED)

| Mode | Behavior |
|------|----------|
| `safe` | Strict allowlist, no destructive ops |
| `dev` | Balanced — allows more commands |
| `aggressive` | Extended access (explicit opt-in) |

### 3.3 Security (OpenClaw Executor)

- 18 allowlisted binaries (python, node, npm, docker, ls, pwd, echo, etc.)
- Blocked shell operators: `;`, `&&`, `||`, `|`, `>`, `>>`, `<`, backticks, `$()`
- Blocked patterns: `sudo`, `shutdown`, `reboot`, `mkfs`, fork bombs
- All commands via `shlex.split` + `subprocess.run(shell=False)`
- Per-command timeout (default 20s)

---

## 4. Task Types

| Type | Description | Agent |
|------|-------------|-------|
| `code` | Code generation, file changes | OpenCode |
| `exec` | Shell commands, deploy, services | OpenClaw |
| `hybrid` | Full cycle: code + execute | OpenCode -> OpenClaw |

---

## 5. Current State

### Implemented

- Core orchestration (AIL Controller, Planner, Router, Validator, Memory)
- Agents (OpenCode with LLM transports, OpenClaw with safe executor)
- Shared models and base agent
- JSON contracts (task, result, validation)
- Validation helpers (code, deploy, ui)
- CLI scripts (run, replay, export)
- State management files

### Not Yet Implemented

- `policy.py` — execution policy engine
- `capabilities.py` — per-agent capability registry
- `file_reader.py` — sandboxed file reading
- `file_applier.py` — safe file writing
- `patch_applier.py` — targeted diffs
- `snapshot_manager.py` — snapshot + rollback
- Wiring `validations/*.py` into core `Validator`

---

## 6. Roadmap

| Step | Name | Description | Status |
|------|------|-------------|--------|
| 13 | Task Manifest | Execution record per task (planned, changed, executed) | DONE |
| 14 | Multi-step Tasks | Task chains with dependencies | DONE |
| 15 | Agent Memory | Learning from past executions | DONE |
| 16 | External Tools | git, docker, cloud API integration | DONE |
| 17 | UI Layer | Pipeline visualization, task management | PLANNED |

---

## 7. Fundamental Principle

```
No agent makes final decisions.
Only AIL controls the system.
```

---

## Quick Start

```bash
cd ai-system

# Run a task
python scripts/run_task.py "Write a healthcheck function" --repo ../

# Run with constraints
python scripts/run_task.py "Build and deploy" --constraint "do not break api" --repo ../

# Replay a failed task
python scripts/replay_task.py tasks/failed/task-00123.json --force

# Export logs
python scripts/export_logs.py --output report.md
```

## Environment

```bash
cp .env.example .env
# Set: OPENAI_API_KEY, ANTHROPIC_API_KEY, LLM_PROVIDER (openai/anthropic/mock)
```
