# AIL — Architecture

## System Overview

```
+-----------------------------------------------------+
|                      OWNER                           |
|        (sets goal, approves result)                  |
+------------------------+----------------------------+
                         |
+------------------------v----------------------------+
|                  AIL / President                     |
|  +----------+ +--------+ +-----------+ +--------+   |
|  | Planner  | | Router | | Validator | | Memory |   |
|  +----------+ +--------+ +-----------+ +--------+   |
|       Sole decision-making authority                 |
+-----------+-----------------------+-----------------+
            |                       |
+-----------v----------+ +---------v------------------+
|     OpenCode         | |       OpenClaw              |
|   (programmer)       | |  (operator)                 |
|                      | |                             |
| - code analysis      | | - OS command execution     |
| - code generation    | | - build / test / deploy    |
| - bug fixing         | | - result reporting         |
| - command suggestion | | - allowlist enforcement    |
+----------------------+ +----------------------------+
```

## Core Principle

> **OpenCode** does not execute system commands.
> **OpenClaw** does not generate code or set strategy.
> **AIL** orchestrates both and remains the sole decision-maker.

## Task Flow

```
1. Owner defines goal
2. AIL classifies task: code / exec / hybrid
3. AIL creates execution plan (steps)
4. AIL dispatches steps to agents (OpenCode -> OpenClaw)
5. Agents return structured results
6. AIL validates results
7. On failure: retry loop (up to max_retries)
8. On success: task complete
```

## Repository Structure

```
AIL-Assistant-Instruction-Layer/
|
+-- ai-system/                  <-- AIL execution engine (Python)
|   +-- core/                   AIL Controller, Router, Planner, Validator, Memory
|   +-- agents/                 OpenCode (LLM) + OpenClaw (shell) + shared models
|   +-- contracts/              JSON schemas for task/result/validation
|   +-- state/                  Runtime state (task queue, agent state, routing)
|   +-- validations/            Code, deploy, UI check modules
|   +-- scripts/                CLI: run_task, replay_task, export_logs
|   +-- logs/                   Session and task logs
|   +-- project.init.md         Full engineering map (AI entry point)
|   +-- .env.example            Environment config template
|
+-- ARCHITECTURE.md             This file
+-- README.md                   Project overview
+-- project.init.md             AI session entry point
+-- ai.meta.json                AI behavior rules
```

## Relation to OpenClaw

The AIL Python agent `agents/openclaw/` is a **safe shell executor** within the AIL pipeline.

The external OpenClaw project (sibling repository) is a **multi-channel AI gateway** — a TypeScript monorepo with CLI, extensions, plugin SDK, native apps, and web UI. AIL serves as the orchestration and instruction layer that can work alongside or on top of OpenClaw's execution capabilities.

## Task Types

| Type | Description | Agent |
|------|-------------|-------|
| `code` | Code generation, file changes | OpenCode |
| `exec` | Shell commands, deploy, services | OpenClaw |
| `hybrid` | Full cycle: code then execute | Both (ordered) |

## Current Status

**Implemented:** Core orchestration, both agents, JSON contracts, validation helpers, CLI scripts, state management.

**Planned:** Policy engine, capability registry, file operations (read/write/patch/snapshot), task manifest, multi-step tasks, agent memory, external tool integration, UI layer.

See [ai-system/project.init.md](ai-system/project.init.md) for the full engineering map with per-module status and roadmap.
