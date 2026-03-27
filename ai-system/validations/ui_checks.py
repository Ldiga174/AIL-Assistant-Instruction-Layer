"""
UI-level verify gates.

Currently a placeholder — no real UI automation yet.
All gates return passed=True with status "not_applicable".

Will be activated when OpenClaw gains browser/UI capabilities.
"""

from __future__ import annotations

from agents.shared.models import ValidationCheck


def gate_ui_not_applicable() -> ValidationCheck:
    """Placeholder: UI verification not yet implemented."""
    return ValidationCheck(
        check_name="gate:ui_check",
        check_type="ui",
        passed=True,
        message="N/A (UI automation not active)",
    )
