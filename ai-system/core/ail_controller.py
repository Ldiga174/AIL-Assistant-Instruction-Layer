"""
AIL Controller — the President.

This is the single decision-making authority in the system.
No agent acts independently; everything flows through here.

Lifecycle:
  1. Receive goal from Owner (handle_goal) or Task object (handle_task)
  2. Plan (via Planner)
  3. Route (via Router)
  4. Dispatch to agents — OpenCode first, then OpenClaw
  5. Validate results (via Validator)
  6. Retry or accept
  7. Log everything (via Memory)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from agents.opencode.adapter import OpenCodeAdapter
from agents.openclaw.adapter import OpenClawAdapter
from agents.shared.base_agent import BaseAgent
from agents.shared.models import (
    AgentName,
    AgentResult,
    Task,
    TaskRole,
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
from core.file_applier import FileApplier
from core.file_reader import FileReader
from core.planner import Planner
from core.router import Router
from core.validator import Validator

logger = logging.getLogger(__name__)

DISPATCH_ORDER = [AgentName.OPENCODE, AgentName.OPENCLAW]


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
        self.file_applier = FileApplier()
        self.file_reader = FileReader()
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
        """Entry point for text goals — plans the task, then runs it."""
        task = self.planner.plan(goal, repo=repo, constraints=constraints)
        return self.handle_task(task)

    def handle_task(self, task: Task) -> dict[str, Any]:
        """
        Entry point for pre-built Task objects (e.g. loaded from JSON).

        Full cycle: plan -> route -> dispatch -> validate -> decide -> log.
        """
        append_log(f"New task received: {task.task_id} — {task.goal}")
        append_log(f"Task {task.task_id} classified: role={task.role.value}")

        persist_task(task.to_dict(), "incoming")

        routing = self.router.route(task)
        self._save_routing(routing)
        primary = routing.primary_agent.value if routing.primary_agent else "both"
        append_log(f"Task {task.task_id} routed: primary={primary}")

        task.status = TaskStatus.RUNNING
        move_task(task.task_id, "incoming", "running")

        self._inject_file_context(task)

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

    def _inject_file_context(self, task: Task) -> None:
        """Read project files and inject into task context for OpenCode."""
        from pathlib import Path
        repo_root = str(Path(task.inputs.repo).resolve())

        file_contexts = self.file_reader.read_with_defaults(
            task.inputs.files or None,
            repo_root,
        )

        if file_contexts:
            task.inputs.context["files_context"] = [
                fc.to_dict() for fc in file_contexts
            ]
            paths = [fc.path for fc in file_contexts]
            total = sum(fc.size for fc in file_contexts)
            append_log(
                f"Safe read injected into context: {paths} ({total} bytes)"
            )
        else:
            append_log("No files injected into context (none found or requested)")

    def _dispatch(self, task: Task) -> list[AgentResult]:
        """
        Send task steps to appropriate agents and collect results.

        Order is guaranteed: OpenCode first, OpenClaw second.
        For hybrid tasks, after OpenCode completes, AIL transfers
        produced commands into task.inputs.commands so OpenClaw
        picks them up automatically — no manual injection.
        """
        results: list[AgentResult] = []

        agents_needed: set[AgentName] = set()
        for step in task.steps:
            agents_needed.add(step.agent)

        for agent_name in DISPATCH_ORDER:
            if agent_name not in agents_needed:
                continue

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
                f"Agent {agent_name.value} returned: "
                f"status={result.status.value}, notes={result.notes[:80]}"
            )

            if agent_name == AgentName.OPENCODE:
                self._apply_files(task, result)
                self._handoff_commands(task, result, agents_needed)

        return results

    def _apply_files(self, task: Task, opencode_result: AgentResult) -> None:
        """Apply files produced by OpenCode via the safe FileApplier."""
        files_to_write = opencode_result.artifacts.files_to_write
        if not files_to_write:
            return

        from pathlib import Path
        repo_root = str(Path(task.inputs.repo).resolve())

        append_log(
            f"OpenCode produced {len(files_to_write)} file(s) to write: "
            f"{[fw.path for fw in files_to_write]}"
        )

        results = self.file_applier.apply(files_to_write, repo_root)

        written = [r for r in results if r.status == "written"]
        skipped = [r for r in results if r.status == "skipped"]
        errors = [r for r in results if r.status == "error"]

        append_log(
            f"FileApplier: {len(written)} written, "
            f"{len(skipped)} skipped, {len(errors)} errors"
        )

        task.inputs.context["files_applied"] = [r.to_dict() for r in results]

    def _handoff_commands(
        self,
        task: Task,
        opencode_result: AgentResult,
        agents_needed: set[AgentName],
    ) -> None:
        """
        Transfer commands from OpenCode result into task.inputs.commands
        so OpenClaw can pick them up in hybrid tasks.
        """
        if AgentName.OPENCLAW not in agents_needed:
            return

        produced = opencode_result.artifacts.commands
        if not produced:
            append_log(f"OpenCode produced no commands — nothing to hand off")
            return

        task.inputs.commands = list(produced)
        append_log(
            f"OpenCode produced commands: {produced}"
        )
        append_log(
            f"Injected commands into task.inputs.commands for OpenClaw"
        )

    def _validate_all(
        self, task: Task, results: list[AgentResult]
    ) -> list[dict[str, Any]]:
        summaries = []
        for result in results:
            vr = self.validator.validate(task, result)
            summaries.append(vr.to_dict())

        if task.inputs.files:
            ctx_vr = self.validator.validate_file_context(task)
            summaries.append(ctx_vr.to_dict())

        if task.inputs.context.get("files_applied"):
            files_vr = self.validator.validate_files_applied(task)
            summaries.append(files_vr.to_dict())

        if task.role == TaskRole.HYBRID and len(results) >= 2:
            handoff_vr = self.validator.validate_handoff(task, results)
            summaries.append(handoff_vr.to_dict())

        return summaries

    def _decide(
        self, task: Task, validation_summary: list[dict[str, Any]]
    ) -> TaskStatus:
        for vs in validation_summary:
            action = vs.get("action", "accept")
            if action == ValidationAction.RETRY.value:
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    append_log(
                        f"Retrying task {task.task_id} "
                        f"(attempt {task.retry_count}/{task.max_retries})"
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
            lines.append(f"### {r.agent.value}")
            lines.append(f"- Status: {r.status.value}")
            lines.append(f"- Notes: {r.notes}")
            if r.artifacts.files_changed:
                lines.append(f"- Files changed: {', '.join(r.artifacts.files_changed)}")
            if r.artifacts.commands:
                lines.append(f"- Commands: {', '.join(r.artifacts.commands)}")
            if r.errors:
                lines.append("- Errors:")
                for e in r.errors:
                    lines.append(f"  - {e.message}")
            lines.append("")

        lines.append("## Validation")
        for v in validations:
            lines.append(f"- Passed: {v['passed']}, Action: {v['action']}")
            for c in v.get("checks", []):
                icon = "PASS" if c["passed"] else "FAIL"
                lines.append(f"  - [{icon}] {c['check_name']}: {c.get('message', '')}")
            lines.append("")

        save_task_log(task.task_id, "\n".join(lines))
