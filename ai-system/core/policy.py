"""
Task Policy Layer — centralized execution constraints.

Three modes:
  - safe:       strictest limits, no retry, for prod-like tasks
  - dev:        balanced, with retry, for local development
  - aggressive: wider limits for experiments (still no dangerous shell)

Policy is resolved once per task and passed to all components.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskPolicy:
    """Immutable execution policy for a single task."""
    mode: str
    allow_file_write: bool
    allow_patch: bool
    allow_exec: bool
    allow_network_commands: bool
    max_files_read: int
    max_files_write: int
    max_patch_ops: int
    require_verify: bool
    require_snapshot: bool
    allow_retry: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "allow_file_write": self.allow_file_write,
            "allow_patch": self.allow_patch,
            "allow_exec": self.allow_exec,
            "allow_network_commands": self.allow_network_commands,
            "max_files_read": self.max_files_read,
            "max_files_write": self.max_files_write,
            "max_patch_ops": self.max_patch_ops,
            "require_verify": self.require_verify,
            "require_snapshot": self.require_snapshot,
            "allow_retry": self.allow_retry,
        }


POLICIES: dict[str, TaskPolicy] = {
    "safe": TaskPolicy(
        mode="safe",
        allow_file_write=True,
        allow_patch=True,
        allow_exec=True,
        allow_network_commands=False,
        max_files_read=3,
        max_files_write=2,
        max_patch_ops=10,
        require_verify=True,
        require_snapshot=True,
        allow_retry=False,
    ),
    "dev": TaskPolicy(
        mode="dev",
        allow_file_write=True,
        allow_patch=True,
        allow_exec=True,
        allow_network_commands=False,
        max_files_read=8,
        max_files_write=5,
        max_patch_ops=25,
        require_verify=True,
        require_snapshot=True,
        allow_retry=True,
    ),
    "aggressive": TaskPolicy(
        mode="aggressive",
        allow_file_write=True,
        allow_patch=True,
        allow_exec=True,
        allow_network_commands=False,
        max_files_read=20,
        max_files_write=10,
        max_patch_ops=50,
        require_verify=True,
        require_snapshot=True,
        allow_retry=True,
    ),
}

DEFAULT_MODE = "dev"


def resolve_policy(mode: str | None = None) -> TaskPolicy:
    """Resolve a policy by mode name. Falls back to dev."""
    effective = (mode or "").lower().strip() or DEFAULT_MODE
    policy = POLICIES.get(effective)
    if policy is None:
        logger.warning("[Policy] Unknown mode '%s', falling back to '%s'", effective, DEFAULT_MODE)
        policy = POLICIES[DEFAULT_MODE]
    logger.info("[Policy] Resolved: mode=%s", policy.mode)
    return policy
