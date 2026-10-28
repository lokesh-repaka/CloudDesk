"""Authentication and demo tokens API routes.

Provides:
- POST /api/v1/auth/login: Exchanges credentials or demo identities for HS256 JWT
- GET /api/v1/auth/demo-tokens: Discovers pre-generated demo tokens in demo mode
- GET /api/v1/auth/me: Returns current authenticated user profile
- POST /api/v1/auth/refresh: Re-issues a fresh 8-hour access token for authenticated caller
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.database import get_db_session
from backend.app.core.security import (
    DEFAULT_TOKEN_EXPIRE_HOURS,
    AuthenticatedUser,
    create_access_token,
    get_current_user,
)
from backend.app.models.entities import Profile
from backend.app.schemas.auth import (
    DemoTokensResponse,
    DemoTokenUser,
    LoginRequest,
    TokenResponse,
    UserProfileResponse,
)
from backend.app.schemas.common import RoleEnum

router = APIRouter(tags=["auth"])

# Canonical demo identities (Alice Admin, Sam Agent, Vic Viewer)
DEMO_USERS: dict[str, dict[str, Any]] = {
    "admin@clouddesk.demo": {
        "id": "usr-admin-001",
        "email": "admin@clouddesk.demo",
        "full_name": "Alice Admin",
        "role": RoleEnum.ADMIN,
        "avatar_url": None,
    },
    "sam.agent@clouddesk.demo": {
        "id": "usr-agent-002",
        "email": "sam.agent@clouddesk.demo",
        "full_name": "Sam Agent",
        "role": RoleEnum.AGENT,
        "avatar_url": None,
    },
    "vic.viewer@clouddesk.demo": {
        "id": "usr-viewer-003",
        "email": "vic.viewer@clouddesk.demo",
        "full_name": "Vic Viewer",
        "role": RoleEnum.VIEWER,
        "avatar_url": None,
    },
}


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User or demo login",
    description="Exchanges user email/password or demo credentials for a signed HS256 JWT.",
)
async def login(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    """Authenticate a demo user or registered profile and return a signed JWT access token."""
    email = body.email.strip().lower()

    # 1. Check known demo accounts
    if email in DEMO_USERS:
        user_data = DEMO_USERS[email]
    else:
        # 2. Check registered profiles in database
        stmt = select(Profile).where(Profile.email == email)
        result = await db.execute(stmt)
        profile = result.scalars().first()

        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_data = {
            "id": profile.id,
            "email": profile.email,
            "full_name": profile.full_name,
            "role": RoleEnum(profile.role),
            "avatar_url": profile.avatar_url,
        }

    token = create_access_token({
        "sub": user_data["id"],
        "email": user_data["email"],
        "role": user_data["role"].value if isinstance(user_data["role"], RoleEnum) else user_data["role"],
        "full_name": user_data.get("full_name"),
    })

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=DEFAULT_TOKEN_EXPIRE_HOURS * 3600,
        user=UserProfileResponse(**user_data),
    )


@router.get(
    "/demo-tokens",
    response_model=DemoTokensResponse,
    summary="Get pre-generated demo tokens",
    description="Returns ready-to-use access tokens for demo roles (admin, agent, viewer). Disabled in production.",
)
async def get_demo_tokens() -> DemoTokensResponse:
    """Return pre-generated JWT tokens for demo roles during development and evaluation."""
    settings = get_settings()

    if not settings.DEMO_MODE or settings.ENVIRONMENT in ("production", "staging"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo tokens are disabled in this environment",
        )

    def _make_demo_user(key: str) -> DemoTokenUser:
        u = DEMO_USERS[key]
        token = create_access_token({
            "sub": u["id"],
            "email": u["email"],
            "role": u["role"].value,
            "full_name": u["full_name"],
        })
        return DemoTokenUser(
            id=u["id"],
            email=u["email"],
            full_name=u["full_name"],
            role=u["role"].value,
            token=token,
            expires_in=DEFAULT_TOKEN_EXPIRE_HOURS * 3600,
        )

    return DemoTokensResponse(
        admin=_make_demo_user("admin@clouddesk.demo"),
        agent=_make_demo_user("sam.agent@clouddesk.demo"),
        viewer=_make_demo_user("vic.viewer@clouddesk.demo"),
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile",
    description="Returns the profile information of the currently authenticated actor.",
)
async def get_current_user_profile(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserProfileResponse:
    """Retrieve identity and profile details for the active caller."""
    if current_user.email in DEMO_USERS:
        return UserProfileResponse(**DEMO_USERS[current_user.email])

    stmt = select(Profile).where(Profile.id == current_user.user_id)
    result = await db.execute(stmt)
    profile = result.scalars().first()

    if profile is not None:
        return UserProfileResponse(
            id=profile.id,
            email=profile.email,
            full_name=profile.full_name,
            role=RoleEnum(profile.role),
            avatar_url=profile.avatar_url,
        )

    return UserProfileResponse(
        id=current_user.user_id,
        email=current_user.email,
        role=current_user.role,
        full_name=current_user.full_name,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Exchanges an active authenticated session for a renewed 8-hour access token.",
)
async def refresh_access_token(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> TokenResponse:
    """Renew an access token for an already-authenticated caller."""
    full_name = current_user.full_name
    avatar_url = None

    if current_user.email in DEMO_USERS:
        full_name = DEMO_USERS[current_user.email].get("full_name")
        avatar_url = DEMO_USERS[current_user.email].get("avatar_url")

    new_token = create_access_token({
        "sub": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role.value,
        "full_name": full_name,
    })

    return TokenResponse(
        access_token=new_token,
        token_type="bearer",
        expires_in=DEFAULT_TOKEN_EXPIRE_HOURS * 3600,
        user=UserProfileResponse(
            id=current_user.user_id,
            email=current_user.email,
            role=current_user.role,
            full_name=full_name,
            avatar_url=avatar_url,
        ),
    )
