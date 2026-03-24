"""
OpenCode adapter — bridge between AIL and an LLM backend.

Responsibilities:
  1. Load system prompt from prompts/system.md
  2. Build user prompt from Task fields
  3. Call LLM via transport (OpenAI / Anthropic / Mock)
  4. Return raw JSON string

Transport is auto-detected from env vars:
  OPENAI_API_KEY   -> OpenAI
  ANTHROPIC_API_KEY -> Anthropic
  (none)           -> Mock (deterministic, for testing)
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path

from agents.shared.base_agent import BaseAgent
from agents.shared.models import AgentName, AgentResult, ErrorInfo, Task
from agents.opencode.executor import OpenCodeExecutor

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
REQUEST_TIMEOUT_S = 60


def _load_system_prompt() -> str:
    path = PROMPTS_DIR / "system.md"
    return path.read_text(encoding="utf-8")


def _build_user_prompt(task: Task) -> str:
    """Build the user-facing prompt from Task fields."""
    parts = [
        f"Task ID: {task.task_id}",
        f"Goal: {task.goal}",
        f"Role: {task.role.value}",
        f"Repo: {task.inputs.repo}",
    ]
    if task.inputs.constraints:
        parts.append(f"Constraints: {json.dumps(task.inputs.constraints, ensure_ascii=False)}")
    if task.inputs.files:
        parts.append(f"Files: {json.dumps(task.inputs.files, ensure_ascii=False)}")
    if task.expected_output:
        parts.append(f"Expected output: {json.dumps(task.expected_output, ensure_ascii=False)}")

    files_context = task.inputs.context.get("files_context", [])
    if files_context:
        parts.append("")
        parts.append("=== Existing project files ===")
        for fc in files_context:
            path = fc.get("path", "?")
            content = fc.get("content", "")
            parts.append(f"--- {path} ---")
            parts.append(content)
            parts.append(f"--- end {path} ---")
        parts.append("=== End of project files ===")

    other_context = {
        k: v for k, v in task.inputs.context.items()
        if k != "files_context" and k != "files_applied"
    }
    if other_context:
        parts.append(f"Context: {json.dumps(other_context, ensure_ascii=False)}")

    parts.append("")
    parts.append("Return ONLY a JSON object as specified in the system prompt.")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Transport layer
# ---------------------------------------------------------------------------

class LLMTransport(ABC):
    """Unified interface for calling an LLM backend."""

    @abstractmethod
    def call(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompts to LLM, return raw text response."""


class OpenAITransport(LLMTransport):
    """Calls OpenAI Chat Completions API via urllib (no SDK dependency)."""

    def __init__(self) -> None:
        self.api_key = os.environ["OPENAI_API_KEY"]
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        self.base_url = os.environ.get(
            "OPENAI_API_BASE", "https://api.openai.com/v1"
        )

    def call(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            logger.error("OpenAI API error: %s", exc)
            raise


class AnthropicTransport(LLMTransport):
    """Calls Anthropic Messages API via urllib (no SDK dependency)."""

    def __init__(self) -> None:
        self.api_key = os.environ["ANTHROPIC_API_KEY"]
        self.model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    def call(self, system_prompt: str, user_prompt: str) -> str:
        url = "https://api.anthropic.com/v1/messages"
        payload = json.dumps({
            "model": self.model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt},
            ],
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"]
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            logger.error("Anthropic API error: %s", exc)
            raise


class MockTransport(LLMTransport):
    """
    Deterministic mock that returns structured JSON based on task input.
    Used when no API key is configured — allows full pipeline testing.
    """

    def call(self, system_prompt: str, user_prompt: str) -> str:
        goal = ""
        repo = "."
        has_context = "=== Existing project files ===" in user_prompt
        context_files: list[str] = []
        for line in user_prompt.splitlines():
            if line.startswith("Goal:"):
                goal = line[len("Goal:"):].strip()
            elif line.startswith("Repo:"):
                repo = line[len("Repo:"):].strip()
            elif line.startswith("--- ") and line.endswith(" ---") and not line.startswith("--- end"):
                context_files.append(line[4:-4].strip())

        commands = self._infer_commands(goal)

        if has_context and context_files:
            file_patches = self._infer_patches(goal, context_files)
            result = {
                "status": "success",
                "artifacts": {
                    "files_changed": context_files,
                    "commands": commands,
                },
                "file_patches": file_patches,
                "notes": f"[mock] Patched: {goal}",
                "errors": [],
            }
        else:
            files_to_write = self._infer_files_to_write(goal)
            files_changed = [fw["path"] for fw in files_to_write]
            result = {
                "status": "success",
                "artifacts": {
                    "files_changed": files_changed,
                    "commands": commands,
                },
                "files_to_write": files_to_write,
                "notes": f"[mock] Processed: {goal}",
                "errors": [],
            }

        return json.dumps(result, ensure_ascii=False)

    @staticmethod
    def _infer_files_to_write(goal: str) -> list[dict]:
        goal_lower = goal.lower()
        files: list[dict] = []
        if "endpoint" in goal_lower or "api" in goal_lower or "health" in goal_lower:
            files.append({
                "path": "src/api.py",
                "content": (
                    "from fastapi import FastAPI\n\n"
                    "app = FastAPI()\n\n\n"
                    "@app.get('/health')\n"
                    "def health():\n"
                    "    return {'status': 'ok'}\n"
                ),
                "mode": "create",
            })
        if "config" in goal_lower or "конфиг" in goal_lower:
            files.append({
                "path": "config/settings.py",
                "content": "HOST = '0.0.0.0'\nPORT = 8000\nDEBUG = True\n",
                "mode": "create",
            })
        if "test" in goal_lower or "тест" in goal_lower:
            files.append({
                "path": "tests/test_main.py",
                "content": "def test_placeholder():\n    assert True\n",
                "mode": "create",
            })
        if not files:
            files.append({
                "path": "src/main.py",
                "content": "print('hello')\n",
                "mode": "create",
            })
        return files

    @staticmethod
    def _infer_patches(goal: str, context_files: list[str]) -> list[dict]:
        """Generate patch operations based on goal and available context files."""
        patches: list[dict] = []
        goal_lower = goal.lower()
        for fpath in context_files:
            if "api" in fpath and ("health" in goal_lower or "endpoint" in goal_lower or "обновить" in goal_lower):
                patches.append({
                    "path": fpath,
                    "mode": "replace_block",
                    "target": 'def health():\n    return {"status": "ok"}',
                    "content": 'def health():\n    return {"status": "ok", "version": "2"}',
                })
            elif "main" in fpath:
                patches.append({
                    "path": fpath,
                    "mode": "insert_after",
                    "target": "print('hello')",
                    "content": "\nprint('updated')\n",
                })
        if not patches and context_files:
            patches.append({
                "path": context_files[0],
                "mode": "insert_before",
                "target": "\n",
                "content": "# Updated by OpenCode\n",
            })
        return patches

    @staticmethod
    def _infer_commands(goal: str) -> list[str]:
        goal_lower = goal.lower()
        cmds = []
        if "test" in goal_lower or "тест" in goal_lower:
            cmds.append("python -m pytest tests/ -v")
        if "запуск" in goal_lower or "run" in goal_lower or "start" in goal_lower:
            cmds.append("uvicorn src.main:app --reload --port 8000")
        if not cmds:
            cmds.append("python -m pytest tests/")
        return cmds


# ---------------------------------------------------------------------------
# Transport factory
# ---------------------------------------------------------------------------

def _create_transport() -> LLMTransport:
    """Auto-detect the best available transport from env vars."""
    if os.environ.get("OPENAI_API_KEY"):
        logger.info("Transport: OpenAI (%s)", os.environ.get("OPENAI_MODEL", "gpt-4o"))
        return OpenAITransport()

    if os.environ.get("ANTHROPIC_API_KEY"):
        logger.info("Transport: Anthropic (%s)", os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"))
        return AnthropicTransport()

    logger.info("Transport: Mock (no API key found)")
    return MockTransport()


# ---------------------------------------------------------------------------
# Adapter (BaseAgent implementation)
# ---------------------------------------------------------------------------

class OpenCodeAdapter(BaseAgent):
    """
    Adapter connecting AIL to the OpenCode LLM-backed executor.

    Flow: Task -> build prompt -> call transport -> parse -> AgentResult
    """

    def __init__(self) -> None:
        super().__init__(AgentName.OPENCODE)
        self.transport = _create_transport()
        self.system_prompt = _load_system_prompt()
        self.executor = OpenCodeExecutor()

    def execute(self, task: Task) -> AgentResult:
        logger.info("[OpenCode] task %s: %s", task.task_id, task.goal)

        user_prompt = _build_user_prompt(task)
        logger.debug("[OpenCode] user prompt:\n%s", user_prompt)

        try:
            raw_response = self.transport.call(self.system_prompt, user_prompt)
        except Exception as exc:
            logger.error("[OpenCode] transport error: %s", exc)
            return self._failure(
                task,
                errors=[ErrorInfo(
                    message=f"LLM transport error: {exc}",
                    code="TRANSPORT_ERROR",
                )],
                notes="code step failed: could not reach LLM",
            )

        logger.debug("[OpenCode] raw response: %s", raw_response[:500])

        return self.executor.parse_and_build(task, raw_response)
