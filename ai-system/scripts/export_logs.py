#!/usr/bin/env python3
"""
Export AIL logs and task history to a single report.

Usage:
  python scripts/export_logs.py
  python scripts/export_logs.py --output report.md
  python scripts/export_logs.py --format json --output report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_DIR = Path(__file__).resolve().parent.parent


def collect_task_files() -> dict[str, list[dict]]:
    """Collect all task JSON files grouped by stage."""
    stages = ["incoming", "running", "done", "failed"]
    result: dict[str, list[dict]] = {}
    for stage in stages:
        stage_dir = BASE_DIR / "tasks" / stage
        tasks = []
        if stage_dir.exists():
            for fp in sorted(stage_dir.glob("*.json")):
                with open(fp, "r", encoding="utf-8") as f:
                    tasks.append(json.load(f))
        result[stage] = tasks
    return result


def collect_logs() -> str:
    """Read the main AIL log."""
    log_path = BASE_DIR / "logs" / "ailog.md"
    if log_path.exists():
        return log_path.read_text(encoding="utf-8")
    return "(no logs)"


def collect_task_logs() -> list[tuple[str, str]]:
    """Read all per-task logs."""
    logs_dir = BASE_DIR / "logs" / "tasks"
    result = []
    if logs_dir.exists():
        for fp in sorted(logs_dir.glob("*.md")):
            result.append((fp.stem, fp.read_text(encoding="utf-8")))
    return result


def export_markdown() -> str:
    lines = [
        f"# AIL System Report",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
    ]

    lines.append("## Main Log")
    lines.append("```")
    lines.append(collect_logs())
    lines.append("```")
    lines.append("")

    task_files = collect_task_files()
    for stage, tasks in task_files.items():
        lines.append(f"## Tasks: {stage} ({len(tasks)})")
        if not tasks:
            lines.append("_(none)_")
        for t in tasks:
            lines.append(f"- **{t.get('task_id', '?')}** — {t.get('goal', '?')} [{t.get('status', '?')}]")
        lines.append("")

    task_logs = collect_task_logs()
    if task_logs:
        lines.append("## Task Logs")
        for name, content in task_logs:
            lines.append(f"### {name}")
            lines.append(content)
            lines.append("")

    return "\n".join(lines)


def export_json() -> str:
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "main_log": collect_logs(),
        "tasks": collect_task_files(),
        "task_logs": {name: content for name, content in collect_task_logs()},
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export AIL logs and task history")
    parser.add_argument("--output", "-o", help="Output file path (stdout if omitted)")
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    args = parser.parse_args()

    if args.format == "json":
        content = export_json()
    else:
        content = export_markdown()

    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(content)


if __name__ == "__main__":
    main()
