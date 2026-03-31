"""
AIL Step Executor — dependency-aware step runner.

Resolves step dependencies via topological sort and executes
steps in correct order. Output from completed steps is passed
as context to dependent steps.

Key behaviors:
  - Steps with no dependencies run first
  - A step only runs after all depends_on steps are DONE
  - If a dependency FAILED, the dependent step is SKIPPED
  - Per-step results are tracked independently
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Any

from agents.shared.base_agent import BaseAgent
from agents.shared.models import (
    AgentName,
    AgentResult,
    ResultStatus,
    StepResult,
    StepStatus,
    Task,
    TaskStep,
)
from core.memory import append_log

logger = logging.getLogger(__name__)


class StepExecutor:
    """Executes task steps respecting dependency order."""

    def __init__(self, agents: dict[AgentName, BaseAgent]) -> None:
        self.agents = agents

    def execute_steps(self, task: Task) -> list[StepResult]:
        """
        Run all steps in dependency order.

        Returns a StepResult per step (including skipped ones).
        """
        order = self._resolve_order(task.steps)
        step_map = {s.step_id: s for s in task.steps}
        step_results: dict[str, StepResult] = {}

        for step_id in order:
            step = step_map[step_id]

            if self._should_skip(step, step_results):
                step.status = StepStatus.SKIPPED
                sr = StepResult(
                    step_id=step_id,
                    agent=step.agent,
                    status=ResultStatus.ERROR,
                    skipped_reason="dependency failed",
                )
                step_results[step_id] = sr
                append_log(
                    f"Step {step_id} SKIPPED: dependency failed"
                )
                continue

            self._inject_context(task, step, step_results)

            agent = self.agents.get(step.agent)
            if not agent:
                logger.error("No agent for %s", step.agent.value)
                step.status = StepStatus.FAILED
                sr = StepResult(
                    step_id=step_id,
                    agent=step.agent,
                    status=ResultStatus.ERROR,
                    skipped_reason=f"agent {step.agent.value} not registered",
                )
                step_results[step_id] = sr
                continue

            step.status = StepStatus.RUNNING
            append_log(
                f"Step {step_id} ({step.agent.value}): {step.action[:60]}"
            )

            task.assigned_to = step.agent
            result = agent.safe_execute(task)

            if result.status in (ResultStatus.SUCCESS, ResultStatus.PARTIAL):
                step.status = StepStatus.DONE
            else:
                step.status = StepStatus.FAILED

            sr = StepResult(
                step_id=step_id,
                agent=step.agent,
                status=result.status,
                result=result,
            )
            step_results[step_id] = sr
            append_log(
                f"Step {step_id} finished: {result.status.value}"
            )

        return [step_results[s.step_id] for s in task.steps if s.step_id in step_results]

    def _should_skip(
        self, step: TaskStep, completed: dict[str, StepResult]
    ) -> bool:
        """Check if any dependency failed or was skipped."""
        for dep_id in step.depends_on:
            dep = completed.get(dep_id)
            if dep is None:
                return True
            if dep.status not in (ResultStatus.SUCCESS, ResultStatus.PARTIAL):
                return True
        return False

    def _inject_context(
        self,
        task: Task,
        step: TaskStep,
        completed: dict[str, StepResult],
    ) -> None:
        """Pass outputs from completed dependencies into task context."""
        prior_outputs: dict[str, Any] = {}
        prior_files: list[str] = []
        prior_commands: list[str] = []

        for dep_id in step.depends_on:
            dep = completed.get(dep_id)
            if dep and dep.result:
                prior_outputs[dep_id] = {
                    "status": dep.result.status.value,
                    "files_changed": dep.result.artifacts.files_changed,
                    "commands": dep.result.artifacts.commands,
                    "notes": dep.result.notes,
                }
                prior_files.extend(dep.result.artifacts.files_changed)
                prior_commands.extend(dep.result.artifacts.commands)

        if prior_outputs:
            task.inputs.context["prior_steps"] = prior_outputs
        if prior_files:
            task.inputs.context["prior_files"] = prior_files
        if prior_commands and step.agent == AgentName.OPENCLAW:
            existing = task.inputs.context.get("commands", [])
            task.inputs.context["commands"] = existing + prior_commands

    @staticmethod
    def _resolve_order(steps: list[TaskStep]) -> list[str]:
        """Topological sort of steps by depends_on."""
        graph: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {}

        for s in steps:
            in_degree.setdefault(s.step_id, 0)
            for dep in s.depends_on:
                graph[dep].append(s.step_id)
                in_degree[s.step_id] = in_degree.get(s.step_id, 0) + 1

        queue: deque[str] = deque()
        for sid, deg in in_degree.items():
            if deg == 0:
                queue.append(sid)

        order: list[str] = []
        while queue:
            current = queue.popleft()
            order.append(current)
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(steps):
            logger.error("Cycle detected in step dependencies, falling back to input order")
            return [s.step_id for s in steps]

        return order
