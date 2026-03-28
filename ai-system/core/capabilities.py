"""
Agent Capability Registry — formal contract of what each agent can do.

Enforced at two points:
  1. Router: refuses to dispatch a task role the agent cannot handle
  2. Validator: catches output artifacts an agent is not allowed to produce

This makes architectural boundaries machine-enforced, not just convention.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from agents.shared.models import AgentName, AgentResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentCapabilityProfile:
    agent: AgentName
    can_read_files: bool
    can_write_files: bool
    can_patch_files: bool
    can_execute_commands: bool
    can_use_network: bool
    can_plan: bool
    can_validate: bool
    allowed_task_roles: tuple[str, ...]
    allowed_outputs: tuple[str, ...]
    forbidden_outputs: tuple[str, ...]


CAPABILITIES: dict[AgentName, AgentCapabilityProfile] = {
    AgentName.OPENCODE: AgentCapabilityProfile(
        agent=AgentName.OPENCODE,
        can_read_files=True,
        can_write_files=False,
        can_patch_files=False,
        can_execute_commands=False,
        can_use_network=False,
        can_plan=False,
        can_validate=False,
        allowed_task_roles=("code", "hybrid"),
        allowed_outputs=(
            "files_changed", "files_to_write", "file_patches",
            "commands", "notes", "errors",
        ),
        forbidden_outputs=(
            "commands_executed", "rollback_result",
        ),
    ),
    AgentName.OPENCLAW: AgentCapabilityProfile(
        agent=AgentName.OPENCLAW,
        can_read_files=False,
        can_write_files=False,
        can_patch_files=False,
        can_execute_commands=True,
        can_use_network=False,
        can_plan=False,
        can_validate=False,
        allowed_task_roles=("exec", "hybrid"),
        allowed_outputs=(
            "commands", "commands_executed", "notes", "errors",
        ),
        forbidden_outputs=(
            "files_to_write", "file_patches",
        ),
    ),
}


def get_capabilities(agent: AgentName) -> AgentCapabilityProfile | None:
    return CAPABILITIES.get(agent)


def is_task_role_allowed(agent: AgentName, role: str) -> bool:
    cap = CAPABILITIES.get(agent)
    if cap is None:
        return False
    return role in cap.allowed_task_roles


def validate_agent_output(result: AgentResult) -> list[str]:
    """
    Check if an agent produced forbidden output artifacts.

    Returns list of violations (empty = clean).
    """
    cap = CAPABILITIES.get(result.agent)
    if cap is None:
        return [f"No capability profile for agent '{result.agent.value}'"]

    violations: list[str] = []

    if result.artifacts.files_to_write and "files_to_write" in cap.forbidden_outputs:
        violations.append(
            f"{result.agent.value} returned files_to_write "
            f"({len(result.artifacts.files_to_write)} items) — FORBIDDEN"
        )

    if result.artifacts.file_patches and "file_patches" in cap.forbidden_outputs:
        violations.append(
            f"{result.agent.value} returned file_patches "
            f"({len(result.artifacts.file_patches)} items) — FORBIDDEN"
        )

    exec_data = result.artifacts.outputs.get("commands_executed")
    if exec_data and "commands_executed" in cap.forbidden_outputs:
        violations.append(
            f"{result.agent.value} returned commands_executed — FORBIDDEN"
        )

    if violations:
        logger.warning(
            "[Capability] %s violations: %s", result.agent.value, violations
        )

    return violations
