"""
AIL Controller — the President.

This is the single decision-making authority in the system.
No agent acts independently; everything flows through here.

Lifecycle:
  1. Receive goal from Owner
  2. Plan (via Planner)
  3. Route (via Router)
  4. Dispatch to agents (OpenCode / OpenClaw)
  5. Validate results (via Validator)
  6. Retry or accept
  7. Log everything (via Memory)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from agents.opencode.adapter import OpenCodeAdapter
from agents.openclaw.adapter import OpenClawAdapter
from agents.shared.base_agent import BaseAgent
from agents.shared.models import (
    AgentName,
    AgentResult,
    ResultStatus,
    Task,
    TaskStatus,
    ValidationAction,
)
from core.memory import (
    append_log,
    load_agents_state,
    load_routing_state,
    move_task,
    persist_task,
    save_agents_state,
    save_routing_state,
    save_task_log,
)
from core.planner import Planner
from core.router import Router
from core.validator import Validator

logger = logging.getLogger(__name__)


class AILController:
    """
    The President of the AIL system.

    Orchestrates the full task lifecycle:
      goal -> plan -> route -> execute -> validate -> decide
    """

    def __init__(self) -> None:
        self.planner = Planner()
        self.router = Router()
        self.validator = Validator()
        self.agents: dict[AgentName, BaseAgent] = {
            AgentName.OPENCODE: OpenCodeAdapter(),
            AgentName.OPENCLAW: OpenClawAdapter(),
        }
        self.session_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    def handle_goal(
        self,
        goal: str,
        *,
        repo: str = ".",
        constraints: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Entry point: Owner gives a goal, AIL handles the rest.

        Returns a summary dict with task_id, status, validation, and logs.
        """
        append_log(f"New goal received: {goal}")

        task = self.planner.plan(goal, repo=repo, constraints=constraints)
        append_log(f"Task {task.task_id} planned: role={task.role.value}, steps={len(task.steps)}")

        persist_task(task.to_dict(), "incoming")

        routing = self.router.route(task)
        self._save_routing(routing)
        primary = routing.primary_agent.value if routing.primary_agent else "both"
        append_log(f"Task {task.task_id} routed: primary={primary}")

        task.status = TaskStatus.RUNNING
        move_task(task.task_id, "incoming", "running")

        results = self._dispatch(task)

        task.status = TaskStatus.VALIDATING
        validation_summary = self._validate_all(task, results)

        final_status = self._decide(task, validation_summary)
        task.status = final_status

        dest_stage = "done" if final_status == TaskStatus.DONE else "failed"
        move_task(task.task_id, "running", dest_stage)
        persist_task(task.to_dict(), dest_stage)

        self._log_task_summary(task, results, validation_summary)
        append_log(f"Task {task.task_id} finished: status={final_status.value}")

        return {
            "task_id": task.task_id,
            "goal": task.goal,
            "role": task.role.value,
            "status": final_status.value,
            "results": [r.to_dict() for r in results],
            "validation": validation_summary,
        }

    def _dispatch(self, task: Task) -> list[AgentResult]:
        """Send task steps to appropriate agents and collect results."""
        results: list[AgentResult] = []

        agents_needed: set[AgentName] = set()
        for step in task.steps:
            agents_needed.add(step.agent)

        for agent_name in agents_needed:
            agent = self.agents.get(agent_name)
            if not agent:
                logger.error("No agent registered for %s", agent_name.value)
                continue

            task.assigned_to = agent_name
            self._update_agent_state(agent_name, "running", task.task_id)
            append_log(f"Dispatching {task.task_id} to {agent_name.value}")

            result = agent.safe_execute(task)
            results.append(result)

            self._update_agent_state(agent_name, "idle", None)
            append_log(
                f"Agent {agent_name.value} returned: status={result.status.value}"
            )

        return results

    def _validate_all(
        self, task: Task, results: list[AgentResult]
    ) -> list[dict[str, Any]]:
        summaries = []
        for result in results:
            vr = self.validator.validate(task, result)
            summaries.append(vr.to_dict())
        return summaries

    def _decide(
        self, task: Task, validation_summary: list[dict[str, Any]]
    ) -> TaskStatus:
        """
        Final decision: accept, retry, or fail.

        Retry loop is capped by task.max_retries.
        """
        for vs in validation_summary:
            action = vs.get("action", "accept")
            if action == ValidationAction.RETRY.value:
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    append_log(
                        f"Retrying task {task.task_id} (attempt {task.retry_count}/{task.max_retries})"
                    )
                    return TaskStatus.RETRYING
                else:
                    append_log(f"Task {task.task_id} exceeded max retries")
                    return TaskStatus.FAILED
            elif action == ValidationAction.ABORT.value:
                return TaskStatus.FAILED

        return TaskStatus.DONE

    def _save_routing(self, routing) -> None:
        state = load_routing_state()
        history = state.get("history", [])
        history.append(routing.to_dict())
        state["history"] = history
        state["last_decision"] = routing.to_dict()
        save_routing_state(state)

    def _update_agent_state(
        self, agent_name: AgentName, status: str, current_task: str | None
    ) -> None:
        state = load_agents_state()
        agents = state.get("agents", {})
        agents[agent_name.value] = {
            "status": status,
            "current_task": current_task,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        state["agents"] = agents
        save_agents_state(state)

    def _log_task_summary(
        self,
        task: Task,
        results: list[AgentResult],
        validations: list[dict[str, Any]],
    ) -> None:
        lines = [
            f"# Task {task.task_id}",
            f"**Goal:** {task.goal}",
            f"**Role:** {task.role.value}",
            f"**Status:** {task.status.value}",
            "",
            "## Agent Results",
        ]
        for r in results:
            lines.append(f"### {r.agent}")
            lines.append(f"- Status: {r.status.value}")
            lines.append(f"- Notes: {r.notes}")
            if r.errors:
                lines.append("- Errors:")
                for e in r.errors:
                    lines.append(f"  - {e.message}")
            lines.append("")

        lines.append("## Validation")
        for v in validations:
            lines.append(f"- Passed: {v['passed']}, Action: {v['action']}")
            for c in v.get("checks", []):
                status_icon = "pass" if c["passed"] else "FAIL"
                lines.append(f"  - [{status_icon}] {c['check_name']}: {c.get('message', '')}")
            lines.append("")

        save_task_log(task.task_id, "\n".join(lines))
