"""Remove known secrets and common key shapes before a log line is written."""

from __future__ import annotations

import re

_KEY_SHAPES = re.compile(r"\b(?:sk-[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9._\-]{8,})\b")


def scrub(text: str, secrets: list[str]) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[redacted]")
    return _KEY_SHAPES.sub("[redacted]", redacted)
