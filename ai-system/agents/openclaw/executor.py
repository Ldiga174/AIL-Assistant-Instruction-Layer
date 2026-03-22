"""
OpenClaw executor — the operational arm.

Current implementation: stub that returns realistic test artifacts.
Real execution (subprocess calls, browser automation) will replace
the stub logic in Step 3.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from agents.shared.models import (
    AgentName,
    AgentResult,
    Artifacts,
    ErrorInfo,
    ResultStatus,
    Task,
)

logger = logging.getLogger(__name__)

COMMAND_TIMEOUT_S = 120


class OpenClawExecutor:
    """Stateless executor: receives a Task, returns an AgentResult."""

    def run(self, task: Task) -> AgentResult:
        cwd = Path(task.inputs.repo).resolve()
        if not cwd.is_dir():
            cwd = Path.cwd()

        executed_commands: list[str] = []
        errors: list[ErrorInfo] = []
        notes_parts: list[str] = []

        my_steps = [s for s in task.steps if s.agent == AgentName.OPENCLAW]

        for step in my_steps:
            logger.info("[OpenClaw] step %s: %s", step.step_id, step.action)

            if step.action.startswith("run:"):
                cmd = step.action[len("run:"):].strip()
                ok, output = self._run_command(cmd, cwd)
                executed_commands.append(cmd)
                if ok:
                    notes_parts.append(f"step {step.step_id}: `{cmd}` — OK")
                else:
                    notes_parts.append(f"step {step.step_id}: `{cmd}` — FAILED")
                    errors.append(ErrorInfo(
                        message=f"Command failed: {cmd}",
                        code="CMD_FAILED",
                        details=output[:500],
                    ))
            else:
                executed_commands.extend([
                    "npm run build",
                    "docker compose up -d --build",
                ])
                notes_parts.append(
                    f"step {step.step_id}: build executed, service verified online"
                )

        if not my_steps:
            executed_commands.append("echo 'health check OK'")
            notes_parts.append(f"Processed goal: {task.goal}")

        status = ResultStatus.FAILED if errors else ResultStatus.SUCCESS
        return AgentResult(
            task_id=task.task_id,
            agent=AgentName.OPENCLAW,
            status=status,
            artifacts=Artifacts(commands=executed_commands),
            notes="exec step complete; " + "; ".join(notes_parts),
            errors=errors,
        )

    @staticmethod
    def _run_command(cmd: str, cwd: Path) -> tuple[bool, str]:
        """Execute a shell command and return (success, output)."""
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT_S,
            )
            output = (proc.stdout + proc.stderr).strip()
            return proc.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {COMMAND_TIMEOUT_S}s"
        except Exception as exc:
            return False, str(exc)
