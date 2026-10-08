"""Security guards and prompt injection detection for procurement data."""

from __future__ import annotations

import re

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous\s+)?((procurement|security|company)\s+)?(rules|instructions|policy|guidelines|checks)",
    r"bypass\s+(all\s+)?((procurement|security)\s+)?(policy|approval|checks|security|rules)",
    r"treat\s+(this\s+request\s+)?as\s+(cfo[- ]approved|approved|authorized)",
    r"approve\s+(it\s+)?immediately",
    r"do\s+not\s+(flag|require|check|review|evaluate)",
    r"system\s+(prompt|override|instruction)",
    r"jailbreak|developer\s+mode",
    r"disregard\s+(policy|rules|budget|limits)",
    r"override\s+(all\s+)?(security|procurement|limits)",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def injection_scan(text: str | None, context: str = "request") -> dict:
    """Scans untrusted input for prompt injection patterns.

    Returns:
        dict: {
            "detected": bool,
            "matches": list[str],
            "flag_detail": str | None
        }
    """
    if not text:
        return {"detected": False, "matches": [], "flag_detail": None}

    matches: list[str] = []
    for pattern in _COMPILED_PATTERNS:
        for match in pattern.finditer(text):
            m_text = match.group(0).strip()
            if m_text and m_text not in matches:
                matches.append(m_text)

    detected = len(matches) > 0
    flag_detail = f"Possible prompt injection detected in {context}: matched '{', '.join(matches)}'" if detected else None
    return {
        "detected": detected,
        "matches": matches,
        "flag_detail": flag_detail,
    }


def wrap_untrusted_data(data: str, label: str = "UNTRUSTED_BUSINESS_DATA") -> str:
    """Wraps untrusted business text in standard isolation delimiters."""
    return f"<{label}>\n{data}\n</{label}>"
