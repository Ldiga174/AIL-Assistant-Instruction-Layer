#!/usr/bin/env python3
"""
Run a task through the AIL system.

Two modes:
  1. From JSON file:  python scripts/run_task.py --file tasks/incoming/task-001.json
  2. From CLI goal:   python scripts/run_task.py "Написать функцию healthcheck"

The JSON file must match contracts/task.schema.json.
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
    parser = argparse.ArgumentParser(description="Run a task through AIL")
    parser.add_argument("goal", nargs="?", default=None, help="Task goal (text mode)")
    parser.add_argument("--file", "-f", help="Path to task JSON file")
    parser.add_argument("--repo", default=".", help="Path to the target repository")
    parser.add_argument(
        "--constraint", action="append", default=[],
        help="Constraint (can be repeated)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if not args.file and not args.goal:
        parser.error("Provide either a goal text or --file path")

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    controller = AILController()

    if args.file:
        task_path = Path(args.file)
        if not task_path.exists():
            print(f"Error: file not found: {task_path}", file=sys.stderr)
            sys.exit(1)
        with open(task_path, "r", encoding="utf-8") as f:
            task_data = json.load(f)
        task = Task.from_dict(task_data)
        print(f"Loaded task from {task_path}")
        print(f"  task_id: {task.task_id}")
        print(f"  goal:    {task.goal}")
        print(f"  role:    {task.role.value}")
        print()
        result = controller.handle_task(task)
    else:
        result = controller.handle_goal(
            args.goal,
            repo=args.repo,
            constraints=args.constraint or None,
        )

    print()
    print("=" * 60)
    print("AIL TASK RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    status = result.get("status", "unknown")
    print()
    if status == "done":
        print(">>> TASK COMPLETED SUCCESSFULLY")
    else:
        print(f">>> TASK FINISHED WITH STATUS: {status}")


if __name__ == "__main__":
    main()
