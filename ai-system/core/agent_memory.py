"""
AIL Agent Memory — learning from past executions.

Reads completed manifests to build a searchable memory of:
  - What goals were attempted and their outcomes
  - Which approaches (steps, agents) succeeded or failed
  - Common error patterns to avoid
  - File/command patterns per goal type

Memory is rebuilt from manifests on init (no separate DB).
Provides recall() to find relevant past experiences for new tasks.

Storage: state/memory.json (cached index, rebuilt from manifests/)
"""

from __future__ import annotations

import json
import logging
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
MANIFESTS_DIR = BASE_DIR / "manifests"
MEMORY_CACHE = BASE_DIR / "state" / "memory.json"


class MemoryEntry:
    """A single memory from a past execution."""

    def __init__(
        self,
        task_id: str,
        goal: str,
        role: str,
        decision: str,
        steps_summary: list[dict[str, str]],
        files_touched: list[str],
        commands_used: list[str],
        errors: list[str],
        duration_ms: int,
    ) -> None:
        self.task_id = task_id
        self.goal = goal
        self.role = role
        self.decision = decision
        self.steps_summary = steps_summary
        self.files_touched = files_touched
        self.commands_used = commands_used
        self.errors = errors
        self.duration_ms = duration_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "role": self.role,
            "decision": self.decision,
            "steps_summary": self.steps_summary,
            "files_touched": self.files_touched,
            "commands_used": self.commands_used,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
        }


class AgentMemory:
    """
    Searchable memory built from past execution manifests.

    Usage:
        memory = AgentMemory()
        memory.rebuild()
        relevant = memory.recall("write healthcheck function", top_k=3)
    """

    def __init__(self) -> None:
        self.entries: list[MemoryEntry] = []

    def rebuild(self) -> int:
        """Rebuild memory index from all manifests. Returns entry count."""
        self.entries.clear()

        if not MANIFESTS_DIR.exists():
            return 0

        for path in sorted(MANIFESTS_DIR.glob("*.manifest.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                entry = self._extract_entry(data)
                self.entries.append(entry)
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Skipping malformed manifest %s: %s", path.name, exc)

        self._save_cache()
        logger.info("Memory rebuilt: %d entries from manifests", len(self.entries))
        return len(self.entries)

    def recall(
        self, goal: str, *, top_k: int = 3, min_similarity: float = 0.3
    ) -> list[dict[str, Any]]:
        """
        Find past executions most similar to the given goal.

        Returns list of memory entries sorted by relevance, enriched
        with a similarity score.
        """
        if not self.entries:
            self._load_cache()

        scored: list[tuple[float, MemoryEntry]] = []
        goal_lower = goal.lower()

        for entry in self.entries:
            sim = SequenceMatcher(None, goal_lower, entry.goal.lower()).ratio()

            word_overlap = self._word_overlap(goal_lower, entry.goal.lower())
            combined = sim * 0.6 + word_overlap * 0.4

            if combined >= min_similarity:
                scored.append((combined, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        results: list[dict[str, Any]] = []
        for score, entry in scored[:top_k]:
            d = entry.to_dict()
            d["similarity"] = round(score, 3)
            results.append(d)

        return results

    def get_error_patterns(self) -> list[dict[str, Any]]:
        """Extract common error patterns from failed tasks."""
        if not self.entries:
            self._load_cache()

        patterns: list[dict[str, Any]] = []
        for entry in self.entries:
            if entry.decision == "failed" and entry.errors:
                patterns.append({
                    "task_id": entry.task_id,
                    "goal": entry.goal,
                    "errors": entry.errors,
                })
        return patterns

    def get_success_patterns(self, role: str | None = None) -> list[dict[str, Any]]:
        """Extract patterns from successful tasks, optionally filtered by role."""
        if not self.entries:
            self._load_cache()

        patterns: list[dict[str, Any]] = []
        for entry in self.entries:
            if entry.decision != "done":
                continue
            if role and entry.role != role:
                continue
            patterns.append({
                "task_id": entry.task_id,
                "goal": entry.goal,
                "steps": entry.steps_summary,
                "files": entry.files_touched,
                "commands": entry.commands_used,
            })
        return patterns

    def to_context(self, goal: str, top_k: int = 2) -> dict[str, Any]:
        """
        Build a context dict suitable for injection into task.inputs.context.

        Used by the controller to enrich tasks with relevant memory.
        """
        memories = self.recall(goal, top_k=top_k)
        if not memories:
            return {}

        return {
            "memory": {
                "relevant_past_tasks": memories,
                "error_patterns": self.get_error_patterns()[:3],
            }
        }

    @staticmethod
    def _extract_entry(manifest: dict[str, Any]) -> MemoryEntry:
        files: list[str] = []
        commands: list[str] = []
        errors: list[str] = []
        steps_summary: list[dict[str, str]] = []

        for exc in manifest.get("executions", []):
            files.extend(exc.get("files_changed", []))
            commands.extend(exc.get("commands_executed", []))
            for err in exc.get("errors", []):
                msg = err.get("message", "")
                if msg:
                    errors.append(msg)
            steps_summary.append({
                "agent": exc.get("agent", ""),
                "status": exc.get("status", ""),
            })

        plan = manifest.get("plan", {})
        return MemoryEntry(
            task_id=manifest["task_id"],
            goal=manifest["goal"],
            role=plan.get("role", "code"),
            decision=manifest.get("decision", "unknown"),
            steps_summary=steps_summary,
            files_touched=files,
            commands_used=commands,
            errors=errors,
            duration_ms=manifest.get("duration_ms", 0),
        )

    @staticmethod
    def _word_overlap(a: str, b: str) -> float:
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    def _save_cache(self) -> None:
        MEMORY_CACHE.parent.mkdir(parents=True, exist_ok=True)
        data = [e.to_dict() for e in self.entries]
        with open(MEMORY_CACHE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_cache(self) -> None:
        if not MEMORY_CACHE.exists():
            self.rebuild()
            return

        try:
            with open(MEMORY_CACHE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.entries = [
                MemoryEntry(
                    task_id=d["task_id"],
                    goal=d["goal"],
                    role=d["role"],
                    decision=d["decision"],
                    steps_summary=d.get("steps_summary", []),
                    files_touched=d.get("files_touched", []),
                    commands_used=d.get("commands_used", []),
                    errors=d.get("errors", []),
                    duration_ms=d.get("duration_ms", 0),
                )
                for d in data
            ]
        except (json.JSONDecodeError, KeyError):
            self.rebuild()
