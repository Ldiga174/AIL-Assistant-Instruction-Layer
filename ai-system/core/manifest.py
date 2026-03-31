"""
AIL Manifest Manager — execution records for tasks.

Each completed task produces a manifest: a structured record of
what was planned, what changed, what was executed, and the outcome.
Like a git commit, but for AI execution.

Storage: manifests/<task_id>.manifest.json
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.shared.models import (
    AgentResult,
    ManifestExecution,
    ManifestPlan,
    Task,
    TaskManifest,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
MANIFESTS_DIR = BASE_DIR / "manifests"


def _gen_manifest_id(task_id: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"m-{task_id}-{ts}"


def build_manifest(
    task: Task,
    results: list[AgentResult],
    validation_summary: list[dict[str, Any]],
    decision: str,
    started_at: float,
) -> TaskManifest:
    """Build a TaskManifest from execution data."""
    elapsed = int((time.monotonic() - started_at) * 1000)
    now_iso = datetime.now(timezone.utc).isoformat()

    plan = ManifestPlan(
        role=task.role.value,
        steps=[
            {"step_id": s.step_id, "action": s.action, "agent": s.agent.value}
            for s in task.steps
        ],
        constraints=task.inputs.constraints,
    )

    executions: list[ManifestExecution] = []
    for r in results:
        executions.append(ManifestExecution(
            agent=r.agent.value,
            status=r.status.value,
            duration_ms=r.duration_ms,
            files_changed=r.artifacts.files_changed,
            files_deleted=r.artifacts.files_deleted,
            commands_executed=r.artifacts.commands,
            errors=[e.to_dict() for e in r.errors],
            notes=r.notes,
        ))

    return TaskManifest(
        manifest_id=_gen_manifest_id(task.task_id),
        task_id=task.task_id,
        goal=task.goal,
        plan=plan,
        executions=executions,
        validation=validation_summary,
        decision=decision,
        retry_count=task.retry_count,
        started_at=task.created_at,
        completed_at=now_iso,
        duration_ms=elapsed,
    )


def save_manifest(manifest: TaskManifest) -> Path:
    """Persist manifest to manifests/<task_id>.manifest.json."""
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    path = MANIFESTS_DIR / f"{manifest.task_id}.manifest.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)
    logger.info("Manifest saved: %s", path)
    return path


def load_manifest(task_id: str) -> TaskManifest | None:
    """Load a manifest by task_id."""
    path = MANIFESTS_DIR / f"{task_id}.manifest.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return TaskManifest.from_dict(data)


def list_manifests() -> list[dict[str, Any]]:
    """Return summary of all saved manifests, newest first."""
    if not MANIFESTS_DIR.exists():
        return []

    summaries: list[dict[str, Any]] = []
    for p in sorted(MANIFESTS_DIR.glob("*.manifest.json"), reverse=True):
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        summaries.append({
            "manifest_id": data["manifest_id"],
            "task_id": data["task_id"],
            "goal": data["goal"],
            "decision": data["decision"],
            "duration_ms": data.get("duration_ms", 0),
            "completed_at": data.get("completed_at", ""),
        })
    return summaries
