"""In-memory authentication helpers for optional sign-in flows."""

from __future__ import annotations

import os
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Optional


MAGIC_LINK_TTL_SECONDS = 15 * 60


@dataclass
class User:
    user_id: str
    email: str
    display_name: str
    provider: str
    google_subject: Optional[str] = None
    created_at: float = 0.0
    last_login_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "provider": self.provider,
            "created_at": self.created_at,
            "last_login_at": self.last_login_at,
        }


@dataclass
class MagicLinkChallenge:
    token: str
    user_id: str
    email: str
    expires_at: float


_users_by_id: dict[str, User] = {}
_users_by_email: dict[str, User] = {}
_users_by_google_subject: dict[str, User] = {}
_session_tokens: dict[str, str] = {}
_magic_links: dict[str, MagicLinkChallenge] = {}


def _now() -> float:
    return time.time()


def _normalise_email(email: str) -> str:
    value = email.strip().lower()
    if not value or "@" not in value:
        raise ValueError("A valid email address is required.")
    return value


def _default_display_name(email: str) -> str:
    return email.split("@", 1)[0]


def _upsert_user(
    email: str,
    display_name: Optional[str],
    provider: str,
    google_subject: Optional[str] = None,
) -> User:
    normalised_email = _normalise_email(email)
    existing = None
    if google_subject and google_subject in _users_by_google_subject:
        existing = _users_by_google_subject[google_subject]
    if existing is None:
        existing = _users_by_email.get(normalised_email)

    now = _now()
    resolved_name = (display_name or "").strip() or _default_display_name(normalised_email)

    if existing is not None:
        existing.display_name = resolved_name
        existing.provider = provider
        existing.last_login_at = now
        if google_subject:
            existing.google_subject = google_subject
            _users_by_google_subject[google_subject] = existing
        _users_by_email[normalised_email] = existing
        return existing

    user = User(
        user_id=str(uuid.uuid4()),
        email=normalised_email,
        display_name=resolved_name,
        provider=provider,
        google_subject=google_subject,
        created_at=now,
        last_login_at=now,
    )
    _users_by_id[user.user_id] = user
    _users_by_email[normalised_email] = user
    if google_subject:
        _users_by_google_subject[google_subject] = user
    return user


def _issue_session_token(user: User) -> str:
    token = secrets.token_urlsafe(32)
    _session_tokens[token] = user.user_id
    user.last_login_at = _now()
    return token


def auth_config() -> dict:
    google_client_id = os.getenv("GOOGLE_CLIENT_ID") or os.getenv("VITE_GOOGLE_CLIENT_ID")
    return {
        "magic_link_enabled": True,
        "google_enabled": bool(google_client_id),
        "google_client_id": google_client_id,
    }


def request_magic_link(email: str, display_name: Optional[str], app_base_url: str) -> dict:
    user = _upsert_user(email=email, display_name=display_name, provider="magic_link")
    token = secrets.token_urlsafe(24)
    _magic_links[token] = MagicLinkChallenge(
        token=token,
        user_id=user.user_id,
        email=user.email,
        expires_at=_now() + MAGIC_LINK_TTL_SECONDS,
    )
    magic_link_url = f"{app_base_url.rstrip('/')}/?magic_token={token}"
    return {
        "sent": True,
        "magic_link_token": token,
        "magic_link_url": magic_link_url,
        "expires_in_seconds": MAGIC_LINK_TTL_SECONDS,
        "user": user.to_dict(),
    }


def verify_magic_link(token: str) -> dict:
    challenge = _magic_links.pop(token, None)
    if challenge is None:
        raise ValueError("Magic link token is invalid or has already been used.")
    if challenge.expires_at < _now():
        raise ValueError("Magic link token has expired.")
    user = _users_by_id[challenge.user_id]
    access_token = _issue_session_token(user)
    return {"access_token": access_token, "user": user.to_dict()}


def _verify_google_identity_token(token: str) -> dict:
    google_client_id = auth_config()["google_client_id"]
    if not google_client_id:
        raise ValueError("Google login is not configured on the backend.")

    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token
    except ImportError as exc:
        raise ValueError("google-auth is required for Google login support.") from exc

    try:
        payload = id_token.verify_oauth2_token(token, Request(), google_client_id)
    except Exception as exc:
        raise ValueError("Google token verification failed.") from exc

    if payload.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise ValueError("Google token issuer is invalid.")

    return payload


def login_with_google(google_id_token: str) -> dict:
    payload = _verify_google_identity_token(google_id_token)
    email = payload.get("email")
    if not email:
        raise ValueError("Google account did not provide an email address.")

    user = _upsert_user(
        email=email,
        display_name=payload.get("name") or payload.get("given_name"),
        provider="google",
        google_subject=payload.get("sub"),
    )
    access_token = _issue_session_token(user)
    return {"access_token": access_token, "user": user.to_dict()}


def get_user_for_token(access_token: Optional[str]) -> Optional[User]:
    if not access_token:
        return None
    user_id = _session_tokens.get(access_token)
    if not user_id:
        return None
    return _users_by_id.get(user_id)


def require_user(access_token: Optional[str]) -> User:
    user = get_user_for_token(access_token)
    if user is None:
        raise KeyError("Authentication is required.")
    return user


def logout(access_token: Optional[str]) -> None:
    if access_token:
        _session_tokens.pop(access_token, None)