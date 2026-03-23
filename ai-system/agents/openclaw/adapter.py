"""
OpenClaw adapter — bridge between AIL and the shell executor.

OpenClaw is an executor, not a thinker. No LLM call needed.
The adapter extracts commands from the task and passes them
to the executor for safe, controlled execution.

Command sources (checked in priority order):
  1. task.inputs.commands — primary (set by AIL handoff from OpenCode)
  2. task.inputs.context["commands"] — fallback for compatibility
  3. task.steps[].action — last resort from step definitions
"""

from __future__ import annotations

import logging

from agents.shared.base_agent import BaseAgent
from agents.shared.models import AgentName, AgentResult, ErrorInfo, ResultStatus, Task
from agents.openclaw.executor import OpenClawExecutor

logger = logging.getLogger(__name__)


class OpenClawAdapter(BaseAgent):
    """
    Adapter connecting AIL to the OpenClaw shell executor.

    Flow: Task -> extract commands -> executor.execute() -> AgentResult
    """

    def __init__(self) -> None:
        super().__init__(AgentName.OPENCLAW)
        self.executor = OpenClawExecutor()

    def execute(self, task: Task) -> AgentResult:
        logger.info("[OpenClaw] task %s: %s", task.task_id, task.goal)

        commands = self._extract_commands(task)

        if not commands:
            logger.warning("[OpenClaw] No commands found in task %s", task.task_id)
            return AgentResult(
                task_id=task.task_id,
                agent=AgentName.OPENCLAW,
                status=ResultStatus.ERROR,
                errors=[ErrorInfo(
                    message="No commands to execute",
                    code="NO_COMMANDS",
                    details="No commands in inputs.commands, context.commands, or steps",
                )],
                notes="exec step failed: no commands provided",
            )

        logger.info("[OpenClaw] Extracted %d command(s): %s", len(commands), commands)
        return self.executor.execute(task, commands)

    @staticmethod
    def _extract_commands(task: Task) -> list[str]:
        """
        Extract commands in priority order:
          1. task.inputs.commands (primary — set by AIL handoff)
          2. task.inputs.context["commands"] (fallback)
          3. task.steps[].action (last resort)
        """
        if task.inputs.commands:
            logger.info("[OpenClaw] Source: task.inputs.commands")
            return list(task.inputs.commands)

        ctx_commands = task.inputs.context.get("commands")
        if isinstance(ctx_commands, list) and ctx_commands:
            logger.info("[OpenClaw] Source: task.inputs.context['commands'] (fallback)")
            return [str(c) for c in ctx_commands if c]

        commands: list[str] = []
        for step in task.steps:
            if step.agent != AgentName.OPENCLAW:
                continue
            action = step.action
            if action.startswith("run:"):
                commands.append(action[len("run:"):].strip())
            elif action.strip():
                commands.append(action.strip())

        if commands:
            logger.info("[OpenClaw] Source: task.steps (last resort)")
        return commands
