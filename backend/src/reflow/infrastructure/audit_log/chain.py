"""Chain anchoring service.

Periodically:
    1. Find unanchored events (those with global_sequence > last anchored seq).
    2. Compute the Merkle root over their event_hashes (leaf order = ASC by
       global_sequence).
    3. Sign the root with the audit signing key.
    4. Persist the anchor row.

Runs from the `learning_worker` (or a dedicated `anchor_worker`). Idempotent:
double-runs do nothing because the latest anchor is the source of truth for
"how far we've anchored."
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reflow.core.observability.logging import get_logger
from reflow.core.security.signing import sign
from reflow.infrastructure.audit_log.merkle import merkle_root_hex
from reflow.infrastructure.persistence.models import ChainAnchorModel, EventModel

_logger = get_logger(__name__)

# Anchor at most this many events at once — bounds memory and proof tree size.
DEFAULT_BATCH_SIZE: Final[int] = 1024
MIN_EVENTS_PER_ANCHOR: Final[int] = 1  # raise to e.g. 100 to amortize signing cost


@dataclass(frozen=True, slots=True)
class AnchorResult:
    anchor_id: str
    start_sequence: int
    end_sequence: int
    event_count: int
    merkle_root: str


class ChainAnchorService:
    """Anchor unanchored events behind a signed Merkle root."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def latest_anchored_sequence(self) -> int:
        """Return the highest `end_sequence` previously anchored, or 0."""
        stmt = select(func.max(ChainAnchorModel.end_sequence))
        return (await self._session.execute(stmt)).scalar() or 0

    async def anchor_pending(
        self, *, batch_size: int = DEFAULT_BATCH_SIZE
    ) -> AnchorResult | None:
        """Anchor up to `batch_size` unanchored events. Returns None if nothing to do."""
        from_sequence = await self.latest_anchored_sequence()

        stmt = (
            select(EventModel.global_sequence, EventModel.event_hash)
            .where(EventModel.global_sequence > from_sequence)
            .order_by(EventModel.global_sequence.asc())
            .limit(batch_size)
        )
        rows = (await self._session.execute(stmt)).all()

        if len(rows) < MIN_EVENTS_PER_ANCHOR:
            return None

        start_seq = rows[0].global_sequence
        end_seq = rows[-1].global_sequence
        leaves = [r.event_hash for r in rows]

        root_hex = merkle_root_hex(leaves)
        signature = sign(root_hex.encode("ascii"))

        anchor = ChainAnchorModel(
            tenant_id=None,  # global anchor
            start_sequence=start_seq,
            end_sequence=end_seq,
            event_count=len(rows),
            merkle_root=root_hex,
            signature=signature.signature_hex,
            signer_key_id=signature.key_id,
        )
        self._session.add(anchor)
        await self._session.flush()

        _logger.info(
            "audit.anchor.created",
            anchor_id=str(anchor.id),
            start_sequence=start_seq,
            end_sequence=end_seq,
            event_count=len(rows),
            signer_key_id=signature.key_id,
        )

        return AnchorResult(
            anchor_id=str(anchor.id),
            start_sequence=start_seq,
            end_sequence=end_seq,
            event_count=len(rows),
            merkle_root=root_hex,
        )

    async def latest_anchor(self) -> ChainAnchorModel | None:
        stmt = (
            select(ChainAnchorModel)
            .order_by(ChainAnchorModel.signed_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
