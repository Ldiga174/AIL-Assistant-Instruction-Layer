"""
Deploy-level validation checks.

Used by AIL Validator to verify deployment/infrastructure actions:
  - Process is running
  - Port is listening
  - Docker container is up
  - Service responds to healthcheck
"""

from __future__ import annotations

import shutil
import socket
import subprocess

from agents.shared.models import ValidationCheck


def check_port_open(host: str, port: int, timeout_seconds: float = 5) -> ValidationCheck:
    """Verify that a TCP port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return ValidationCheck(
                check_name=f"port_open:{host}:{port}",
                check_type="deploy",
                passed=True,
                message=f"Port {port} is open on {host}",
            )
    except (ConnectionRefusedError, socket.timeout, OSError) as e:
        return ValidationCheck(
            check_name=f"port_open:{host}:{port}",
            check_type="deploy",
            passed=False,
            message=f"Port {port} not reachable on {host}: {e}",
        )


def check_process_running(process_name: str) -> ValidationCheck:
    """Verify that a named process is running (via `pgrep`)."""
    if not shutil.which("pgrep"):
        return ValidationCheck(
            check_name=f"process_running:{process_name}",
            check_type="deploy",
            passed=False,
            message="pgrep not available on this system",
        )
    try:
        result = subprocess.run(
            ["pgrep", "-f", process_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        found = result.returncode == 0
        return ValidationCheck(
            check_name=f"process_running:{process_name}",
            check_type="deploy",
            passed=found,
            message=f"Process {'found' if found else 'NOT found'}: {process_name}",
        )
    except Exception as e:
        return ValidationCheck(
            check_name=f"process_running:{process_name}",
            check_type="deploy",
            passed=False,
            message=f"Check failed: {e}",
        )


def check_docker_container(container_name: str) -> ValidationCheck:
    """Verify a Docker container is running."""
    if not shutil.which("docker"):
        return ValidationCheck(
            check_name=f"docker_running:{container_name}",
            check_type="deploy",
            passed=False,
            message="Docker CLI not available",
        )
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        running = result.stdout.strip() == "true"
        return ValidationCheck(
            check_name=f"docker_running:{container_name}",
            check_type="deploy",
            passed=running,
            message=f"Container {'running' if running else 'NOT running'}: {container_name}",
        )
    except Exception as e:
        return ValidationCheck(
            check_name=f"docker_running:{container_name}",
            check_type="deploy",
            passed=False,
            message=f"Docker check failed: {e}",
        )
