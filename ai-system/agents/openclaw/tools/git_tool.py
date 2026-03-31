"""
Git tool — structured git operations.

Supported operations:
  - status: working tree status
  - diff: show changes (staged/unstaged)
  - log: recent commit history
  - add: stage files
  - commit: create a commit
  - push: push to remote
  - pull: pull from remote
  - branch: list/create branches
  - checkout: switch branches
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
import time
from typing import Any

from agents.shared.tools import BaseTool, ToolResult

logger = logging.getLogger(__name__)

GIT_TIMEOUT = 30


class GitTool(BaseTool):
    name = "git"
    operations = [
        "status", "diff", "log", "add", "commit",
        "push", "pull", "branch", "checkout",
    ]

    BLOCKED_GIT_OPS = {"reset --hard", "push --force", "clean -fd", "reflog expire"}

    def run(self, operation: str, params: dict[str, Any], cwd: str) -> ToolResult:
        handler = getattr(self, f"_op_{operation}", None)
        if not handler:
            return self._fail(operation, f"Unknown git operation: {operation}")
        return handler(params, cwd)

    def detect(self, text: str) -> tuple[str, dict[str, Any]] | None:
        mappings = [
            (["git status", "git diff --stat", "статус репо"], "status", {}),
            (["git diff", "покажи изменения", "show changes"], "diff", {}),
            (["git log", "история коммитов", "commit history"], "log", {}),
            (["git add", "добавь в индекс", "stage files"], "add", {}),
            (["git commit", "закоммить", "сделай коммит"], "commit", {}),
            (["git push", "запушь", "push to remote"], "push", {}),
            (["git pull", "подтяни", "pull from remote"], "pull", {}),
        ]
        for keywords, op, default_params in mappings:
            if any(kw in text for kw in keywords):
                return op, default_params
        return None

    def _exec_git(self, args: list[str], cwd: str) -> tuple[int, str, str, int]:
        cmd = ["git"] + args
        cmd_str = " ".join(cmd)

        for blocked in self.BLOCKED_GIT_OPS:
            if blocked in cmd_str:
                return -1, "", f"BLOCKED: destructive git operation ({blocked})", 0

        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT,
            )
            dur = int((time.monotonic() - t0) * 1000)
            return proc.returncode, proc.stdout.strip(), proc.stderr.strip(), dur
        except subprocess.TimeoutExpired:
            dur = int((time.monotonic() - t0) * 1000)
            return -1, "", f"Timeout after {GIT_TIMEOUT}s", dur
        except FileNotFoundError:
            return 127, "", "git not found", 0

    def _op_status(self, params: dict[str, Any], cwd: str) -> ToolResult:
        code, out, err, dur = self._exec_git(["status", "--porcelain=v1"], cwd)
        if code != 0:
            return self._fail("status", err or out, ["git status --porcelain=v1"])

        files = {"modified": [], "added": [], "deleted": [], "untracked": []}
        for line in out.splitlines():
            if len(line) < 3:
                continue
            xy, path = line[:2], line[3:]
            if "M" in xy:
                files["modified"].append(path)
            elif "A" in xy:
                files["added"].append(path)
            elif "D" in xy:
                files["deleted"].append(path)
            elif "?" in xy:
                files["untracked"].append(path)

        return self._ok("status", {"files": files, "clean": not out.strip()}, ["git status --porcelain=v1"])

    def _op_diff(self, params: dict[str, Any], cwd: str) -> ToolResult:
        staged = params.get("staged", False)
        args = ["diff", "--stat"]
        if staged:
            args.append("--cached")
        code, out, err, dur = self._exec_git(args, cwd)
        if code != 0:
            return self._fail("diff", err, [f"git {' '.join(args)}"])
        return self._ok("diff", {"diff_stat": out}, [f"git {' '.join(args)}"])

    def _op_log(self, params: dict[str, Any], cwd: str) -> ToolResult:
        n = params.get("count", 10)
        fmt = params.get("format", "%H|%s|%an|%ar")
        args = ["log", f"-{n}", f"--format={fmt}"]
        code, out, err, dur = self._exec_git(args, cwd)
        if code != 0:
            return self._fail("log", err, [f"git {' '.join(args)}"])

        commits = []
        for line in out.splitlines():
            parts = line.split("|", 3)
            if len(parts) >= 4:
                commits.append({
                    "hash": parts[0], "subject": parts[1],
                    "author": parts[2], "relative_date": parts[3],
                })

        return self._ok("log", {"commits": commits, "count": len(commits)}, [f"git log -{n}"])

    def _op_add(self, params: dict[str, Any], cwd: str) -> ToolResult:
        files = params.get("files", ["."])
        if isinstance(files, str):
            files = [files]
        args = ["add"] + files
        code, out, err, dur = self._exec_git(args, cwd)
        if code != 0:
            return self._fail("add", err, [f"git {' '.join(args)}"])
        return self._ok("add", {"staged": files}, [f"git {' '.join(args)}"])

    def _op_commit(self, params: dict[str, Any], cwd: str) -> ToolResult:
        message = params.get("message", "")
        if not message:
            return self._fail("commit", "Commit message is required")
        args = ["commit", "-m", message]
        code, out, err, dur = self._exec_git(args, cwd)
        if code != 0:
            return self._fail("commit", err or out, [f"git commit -m '{message}'"])
        return self._ok("commit", {"message": message, "output": out}, [f"git commit -m '{message}'"])

    def _op_push(self, params: dict[str, Any], cwd: str) -> ToolResult:
        remote = params.get("remote", "origin")
        branch = params.get("branch", "")
        args = ["push", remote]
        if branch:
            args.append(branch)
        code, out, err, dur = self._exec_git(args, cwd)
        combined = (out + "\n" + err).strip()
        if code != 0:
            return self._fail("push", combined, [f"git {' '.join(args)}"])
        return self._ok("push", {"output": combined}, [f"git {' '.join(args)}"])

    def _op_pull(self, params: dict[str, Any], cwd: str) -> ToolResult:
        remote = params.get("remote", "origin")
        branch = params.get("branch", "")
        args = ["pull", remote]
        if branch:
            args.append(branch)
        code, out, err, dur = self._exec_git(args, cwd)
        combined = (out + "\n" + err).strip()
        if code != 0:
            return self._fail("pull", combined, [f"git {' '.join(args)}"])
        return self._ok("pull", {"output": combined}, [f"git {' '.join(args)}"])

    def _op_branch(self, params: dict[str, Any], cwd: str) -> ToolResult:
        create = params.get("create", "")
        if create:
            args = ["checkout", "-b", create]
        else:
            args = ["branch", "--list"]
        code, out, err, dur = self._exec_git(args, cwd)
        if code != 0:
            return self._fail("branch", err, [f"git {' '.join(args)}"])

        if create:
            return self._ok("branch", {"created": create}, [f"git {' '.join(args)}"])

        branches = [b.strip().lstrip("* ") for b in out.splitlines() if b.strip()]
        current = next((b.strip()[2:] for b in out.splitlines() if b.startswith("*")), "")
        return self._ok("branch", {"branches": branches, "current": current}, [f"git {' '.join(args)}"])

    def _op_checkout(self, params: dict[str, Any], cwd: str) -> ToolResult:
        target = params.get("branch", params.get("target", ""))
        if not target:
            return self._fail("checkout", "Branch/target is required")
        args = ["checkout", target]
        code, out, err, dur = self._exec_git(args, cwd)
        combined = (out + "\n" + err).strip()
        if code != 0:
            return self._fail("checkout", combined, [f"git {' '.join(args)}"])
        return self._ok("checkout", {"target": target, "output": combined}, [f"git {' '.join(args)}"])
