"""Pydantic request and response schemas for authentication and demo tokens."""

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import RoleEnum


class LoginRequest(BaseModel):
    """Payload for user credential login."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., min_length=3, description="Registered user or demo email address")
    password: str | None = Field(default=None, description="Optional password for demo/credentials login")


class UserProfileResponse(BaseModel):
    """Public user identity and profile metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique user profile UUID")
    email: str = Field(..., description="User email address")
    full_name: str | None = Field(default=None, description="Display name")
    role: RoleEnum = Field(..., description="Role-based access control level")
    avatar_url: str | None = Field(default=None, description="Avatar image URL")


class TokenResponse(BaseModel):
    """OAuth2 / JWT token response envelope."""

    access_token: str = Field(..., description="Signed HS256 JWT access token")
    token_type: str = Field(default="bearer", description="Token authorization type")
    expires_in: int = Field(default=28800, description="Token lifetime in seconds (8 hours)")
    user: UserProfileResponse = Field(..., description="Authenticated user profile summary")


class DemoTokenUser(BaseModel):
    """Demo user descriptor and pre-generated access token."""

    id: str = Field(..., description="Demo user ID")
    email: str = Field(..., description="Demo user email")
    full_name: str = Field(..., description="Demo user full name")
    role: str = Field(..., description="Assigned role string")
    token: str = Field(..., description="Valid 8-hour HS256 access token")
    expires_in: int = Field(default=28800, description="Lifetime in seconds")


class DemoTokensResponse(BaseModel):
    """Pre-generated demo tokens for rapid local development and demo evaluation."""

    admin: DemoTokenUser = Field(..., description="Full administrator access token")
    agent: DemoTokenUser = Field(..., description="Standard support agent access token")
    viewer: DemoTokenUser = Field(..., description="Read-only viewer access token")
