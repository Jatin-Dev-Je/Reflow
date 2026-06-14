"""SQLAlchemy declarative base + common column conventions.

Schema-aware: every ORM model declares `__table_args__ = {"schema": "..."}` so
the Python class lives in one place but the table maps to the right Postgres
namespace (core, txn, recovery, ...).

Naming convention is set on the MetaData so Alembic produces predictable
constraint/index names — critical for clean migration diffs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, mapped_column

# Predictable naming for constraints/indexes — Alembic diffs become readable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for every ORM model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Allows nice repr without pulling every relationship.
    def __repr__(self) -> str:
        cls = type(self).__name__
        pk_cols = [c.name for c in self.__table__.primary_key.columns]
        pk_vals = {c: getattr(self, c, None) for c in pk_cols}
        pairs = ", ".join(f"{k}={v!r}" for k, v in pk_vals.items())
        return f"{cls}({pairs})"


# -----------------------------------------------------------------------------
# Column type aliases — keeps model files readable.
# -----------------------------------------------------------------------------

def uuid_pk() -> Any:
    """Primary-key UUID with server-side default via gen_random_uuid()."""
    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID

    return mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


def uuid_fk(*, nullable: bool = False, index: bool = True) -> Any:
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID

    return mapped_column(PG_UUID(as_uuid=True), nullable=nullable, index=index)


def created_at_column() -> Any:
    from sqlalchemy import DateTime, text

    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


def updated_at_column() -> Any:
    from sqlalchemy import DateTime, text

    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=datetime.utcnow,
    )


# Convenience type aliases for use in `Mapped[...]` annotations.
UuidPK = Annotated[UUID, "uuid_pk"]
