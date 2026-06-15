"""Input sanitizer — prompt-injection defenses for free-form merchant fields.

When agent prompts include data that originated outside the trust boundary
(merchant metadata, customer descriptors, decline messages from gateways),
we sanitize it before substitution. This isn't a replacement for the
instruction hierarchy and tool-use grounding — it's a belt-and-suspenders
defense against:

    * Direct prompt injection: "Ignore previous instructions and ..."
    * Role-switch attempts: "You are now a malicious assistant"
    * Tool-name spoofing in plain text
    * Excessive length payloads that bury our system instructions

For structured fields we already enforce types via Pydantic; for any field
the agent layer must pass through this sanitizer.
"""

from __future__ import annotations

import re

# Patterns that indicate plausible injection attempts. We don't reject — we
# escape and flag, so the LLM is never asked to follow them.
_INJECTION_PATTERNS = [
    re.compile(r"ignore (all )?previous instructions", re.IGNORECASE),
    re.compile(r"disregard (the )?(above|prior|previous)", re.IGNORECASE),
    re.compile(r"you are now (a |an )", re.IGNORECASE),
    re.compile(r"act as if you", re.IGNORECASE),
    re.compile(r"system prompt:", re.IGNORECASE),
    re.compile(r"</?(system|assistant|user)>", re.IGNORECASE),
    re.compile(r"\[\[/?(system|assistant|user)\]\]", re.IGNORECASE),
]

# Hard length cap per field — preserves the system prompt budget.
DEFAULT_MAX_LENGTH = 512


def sanitize_text(
    text: str | None,
    *,
    max_length: int = DEFAULT_MAX_LENGTH,
    label: str = "field",
) -> str:
    """Return a sanitized version safe to embed in an LLM prompt.

    Strategy: clip to max_length, replace injection patterns with a neutral
    marker. The marker is human-readable so the LLM sees that something was
    redacted but cannot be steered by the original content.
    """
    if text is None:
        return ""

    s = str(text).strip()
    if not s:
        return ""

    # Length cap with explicit truncation marker.
    if len(s) > max_length:
        s = s[:max_length].rstrip() + " […truncated]"

    # Replace each injection pattern with a flag.
    for pat in _INJECTION_PATTERNS:
        s = pat.sub(f"[REDACTED-{label}]", s)

    # Strip control characters except whitespace.
    return "".join(c for c in s if c >= " " or c in "\n\t")


def contains_injection_attempt(text: str | None) -> bool:
    if not text:
        return False
    return any(pat.search(text) for pat in _INJECTION_PATTERNS)
