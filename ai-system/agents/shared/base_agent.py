"""
Base agent interface.

Every agent (OpenCode, OpenClaw, future agents) must inherit from
BaseAgent and implement `execute`.  AIL dispatches tasks through
this uniform interface, keeping the controller agent-agnostic.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

from agents.shared.models import (
    AgentName,
    AgentResult,
    Artifacts,
    ErrorInfo,
    ResultStatus,
    Task,
)

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base for all AIL-managed agents."""

    name: AgentName

    def __init__(self, name: AgentName) -> None:
        self.name = name

    @abstractmethod
    def execute(self, task: Task) -> AgentResult:
        """Run the task and return a structured result."""

    def _success(
        self,
        task: Task,
        *,
        artifacts: Artifacts | None = None,
        notes: str = "",
        duration_ms: int = 0,
    ) -> AgentResult:
        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status=ResultStatus.SUCCESS,
            artifacts=artifacts or Artifacts(),
            notes=notes,
            duration_ms=duration_ms,
        )

    def _failure(
        self,
        task: Task,
        *,
        errors: list[ErrorInfo] | None = None,
        notes: str = "",
        duration_ms: int = 0,
    ) -> AgentResult:
        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            status=ResultStatus.FAILED,
            errors=errors or [],
            notes=notes,
            duration_ms=duration_ms,
        )

    def safe_execute(self, task: Task) -> AgentResult:
        """Wrapper that catches unexpected exceptions."""
        t0 = time.monotonic()
        try:
            result = self.execute(task)
            result.duration_ms = int((time.monotonic() - t0) * 1000)
            return result
        except Exception as exc:
            duration = int((time.monotonic() - t0) * 1000)
            logger.exception("Agent %s crashed on task %s", self.name.value, task.task_id)
            return self._failure(
                task,
                errors=[ErrorInfo(message=str(exc), code="AGENT_CRASH")],
                notes=f"Unhandled exception in {self.name.value}",
                duration_ms=duration,
            )
