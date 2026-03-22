"""
OpenClaw executor — safe shell command runner.

Executes only allowlisted commands via subprocess (shell=False).
Returns structured CommandResult per command with exit_code, stdout,
stderr, duration_ms.

Security model:
  - Allowlist of permitted binary names
  - Blocklist of dangerous patterns (rm -rf, sudo, reboot, etc.)
  - Shell operators blocked (;, &&, ||, |, >, >>, backticks, $())
  - All commands run via shlex.split + subprocess (no shell=True)
  - Per-command timeout
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
import time
from pathlib import Path

from agents.shared.models import (
    AgentName,
    AgentResult,
    Artifacts,
    CommandResult,
    ErrorInfo,
    ResultStatus,
    Task,
)

logger = logging.getLogger(__name__)

COMMAND_TIMEOUT_S = int(os.environ.get("OPENCLAW_TIMEOUT", "60"))

# ── Allowlist: only these binaries are permitted ──────────────────────────

ALLOWED_BINARIES: set[str] = {
    "python", "python3",
    "pip", "pip3",
    "pytest",
    "uvicorn",
    "node", "npm", "pnpm", "yarn",
    "docker",
    "ls", "pwd", "echo", "cat",
    "mkdir", "cp", "mv",
}

# ── Blocklist: these patterns are always rejected ─────────────────────────

BLOCKED_PATTERNS: list[str] = [
    "sudo ",
    "shutdown",
    "reboot",
    "mkfs",
    ":(){ :",
    "> /dev/",
]

BLOCKED_SHELL_OPERATORS: list[str] = [
    ";",
    "&&",
    "||",
    "|",
    ">>",
    ">",
    "<",
    "`",
    "$(",
]


class OpenClawExecutor:
    """
    Safe shell executor.

    Runs allowlisted commands via subprocess.run(shell=False).
    Returns per-command structured results.
    """

    def run(self, task: Task, commands: list[str]) -> AgentResult:
        """
        Execute a list of commands and return structured AgentResult.

        Args:
            task: The AIL task being executed.
            commands: List of shell command strings to run.
        """
        cwd = Path(task.inputs.repo).resolve()
        if not cwd.is_dir():
            cwd = Path.cwd()
            logger.warning("[OpenClaw] repo %s not found, using cwd %s", task.inputs.repo, cwd)

        command_results: list[CommandResult] = []
        errors: list[ErrorInfo] = []
        notes_parts: list[str] = []

        for cmd in commands:
            cr = self._execute_one(cmd, cwd)
            command_results.append(cr)

            if not cr.allowed:
                errors.append(ErrorInfo(
                    message=f"BLOCKED: {cmd}",
                    code="CMD_BLOCKED",
                    details="Command not in allowlist or contains blocked pattern",
                ))
                notes_parts.append(f"`{cmd}` — BLOCKED")
            elif cr.exit_code != 0:
                errors.append(ErrorInfo(
                    message=f"Command failed (exit {cr.exit_code}): {cmd}",
                    code="CMD_FAILED",
                    details=cr.stderr[:500] if cr.stderr else cr.stdout[:500],
                ))
                notes_parts.append(f"`{cmd}` — FAILED (exit {cr.exit_code})")
            else:
                notes_parts.append(f"`{cmd}` — OK ({cr.duration_ms}ms)")

        has_failures = any(e.code in ("CMD_FAILED", "CMD_BLOCKED") for e in errors)
        all_blocked = all(not cr.allowed for cr in command_results) if command_results else False

        if all_blocked:
            status = ResultStatus.ERROR
        elif has_failures:
            status = ResultStatus.PARTIAL
        else:
            status = ResultStatus.SUCCESS

        return AgentResult(
            task_id=task.task_id,
            agent=AgentName.OPENCLAW,
            status=status,
            artifacts=Artifacts(
                commands=[cr.command for cr in command_results if cr.allowed],
                outputs={
                    "commands_executed": [cr.to_dict() for cr in command_results],
                },
            ),
            notes="exec step complete; " + "; ".join(notes_parts),
            errors=errors,
        )

    def _execute_one(self, cmd: str, cwd: Path) -> CommandResult:
        """Validate and execute a single command."""

        blocked_reason = self._check_safety(cmd)
        if blocked_reason:
            logger.warning("[OpenClaw] BLOCKED: %s (%s)", cmd, blocked_reason)
            return CommandResult(
                command=cmd,
                exit_code=-1,
                stdout="",
                stderr=f"BLOCKED: {blocked_reason}",
                duration_ms=0,
                allowed=False,
            )

        try:
            args = shlex.split(cmd)
        except ValueError as exc:
            logger.warning("[OpenClaw] Cannot parse command: %s (%s)", cmd, exc)
            return CommandResult(
                command=cmd,
                exit_code=-1,
                stdout="",
                stderr=f"Parse error: {exc}",
                duration_ms=0,
                allowed=False,
            )

        logger.info("[OpenClaw] RUN: %s (cwd=%s)", cmd, cwd)
        t0 = time.monotonic()

        try:
            proc = subprocess.run(
                args,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT_S,
            )
            duration = int((time.monotonic() - t0) * 1000)

            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()

            if proc.returncode == 0:
                logger.info("[OpenClaw] OK: %s (exit 0, %dms)", cmd, duration)
            else:
                logger.warning("[OpenClaw] FAIL: %s (exit %d, %dms)", cmd, proc.returncode, duration)

            return CommandResult(
                command=cmd,
                exit_code=proc.returncode,
                stdout=stdout[:5000],
                stderr=stderr[:5000],
                duration_ms=duration,
                allowed=True,
            )

        except subprocess.TimeoutExpired:
            duration = int((time.monotonic() - t0) * 1000)
            logger.error("[OpenClaw] TIMEOUT: %s (%dms)", cmd, duration)
            return CommandResult(
                command=cmd,
                exit_code=-1,
                stdout="",
                stderr=f"Timeout after {COMMAND_TIMEOUT_S}s",
                duration_ms=duration,
                allowed=True,
            )

        except FileNotFoundError:
            duration = int((time.monotonic() - t0) * 1000)
            binary = shlex.split(cmd)[0] if cmd else cmd
            logger.error("[OpenClaw] NOT FOUND: %s", binary)
            return CommandResult(
                command=cmd,
                exit_code=127,
                stdout="",
                stderr=f"Command not found: {binary}",
                duration_ms=duration,
                allowed=True,
            )

        except Exception as exc:
            duration = int((time.monotonic() - t0) * 1000)
            logger.error("[OpenClaw] ERROR: %s — %s", cmd, exc)
            return CommandResult(
                command=cmd,
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                duration_ms=duration,
                allowed=True,
            )

    @staticmethod
    def _check_safety(cmd: str) -> str | None:
        """
        Return a rejection reason if the command is unsafe, or None if OK.
        """
        for pattern in BLOCKED_PATTERNS:
            if pattern in cmd:
                return f"matches blocked pattern: '{pattern}'"

        for op in BLOCKED_SHELL_OPERATORS:
            if op in cmd:
                return f"contains shell operator: '{op}'"

        try:
            args = shlex.split(cmd)
        except ValueError:
            return "unparseable command"

        if not args:
            return "empty command"

        binary = os.path.basename(args[0])

        if binary not in ALLOWED_BINARIES:
            return f"binary '{binary}' not in allowlist"

        return None
