"""
OpenCode adapter — translates AIL tasks into code-oriented actions.

Responsibilities:
  - analyse the codebase
  - design a solution
  - create / modify files
  - write code
  - fix bugs
  - prepare build / test / run commands
  - return a structured result
"""

from __future__ import annotations

import logging

from agents.shared.base_agent import BaseAgent
from agents.shared.models import AgentName, AgentResult, Task
from agents.opencode.executor import OpenCodeExecutor

logger = logging.getLogger(__name__)


class OpenCodeAdapter(BaseAgent):
    """Adapter that wraps the OpenCode executor behind the BaseAgent interface."""

    def __init__(self) -> None:
        super().__init__(AgentName.OPENCODE)
        self.executor = OpenCodeExecutor()

    def execute(self, task: Task) -> AgentResult:
        logger.info("[OpenCode] Received task %s: %s", task.task_id, task.goal)
        return self.executor.run(task)
