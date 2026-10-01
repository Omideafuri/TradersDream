"""Authentication and authorization utilities for the Web Dashboard."""

import os
import secrets
from typing import Optional
from fastapi import Header, HTTPException, status

# Default to environment variable DASHBOARD_API_KEY or generate a session token
_DEFAULT_KEY = os.getenv("DASHBOARD_API_KEY")
if not _DEFAULT_KEY:
    _DEFAULT_KEY = secrets.token_urlsafe(16)
    os.environ["DASHBOARD_API_KEY"] = _DEFAULT_KEY

CURRENT_SESSION_KEY = _DEFAULT_KEY


def get_current_token() -> str:
    """Returns the active dashboard API key for local session access."""
    return os.getenv("DASHBOARD_API_KEY", CURRENT_SESSION_KEY)


def verify_control_auth(x_api_key: Optional[str] = Header(None)) -> bool:
    """Validates authorization token for bot mutation / control endpoints."""
    # Allow seamless local development access if explicitly configured
    allow_local_unauth = os.getenv("ALLOW_LOCAL_UNAUTH_DASHBOARD", "false").lower() in ("true", "1")
    if allow_local_unauth:
        return True

    expected = get_current_token()
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header. Bot control endpoints require authentication.",
        )
    return True
