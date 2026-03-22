"""
Data models for AIL task/result contracts.

All structured communication between AIL, OpenCode, and OpenClaw
goes through these models.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TaskRole(str, Enum):
    CODE = "code"
    EXEC = "exec"
    HYBRID = "hybrid"


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    VALIDATING = "validating"
    DONE = "done"
    FAILED = "failed"
    RETRYING = "retrying"


class AgentName(str, Enum):
    OPENCODE = "opencode"
    OPENCLAW = "openclaw"


class ResultStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    ERROR = "error"


class ValidationAction(str, Enum):
    ACCEPT = "accept"
    RETRY = "retry"
    ESCALATE = "escalate"
    ABORT = "abort"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_task_id() -> str:
    seq = uuid.uuid4().int % 100000
    return f"task-{seq:05d}"


@dataclass
class TaskInputs:
    repo: str = "."
    constraints: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)


@dataclass
class TaskStep:
    step_id: str
    action: str
    agent: AgentName
    depends_on: list[str] = field(default_factory=list)


@dataclass
class Task:
    goal: str
    role: TaskRole
    task_id: str = field(default_factory=_gen_task_id)
    inputs: TaskInputs = field(default_factory=TaskInputs)
    expected_output: list[str] = field(default_factory=list)
    steps: list[TaskStep] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: AgentName | None = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "role": self.role.value,
            "inputs": {
                "repo": self.inputs.repo,
                "constraints": self.inputs.constraints,
                "context": self.inputs.context,
                "files": self.inputs.files,
            },
            "expected_output": self.expected_output,
            "steps": [
                {
                    "step_id": s.step_id,
                    "action": s.action,
                    "agent": s.agent.value,
                    "depends_on": s.depends_on,
                }
                for s in self.steps
            ],
            "status": self.status.value,
            "assigned_to": self.assigned_to.value if self.assigned_to else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        inputs_raw = data.get("inputs", {})
        inputs = TaskInputs(
            repo=inputs_raw.get("repo", "."),
            constraints=inputs_raw.get("constraints", []),
            context=inputs_raw.get("context", {}),
            files=inputs_raw.get("files", []),
        )
        steps = [
            TaskStep(
                step_id=s["step_id"],
                action=s["action"],
                agent=AgentName(s["agent"]),
                depends_on=s.get("depends_on", []),
            )
            for s in data.get("steps", [])
        ]
        return cls(
            task_id=data.get("task_id", _gen_task_id()),
            goal=data["goal"],
            role=TaskRole(data["role"]),
            inputs=inputs,
            expected_output=data.get("expected_output", []),
            steps=steps,
            status=TaskStatus(data.get("status", "pending")),
            assigned_to=AgentName(data["assigned_to"]) if data.get("assigned_to") else None,
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            created_at=data.get("created_at", _now()),
            updated_at=data.get("updated_at", _now()),
        )


@dataclass
class ErrorInfo:
    message: str
    code: str = ""
    details: str = ""

    def to_dict(self) -> dict[str, str]:
        d: dict[str, str] = {"message": self.message}
        if self.code:
            d["code"] = self.code
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class Artifacts:
    files_changed: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_changed": self.files_changed,
            "files_deleted": self.files_deleted,
            "commands": self.commands,
            "outputs": self.outputs,
        }


@dataclass
class AgentResult:
    task_id: str
    agent: AgentName
    status: ResultStatus
    artifacts: Artifacts = field(default_factory=Artifacts)
    notes: str = ""
    errors: list[ErrorInfo] = field(default_factory=list)
    duration_ms: int = 0
    completed_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent": self.agent.value,
            "status": self.status.value,
            "artifacts": self.artifacts.to_dict(),
            "notes": self.notes,
            "errors": [e.to_dict() for e in self.errors],
            "duration_ms": self.duration_ms,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentResult:
        arts = data.get("artifacts", {})
        return cls(
            task_id=data["task_id"],
            agent=AgentName(data["agent"]),
            status=ResultStatus(data["status"]),
            artifacts=Artifacts(
                files_changed=arts.get("files_changed", []),
                files_deleted=arts.get("files_deleted", []),
                commands=arts.get("commands", []),
                outputs=arts.get("outputs", {}),
            ),
            notes=data.get("notes", ""),
            errors=[
                ErrorInfo(
                    message=e["message"],
                    code=e.get("code", ""),
                    details=e.get("details", ""),
                )
                for e in data.get("errors", [])
            ],
            duration_ms=data.get("duration_ms", 0),
            completed_at=data.get("completed_at", _now()),
        )


@dataclass
class ValidationCheck:
    check_name: str
    passed: bool
    check_type: str = "generic"
    message: str = ""
    expected: Any = None
    actual: Any = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "check_name": self.check_name,
            "check_type": self.check_type,
            "passed": self.passed,
        }
        if self.message:
            d["message"] = self.message
        if self.expected is not None:
            d["expected"] = self.expected
        if self.actual is not None:
            d["actual"] = self.actual
        return d


@dataclass
class ValidationResult:
    task_id: str
    passed: bool
    checks: list[ValidationCheck]
    validated_by: str = "ail"
    action: ValidationAction = ValidationAction.ACCEPT
    validated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "validated_by": self.validated_by,
            "passed": self.passed,
            "checks": [c.to_dict() for c in self.checks],
            "action": self.action.value,
            "validated_at": self.validated_at,
        }
