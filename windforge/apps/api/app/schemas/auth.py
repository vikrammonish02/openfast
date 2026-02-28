"""Authentication / user schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Payload for registering a new user (creates an org too)."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    organization_name: str = Field(default="My Organization", min_length=1, max_length=255)


class UserLogin(BaseModel):
    """Payload for logging in."""

    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT response."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public representation of a user."""

    id: str
    email: str
    full_name: str
    org_id: str
    organization_name: str | None = None
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}
