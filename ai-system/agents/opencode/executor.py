"""
OpenCode executor — the programming brain.

This module contains the actual logic that OpenCode uses to:
  1. Analyse the task
  2. Read / inspect project files
  3. Generate or modify code
  4. Prepare shell commands for build/test
  5. Return artefacts to AIL

The current implementation is a *synchronous skeleton* that returns
structured results.  Real AI-backed execution (LLM calls, tool use)
will be plugged in here.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from agents.shared.models import (
    AgentName,
    AgentResult,
    Artifacts,
    ErrorInfo,
    ResultStatus,
    Task,
)

logger = logging.getLogger(__name__)


class OpenCodeExecutor:
    """Stateless executor: receives a Task, returns an AgentResult."""

    def run(self, task: Task) -> AgentResult:
        repo = Path(task.inputs.repo).resolve()
        if not repo.is_dir():
            return AgentResult(
                task_id=task.task_id,
                agent=AgentName.OPENCODE,
                status=ResultStatus.FAILED,
                errors=[ErrorInfo(message=f"Repository path not found: {repo}", code="REPO_NOT_FOUND")],
            )

        files_changed: list[str] = []
        commands: list[str] = []
        notes_parts: list[str] = []

        for step in task.steps:
            if step.agent.value != "opencode":
                continue

            logger.info("[OpenCode] Executing step %s: %s", step.step_id, step.action)
            notes_parts.append(f"step {step.step_id}: {step.action} — acknowledged")

        if not task.steps:
            notes_parts.append(f"Goal acknowledged: {task.goal}")
            notes_parts.append(f"Repo: {repo}")
            notes_parts.append(f"Constraints: {', '.join(task.inputs.constraints) or 'none'}")

        return AgentResult(
            task_id=task.task_id,
            agent=AgentName.OPENCODE,
            status=ResultStatus.SUCCESS,
            artifacts=Artifacts(
                files_changed=files_changed,
                commands=commands,
            ),
            notes="; ".join(notes_parts),
        )
