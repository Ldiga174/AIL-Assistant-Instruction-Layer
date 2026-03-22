"""
AIL Planner — breaks a high-level goal into executable steps.

The planner receives a raw user goal and produces a Task
with classified role and ordered steps.

Current implementation uses simple heuristics.
Future versions may delegate planning to an LLM.
"""

from __future__ import annotations

import logging
import re

from agents.shared.models import (
    AgentName,
    Task,
    TaskInputs,
    TaskRole,
    TaskStep,
)

logger = logging.getLogger(__name__)

EXEC_KEYWORDS = [
    "запусти", "deploy", "деплой", "открой", "restart",
    "stop", "start", "build", "run", "execute",
    "выполни", "собери", "проверь сервис",
]

CODE_KEYWORDS = [
    "напиши", "создай файл", "исправь", "рефактор",
    "добавь функцию", "код", "write", "fix", "refactor",
    "implement", "create file", "add endpoint",
]


class Planner:
    """Produces a Task from a raw goal string."""

    def plan(
        self,
        goal: str,
        *,
        repo: str = ".",
        constraints: list[str] | None = None,
    ) -> Task:
        role = self._classify(goal)
        steps = self._generate_steps(goal, role)

        task = Task(
            goal=goal,
            role=role,
            inputs=TaskInputs(
                repo=repo,
                constraints=constraints or [],
            ),
            expected_output=self._expected_outputs(role),
            steps=steps,
        )
        logger.info(
            "Planned task %s: role=%s steps=%d",
            task.task_id, role.value, len(steps),
        )
        return task

    def _classify(self, goal: str) -> TaskRole:
        goal_lower = goal.lower()
        has_code = any(kw in goal_lower for kw in CODE_KEYWORDS)
        has_exec = any(kw in goal_lower for kw in EXEC_KEYWORDS)

        if has_code and has_exec:
            return TaskRole.HYBRID
        if has_exec:
            return TaskRole.EXEC
        return TaskRole.CODE

    def _generate_steps(self, goal: str, role: TaskRole) -> list[TaskStep]:
        if role == TaskRole.CODE:
            return [
                TaskStep(step_id="s1", action=goal, agent=AgentName.OPENCODE),
            ]
        elif role == TaskRole.EXEC:
            return [
                TaskStep(step_id="s1", action=goal, agent=AgentName.OPENCLAW),
            ]
        else:
            return [
                TaskStep(step_id="s1", action=f"[code] {goal}", agent=AgentName.OPENCODE),
                TaskStep(
                    step_id="s2",
                    action=f"[exec] Verify and run: {goal}",
                    agent=AgentName.OPENCLAW,
                    depends_on=["s1"],
                ),
            ]

    @staticmethod
    def _expected_outputs(role: TaskRole) -> list[str]:
        if role == TaskRole.CODE:
            return ["updated_files", "summary"]
        elif role == TaskRole.EXEC:
            return ["run_commands", "summary"]
        else:
            return ["updated_files", "run_commands", "summary"]
