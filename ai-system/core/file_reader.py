"""
FileReader — safe, controlled file reading for project context.

Reads files from within the repo root only, with strict limits:
  - Path validation (no ../, no absolute, no escape)
  - Extension whitelist
  - Per-file size limit (64 KB)
  - Max files per read (5)
  - Total context size limit (150 KB)

Used by AIL before calling OpenCode so the model works
on real code, not in a vacuum.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 64 * 1024       # 64 KB per file
MAX_FILES = 5                    # max files per task
MAX_TOTAL_SIZE = 150 * 1024     # 150 KB total context

ALLOWED_EXTENSIONS: set[str] = {
    ".py", ".json", ".md", ".yml", ".yaml", ".toml", ".txt",
}

DEFAULT_SCAN_PATHS: list[str] = [
    "README.md",
    "src/main.py",
    "src/api.py",
]


@dataclass
class FileContext:
    """A single file's content read from the project."""
    path: str
    content: str
    size: int

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "content": self.content, "size": self.size}


class FileReader:
    """
    Safe file reader. Validates every path before reading.

    Usage:
        reader = FileReader()
        context = reader.read(file_paths, repo_root)
    """

    def read(
        self,
        file_paths: list[str],
        repo_root: str,
        max_files: int | None = None,
    ) -> list[FileContext]:
        """
        Read a list of files within repo_root.

        Returns list of FileContext for files that passed validation.
        Silently skips files that fail validation or don't exist.
        """
        root = Path(repo_root).resolve()
        if not root.is_dir():
            logger.error("[FileReader] repo_root not found: %s", root)
            return []

        limit = max_files if max_files is not None else MAX_FILES
        paths = file_paths[:limit]
        if len(file_paths) > limit:
            logger.warning(
                "[FileReader] Truncated file list from %d to %d",
                len(file_paths), limit,
            )

        results: list[FileContext] = []
        total_size = 0

        for rel_path in paths:
            fc = self._read_one(rel_path, root, total_size)
            if fc:
                results.append(fc)
                total_size += fc.size

        logger.info(
            "[FileReader] Read %d file(s), %d bytes total from %s",
            len(results), total_size, root,
        )
        return results

    def read_with_defaults(
        self,
        file_paths: list[str] | None,
        repo_root: str,
        max_files: int | None = None,
    ) -> list[FileContext]:
        """
        Read specified files, falling back to default scan paths
        if none are specified.
        """
        if file_paths:
            return self.read(file_paths, repo_root, max_files=max_files)

        root = Path(repo_root).resolve()
        existing = [
            p for p in DEFAULT_SCAN_PATHS
            if (root / p).exists()
        ]
        if existing:
            logger.info("[FileReader] Using default scan paths: %s", existing)
            return self.read(existing, repo_root, max_files=max_files)

        logger.info("[FileReader] No files to read (no explicit paths, no defaults found)")
        return []

    def _read_one(
        self, rel_path: str, root: Path, current_total: int
    ) -> FileContext | None:
        """Validate and read a single file."""

        error = self._validate_path(rel_path, root)
        if error:
            logger.warning("[FileReader] REJECTED: %s — %s", rel_path, error)
            return None

        full_path = (root / rel_path).resolve()

        if not full_path.exists():
            logger.debug("[FileReader] SKIP (not found): %s", rel_path)
            return None

        if not full_path.is_file():
            logger.warning("[FileReader] SKIP (not a file): %s", rel_path)
            return None

        file_size = full_path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            logger.warning(
                "[FileReader] SKIP (too large): %s (%d bytes, limit %d)",
                rel_path, file_size, MAX_FILE_SIZE,
            )
            return None

        if current_total + file_size > MAX_TOTAL_SIZE:
            logger.warning(
                "[FileReader] SKIP (total limit): %s would push total to %d (limit %d)",
                rel_path, current_total + file_size, MAX_TOTAL_SIZE,
            )
            return None

        try:
            content = full_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.error("[FileReader] ERROR reading %s: %s", rel_path, exc)
            return None

        logger.info("[FileReader] READ: %s (%d bytes)", rel_path, len(content))
        return FileContext(path=rel_path, content=content, size=len(content))

    @staticmethod
    def _validate_path(rel_path: str, root: Path) -> str | None:
        """Return rejection reason or None if path is safe."""

        if not rel_path or not rel_path.strip():
            return "empty path"

        if rel_path.startswith("/"):
            return "absolute path not allowed"

        if ".." in rel_path.split("/"):
            return "path traversal (..) not allowed"

        full_path = (root / rel_path).resolve()
        if not str(full_path).startswith(str(root)):
            return f"path escapes repo root"

        ext = Path(rel_path).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return f"extension '{ext}' not in whitelist"

        return None
