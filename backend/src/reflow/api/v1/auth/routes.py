"""Auth endpoints — register, login, refresh, me."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select

from reflow.api.deps import SessionDep, SettingsDep
from reflow.api.v1.auth.schemas import (
    CurrentUserResponse,
    LoginBody,
    RefreshBody,
    RegisterBody,
    TokenPair,
    UserRead,
)
from reflow.core.config import get_settings
from reflow.core.observability.logging import bind_contextvars, get_logger
from reflow.core.security import (
    InvalidAuthTokenError,
    TokenType,
    assert_token_type,
    decode_token,
    encode_token,
    hash_password,
    verify_password,
)
from reflow.infrastructure.persistence.models import (
    UserModel,
    UserTenantRoleModel,
)

# Demo tenant id seeded by 001_initial_schema.sql. New registrations land here
# until tenant CRUD lands.
_DEMO_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")

router = APIRouter(prefix="/auth", tags=["auth"])
_logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Token issuance helpers
# -----------------------------------------------------------------------------


def _issue_token_pair(*, user_id: UUID, tenant_id: UUID) -> TokenPair:
    settings = get_settings().security
    access = encode_token(
        token_type=TokenType.ACCESS,
        user_id=user_id,
        tenant_id=tenant_id,
        settings=settings,
    )
    refresh = encode_token(
        token_type=TokenType.REFRESH,
        user_id=user_id,
        tenant_id=tenant_id,
        settings=settings,
    )
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in_minutes=settings.jwt_access_expires_minutes,
    )


# -----------------------------------------------------------------------------
# Register
# -----------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=TokenPair,
    summary="Register a new user; assigns to the demo tenant by default",
)
async def register(
    body: RegisterBody,
    session: SessionDep,
) -> TokenPair:
    # Reject duplicates explicitly so the error is meaningful.
    existing = await session.execute(
        select(UserModel).where(UserModel.email == body.email)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    user = UserModel(
        email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name,
        is_active=True,
        is_superuser=False,
    )
    session.add(user)
    await session.flush()  # populate user.id

    session.add(
        UserTenantRoleModel(
            user_id=user.id,
            tenant_id=_DEMO_TENANT_ID,
            role="operator",
        )
    )
    await session.commit()

    _logger.info("auth.register.success", user_id=str(user.id), email=user.email)
    return _issue_token_pair(user_id=user.id, tenant_id=_DEMO_TENANT_ID)


# -----------------------------------------------------------------------------
# Login
# -----------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Exchange email + password for an access/refresh token pair",
)
async def login(body: LoginBody, session: SessionDep) -> TokenPair:
    user = (
        await session.execute(
            select(UserModel).where(UserModel.email == body.email)
        )
    ).scalar_one_or_none()
    if user is None or user.hashed_password is None:
        # Same shape as wrong-password to avoid email enumeration.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled"
        )
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Resolve the user's primary tenant. For now: the first row in user_tenant_roles.
    role_row = (
        await session.execute(
            select(UserTenantRoleModel)
            .where(UserTenantRoleModel.user_id == user.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    tenant_id = role_row.tenant_id if role_row else _DEMO_TENANT_ID

    user.last_login_at = datetime.now(UTC)
    await session.commit()
    _logger.info("auth.login.success", user_id=str(user.id))

    return _issue_token_pair(user_id=user.id, tenant_id=tenant_id)


# -----------------------------------------------------------------------------
# Refresh
# -----------------------------------------------------------------------------


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Exchange a refresh token for a new access/refresh pair",
)
async def refresh(body: RefreshBody, settings: SettingsDep) -> TokenPair:
    try:
        payload = decode_token(body.refresh_token, settings=settings.security)
        assert_token_type(payload, TokenType.REFRESH)
    except InvalidAuthTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    user_id = UUID(payload["sub"])
    tenant_id = UUID(payload["tid"]) if payload.get("tid") else _DEMO_TENANT_ID
    return _issue_token_pair(user_id=user_id, tenant_id=tenant_id)


# -----------------------------------------------------------------------------
# Me — depends on bearer token
# -----------------------------------------------------------------------------


async def _resolve_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """Extract user_id + tenant_id from the Authorization: Bearer header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    token = authorization.split(None, 1)[1]
    try:
        payload = decode_token(token)
        assert_token_type(payload, TokenType.ACCESS)
    except InvalidAuthTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    bind_contextvars(
        user_id=payload["sub"],
        tenant_id=payload.get("tid"),
    )
    return payload


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Current user + tenant + roles, resolved from the bearer token",
)
async def me(
    session: SessionDep,
    claims: Annotated[dict, Depends(_resolve_current_user)],
) -> CurrentUserResponse:
    user_id = UUID(claims["sub"])
    tenant_id = UUID(claims["tid"]) if claims.get("tid") else _DEMO_TENANT_ID

    user = await session.get(UserModel, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    roles = (
        await session.execute(
            select(UserTenantRoleModel.role)
            .where(UserTenantRoleModel.user_id == user_id)
            .where(UserTenantRoleModel.tenant_id == tenant_id)
        )
    ).scalars().all()

    return CurrentUserResponse(
        user=UserRead.model_validate(user),
        tenant_id=tenant_id,
        roles=list(roles),
    )
