# AIL System — Project Init

## Architecture

**AIL (Assistant Instruction Layer)** — трёхуровневая система управления задачами:

| Role | Module | Responsibility |
|------|--------|---------------|
| **President** | AIL Controller | Планирование, маршрутизация, валидация, принятие решений |
| **Programmer** | OpenCode | Анализ кода, создание/изменение файлов, подготовка команд сборки |
| **Operator** | OpenClaw | Выполнение ОС-команд, запуск сервисов, взаимодействие с UI |

## Core Principle

> Ни один агент не является верховным управляющим.
> Верховный управляющий — только AIL.

## Task Lifecycle

```
Owner → AIL (plan) → Router (classify) → Agent (execute) → Validator (check) → AIL (decide)
```

## Quick Start

```bash
cd ai-system
python scripts/run_task.py "Написать функцию healthcheck" --repo ../
python scripts/run_task.py "Запустить тесты" --repo ../
python scripts/export_logs.py
```

## File Structure

```
ai-system/
├── core/           — AIL Controller, Router, Validator, Planner, Memory
├── agents/         — OpenCode, OpenClaw adapters + shared base
├── contracts/      — JSON schemas for task/result/validation
├── state/          — Runtime state files
├── tasks/          — Task lifecycle folders (incoming/running/done/failed)
├── validations/    — Code, UI, Deploy check modules
├── scripts/        — CLI entry points
└── logs/           — Session and task logs
```

## Contracts

All agent communication uses structured JSON contracts:
- `contracts/task.schema.json` — task format
- `contracts/result.schema.json` — result format
- `contracts/validation.schema.json` — validation format
