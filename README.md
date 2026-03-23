# AIL — Assistant Instruction Layer

Трёхуровневая система управления AI-агентами для автоматизации разработки и операций.

## Архитектура

```
┌─────────────────────────────────────────────────────┐
│                     OWNER                           │
│        (ставит цель, утверждает результат)          │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                AIL / President                       │
│  ┌──────────┐ ┌────────┐ ┌───────────┐ ┌────────┐  │
│  │ Planner  │ │ Router │ │ Validator │ │ Memory │  │
│  └──────────┘ └────────┘ └───────────┘ └────────┘  │
│         Единственная точка принятия решений          │
└───────────┬─────────────────────┬───────────────────┘
            │                     │
┌───────────▼──────────┐ ┌───────▼────────────────────┐
│     OpenCode         │ │       OpenClaw              │
│   (программист)      │ │  (операционный исполнитель) │
│                      │ │                             │
│ • анализ кодовой базы│ │ • выполнение команд ОС     │
│ • создание кода      │ │ • запуск сборки/тестов     │
│ • исправление багов  │ │ • деплой                   │
│ • подготовка команд  │ │ • проверка результата      │
└──────────────────────┘ └─────────────────────────────┘
```

## Принцип

> **OpenCode** не выполняет системные команды.
> **OpenClaw** не определяет стратегию.
> **AIL** управляет обоими и остаётся единственной точкой принятия решений.

## Типы задач

| Тип | Описание | Агент |
|-----|----------|-------|
| `code` | Написание/изменение кода, проектирование | OpenCode |
| `exec` | Команды ОС, деплой, запуск сервисов | OpenClaw |
| `hybrid` | Код + операции (сборка + деплой) | Оба |

## Жизненный цикл задачи

```
1. Owner формулирует цель
2. AIL создаёт task_id и классифицирует: code / exec / hybrid
3. AIL создаёт план шагов
4. AIL отправляет шаги агентам (OpenCode / OpenClaw)
5. Агенты возвращают структурированный результат
6. AIL валидирует результат
7. При ошибке — цикл исправления (до max_retries)
8. При успехе — задача завершена
```

## Структура проекта

```
ai-system/
├── project.init.md          — описание архитектуры
├── .env.example             — пример конфигурации
├── logs/                    — логи выполнения
│   ├── ailog.md
│   ├── sessions/
│   └── tasks/
├── state/                   — runtime-состояние
│   ├── task.todo.json
│   ├── agents.state.json
│   └── routing.state.json
├── contracts/               — JSON-схемы контрактов
│   ├── task.schema.json
│   ├── result.schema.json
│   └── validation.schema.json
├── core/                    — ядро AIL
│   ├── ail_controller.py    — главный контроллер (President)
│   ├── router.py            — маршрутизация задач
│   ├── validator.py         — валидация результатов
│   ├── planner.py           — планирование шагов
│   └── memory.py            — управление состоянием
├── agents/                  — агенты-исполнители
│   ├── opencode/            — программист
│   │   ├── adapter.py
│   │   ├── executor.py
│   │   └── prompts/
│   ├── openclaw/            — оператор
│   │   ├── adapter.py
│   │   ├── executor.py
│   │   └── prompts/
│   └── shared/              — общая база
│       ├── base_agent.py
│       └── models.py
├── tasks/                   — жизненный цикл задач
│   ├── incoming/
│   ├── running/
│   ├── failed/
│   └── done/
├── validations/             — модули проверки
│   ├── code_checks.py
│   ├── ui_checks.py
│   └── deploy_checks.py
└── scripts/                 — CLI-скрипты
    ├── run_task.py
    ├── replay_task.py
    └── export_logs.py
```

## Быстрый старт

```bash
cd ai-system

# Запустить задачу
python scripts/run_task.py "Написать функцию healthcheck" --repo ../

# Запустить задачу с ограничениями
python scripts/run_task.py "Собрать и задеплоить сайт" --constraint "не ломать api" --repo ../

# Переиграть задачу
python scripts/replay_task.py tasks/failed/task-00123.json --force

# Экспортировать логи
python scripts/export_logs.py --output report.md
```

## Контракт взаимодействия

### Формат задачи
```json
{
  "task_id": "task-00001",
  "goal": "Собрать и задеплоить сайт",
  "role": "hybrid",
  "inputs": {
    "repo": "./project",
    "constraints": ["не ломать существующий api"]
  },
  "expected_output": ["updated_files", "run_commands", "summary"],
  "status": "pending"
}
```

### Формат результата
```json
{
  "task_id": "task-00001",
  "agent": "opencode",
  "status": "success",
  "artifacts": {
    "files_changed": ["app/main.py", "docker-compose.yml"],
    "commands": ["docker compose up -d --build"]
  },
  "notes": "Добавлен endpoint healthcheck",
  "errors": []
}
```

## Первый практический этап

Реализовано минимальное ядро:
- [x] AIL Controller (President)
- [x] Router (маршрутизация code/exec/hybrid)
- [x] Planner (классификация и планирование)
- [x] Validator (проверка результатов)
- [x] Memory (состояние и логирование)
- [x] OpenCode adapter + executor
- [x] OpenClaw adapter + executor
- [x] JSON-контракты (task, result, validation)
- [x] Базовая валидация (code, ui, deploy)
- [x] CLI-скрипты (run, replay, export)
