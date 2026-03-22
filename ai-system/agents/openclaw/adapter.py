"""
OpenClaw adapter — translates AIL tasks into operational actions.

Responsibilities:
  - execute OS commands
  - open IDE, terminal, browser, panels
  - run build, tests, deploy
  - interact with UI
  - verify visible results
  - report actual execution status
"""

from __future__ import annotations

import logging

from agents.shared.base_agent import BaseAgent
from agents.shared.models import AgentName, AgentResult, Task
from agents.openclaw.executor import OpenClawExecutor

logger = logging.getLogger(__name__)


class OpenClawAdapter(BaseAgent):
    """Adapter that wraps the OpenClaw executor behind the BaseAgent interface."""

    def __init__(self) -> None:
        super().__init__(AgentName.OPENCLAW)
        self.executor = OpenClawExecutor()

    def execute(self, task: Task) -> AgentResult:
        logger.info("[OpenClaw] Received task %s: %s", task.task_id, task.goal)
        return self.executor.run(task)
