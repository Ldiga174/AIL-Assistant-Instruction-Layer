"""
External tools — structured wrappers over shell commands.

Each tool:
  - Defines allowed operations (e.g. git.status, docker.build)
  - Validates parameters before execution
  - Generates safe shell commands
  - Parses structured output

Tools are used by OpenClaw instead of raw commands when the
task action matches a known tool pattern.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Structured result from a tool operation."""

    tool: str
    operation: str
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    commands_generated: list[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "tool": self.tool,
            "operation": self.operation,
            "success": self.success,
            "commands_generated": self.commands_generated,
        }
        if self.output:
            d["output"] = self.output
        if self.error:
            d["error"] = self.error
        return d


class BaseTool(ABC):
    """Abstract base for external tool integrations."""

    name: str
    operations: list[str]

    @abstractmethod
    def run(self, operation: str, params: dict[str, Any], cwd: str) -> ToolResult:
        """Execute a tool operation with given parameters."""

    def detect(self, text: str) -> tuple[str, dict[str, Any]] | None:
        """Try to detect an operation from natural language. Override in subclasses."""
        return None

    def supports(self, operation: str) -> bool:
        return operation in self.operations

    def _ok(
        self,
        operation: str,
        output: dict[str, Any],
        commands: list[str],
    ) -> ToolResult:
        return ToolResult(
            tool=self.name,
            operation=operation,
            success=True,
            output=output,
            commands_generated=commands,
        )

    def _fail(
        self,
        operation: str,
        error: str,
        commands: list[str] | None = None,
    ) -> ToolResult:
        return ToolResult(
            tool=self.name,
            operation=operation,
            success=False,
            error=error,
            commands_generated=commands or [],
        )


class ToolRegistry:
    """
    Registry of available external tools.

    Usage:
        registry = ToolRegistry()
        registry.register(GitTool())
        tool, op = registry.resolve("git.status")
        result = tool.run(op, {}, cwd="/repo")
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool
        logger.info("Tool registered: %s (%s)", tool.name, tool.operations)

    def resolve(self, action: str) -> tuple[BaseTool | None, str]:
        """
        Resolve an action string to a (tool, operation) pair.

        Accepts formats:
          - "git.status" -> (GitTool, "status")
          - "docker.build" -> (DockerTool, "build")
        """
        if "." not in action:
            return None, ""

        parts = action.split(".", 1)
        tool_name = parts[0]
        operation = parts[1] if len(parts) > 1 else ""

        tool = self._tools.get(tool_name)
        if tool and tool.supports(operation):
            return tool, operation

        return None, ""

    def detect_tool(self, text: str) -> tuple[BaseTool | None, str, dict[str, Any]]:
        """
        Detect if a natural-language action should use a tool.

        Returns (tool, operation, extracted_params) or (None, "", {}).
        """
        text_lower = text.lower().strip()

        for tool in self._tools.values():
            result = tool.detect(text_lower)
            if result:
                op, params = result
                return tool, op, params

        return None, "", {}

    @property
    def available_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_tool(self, name: str) -> BaseTool | None:
        return self._tools.get(name)
