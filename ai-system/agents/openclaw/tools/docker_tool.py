"""
Docker tool — structured Docker operations.

Supported operations:
  - build: build an image from Dockerfile
  - run: run a container
  - stop: stop a running container
  - ps: list running containers
  - logs: fetch container logs
  - images: list local images
  - push: push image to registry
"""

from __future__ import annotations

import logging
import subprocess
import time
from typing import Any

from agents.shared.tools import BaseTool, ToolResult

logger = logging.getLogger(__name__)

DOCKER_TIMEOUT = 120


class DockerTool(BaseTool):
    name = "docker"
    operations = ["build", "run", "stop", "ps", "logs", "images", "push"]

    BLOCKED_DOCKER_OPS = {"system prune -a --force", "rmi -f $("}

    def run(self, operation: str, params: dict[str, Any], cwd: str) -> ToolResult:
        handler = getattr(self, f"_op_{operation}", None)
        if not handler:
            return self._fail(operation, f"Unknown docker operation: {operation}")
        return handler(params, cwd)

    def detect(self, text: str) -> tuple[str, dict[str, Any]] | None:
        mappings = [
            (["docker build", "собери образ", "build image"], "build", {}),
            (["docker run", "запусти контейнер", "run container"], "run", {}),
            (["docker stop", "останови контейнер", "stop container"], "stop", {}),
            (["docker ps", "список контейнеров", "list containers"], "ps", {}),
            (["docker logs", "логи контейнера", "container logs"], "logs", {}),
            (["docker images", "список образов", "list images"], "images", {}),
            (["docker push", "запушь образ", "push image"], "push", {}),
        ]
        for keywords, op, default_params in mappings:
            if any(kw in text for kw in keywords):
                return op, default_params
        return None

    def _exec_docker(
        self, args: list[str], cwd: str, timeout: int = DOCKER_TIMEOUT,
    ) -> tuple[int, str, str, int]:
        cmd = ["docker"] + args
        cmd_str = " ".join(cmd)

        for blocked in self.BLOCKED_DOCKER_OPS:
            if blocked in cmd_str:
                return -1, "", f"BLOCKED: destructive docker operation ({blocked})", 0

        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
            )
            dur = int((time.monotonic() - t0) * 1000)
            return proc.returncode, proc.stdout.strip()[:5000], proc.stderr.strip()[:5000], dur
        except subprocess.TimeoutExpired:
            dur = int((time.monotonic() - t0) * 1000)
            return -1, "", f"Timeout after {timeout}s", dur
        except FileNotFoundError:
            return 127, "", "docker not found", 0

    def _op_build(self, params: dict[str, Any], cwd: str) -> ToolResult:
        tag = params.get("tag", "")
        dockerfile = params.get("dockerfile", "Dockerfile")
        context = params.get("context", ".")
        args = ["build", "-f", dockerfile]
        if tag:
            args.extend(["-t", tag])
        args.append(context)

        cmd_str = f"docker {' '.join(args)}"
        code, out, err, dur = self._exec_docker(args, cwd)
        if code != 0:
            return self._fail("build", err or out, [cmd_str])
        return self._ok("build", {"tag": tag, "output": out[-1000:]}, [cmd_str])

    def _op_run(self, params: dict[str, Any], cwd: str) -> ToolResult:
        image = params.get("image", "")
        if not image:
            return self._fail("run", "Image name is required")

        args = ["run", "-d"]
        name = params.get("name", "")
        if name:
            args.extend(["--name", name])

        ports = params.get("ports", [])
        for p in ports:
            args.extend(["-p", str(p)])

        env_vars = params.get("env", {})
        for k, v in env_vars.items():
            args.extend(["-e", f"{k}={v}"])

        args.append(image)

        cmd_str = f"docker {' '.join(args)}"
        code, out, err, dur = self._exec_docker(args, cwd)
        if code != 0:
            return self._fail("run", err or out, [cmd_str])
        return self._ok("run", {"container_id": out[:12], "image": image}, [cmd_str])

    def _op_stop(self, params: dict[str, Any], cwd: str) -> ToolResult:
        container = params.get("container", "")
        if not container:
            return self._fail("stop", "Container name/id is required")
        args = ["stop", container]
        cmd_str = f"docker {' '.join(args)}"
        code, out, err, dur = self._exec_docker(args, cwd)
        if code != 0:
            return self._fail("stop", err or out, [cmd_str])
        return self._ok("stop", {"stopped": container}, [cmd_str])

    def _op_ps(self, params: dict[str, Any], cwd: str) -> ToolResult:
        show_all = params.get("all", False)
        args = ["ps", "--format", "{{.ID}}|{{.Image}}|{{.Status}}|{{.Names}}"]
        if show_all:
            args.append("-a")
        cmd_str = f"docker {' '.join(args)}"
        code, out, err, dur = self._exec_docker(args, cwd)
        if code != 0:
            return self._fail("ps", err, [cmd_str])

        containers = []
        for line in out.splitlines():
            parts = line.split("|", 3)
            if len(parts) >= 4:
                containers.append({
                    "id": parts[0], "image": parts[1],
                    "status": parts[2], "name": parts[3],
                })

        return self._ok("ps", {"containers": containers, "count": len(containers)}, [cmd_str])

    def _op_logs(self, params: dict[str, Any], cwd: str) -> ToolResult:
        container = params.get("container", "")
        if not container:
            return self._fail("logs", "Container name/id is required")
        tail = params.get("tail", 50)
        args = ["logs", "--tail", str(tail), container]
        cmd_str = f"docker {' '.join(args)}"
        code, out, err, dur = self._exec_docker(args, cwd)
        if code != 0:
            return self._fail("logs", err, [cmd_str])
        return self._ok("logs", {"logs": out, "container": container}, [cmd_str])

    def _op_images(self, params: dict[str, Any], cwd: str) -> ToolResult:
        args = ["images", "--format", "{{.Repository}}:{{.Tag}}|{{.Size}}|{{.ID}}"]
        cmd_str = f"docker {' '.join(args)}"
        code, out, err, dur = self._exec_docker(args, cwd)
        if code != 0:
            return self._fail("images", err, [cmd_str])

        images = []
        for line in out.splitlines():
            parts = line.split("|", 2)
            if len(parts) >= 3:
                images.append({"name": parts[0], "size": parts[1], "id": parts[2]})

        return self._ok("images", {"images": images, "count": len(images)}, [cmd_str])

    def _op_push(self, params: dict[str, Any], cwd: str) -> ToolResult:
        image = params.get("image", "")
        if not image:
            return self._fail("push", "Image name is required")
        args = ["push", image]
        cmd_str = f"docker {' '.join(args)}"
        code, out, err, dur = self._exec_docker(args, cwd, timeout=300)
        combined = (out + "\n" + err).strip()
        if code != 0:
            return self._fail("push", combined, [cmd_str])
        return self._ok("push", {"image": image, "output": combined[-500:]}, [cmd_str])
