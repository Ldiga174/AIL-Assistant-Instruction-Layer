"""
OpenClaw executor — safe shell command runner.

Executes only allowlisted commands via subprocess (shell=False).
Returns structured CommandResult per command with exit_code, stdout,
stderr, duration_ms.

Security:
  - Allowlist of permitted binary names (18 total)
  - Shell operators blocked (;, &&, ||, |, >, >>, <, backticks, $())
  - Blocklist patterns (sudo, shutdown, reboot, mkfs, forkbomb)
  - All commands run via shlex.split + subprocess.run(shell=False)
  - Per-command timeout (default 20s)
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

COMMAND_TIMEOUT_S = int(os.environ.get("OPENCLAW_TIMEOUT", "20"))

# ── Allowlist ─────────────────────────────────────────────────────────────

ALLOWED_BINARIES: set[str] = {
    "python", "python3",
    "pip", "pip3",
    "pytest",
    "uvicorn",
    "node", "npm", "pnpm", "yarn",
    "docker",
    "git",
    "gcloud",
    "ls", "pwd", "echo", "cat",
    "mkdir", "cp", "mv",
}

# ── Blocked patterns (caught before allowlist check) ──────────────────────

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

    Public API:
      - is_command_allowed(command) -> (bool, reason | None)
      - run_command(command, cwd, timeout) -> CommandResult
      - execute(task, commands) -> AgentResult
    """

    # ── 1. Check ──────────────────────────────────────────────────────────

    @staticmethod
    def is_command_allowed(command: str) -> tuple[bool, str | None]:
        """
        Check if a command is safe to execute.

        Returns:
            (True, None) if allowed.
            (False, "reason") if blocked.
        """
        for pattern in BLOCKED_PATTERNS:
            if pattern in command:
                return False, f"blocked pattern: '{pattern}'"

        for op in BLOCKED_SHELL_OPERATORS:
            if op in command:
                return False, f"shell operator: '{op}'"

        try:
            args = shlex.split(command)
        except ValueError:
            return False, "unparseable command"

        if not args:
            return False, "empty command"

        binary = os.path.basename(args[0])

        if binary not in ALLOWED_BINARIES:
            return False, f"'{binary}' not in allowlist"

        return True, None

    # ── 2. Run one command ────────────────────────────────────────────────

    def run_command(
        self,
        command: str,
        cwd: str | None = None,
        timeout: int = COMMAND_TIMEOUT_S,
    ) -> CommandResult:
        """
        Validate and execute a single shell command.

        Returns CommandResult with exit_code, stdout, stderr, duration_ms.
        Blocked commands get allowed=False without execution.
        """
        allowed, reason = self.is_command_allowed(command)

        if not allowed:
            logger.warning("[OpenClaw] BLOCKED: %s (%s)", command, reason)
            return CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"BLOCKED: {reason}",
                duration_ms=0,
                allowed=False,
            )

        try:
            args = shlex.split(command)
        except ValueError as exc:
            return CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Parse error: {exc}",
                duration_ms=0,
                allowed=False,
            )

        work_dir = cwd or os.getcwd()
        logger.info("[OpenClaw] RUN: %s (cwd=%s)", command, work_dir)
        t0 = time.monotonic()

        try:
            proc = subprocess.run(
                args,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = int((time.monotonic() - t0) * 1000)

            if proc.returncode == 0:
                logger.info("[OpenClaw] OK: %s (exit 0, %dms)", command, duration)
            else:
                logger.warning(
                    "[OpenClaw] FAIL: %s (exit %d, %dms)",
                    command, proc.returncode, duration,
                )

            return CommandResult(
                command=command,
                exit_code=proc.returncode,
                stdout=proc.stdout.strip()[:5000],
                stderr=proc.stderr.strip()[:5000],
                duration_ms=duration,
                allowed=True,
            )

        except subprocess.TimeoutExpired:
            duration = int((time.monotonic() - t0) * 1000)
            logger.error("[OpenClaw] TIMEOUT: %s (%dms)", command, duration)
            return CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Timeout after {timeout}s",
                duration_ms=duration,
                allowed=True,
            )

        except FileNotFoundError:
            duration = int((time.monotonic() - t0) * 1000)
            binary = args[0] if args else command
            logger.error("[OpenClaw] NOT FOUND: %s", binary)
            return CommandResult(
                command=command,
                exit_code=127,
                stdout="",
                stderr=f"Command not found: {binary}",
                duration_ms=duration,
                allowed=True,
            )

        except Exception as exc:
            duration = int((time.monotonic() - t0) * 1000)
            logger.error("[OpenClaw] ERROR: %s — %s", command, exc)
            return CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                duration_ms=duration,
                allowed=True,
            )

    # ── 3. Execute all commands ───────────────────────────────────────────

    def execute(self, task: Task, commands: list[str]) -> AgentResult:
        """
        Run a list of commands and return structured AgentResult.

        Status logic:
          - success: all allowed commands exited 0
          - partial: some OK, some failed/blocked
          - error:   all blocked or all failed
        """
        cwd = Path(task.inputs.repo).resolve()
        if not cwd.is_dir():
            cwd = Path.cwd()
            logger.warning("[OpenClaw] repo not found, using cwd: %s", cwd)

        results: list[CommandResult] = []
        errors: list[ErrorInfo] = []
        notes_parts: list[str] = []

        for cmd in commands:
            cr = self.run_command(cmd, cwd=str(cwd))
            results.append(cr)

            if not cr.allowed:
                errors.append(ErrorInfo(
                    message=f"BLOCKED: {cmd}",
                    code="CMD_BLOCKED",
                    details=cr.stderr,
                ))
                notes_parts.append(f"`{cmd}` — BLOCKED")
            elif cr.exit_code != 0:
                errors.append(ErrorInfo(
                    message=f"Failed (exit {cr.exit_code}): {cmd}",
                    code="CMD_FAILED",
                    details=cr.stderr[:500] if cr.stderr else cr.stdout[:500],
                ))
                notes_parts.append(f"`{cmd}` — FAILED (exit {cr.exit_code})")
            else:
                notes_parts.append(f"`{cmd}` — OK ({cr.duration_ms}ms)")

        status = self._determine_status(results, errors)

        return AgentResult(
            task_id=task.task_id,
            agent=AgentName.OPENCLAW,
            status=status,
            artifacts=Artifacts(
                commands=[cr.command for cr in results if cr.allowed],
                outputs={
                    "commands_executed": [cr.to_dict() for cr in results],
                },
            ),
            notes="exec step complete; " + "; ".join(notes_parts),
            errors=errors,
        )

    @staticmethod
    def _determine_status(
        results: list[CommandResult], errors: list[ErrorInfo]
    ) -> ResultStatus:
        if not results:
            return ResultStatus.ERROR

        all_blocked = all(not cr.allowed for cr in results)
        if all_blocked:
            return ResultStatus.ERROR

        all_ok = all(cr.allowed and cr.exit_code == 0 for cr in results)
        if all_ok:
            return ResultStatus.SUCCESS

        any_ok = any(cr.allowed and cr.exit_code == 0 for cr in results)
        if any_ok:
            return ResultStatus.PARTIAL

        return ResultStatus.ERROR
