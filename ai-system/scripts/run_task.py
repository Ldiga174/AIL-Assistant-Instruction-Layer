#!/usr/bin/env python3
"""
Run a task through the AIL system.

Usage:
  python scripts/run_task.py "Написать функцию healthcheck"
  python scripts/run_task.py "Запустить тесты" --repo ./myproject
  python scripts/run_task.py "Собрать и задеплоить сайт" --constraint "не ломать api"
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.ail_controller import AILController


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a task through AIL")
    parser.add_argument("goal", help="Task goal in natural language")
    parser.add_argument("--repo", default=".", help="Path to the target repository")
    parser.add_argument(
        "--constraint",
        action="append",
        default=[],
        help="Constraint to pass to the agent (can be repeated)",
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

    controller = AILController()
    result = controller.handle_goal(
        args.goal,
        repo=args.repo,
        constraints=args.constraint or None,
    )

    print("\n" + "=" * 60)
    print("AIL TASK RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
