"""Unibase authorization helpers shared by SDK consumers.

Two interchangeable credential types — provide ONE of them:

- **Proxy-auth JWT** (``UNIBASE_PROXY_AUTH``): obtained from Unibase Pay via
  the interactive browser flow. Sent as a Bearer token; the platform
  resolves your wallet from it.
- **Wallet private key** (``UNIBASE_WALLET_PRIVATE_KEY``): the SDK derives
  your wallet address locally and registers via the token-less path
  (``user_id`` in the request body). The key never leaves your machine.

Resolution order: env var -> cached config file -> interactive flow (which
lets you pick either method). Mirrors the Go SDK's ``auth`` package.

Typical usage::

    from aip_sdk import auth

    token, wallet = auth.ensure_auth()  # interactive on first run

    expose_as_a2a(
        ...,
        privy_token=token or None,  # JWT mode
        user_id=wallet,             # private-key mode (token == "")
    )
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
    "load_private_key",
    "save_private_key",
    "extract_wallet",
    "wallet_from_private_key",
    "interactive_auth",
    "ensure_auth",
]


def config_file() -> Path:
    """Return the path to the cached auth config."""
    return Path.home() / ".config" / "unibase-aip-sdk" / "config.json"


def _pay_url() -> str:
    return os.environ.get("UNIBASE_PAY_URL", "https://api.pay.unibase.com")


def _read_config() -> dict:
    try:
        return json.loads(config_file().read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _write_config(updates: dict) -> None:
    """Merge updates into the config file (0600 perms)."""
    path = config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_config()
    data.update({k: v for k, v in updates.items() if v})
    path.write_text(json.dumps(data, indent=2))
    path.chmod(0o600)


def load_token() -> Optional[str]:
    """Read UNIBASE_PROXY_AUTH from the environment, then the config file."""
    env_token = os.environ.get("UNIBASE_PROXY_AUTH")
    if env_token:
        return env_token
    return _read_config().get("UNIBASE_PROXY_AUTH")


def save_token(
    token: str,
    agent_id: Optional[str] = None,
    agent_wallet: Optional[str] = None,
) -> None:
    """Persist the token (and optional agent identity) to the config file."""
    _write_config(
        {
            "UNIBASE_PROXY_AUTH": token,
            "AGENT_ID": agent_id,
            "AGENT_WALLET": agent_wallet,
        }
    )
    print(f"  saved auth token to {config_file()}")


def load_private_key() -> Optional[str]:
    """Read UNIBASE_WALLET_PRIVATE_KEY from the environment, then the config file."""
    env_key = os.environ.get("UNIBASE_WALLET_PRIVATE_KEY")
    if env_key:
        return env_key
    return _read_config().get("UNIBASE_WALLET_PRIVATE_KEY")


def save_private_key(private_key: str) -> None:
    """Persist the wallet private key to the config file (0600 perms).

    The key is stored locally only — it is never sent to the platform.
    """
    _write_config({"UNIBASE_WALLET_PRIVATE_KEY": private_key})
    print(f"  saved wallet key to {config_file()} (never sent to the platform)")


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


def wallet_from_private_key(private_key: str) -> str:
    """Derive the wallet address from a hex private key (locally, offline)."""
    from eth_account import Account

    key = private_key.strip()
    if not key.startswith("0x"):
        key = "0x" + key
    return Account.from_key(key).address


def interactive_auth() -> Tuple[str, str]:
    """Interactive first-run flow. Lets the user pick a credential type.

    Returns:
        (token, wallet_address) — token is "" in private-key mode.
    """
    print("\n=== Unibase Authorization ===")
    print("Choose an authorization method:")
    print("  1) Browser authorization — open a URL, approve, paste the JWT token")
    print("  2) Wallet private key — paste a hex private key (stored locally only)")
    choice = input("Choice [1]: ").strip() or "1"

    if choice == "2":
        return _interactive_private_key()
    return _interactive_token()


def _interactive_token() -> Tuple[str, str]:
    import httpx

    print("\n[1/3] Fetching authorization URL ...")
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


def _interactive_private_key() -> Tuple[str, str]:
    import getpass

    print("\nPaste your wallet private key (hex, input hidden) and press Enter:")
    key = getpass.getpass("  Private key: ").strip()
    if not key:
        raise RuntimeError("No private key provided — aborted")

    try:
        wallet = wallet_from_private_key(key)
    except Exception as e:
        raise RuntimeError(f"Invalid private key: {e}") from e

    print(f"  wallet: {wallet}")
    save_private_key(key)
    return "", wallet


def ensure_auth() -> Tuple[str, str]:
    """Return usable credentials, running the interactive flow if none cached.

    Returns:
        (token, wallet). JWT mode: both set. Private-key mode: token is ""
        and wallet is the address derived from the key.
    """
    token = load_token()
    if token:
        return token, extract_wallet(token) or ""

    key = load_private_key()
    if key:
        return "", wallet_from_private_key(key)

    return interactive_auth()
