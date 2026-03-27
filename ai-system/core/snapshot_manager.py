"""
SnapshotManager — pre-change backup and rollback for file safety.

Before any file modification (patch or write), the system saves
the current state of affected files. If anything goes wrong
downstream (apply error, verify failure, validation abort),
files are restored to their pre-change state.

Rule: no snapshot → no apply. This is non-negotiable.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SNAPSHOTS_DIR = Path(__file__).resolve().parent.parent / "logs" / "snapshots"


class SnapshotManager:
    """
    Creates and restores file snapshots per task.

    Storage: logs/snapshots/{task_id}.json
    """

    def create_snapshot(
        self,
        task_id: str,
        repo_root: str,
        paths: list[str],
    ) -> dict[str, Any] | None:
        """
        Save current state of listed files before modification.

        Returns snapshot dict on success, None on failure.
        """
        root = Path(repo_root).resolve()
        if not root.is_dir():
            logger.error("[Snapshot] repo_root not found: %s", root)
            return None

        if not paths:
            logger.info("[Snapshot] No paths to snapshot")
            return None

        unique_paths = list(dict.fromkeys(paths))

        files_data: list[dict[str, Any]] = []
        for rel_path in unique_paths:
            full = (root / rel_path).resolve()
            if not str(full).startswith(str(root)):
                continue

            if full.exists() and full.is_file():
                try:
                    content = full.read_text(encoding="utf-8")
                    files_data.append({
                        "path": rel_path,
                        "existed": True,
                        "content": content,
                    })
                except Exception as exc:
                    logger.warning("[Snapshot] Cannot read %s: %s", rel_path, exc)
                    files_data.append({
                        "path": rel_path,
                        "existed": True,
                        "content": None,
                    })
            else:
                files_data.append({
                    "path": rel_path,
                    "existed": False,
                    "content": None,
                })

        snapshot = {
            "task_id": task_id,
            "repo_root": str(root),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": files_data,
        }

        snapshot_path = self._snapshot_path(task_id)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            snapshot_path.write_text(
                json.dumps(snapshot, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("[Snapshot] Cannot save snapshot: %s", exc)
            return None

        logger.info(
            "[Snapshot] Created for %s: %d file(s) tracked",
            task_id, len(files_data),
        )
        return snapshot

    def restore_snapshot(
        self,
        task_id: str,
        repo_root: str,
    ) -> list[str]:
        """
        Restore files from a previously created snapshot.

        Returns list of restored file paths.
        """
        snapshot_path = self._snapshot_path(task_id)
        if not snapshot_path.exists():
            logger.warning("[Snapshot] No snapshot found for %s", task_id)
            return []

        try:
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("[Snapshot] Cannot read snapshot %s: %s", task_id, exc)
            return []

        root = Path(repo_root).resolve()
        restored: list[str] = []

        for file_data in snapshot.get("files", []):
            rel_path = file_data["path"]
            existed = file_data["existed"]
            content = file_data["content"]
            full = (root / rel_path).resolve()

            if not str(full).startswith(str(root)):
                continue

            try:
                if existed and content is not None:
                    full.parent.mkdir(parents=True, exist_ok=True)
                    full.write_text(content, encoding="utf-8")
                    restored.append(rel_path)
                    logger.info("[Snapshot] RESTORED: %s", rel_path)
                elif not existed and full.exists():
                    full.unlink()
                    restored.append(rel_path)
                    logger.info("[Snapshot] DELETED (was new): %s", rel_path)
            except Exception as exc:
                logger.error("[Snapshot] RESTORE FAILED: %s — %s", rel_path, exc)

        logger.info(
            "[Snapshot] Rollback for %s: %d/%d files restored",
            task_id, len(restored), len(snapshot.get("files", [])),
        )
        return restored

    def has_snapshot(self, task_id: str) -> bool:
        return self._snapshot_path(task_id).exists()

    @staticmethod
    def _snapshot_path(task_id: str) -> Path:
        return SNAPSHOTS_DIR / f"{task_id}.json"
