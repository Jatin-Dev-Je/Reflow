"""LLM output validator + repair loop.

Every agent output must conform to a Pydantic schema. When the LLM produces
malformed JSON or misses required fields, we attempt a bounded number of
*repair re-prompts* with the original response and the validation error
attached. If repair attempts are exhausted, we raise — the agent layer
falls back to a deterministic default (Tier 0/1 in the tiered intelligence
model — see ADR-0004).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from reflow.agents.llm.router import LLMRouter, RoutedResponse
from reflow.core.exceptions import LLMValidationError
from reflow.core.observability.logging import get_logger

_logger = get_logger(__name__)


class ValidationStatus(StrEnum):
    VALID = "valid"
    REPAIRED = "repaired"
    FAILED = "failed"


TSchema = TypeVar("TSchema", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ValidatedOutput(Generic[TSchema]):
    parsed: TSchema
    status: ValidationStatus
    attempts: int
    raw_responses: list[RoutedResponse]


REPAIR_PROMPT_TEMPLATE = (
    "Your previous response did not match the required schema. "
    "Validation error:\n{error}\n\n"
    "Original response:\n{original}\n\n"
    "Reply ONLY with valid JSON matching the schema. No prose, no preamble."
)


async def validate_or_repair(
    router: LLMRouter,
    *,
    system_prompt: str,
    user_prompt: str,
    schema: type[TSchema],
    max_repair_attempts: int = 2,
    max_tokens: int | None = None,
) -> ValidatedOutput[TSchema]:
    """Call the LLM, validate the JSON against `schema`, repair if needed."""
    transcript: list[RoutedResponse] = []
    repair_attempts = 0

    # First attempt.
    routed = await router.complete(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        json_mode=True,
    )
    transcript.append(routed)

    last_error: str | None = None
    last_content = routed.response.content

    while True:
        parsed = _try_parse(last_content, schema)
        if parsed is not None:
            return ValidatedOutput(
                parsed=parsed,
                status=ValidationStatus.VALID if repair_attempts == 0 else ValidationStatus.REPAIRED,
                attempts=repair_attempts,
                raw_responses=transcript,
            )

        # Validation failed; can we repair?
        if repair_attempts >= max_repair_attempts:
            _logger.warning(
                "agents.output.validation_failed",
                attempts=repair_attempts,
                error=last_error,
            )
            raise LLMValidationError(
                "LLM output failed schema validation after repair attempts",
                context={
                    "attempts": repair_attempts,
                    "last_error": last_error,
                },
            )

        repair_attempts += 1
        last_error = _last_validation_error(last_content, schema)
        repair_prompt = REPAIR_PROMPT_TEMPLATE.format(
            error=last_error or "unknown",
            original=last_content[:2000],
        )
        routed = await router.complete(
            system_prompt=system_prompt,
            user_prompt=repair_prompt,
            max_tokens=max_tokens,
            json_mode=True,
        )
        transcript.append(routed)
        last_content = routed.response.content


def _try_parse(content: str, schema: type[TSchema]) -> TSchema | None:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    try:
        return schema.model_validate(data)
    except ValidationError:
        return None


def _last_validation_error(content: str, schema: type[TSchema]) -> str:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        return f"Not valid JSON: {exc}"
    try:
        schema.model_validate(data)
    except ValidationError as exc:
        return str(exc)
    return ""
