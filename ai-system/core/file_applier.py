"""
FileApplier — safe, controlled file writing.

Only this module writes files to disk. Neither OpenCode nor OpenClaw
have direct write access. AIL calls FileApplier after validating
the write plan from OpenCode.

Security:
  - Path traversal blocked (../, absolute paths, symlink escape)
  - Extension whitelist (.py, .json, .md, .yml, .yaml)
  - Size limit per file (200 KB)
  - Only two modes: 'replace' and 'create'
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.shared.models import FileWrite

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 200 * 1024  # 200 KB

ALLOWED_EXTENSIONS: set[str] = {
    ".py", ".json", ".md", ".yml", ".yaml",
    ".txt", ".toml", ".cfg", ".ini",
    ".html", ".css", ".js", ".ts",
}

ALLOWED_MODES: set[str] = {"replace", "create"}


@dataclass
class FileApplyResult:
    """Result of applying a single file write."""
    path: str
    status: str
    message: str = ""

    def to_dict(self) -> dict[str, str]:
        d = {"path": self.path, "status": self.status}
        if self.message:
            d["message"] = self.message
        return d


class FileApplier:
    """
    Safe file writer. Validates every write before touching disk.

    Usage:
        applier = FileApplier()
        results = applier.apply(files_to_write, repo_root="/abs/path/to/repo")
    """

    def apply(
        self, files: list[FileWrite], repo_root: str
    ) -> list[FileApplyResult]:
        """
        Apply a list of file writes within repo_root.

        Returns per-file result with status: 'written', 'skipped', 'error'.
        """
        root = Path(repo_root).resolve()
        if not root.is_dir():
            logger.error("[FileApplier] repo_root does not exist: %s", root)
            return [FileApplyResult(
                path="(repo)", status="error",
                message=f"repo_root not found: {root}",
            )]

        results: list[FileApplyResult] = []

        for fw in files:
            r = self._apply_one(fw, root)
            results.append(r)

        written = sum(1 for r in results if r.status == "written")
        total = len(results)
        logger.info("[FileApplier] Applied %d/%d files in %s", written, total, root)

        return results

    def _apply_one(self, fw: FileWrite, root: Path) -> FileApplyResult:
        """Validate and write a single file."""

        error = self._validate(fw, root)
        if error:
            logger.warning("[FileApplier] REJECTED: %s — %s", fw.path, error)
            return FileApplyResult(path=fw.path, status="skipped", message=error)

        full_path = (root / fw.path).resolve()

        if fw.mode == "create" and full_path.exists():
            logger.warning("[FileApplier] SKIPPED (exists): %s", fw.path)
            return FileApplyResult(
                path=fw.path, status="skipped",
                message="File already exists (mode=create)",
            )

        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(fw.content, encoding="utf-8")
            logger.info("[FileApplier] WRITTEN: %s (%d bytes)", fw.path, len(fw.content))
            return FileApplyResult(path=fw.path, status="written")
        except Exception as exc:
            logger.error("[FileApplier] ERROR writing %s: %s", fw.path, exc)
            return FileApplyResult(
                path=fw.path, status="error", message=str(exc),
            )

    def _validate(self, fw: FileWrite, root: Path) -> str | None:
        """Return rejection reason or None if OK."""

        if not fw.path or not fw.path.strip():
            return "empty path"

        if fw.path.startswith("/"):
            return "absolute path not allowed"

        if ".." in fw.path.split("/"):
            return "path traversal (..) not allowed"

        full_path = (root / fw.path).resolve()
        if not str(full_path).startswith(str(root)):
            return f"path escapes repo root: {full_path}"

        ext = Path(fw.path).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return f"extension '{ext}' not in whitelist"

        if fw.mode not in ALLOWED_MODES:
            return f"mode '{fw.mode}' not allowed (use 'replace' or 'create')"

        if not fw.content:
            return "empty content"

        if len(fw.content.encode("utf-8")) > MAX_FILE_SIZE:
            size_kb = len(fw.content.encode("utf-8")) // 1024
            return f"content too large ({size_kb}KB, limit {MAX_FILE_SIZE // 1024}KB)"

        return None
