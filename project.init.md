# AI PROJECT INIT

## Project

**AIL (Assistant Instruction Layer)** — controlled AI execution pipeline.
Three-tier architecture: AIL (President) orchestrates OpenCode (Programmer) and OpenClaw (Operator).

## AI Session Protocol

1. Read this file on session start
2. Read `ail.errors.md` — mandatory no-repeat error register
3. Read `ai-system/project.init.md` — full engineering map
4. Run prestart checklist (below) if environment is fresh; log results to `ailog.md`
5. If checklist fails — stop, report, wait for resolution
6. On success — open `ailog.md`, read current session state
7. Open `task.todo.json` and work from the top task
8. After each task: verify, log to `ailog.md`, record in `snapshot.success.md`
9. On session end: write summary to `ailog.md`, carry over incomplete tasks

## Prestart Checklist

- [ ] Python 3.10+ available
- [ ] Node.js 22+ available
- [ ] pnpm available (for OpenClaw)
- [ ] `ai-system/.env` configured (LLM keys)
- [ ] `ai-system/project.init.md` exists and readable
- [ ] `ailog.md` exists
- [ ] `task.todo.json` exists

## Key Files

| File | Purpose |
|------|---------|
| `project.init.md` | This file — AI entry point |
| `ai-system/project.init.md` | Full engineering map (architecture, status, roadmap) |
| `ARCHITECTURE.md` | High-level architecture diagram |
| `README.md` | Project overview for GitHub |
| `ailog.md` | Session log |
| `ail.errors.md` | Project-specific no-repeat error register |
| `ail.errors.common.template.md` | Reusable template for global AIL |
| `task.todo.json` | Task queue |
| `ai.meta.json` | AI behavior rules |
| `prestart.checklist` | Detailed prestart checks |

## Project Structure

```
AIL-Assistant-Instruction-Layer/
+-- ai-system/              AIL execution engine (Python)
|   +-- core/               Controller, Planner, Router, Validator, Memory
|   +-- agents/             OpenCode (LLM), OpenClaw (shell), shared models
|   +-- contracts/          JSON schemas
|   +-- state/              Runtime state
|   +-- validations/        Check modules
|   +-- scripts/            CLI entry points
|   +-- logs/               Execution logs
|
+-- .github/workflows/      CI/CD (GitHub Actions -> Cloud Run)
+-- Dockerfile              Container build
+-- ARCHITECTURE.md         Architecture diagram
+-- README.md               Project overview
```

## Related Repositories

| Repo | Description |
|------|-------------|
| `../openclaw/` (sibling) | OpenClaw — multi-channel AI gateway (TypeScript monorepo) |
| This repo | AIL — orchestration and instruction layer |

## Fundamental Principle

> No agent makes final decisions. Only AIL controls the system.
