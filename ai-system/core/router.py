"""
AIL Router — decides which agent handles a task.

Routing logic:
  role == "code"   -> OpenCode
  role == "exec"   -> OpenClaw
  role == "hybrid" -> split into steps for both agents

The router does NOT execute anything — it only produces a routing
decision that the controller uses.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from agents.shared.models import AgentName, Task, TaskRole, TaskStep

logger = logging.getLogger(__name__)


class RoutingDecision:
    """Describes how a task should be dispatched."""

    def __init__(
        self,
        task_id: str,
        primary_agent: AgentName | None,
        steps: list[TaskStep] | None = None,
    ) -> None:
        self.task_id = task_id
        self.primary_agent = primary_agent
        self.steps = steps or []
        self.decided_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "primary_agent": self.primary_agent.value if self.primary_agent else None,
            "steps": [
                {"step_id": s.step_id, "action": s.action, "agent": s.agent.value}
                for s in self.steps
            ],
            "decided_at": self.decided_at,
        }


class Router:
    """Stateless router: given a Task, returns a RoutingDecision."""

    def route(self, task: Task) -> RoutingDecision:
        if task.role == TaskRole.CODE:
            return self._route_code(task)
        elif task.role == TaskRole.EXEC:
            return self._route_exec(task)
        elif task.role == TaskRole.HYBRID:
            return self._route_hybrid(task)
        else:
            logger.error("Unknown task role: %s", task.role)
            return RoutingDecision(task.task_id, primary_agent=None)

    def _route_code(self, task: Task) -> RoutingDecision:
        logger.info("Routing task %s to OpenCode (code)", task.task_id)
        if not task.steps:
            task.steps = [
                TaskStep(step_id="s1", action=task.goal, agent=AgentName.OPENCODE)
            ]
        return RoutingDecision(
            task_id=task.task_id,
            primary_agent=AgentName.OPENCODE,
            steps=task.steps,
        )

    def _route_exec(self, task: Task) -> RoutingDecision:
        logger.info("Routing task %s to OpenClaw (exec)", task.task_id)
        if not task.steps:
            task.steps = [
                TaskStep(step_id="s1", action=task.goal, agent=AgentName.OPENCLAW)
            ]
        return RoutingDecision(
            task_id=task.task_id,
            primary_agent=AgentName.OPENCLAW,
            steps=task.steps,
        )

    def _route_hybrid(self, task: Task) -> RoutingDecision:
        logger.info("Routing task %s as hybrid (OpenCode + OpenClaw)", task.task_id)
        if not task.steps:
            task.steps = [
                TaskStep(step_id="s1", action=f"[code] {task.goal}", agent=AgentName.OPENCODE),
                TaskStep(
                    step_id="s2",
                    action=f"[exec] Verify: {task.goal}",
                    agent=AgentName.OPENCLAW,
                    depends_on=["s1"],
                ),
            ]
        return RoutingDecision(
            task_id=task.task_id,
            primary_agent=None,
            steps=task.steps,
        )
