"""Transaction repository — interface only.

Concrete implementation lives in
`infrastructure/persistence/repositories/transaction_repository.py`.
"""

from __future__ import annotations

from typing import Protocol

from reflow.core.types import TransactionId
from reflow.domain.transactions.entities import Transaction


class TransactionRepository(Protocol):
    """Load + save Transaction aggregates.

    Implementations write to the event store and (synchronously) update the
    `txn.transactions` read model so single-aggregate reads don't lag.
    """

    async def load(self, transaction_id: TransactionId) -> Transaction | None: ...

    async def save(self, transaction: Transaction) -> None: ...
