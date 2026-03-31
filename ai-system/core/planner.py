"""
AIL Planner — breaks a high-level goal into executable steps.

The planner receives a raw user goal and produces a Task
with classified role and ordered steps with dependencies.

Supports:
  - Single-step tasks (code or exec)
  - Multi-step hybrid tasks (code -> verify -> deploy)
  - Explicit step lists from task definitions
  - Dependency chains between steps
"""

from __future__ import annotations

import logging
from typing import Any

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

DEPLOY_KEYWORDS = [
    "deploy", "деплой", "publish", "release", "push",
]

TEST_KEYWORDS = [
    "test", "тест", "проверь", "verify", "check", "lint",
]


class Planner:
    """Produces a Task from a raw goal string."""

    def plan(
        self,
        goal: str,
        *,
        repo: str = ".",
        constraints: list[str] | None = None,
        steps: list[dict] | None = None,
        memory_hints: list[dict[str, Any]] | None = None,
    ) -> Task:
        role = self._classify(goal)

        if steps:
            task_steps = self._parse_explicit_steps(steps)
        else:
            task_steps = self._generate_steps(goal, role)

        extra_constraints = constraints or []
        if memory_hints:
            extra_constraints = list(extra_constraints)
            extra_constraints.extend(self._constraints_from_memory(memory_hints))

        task = Task(
            goal=goal,
            role=role,
            inputs=TaskInputs(
                repo=repo,
                constraints=extra_constraints,
            ),
            expected_output=self._expected_outputs(role),
            steps=task_steps,
        )
        logger.info(
            "Planned task %s: role=%s steps=%d",
            task.task_id, role.value, len(task_steps),
        )
        return task

    @staticmethod
    def _constraints_from_memory(
        memories: list[dict[str, Any]],
    ) -> list[str]:
        """Derive constraints from past execution memories."""
        hints: list[str] = []
        for mem in memories:
            if mem.get("decision") == "failed" and mem.get("errors"):
                err_summary = "; ".join(mem["errors"][:2])
                hints.append(
                    f"[memory] Similar task '{mem['goal']}' failed: {err_summary} — avoid this pattern"
                )
            elif mem.get("decision") == "done":
                hints.append(
                    f"[memory] Similar task '{mem['goal']}' succeeded — consider reusing approach"
                )
        return hints

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
        goal_lower = goal.lower()

        if role == TaskRole.CODE:
            return self._plan_code(goal, goal_lower)
        elif role == TaskRole.EXEC:
            return self._plan_exec(goal, goal_lower)
        else:
            return self._plan_hybrid(goal, goal_lower)

    def _plan_code(self, goal: str, goal_lower: str) -> list[TaskStep]:
        steps = [
            TaskStep(step_id="s1", action=goal, agent=AgentName.OPENCODE),
        ]
        if any(kw in goal_lower for kw in TEST_KEYWORDS):
            steps.append(TaskStep(
                step_id="s2",
                action="run: pytest",
                agent=AgentName.OPENCLAW,
                depends_on=["s1"],
            ))
        return steps

    def _plan_exec(self, goal: str, goal_lower: str) -> list[TaskStep]:
        return [
            TaskStep(step_id="s1", action=goal, agent=AgentName.OPENCLAW),
        ]

    def _plan_hybrid(self, goal: str, goal_lower: str) -> list[TaskStep]:
        steps = [
            TaskStep(
                step_id="s1",
                action=f"[code] {goal}",
                agent=AgentName.OPENCODE,
            ),
        ]

        has_test = any(kw in goal_lower for kw in TEST_KEYWORDS)
        has_deploy = any(kw in goal_lower for kw in DEPLOY_KEYWORDS)

        if has_test:
            steps.append(TaskStep(
                step_id="s2",
                action="[verify] Run tests to validate changes",
                agent=AgentName.OPENCLAW,
                depends_on=["s1"],
            ))
            verify_id = "s2"
        else:
            steps.append(TaskStep(
                step_id="s2",
                action=f"[exec] Verify and run: {goal}",
                agent=AgentName.OPENCLAW,
                depends_on=["s1"],
            ))
            verify_id = "s2"

        if has_deploy:
            steps.append(TaskStep(
                step_id="s3",
                action="[deploy] Deploy verified changes",
                agent=AgentName.OPENCLAW,
                depends_on=[verify_id],
            ))

        return steps

    @staticmethod
    def _parse_explicit_steps(steps_data: list[dict]) -> list[TaskStep]:
        """Parse user-provided step definitions."""
        result: list[TaskStep] = []
        for i, s in enumerate(steps_data):
            step = TaskStep(
                step_id=s.get("step_id", f"s{i + 1}"),
                action=s["action"],
                agent=AgentName(s["agent"]),
                depends_on=s.get("depends_on", []),
            )
            result.append(step)
        return result

    @staticmethod
    def _expected_outputs(role: TaskRole) -> list[str]:
        if role == TaskRole.CODE:
            return ["updated_files", "summary"]
        elif role == TaskRole.EXEC:
            return ["run_commands", "summary"]
        else:
            return ["updated_files", "run_commands", "summary"]
