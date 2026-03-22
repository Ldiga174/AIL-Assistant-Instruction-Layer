#!/usr/bin/env python3
"""
Replay a previously executed task from a task JSON file.

Usage:
  python scripts/replay_task.py tasks/done/task-00123.json
  python scripts/replay_task.py tasks/failed/task-00456.json --force
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.shared.models import Task
from core.ail_controller import AILController


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a task through AIL")
    parser.add_argument("task_file", help="Path to task JSON file")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reset retry count and force re-execution",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    task_path = Path(args.task_file)
    if not task_path.exists():
        print(f"Error: task file not found: {task_path}", file=sys.stderr)
        sys.exit(1)

    with open(task_path, "r", encoding="utf-8") as f:
        task_data = json.load(f)

    task = Task.from_dict(task_data)

    if args.force:
        task.retry_count = 0
        task.status = "pending"

    print(f"Replaying task {task.task_id}: {task.goal}")
    print(f"  Role: {task.role.value}")
    print(f"  Steps: {len(task.steps)}")
    print()

    controller = AILController()
    result = controller.handle_goal(
        task.goal,
        repo=task.inputs.repo,
        constraints=task.inputs.constraints or None,
    )

    print("\n" + "=" * 60)
    print("REPLAY RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
