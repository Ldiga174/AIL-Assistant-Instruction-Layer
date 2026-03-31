"""
Cloud tool — structured Google Cloud (gcloud) operations.

Supported operations:
  - deploy: deploy to Cloud Run
  - describe: describe a Cloud Run service
  - logs: read Cloud Run logs
  - list: list Cloud Run services
  - set_env: update env vars on a running service
"""

from __future__ import annotations

import logging
import subprocess
import time
from typing import Any

from agents.shared.tools import BaseTool, ToolResult

logger = logging.getLogger(__name__)

GCLOUD_TIMEOUT = 120


class CloudTool(BaseTool):
    name = "cloud"
    operations = ["deploy", "describe", "logs", "list", "set_env"]

    def run(self, operation: str, params: dict[str, Any], cwd: str) -> ToolResult:
        handler = getattr(self, f"_op_{operation}", None)
        if not handler:
            return self._fail(operation, f"Unknown cloud operation: {operation}")
        return handler(params, cwd)

    def detect(self, text: str) -> tuple[str, dict[str, Any]] | None:
        mappings = [
            (["cloud run deploy", "gcloud run deploy", "задеплой", "deploy to cloud"], "deploy", {}),
            (["cloud run describe", "describe service", "статус сервиса"], "describe", {}),
            (["cloud run logs", "gcloud logs", "логи сервиса", "service logs"], "logs", {}),
            (["cloud run list", "gcloud run services", "список сервисов"], "list", {}),
        ]
        for keywords, op, default_params in mappings:
            if any(kw in text for kw in keywords):
                return op, default_params
        return None

    def _exec_gcloud(
        self, args: list[str], cwd: str, timeout: int = GCLOUD_TIMEOUT,
    ) -> tuple[int, str, str, int]:
        cmd = ["gcloud"] + args + ["--format=json", "--quiet"]
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
            )
            dur = int((time.monotonic() - t0) * 1000)
            return proc.returncode, proc.stdout.strip()[:10000], proc.stderr.strip()[:5000], dur
        except subprocess.TimeoutExpired:
            dur = int((time.monotonic() - t0) * 1000)
            return -1, "", f"Timeout after {timeout}s", dur
        except FileNotFoundError:
            return 127, "", "gcloud not found", 0

    def _op_deploy(self, params: dict[str, Any], cwd: str) -> ToolResult:
        service = params.get("service", "")
        image = params.get("image", "")
        region = params.get("region", "us-central1")

        if not service:
            return self._fail("deploy", "Service name is required")
        if not image:
            return self._fail("deploy", "Image name is required")

        args = [
            "run", "deploy", service,
            "--image", image,
            "--region", region,
            "--platform", "managed",
        ]

        port = params.get("port", "")
        if port:
            args.extend(["--port", str(port)])

        memory = params.get("memory", "")
        if memory:
            args.extend(["--memory", memory])

        allow_unauth = params.get("allow_unauthenticated", False)
        if allow_unauth:
            args.append("--allow-unauthenticated")

        cmd_str = f"gcloud {' '.join(args)}"
        code, out, err, dur = self._exec_gcloud(args, cwd)
        if code != 0:
            return self._fail("deploy", err or out, [cmd_str])
        return self._ok("deploy", {"service": service, "region": region, "output": out[:2000]}, [cmd_str])

    def _op_describe(self, params: dict[str, Any], cwd: str) -> ToolResult:
        service = params.get("service", "")
        region = params.get("region", "us-central1")
        if not service:
            return self._fail("describe", "Service name is required")

        args = ["run", "services", "describe", service, "--region", region]
        cmd_str = f"gcloud {' '.join(args)}"
        code, out, err, dur = self._exec_gcloud(args, cwd)
        if code != 0:
            return self._fail("describe", err or out, [cmd_str])
        return self._ok("describe", {"service": service, "details": out[:3000]}, [cmd_str])

    def _op_logs(self, params: dict[str, Any], cwd: str) -> ToolResult:
        service = params.get("service", "")
        limit = params.get("limit", 50)
        if not service:
            return self._fail("logs", "Service name is required")

        args = ["logging", "read", f'resource.type="cloud_run_revision" AND resource.labels.service_name="{service}"', "--limit", str(limit)]
        cmd_str = f"gcloud {' '.join(args)}"
        code, out, err, dur = self._exec_gcloud(args, cwd, timeout=30)
        if code != 0:
            return self._fail("logs", err or out, [cmd_str])
        return self._ok("logs", {"service": service, "entries": out[:5000]}, [cmd_str])

    def _op_list(self, params: dict[str, Any], cwd: str) -> ToolResult:
        region = params.get("region", "")
        args = ["run", "services", "list"]
        if region:
            args.extend(["--region", region])
        cmd_str = f"gcloud {' '.join(args)}"
        code, out, err, dur = self._exec_gcloud(args, cwd)
        if code != 0:
            return self._fail("list", err or out, [cmd_str])
        return self._ok("list", {"services": out[:5000]}, [cmd_str])

    def _op_set_env(self, params: dict[str, Any], cwd: str) -> ToolResult:
        service = params.get("service", "")
        region = params.get("region", "us-central1")
        env_vars = params.get("env", {})
        if not service:
            return self._fail("set_env", "Service name is required")
        if not env_vars:
            return self._fail("set_env", "Environment variables are required")

        env_str = ",".join(f"{k}={v}" for k, v in env_vars.items())
        args = ["run", "services", "update", service, "--region", region, "--set-env-vars", env_str]
        cmd_str = f"gcloud {' '.join(args)}"
        code, out, err, dur = self._exec_gcloud(args, cwd)
        if code != 0:
            return self._fail("set_env", err or out, [cmd_str])
        return self._ok("set_env", {"service": service, "env_vars": list(env_vars.keys())}, [cmd_str])
