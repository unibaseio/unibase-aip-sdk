"""Unibase authorization helpers shared by SDK consumers.

Provides the first-run flow the examples use: environment variable ->
cached config file -> interactive browser authorization. Mirrors the Go
SDK's ``auth`` package.

Typical usage::

    from aip_sdk import auth

    token, wallet = auth.ensure_auth()  # interactive on first run
"""

import base64
import json
import os
from pathlib import Path
from typing import Optional, Tuple

__all__ = [
    "config_file",
    "load_token",
    "save_token",
    "extract_wallet",
    "interactive_auth",
    "ensure_auth",
]


def config_file() -> Path:
    """Return the path to the cached auth config."""
    return Path.home() / ".config" / "unibase-aip-sdk" / "config.json"


def _pay_url() -> str:
    return os.environ.get("UNIBASE_PAY_URL", "https://api.pay.unibase.com")


def load_token() -> Optional[str]:
    """Read UNIBASE_PROXY_AUTH from the environment, then the config file."""
    env_token = os.environ.get("UNIBASE_PROXY_AUTH")
    if env_token:
        return env_token

    try:
        cfg = json.loads(config_file().read_text())
        return cfg.get("UNIBASE_PROXY_AUTH")
    except (OSError, json.JSONDecodeError):
        return None


def save_token(
    token: str,
    agent_id: Optional[str] = None,
    agent_wallet: Optional[str] = None,
) -> None:
    """Persist the token (and optional agent identity) to the config file."""
    path = config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"UNIBASE_PROXY_AUTH": token}
    if agent_id:
        data["AGENT_ID"] = agent_id
    if agent_wallet:
        data["AGENT_WALLET"] = agent_wallet
    path.write_text(json.dumps(data, indent=2))
    print(f"  saved auth token to {path}")


def extract_wallet(token: str) -> Optional[str]:
    """Decode the JWT payload and return its 'sub' claim (wallet address)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
        return data.get("sub") or None
    except Exception:
        return None


def interactive_auth() -> Tuple[str, str]:
    """Fetch an authorization URL and read the signed JWT from stdin.

    Returns:
        (token, wallet_address)
    """
    import httpx

    print("\n=== Unibase Authorization ===")
    print("[1/3] Fetching authorization URL ...")

    pay_url = _pay_url()
    try:
        resp = httpx.post(f"{pay_url}/v1/init", json=True, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"Cannot reach {pay_url}: {e}") from e

    auth_url = data.get("auth_url") or data.get("authUrl")
    if not auth_url:
        raise RuntimeError(f"No auth URL in response: {data}")

    print(f"\n[2/3] Open this URL in your browser and approve:\n\n  {auth_url}\n")
    print("[3/3] Paste your Authorization token below and press Enter:")
    token = input("  Token: ").strip()
    if not token:
        raise RuntimeError("No token provided — aborted")

    wallet = extract_wallet(token) or ""
    save_token(token)
    return token, wallet


def ensure_auth() -> Tuple[str, str]:
    """Return a usable (token, wallet), running interactive auth if no
    cached token is found."""
    token = load_token()
    if token:
        return token, extract_wallet(token) or ""
    return interactive_auth()
