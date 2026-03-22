"""
OpenCode executor — normalises LLM output into AgentResult.

This is NOT just "call the model". This is controlled packaging:
  1. Receive raw string from adapter
  2. Parse JSON (with fallback for garbage)
  3. Validate required fields
  4. Build AgentResult

Handles three failure modes:
  - Empty response
  - Invalid JSON (text mixed with JSON, markdown fences, etc.)
  - Text instead of JSON (no JSON at all)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agents.shared.models import (
    AgentName,
    AgentResult,
    Artifacts,
    ErrorInfo,
    ResultStatus,
    Task,
)

logger = logging.getLogger(__name__)


class OpenCodeExecutor:
    """Parses raw LLM output and builds a validated AgentResult."""

    def parse_and_build(self, task: Task, raw: str) -> AgentResult:
        """Main entry: raw LLM string -> AgentResult."""

        if not raw or not raw.strip():
            logger.warning("[OpenCode] Empty response from LLM")
            return self._error_result(
                task, "LLM returned empty response", "EMPTY_RESPONSE"
            )

        parsed = self._extract_json(raw)

        if parsed is None:
            logger.warning("[OpenCode] Could not parse JSON from response")
            return self._error_result(
                task,
                "LLM returned non-JSON response",
                "INVALID_JSON",
                details=raw[:300],
            )

        return self._build_result(task, parsed)

    def _extract_json(self, raw: str) -> dict[str, Any] | None:
        """
        Try to get a JSON dict from the raw string.
        Handles: pure JSON, JSON in markdown fences, JSON buried in text.
        """
        text = raw.strip()

        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

        fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if fenced:
            try:
                obj = json.loads(fenced.group(1).strip())
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass

        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace : last_brace + 1]
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass

        return None

    def _build_result(self, task: Task, data: dict[str, Any]) -> AgentResult:
        """Normalise parsed dict into AgentResult with field validation."""

        status_str = data.get("status", "")
        status = self._parse_status(status_str)

        artifacts_raw = data.get("artifacts", {})
        if not isinstance(artifacts_raw, dict):
            artifacts_raw = {}

        files_changed = artifacts_raw.get("files_changed", [])
        if not isinstance(files_changed, list):
            files_changed = []
        files_changed = [str(f) for f in files_changed if f]

        commands = artifacts_raw.get("commands", [])
        if not isinstance(commands, list):
            commands = []
        commands = [str(c) for c in commands if c]

        notes = str(data.get("notes", "")).strip()

        errors_raw = data.get("errors", [])
        if not isinstance(errors_raw, list):
            errors_raw = []
        errors = []
        for e in errors_raw:
            if isinstance(e, dict) and e.get("message"):
                errors.append(ErrorInfo(
                    message=str(e["message"]),
                    code=str(e.get("code", "")),
                    details=str(e.get("details", "")),
                ))
            elif isinstance(e, str) and e.strip():
                errors.append(ErrorInfo(message=e))

        if not notes and not files_changed and not commands:
            notes = "(no content returned by LLM)"

        return AgentResult(
            task_id=task.task_id,
            agent=AgentName.OPENCODE,
            status=status,
            artifacts=Artifacts(
                files_changed=files_changed,
                commands=commands,
            ),
            notes=notes,
            errors=errors,
        )

    @staticmethod
    def _parse_status(raw: str) -> ResultStatus:
        mapping = {
            "success": ResultStatus.SUCCESS,
            "partial": ResultStatus.PARTIAL,
            "failed": ResultStatus.FAILED,
            "error": ResultStatus.ERROR,
        }
        return mapping.get(raw.lower().strip(), ResultStatus.PARTIAL)

    @staticmethod
    def _error_result(
        task: Task,
        message: str,
        code: str,
        details: str = "",
    ) -> AgentResult:
        return AgentResult(
            task_id=task.task_id,
            agent=AgentName.OPENCODE,
            status=ResultStatus.ERROR,
            errors=[ErrorInfo(message=message, code=code, details=details)],
            notes=f"code step failed: {message}",
        )
