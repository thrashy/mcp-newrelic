"""Redact New Relic secrets from error text before it reaches logs or MCP clients."""

import re

# ponytail: text-only redaction — every surface we scrub (error/exception strings) is already a str.
# Add recursive dict/list redaction only if we ever start logging raw request payloads.
_SECRET_PATTERNS = (
    re.compile(r"\b(NR(?:AA|AK|AL|II|IK|SP)-)[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"\b(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"\b(NEW_RELIC_(?:API|INSERT|LICENSE)_KEY\s*=\s*)[^\s'\",}]+", re.IGNORECASE),
)


def redact_secrets(text: str) -> str:
    """Replace New Relic API keys, bearer tokens, and key env-assignments with a redacted marker."""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r"\1[REDACTED]", text)
    return text
