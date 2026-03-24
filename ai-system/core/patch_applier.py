"""
PatchApplier — controlled, atomic patch operations on existing files.

Modes:
  - replace_block: find exact `target` text, replace with `content`
  - insert_after:  find exact `target` text, insert `content` after it
  - insert_before: find exact `target` text, insert `content` before it

Safety:
  - Path validation (no ../, absolute, escape)
  - Extension whitelist
  - Patch size limit (32 KB per patch content)
  - Max 20 patch operations per task
  - Atomic per file: if any patch on a file fails, that file is rolled back
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.shared.models import FilePatch

logger = logging.getLogger(__name__)

MAX_PATCH_SIZE = 32 * 1024   # 32 KB per patch content
MAX_PATCHES = 20              # per task

ALLOWED_MODES: set[str] = {"replace_block", "insert_after", "insert_before"}

ALLOWED_EXTENSIONS: set[str] = {
    ".py", ".json", ".md", ".yml", ".yaml",
    ".txt", ".toml", ".cfg", ".ini",
    ".html", ".css", ".js", ".ts",
}


@dataclass
class PatchResult:
    """Result of applying a single patch operation."""
    path: str
    mode: str
    status: str
    message: str = ""

    def to_dict(self) -> dict[str, str]:
        d = {"path": self.path, "mode": self.mode, "status": self.status}
        if self.message:
            d["message"] = self.message
        return d


class PatchApplier:
    """
    Safe, atomic patch applier.

    Groups patches by file, applies all patches for a file atomically.
    If any patch on a file fails, the entire file is rolled back.
    """

    def apply(
        self, patches: list[FilePatch], repo_root: str
    ) -> list[PatchResult]:
        root = Path(repo_root).resolve()
        if not root.is_dir():
            return [PatchResult(
                path="(repo)", mode="", status="error",
                message=f"repo_root not found: {root}",
            )]

        if len(patches) > MAX_PATCHES:
            logger.warning(
                "[PatchApplier] Truncated patches from %d to %d",
                len(patches), MAX_PATCHES,
            )
            patches = patches[:MAX_PATCHES]

        by_file: dict[str, list[FilePatch]] = {}
        for p in patches:
            by_file.setdefault(p.path, []).append(p)

        results: list[PatchResult] = []

        for file_path, file_patches in by_file.items():
            file_results = self._apply_file_atomic(file_path, file_patches, root)
            results.extend(file_results)

        applied = sum(1 for r in results if r.status == "applied")
        logger.info(
            "[PatchApplier] %d/%d patches applied in %s",
            applied, len(results), root,
        )
        return results

    def _apply_file_atomic(
        self, rel_path: str, patches: list[FilePatch], root: Path
    ) -> list[PatchResult]:
        """Apply all patches for one file atomically."""

        error = self._validate_path(rel_path, root)
        if error:
            logger.warning("[PatchApplier] REJECTED: %s — %s", rel_path, error)
            return [PatchResult(
                path=rel_path, mode=p.mode, status="skipped", message=error,
            ) for p in patches]

        full_path = (root / rel_path).resolve()
        if not full_path.exists():
            return [PatchResult(
                path=rel_path, mode=p.mode, status="error",
                message="file does not exist",
            ) for p in patches]

        try:
            original = full_path.read_text(encoding="utf-8")
        except Exception as exc:
            return [PatchResult(
                path=rel_path, mode=p.mode, status="error",
                message=f"cannot read file: {exc}",
            ) for p in patches]

        current = original
        results: list[PatchResult] = []

        for patch in patches:
            validation = self._validate_patch(patch)
            if validation:
                results.append(PatchResult(
                    path=rel_path, mode=patch.mode,
                    status="skipped", message=validation,
                ))
                self._rollback(full_path, original)
                for remaining in patches[patches.index(patch) + 1:]:
                    results.append(PatchResult(
                        path=rel_path, mode=remaining.mode,
                        status="skipped", message="rolled back due to earlier failure",
                    ))
                return results

            new_content, ok, msg = self._apply_one(current, patch)
            if not ok:
                results.append(PatchResult(
                    path=rel_path, mode=patch.mode,
                    status="error", message=msg,
                ))
                self._rollback(full_path, original)
                for remaining in patches[patches.index(patch) + 1:]:
                    results.append(PatchResult(
                        path=rel_path, mode=remaining.mode,
                        status="skipped", message="rolled back due to earlier failure",
                    ))
                return results

            current = new_content
            results.append(PatchResult(
                path=rel_path, mode=patch.mode,
                status="applied", message=msg,
            ))

        try:
            full_path.write_text(current, encoding="utf-8")
            logger.info(
                "[PatchApplier] WRITTEN: %s (%d patches, %d -> %d bytes)",
                rel_path, len(patches), len(original), len(current),
            )
        except Exception as exc:
            self._rollback(full_path, original)
            return [PatchResult(
                path=rel_path, mode="write", status="error",
                message=f"write failed: {exc}",
            )]

        return results

    @staticmethod
    def _apply_one(
        content: str, patch: FilePatch
    ) -> tuple[str, bool, str]:
        """Apply a single patch to content. Returns (new_content, ok, message)."""

        if patch.target not in content:
            return content, False, f"target not found: '{patch.target[:60]}...'"

        if patch.mode == "replace_block":
            new = content.replace(patch.target, patch.content, 1)
            return new, True, f"replaced '{patch.target[:40]}...'"

        elif patch.mode == "insert_after":
            idx = content.index(patch.target) + len(patch.target)
            new = content[:idx] + patch.content + content[idx:]
            return new, True, f"inserted after '{patch.target[:40]}...'"

        elif patch.mode == "insert_before":
            idx = content.index(patch.target)
            new = content[:idx] + patch.content + content[idx:]
            return new, True, f"inserted before '{patch.target[:40]}...'"

        return content, False, f"unknown mode: {patch.mode}"

    @staticmethod
    def _rollback(full_path: Path, original: str) -> None:
        """Restore original content on failure."""
        try:
            full_path.write_text(original, encoding="utf-8")
            logger.info("[PatchApplier] ROLLBACK: %s", full_path.name)
        except Exception as exc:
            logger.error("[PatchApplier] ROLLBACK FAILED: %s — %s", full_path, exc)

    @staticmethod
    def _validate_path(rel_path: str, root: Path) -> str | None:
        if not rel_path or not rel_path.strip():
            return "empty path"
        if rel_path.startswith("/"):
            return "absolute path not allowed"
        if ".." in rel_path.split("/"):
            return "path traversal (..) not allowed"
        full = (root / rel_path).resolve()
        if not str(full).startswith(str(root)):
            return "path escapes repo root"
        ext = Path(rel_path).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return f"extension '{ext}' not in whitelist"
        return None

    @staticmethod
    def _validate_patch(patch: FilePatch) -> str | None:
        if patch.mode not in ALLOWED_MODES:
            return f"mode '{patch.mode}' not allowed"
        if not patch.target:
            return "empty target"
        if not patch.content:
            return "empty content"
        if len(patch.content.encode("utf-8")) > MAX_PATCH_SIZE:
            return f"content too large ({len(patch.content.encode('utf-8'))} bytes, limit {MAX_PATCH_SIZE})"
        return None
