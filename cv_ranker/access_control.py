"""Fail-closed access policy for the local supervisor UI and opt-in OIDC.

This module only decides access. Streamlit's identity-cookie/OIDC implementation
performs authentication; our explicit verified-email allowlist performs the
application-specific authorization check. Local mode is NOT user authentication.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Mapping


_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_EMAIL = re.compile(r"^[^\s@,]+@[^\s@,]+\.[^\s@,]+$")


@dataclass(frozen=True)
class AccessDecision:
    action: str  # allow / login / deny / misconfigured
    reason: str


def allowed_emails(raw: str) -> frozenset[str]:
    """Require a literal email allowlist; no wildcard/domain-wide access."""
    parts = [item.strip().casefold() for item in raw.split(",")]
    if not parts or not all("*" not in part and _EMAIL.fullmatch(part) for part in parts):
        return frozenset()
    return frozenset(parts)


def evaluate_access(
    *, mode: str, server_address: str | None, emails: str,
    is_logged_in: bool = False, email: str | None = None,
    email_verified: bool = False,
) -> AccessDecision:
    """Separate local bind safety from OIDC authentication + authorization.

    A reverse proxy can expose a loopback listener: the *operator* must still
    restrict that proxy; local mode is never permission for public deployment.
    """
    mode = mode.strip().lower()
    if mode == "local":
        if (server_address or "").strip().lower() not in _LOOPBACK:
            return AccessDecision("misconfigured", "Local mode requires an explicit loopback-only server bind")
        return AccessDecision("allow", "Local host-only workflow")
    if mode != "oidc":
        return AccessDecision("misconfigured", "CVR_ACCESS_MODE must be 'local' or 'oidc'")
    members = allowed_emails(emails)
    if not members:
        return AccessDecision("misconfigured", "OIDC mode requires CVR_ALLOWED_EMAILS with explicit addresses")
    if not is_logged_in:
        return AccessDecision("login", "Sign in with the configured organization identity provider")
    if not email_verified or not isinstance(email, str) or email.strip().casefold() not in members:
        return AccessDecision("deny", "This verified account is not authorized to review applicant records")
    return AccessDecision("allow", "Authorized supervisor")


def access_env(environ: Mapping[str, str] | None = None) -> tuple[str, str]:
    variables = os.environ if environ is None else environ
    return (variables.get("CVR_ACCESS_MODE", "local"),
            variables.get("CVR_ALLOWED_EMAILS", ""))
