"""
OpenClaw adapter — bridge between AIL and the shell executor + external tools.

OpenClaw is an executor, not a thinker. No LLM call needed.
The adapter routes actions through structured tools (git, docker, cloud)
when possible, falling back to raw shell execution.

Routing priority:
  1. task.inputs.context["tool"] — explicit tool call (e.g. {"tool": "git.status", "params": {}})
  2. tool.detect(action) — auto-detect from step action text
  3. raw command execution via OpenClawExecutor
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents.openclaw.executor import OpenClawExecutor
from agents.openclaw.tools import CloudTool, DockerTool, GitTool
from agents.shared.base_agent import BaseAgent
from agents.shared.models import (
    AgentName,
    AgentResult,
    Artifacts,
    ErrorInfo,
    ResultStatus,
    Task,
)
from agents.shared.tools import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


class OpenClawAdapter(BaseAgent):
    """
    Adapter connecting AIL to the OpenClaw executor and external tools.

    Flow: Task -> route to tool or executor -> AgentResult
    """

    def __init__(self) -> None:
        super().__init__(AgentName.OPENCLAW)
        self.executor = OpenClawExecutor()
        self.tools = ToolRegistry()
        self.tools.register(GitTool())
        self.tools.register(DockerTool())
        self.tools.register(CloudTool())

    def execute(self, task: Task) -> AgentResult:
        logger.info("[OpenClaw] task %s: %s", task.task_id, task.goal)

        tool_call = task.inputs.context.get("tool")
        if isinstance(tool_call, dict):
            return self._execute_tool_call(task, tool_call)

        commands = self._extract_commands(task)
        tool_actions = self._extract_tool_actions(task)

        if not commands and not tool_actions:
            logger.warning("[OpenClaw] No commands or tools found in task %s", task.task_id)
            return AgentResult(
                task_id=task.task_id,
                agent=AgentName.OPENCLAW,
                status=ResultStatus.ERROR,
                errors=[ErrorInfo(
                    message="No commands or tool operations to execute",
                    code="NO_COMMANDS",
                    details="Task has no commands in inputs.context or steps",
                )],
                notes="exec step failed: no commands or tools provided",
            )

        cwd = str(Path(task.inputs.repo).resolve())

        all_results: list[dict[str, Any]] = []
        all_commands: list[str] = []
        errors: list[ErrorInfo] = []
        notes_parts: list[str] = []

        for tool, op, params in tool_actions:
            logger.info("[OpenClaw] TOOL: %s.%s %s", tool.name, op, params)
            tr = tool.run(op, params, cwd)
            all_results.append(tr.to_dict())
            all_commands.extend(tr.commands_generated)

            if tr.success:
                notes_parts.append(f"[{tool.name}.{op}] OK")
            else:
                errors.append(ErrorInfo(
                    message=f"Tool {tool.name}.{op} failed: {tr.error}",
                    code="TOOL_FAILED",
                ))
                notes_parts.append(f"[{tool.name}.{op}] FAILED: {tr.error}")

        if commands:
            logger.info("[OpenClaw] Executing %d raw command(s)", len(commands))
            cmd_result = self.executor.execute(task, commands)
            all_commands.extend(cmd_result.artifacts.commands)
            if cmd_result.errors:
                errors.extend(cmd_result.errors)
            notes_parts.append(cmd_result.notes)
            all_results.append(cmd_result.to_dict())

        has_success = any(r.get("success", False) for r in all_results if "success" in r)
        has_failure = bool(errors)

        if has_failure and not has_success:
            status = ResultStatus.ERROR
        elif has_failure and has_success:
            status = ResultStatus.PARTIAL
        else:
            status = ResultStatus.SUCCESS

        return AgentResult(
            task_id=task.task_id,
            agent=AgentName.OPENCLAW,
            status=status,
            artifacts=Artifacts(
                commands=all_commands,
                outputs={"tool_results": all_results},
            ),
            notes="; ".join(notes_parts),
            errors=errors,
        )

    def _execute_tool_call(self, task: Task, tool_call: dict) -> AgentResult:
        """Handle explicit tool call from context: {"tool": "git.status", "params": {...}}."""
        action = tool_call.get("tool", "")
        params = tool_call.get("params", {})
        cwd = str(Path(task.inputs.repo).resolve())

        tool, op = self.tools.resolve(action)
        if not tool:
            return AgentResult(
                task_id=task.task_id,
                agent=AgentName.OPENCLAW,
                status=ResultStatus.ERROR,
                errors=[ErrorInfo(
                    message=f"Unknown tool: {action}",
                    code="UNKNOWN_TOOL",
                    details=f"Available tools: {self.tools.available_tools}",
                )],
                notes=f"tool call failed: unknown tool '{action}'",
            )

        tr = tool.run(op, params, cwd)
        status = ResultStatus.SUCCESS if tr.success else ResultStatus.FAILED
        errors = [ErrorInfo(message=tr.error, code="TOOL_FAILED")] if tr.error else []

        return AgentResult(
            task_id=task.task_id,
            agent=AgentName.OPENCLAW,
            status=status,
            artifacts=Artifacts(
                commands=tr.commands_generated,
                outputs={"tool_result": tr.to_dict()},
            ),
            notes=f"[{tr.tool}.{tr.operation}] {'OK' if tr.success else 'FAILED'}",
            errors=errors,
        )

    def _extract_tool_actions(self, task: Task) -> list[tuple[Any, str, dict[str, Any]]]:
        """Detect tool-based actions from step definitions."""
        actions = []
        for step in task.steps:
            if step.agent != AgentName.OPENCLAW:
                continue

            tool, op = self.tools.resolve(step.action)
            if tool:
                actions.append((tool, op, {}))
                continue

            tool, op, params = self.tools.detect_tool(step.action)
            if tool:
                actions.append((tool, op, params))

        return actions

    @staticmethod
    def _extract_commands(task: Task) -> list[str]:
        """Extract raw shell commands from available task fields."""
        commands: list[str] = []

        ctx_commands = task.inputs.context.get("commands")
        if isinstance(ctx_commands, list):
            commands.extend(str(c) for c in ctx_commands if c)
            if commands:
                return commands

        for step in task.steps:
            if step.agent != AgentName.OPENCLAW:
                continue
            action = step.action
            if action.startswith("run:"):
                commands.append(action[len("run:"):].strip())

        return commands
