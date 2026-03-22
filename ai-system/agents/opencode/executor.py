"""
OpenCode executor — the programming brain.

Current implementation: stub that returns realistic test artifacts.
Real AI-backed execution (LLM calls, tool use) will replace the
stub logic in Step 3.
"""

from __future__ import annotations

import logging
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
                errors=[ErrorInfo(
                    message=f"Repository path not found: {repo}",
                    code="REPO_NOT_FOUND",
                )],
                notes="code step failed: repo missing",
            )

        files_changed: list[str] = []
        commands: list[str] = []
        notes_parts: list[str] = []

        my_steps = [s for s in task.steps if s.agent == AgentName.OPENCODE]

        for step in my_steps:
            logger.info("[OpenCode] step %s: %s", step.step_id, step.action)

            files_changed.extend([
                f"{repo}/src/api/handler.py",
                f"{repo}/src/api/routes.py",
            ])
            commands.append("python -m pytest tests/")
            notes_parts.append(
                f"step {step.step_id}: created handler.py, updated routes.py"
            )

        if not my_steps:
            files_changed.append(f"{repo}/src/main.py")
            commands.append("python -m pytest tests/")
            notes_parts.append(f"Processed goal: {task.goal}")

        return AgentResult(
            task_id=task.task_id,
            agent=AgentName.OPENCODE,
            status=ResultStatus.SUCCESS,
            artifacts=Artifacts(
                files_changed=files_changed,
                commands=commands,
            ),
            notes="code step complete; " + "; ".join(notes_parts),
        )
