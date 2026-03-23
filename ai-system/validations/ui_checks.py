"""
UI-level validation checks.

Used by AIL Validator when OpenClaw claims a UI action was performed:
  - HTTP endpoint responds
  - Expected content is present in response
  - Service health checks pass
"""

from __future__ import annotations

import urllib.error
import urllib.request

from agents.shared.models import ValidationCheck


def check_http_reachable(
    url: str, timeout_seconds: int = 10
) -> ValidationCheck:
    """Verify that an HTTP endpoint is reachable and returns 2xx."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            code = resp.getcode()
            ok = 200 <= code < 300
            return ValidationCheck(
                check_name=f"http_reachable:{url}",
                check_type="ui",
                passed=ok,
                message=f"HTTP {code}",
                expected="2xx",
                actual=str(code),
            )
    except urllib.error.HTTPError as e:
        return ValidationCheck(
            check_name=f"http_reachable:{url}",
            check_type="ui",
            passed=False,
            message=f"HTTP error: {e.code}",
            expected="2xx",
            actual=str(e.code),
        )
    except Exception as e:
        return ValidationCheck(
            check_name=f"http_reachable:{url}",
            check_type="ui",
            passed=False,
            message=f"Connection error: {e}",
            expected="2xx",
            actual="unreachable",
        )


def check_response_contains(
    url: str, expected_text: str, timeout_seconds: int = 10
) -> ValidationCheck:
    """Verify that the response body contains expected text."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            found = expected_text in body
            return ValidationCheck(
                check_name=f"response_contains:{url}",
                check_type="ui",
                passed=found,
                message=f"Text {'found' if found else 'NOT found'}: '{expected_text[:50]}'",
                expected=expected_text[:100],
                actual=f"{'present' if found else 'absent'} in {len(body)} chars",
            )
    except Exception as e:
        return ValidationCheck(
            check_name=f"response_contains:{url}",
            check_type="ui",
            passed=False,
            message=f"Could not fetch: {e}",
        )
