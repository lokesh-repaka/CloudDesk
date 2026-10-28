"""Authentication and role-based access control (RBAC) core infrastructure.

Implements Supabase-compatible HS256 JWT encoding, decoding, token validation,
current user resolution, and role hierarchy authorization as specified in
CLAUDE.md section 2 and acceptance criteria AC-061 / AC-062.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.config import get_settings
from backend.app.schemas.common import RoleEnum

# Strict numerical hierarchy: viewer (1) < agent (2) < admin (3)
ROLE_HIERARCHY: dict[RoleEnum, int] = {
    RoleEnum.VIEWER: 1,
    RoleEnum.AGENT: 2,
    RoleEnum.ADMIN: 3,
}

# Default expiration for demo/session access tokens: 8 hours (28800 seconds)
DEFAULT_TOKEN_EXPIRE_HOURS = 8

# HTTP Bearer authentication scheme without auto_error to standardize 401 response formats
security_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    """Domain model representing an authenticated API actor with assigned RBAC role."""

    model_config = ConfigDict(frozen=True)

    user_id: str = Field(..., description="Unique user identifier (JWT sub)")
    email: str = Field(..., description="User email address")
    role: RoleEnum = Field(..., description="Canonical RBAC role")
    full_name: str | None = Field(default=None, description="Optional user display name")

    @property
    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return self.role == RoleEnum.ADMIN

    @property
    def is_agent(self) -> bool:
        """Check if user has agent or higher privileges."""
        return ROLE_HIERARCHY[self.role] >= ROLE_HIERARCHY[RoleEnum.AGENT]

    @property
    def is_viewer(self) -> bool:
        """Check if user has viewer or higher privileges."""
        return ROLE_HIERARCHY[self.role] >= ROLE_HIERARCHY[RoleEnum.VIEWER]


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed HS256 JWT containing supplied claims and standard timestamps.

    Args:
        data: Custom claims dictionary to encode in the token.
        expires_delta: Optional custom duration. Defaults to 8 hours.

    Returns:
        Encoded and signed JWT string.
    """
    settings = get_settings()
    now = datetime.now(UTC)

    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=DEFAULT_TOKEN_EXPIRE_HOURS)

    to_encode = data.copy()
    to_encode.update({
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    })

    return jwt.encode(to_encode, settings.effective_jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate and decode an HS256 JWT using the effective system secret.

    Guards against:
    - Algorithm confusion / "none" algorithm attacks by strictly requiring HS256
    - Expired tokens
    - Tampered or malformed signatures

    Args:
        token: Raw JWT string.

    Returns:
        Decoded claims dictionary.

    Raises:
        HTTPException: HTTP 401 if invalid, expired, or tampered.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.effective_jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "iat"]},
        )
        return payload
    except (jwt.PyJWTError, ValueError) as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)] = None,
) -> AuthenticatedUser:
    """FastAPI dependency to extract and validate the authenticated actor from the Bearer token.

    Args:
        credentials: Optional extracted HTTP Bearer authorization credentials.

    Returns:
        Validated AuthenticatedUser instance.

    Raises:
        HTTPException: HTTP 401 if credentials are missing, invalid, or missing required claims.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)

    user_id = payload.get("sub")
    email = payload.get("email")
    role_raw = payload.get("role")

    if not user_id or not email or not role_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        role = RoleEnum(role_raw)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err

    return AuthenticatedUser(
        user_id=str(user_id),
        email=str(email),
        role=role,
        full_name=payload.get("full_name"),
    )


class RoleChecker:
    """Callable dependency enforcing the role hierarchy: viewer (1) < agent (2) < admin (3)."""

    def __init__(self, min_role: RoleEnum):
        self.min_role = min_role

    async def __call__(
        self,
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        user_level = ROLE_HIERARCHY.get(current_user.role, 0)
        required_level = ROLE_HIERARCHY.get(self.min_role, 999)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {self.min_role.value} role required",
            )
        return current_user


def require_role(min_role: RoleEnum | str) -> RoleChecker:
    """Factory creating an RBAC role-checking dependency for FastAPI route endpoints.

    Args:
        min_role: Minimum RoleEnum or string role required to access the endpoint.

    Returns:
        RoleChecker dependency callable.

    Raises:
        ValueError: If min_role cannot be resolved to a known RoleEnum.
    """
    if isinstance(min_role, str):
        try:
            min_role = RoleEnum(min_role.lower())
        except ValueError as err:
            raise ValueError(f"Unknown role '{min_role}'. Must be one of {[r.value for r in RoleEnum]}") from err

    return RoleChecker(min_role=min_role)
