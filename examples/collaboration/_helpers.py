"""Shared helpers for collaboration examples.

Configure via environment variables:
    AIP_COLLAB_SERVER  — Collaboration API URL (required)
    AIP_AUTH_TOKEN     — JWT bearer token (required unless server runs in dev mode)
    JWT_SECRET         — Only for local dev: auto-generate tokens with this secret
"""

import os
import time

SERVER = os.getenv("AIP_COLLAB_SERVER", "")
TOKEN = os.getenv("AIP_AUTH_TOKEN", "")


def get_server() -> str:
    if not SERVER:
        raise RuntimeError(
            "Set AIP_COLLAB_SERVER env var (e.g. http://your-server/api/v1/collaboration)"
        )
    return SERVER


def get_token(sub: str = "demo-user") -> str:
    """Return a JWT token.

    Priority:
      1. AIP_AUTH_TOKEN env var (production)
      2. Auto-generate with JWT_SECRET env var (local dev only)
    """
    if TOKEN:
        return TOKEN
    jwt_secret = os.getenv("JWT_SECRET", "")
    if jwt_secret:
        try:
            import jwt as pyjwt
            return pyjwt.encode(
                {"sub": sub, "address": f"0x{sub}", "exp": int(time.time()) + 3600},
                jwt_secret, algorithm="HS256",
            )
        except ImportError:
            pass
    return ""
