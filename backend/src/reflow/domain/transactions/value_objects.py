"""Value objects for the transactions context.

Value objects are frozen, validated, and identity-less. Two value objects with
the same fields are equal. They never hold references to aggregates.

Crucially: no PAN, no CVV — only BIN (first 6), last4, brand, funding, country.
This is the PCI scope minimization line we never cross.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

_BIN_RE = re.compile(r"^\d{6}$")
_LAST4_RE = re.compile(r"^\d{4}$")
_ISO_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
_ISO_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


class TransactionStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RECOVERING = "recovering"
    RECOVERED = "recovered"
    ABANDONED = "abandoned"


class AttemptOutcome(StrEnum):
    SUCCESS = "success"
    SOFT_DECLINE = "soft_decline"
    HARD_DECLINE = "hard_decline"
    ERROR = "error"
    TIMEOUT = "timeout"


class DeclineCategory(StrEnum):
    """Coarse taxonomy used for routing decisions and pattern lookup.

    Maps from gateway-specific codes (e.g. Stripe `insufficient_funds`) to a
    normalized category. The full taxonomy lives in
    `infrastructure/gateways/<provider>/decline_codes.py`.
    """

    ISSUER = "issuer"
    NETWORK = "network"
    FRAUD = "fraud"
    AUTHENTICATION = "authentication"
    FUNDS = "funds"
    GATEWAY = "gateway"
    OTHER = "other"


class CardFunding(StrEnum):
    CREDIT = "credit"
    DEBIT = "debit"
    PREPAID = "prepaid"
    UNKNOWN = "unknown"


Bin = Annotated[str, StringConstraints(pattern=_BIN_RE.pattern)]
Last4 = Annotated[str, StringConstraints(pattern=_LAST4_RE.pattern)]
CountryCode = Annotated[str, StringConstraints(pattern=_ISO_COUNTRY_RE.pattern)]
CurrencyCode = Annotated[str, StringConstraints(pattern=_ISO_CURRENCY_RE.pattern)]


class CardMetadata(BaseModel):
    """Card metadata — strictly non-PCI. No PAN, no CVV, no expiry.

    BIN is the first six digits, used for issuer identification. Stored only
    because it routes evidence ('Issuer X has degraded'). Last4 + brand is
    surfaced in the UI to help operators correlate with merchant records.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    bin: Bin | None = None
    last4: Last4 | None = None
    brand: str | None = None  # visa, mastercard, amex, ...
    funding: CardFunding = CardFunding.UNKNOWN
    country: CountryCode | None = None


class DeclineInfo(BaseModel):
    """A single decline, from a single attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code_raw: str = Field(description="The provider's raw decline code, e.g. 'insufficient_funds'.")
    code_normalized: str = Field(
        description="Our normalized code, e.g. 'FUNDS_INSUFFICIENT'. Single taxonomy.",
    )
    category: DeclineCategory
    message: str | None = None


class GatewayId(BaseModel):
    """Wrapper around a provider+identifier pair (e.g. 'stripe', 'adyen')."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str
    account_ref: str | None = None  # for merchants with multiple accounts per provider

    def __str__(self) -> str:
        return f"{self.provider}:{self.account_ref}" if self.account_ref else self.provider
