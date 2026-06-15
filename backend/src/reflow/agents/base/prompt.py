"""Versioned prompt templates.

Every system prompt has a stable identifier + integer version. The version
is bumped whenever the prompt text changes meaningfully; the hash of the
content is stored alongside so we detect accidental edits in production.

Prompts are *not* stored in the database in this codebase — they live in
source so they're versioned with the rest of the code. Telemetry records
the (name, version, content_hash) tuple so every LLM call ties back to the
exact prompt used.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from reflow.core.security.signing import sha256_hex


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    name: str
    version: int
    content: str
    content_hash: str = field(init=False)

    def __post_init__(self) -> None:
        # `frozen=True` blocks normal assignment; bypass via object.__setattr__.
        object.__setattr__(self, "content_hash", sha256_hex(self.content.encode("utf-8")))

    def render(self, **kwargs: object) -> str:
        """Substitute named placeholders. Missing keys raise — never silent."""
        try:
            return self.content.format(**kwargs)
        except KeyError as exc:
            raise ValueError(
                f"Prompt {self.name!r} v{self.version} missing placeholder: {exc}"
            ) from exc
