"""
AIL Memory — persistent state management.

Handles reading/writing JSON state files:
  - state/task.todo.json   — active task queue
  - state/agents.state.json — agent status registry
  - state/routing.state.json — routing decisions log

Also manages task lifecycle folders:
  - tasks/incoming/
  - tasks/running/
  - tasks/failed/
  - tasks/done/
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent


def _state_path(filename: str) -> Path:
    return BASE_DIR / "state" / filename


def _tasks_dir(stage: str) -> Path:
    d = BASE_DIR / "tasks" / stage
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.debug("Wrote %s", path)


def load_task_queue() -> list[dict[str, Any]]:
    data = _read_json(_state_path("task.todo.json"))
    return data.get("tasks", []) if isinstance(data, dict) else data


def save_task_queue(tasks: list[dict[str, Any]]) -> None:
    _write_json(_state_path("task.todo.json"), {"tasks": tasks})


def load_agents_state() -> dict[str, Any]:
    return _read_json(_state_path("agents.state.json"))


def save_agents_state(state: dict[str, Any]) -> None:
    _write_json(_state_path("agents.state.json"), state)


def load_routing_state() -> dict[str, Any]:
    return _read_json(_state_path("routing.state.json"))


def save_routing_state(state: dict[str, Any]) -> None:
    _write_json(_state_path("routing.state.json"), state)


def persist_task(task_dict: dict[str, Any], stage: str) -> Path:
    """Save a task to the appropriate lifecycle folder."""
    task_id = task_dict["task_id"]
    dest = _tasks_dir(stage) / f"{task_id}.json"
    _write_json(dest, task_dict)
    return dest


def move_task(task_id: str, from_stage: str, to_stage: str) -> Path | None:
    """Move a task file between lifecycle folders."""
    src = _tasks_dir(from_stage) / f"{task_id}.json"
    if not src.exists():
        logger.warning("Task file %s not found in %s", task_id, from_stage)
        return None
    dest = _tasks_dir(to_stage) / f"{task_id}.json"
    shutil.move(str(src), str(dest))
    logger.info("Moved task %s: %s -> %s", task_id, from_stage, to_stage)
    return dest


def append_log(message: str) -> None:
    """Append a line to logs/ailog.md."""
    log_path = BASE_DIR / "logs" / "ailog.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"- [{ts}] {message}\n")


def save_session_log(session_id: str, content: str) -> Path:
    """Save a session log file."""
    path = BASE_DIR / "logs" / "sessions" / f"{session_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def save_task_log(task_id: str, content: str) -> Path:
    """Save a per-task log file."""
    path = BASE_DIR / "logs" / "tasks" / f"{task_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
