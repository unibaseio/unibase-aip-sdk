#!/usr/bin/env python3
"""
Agent SDK Startup Guide

This example demonstrates how to start an Agent service using unibase-aip-sdk,
and how the Agent communicates with the Gateway after startup.

The example uses a real Binance price query agent with job_offerings to show
how to publish structured job offerings in the ERC-8183 marketplace.

Authorization Flow:
  - On startup, check for local config.json (~/.config/unibase-aip-sdk/config.json)
  - If UNIBASE_PROXY_AUTH token exists, load it directly
  - If not found, run interactive auth: call /v1/init → print authUrl → ask for token
  - After token is obtained, save to config.json
  - Then proceed to POST /agents/register and start the agent service

Privy/Unibase Pay docs:
  POST https://api.pay.unibase.com/v1/init        → get authUrl
  POST https://api.pay.unibase.com/v1/wallets/me/rpc  → wallet RPC calls

Binance API docs:
  https://developers.binance.com/docs/price-index-queries/klines/Klines_Data

=============================================================================
1. Startup Flow Overview
=============================================================================

    ┌─────────────────────────────────────────────────────────────────┐
    │                     Agent SDK Startup Flow                       │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │  1. [Authorization] Check config.json → load UNIBASE_PROXY_AUTH │
    │         │ (if missing: interactive auth flow)                    │
    │         ▼                                                       │
    │  2. Extract wallet address from token (sub claim)                 │
    │         ▼                                                       │
    │  3. Call POST /agents/register (auth via Bearer token)           │
    │         │                                                       │
    │         ├── auto_register=True  →  Auto register on startup     │
    │         ├── auto_register=False →  Manual register (call API)    │
    │         ▼                                                       │
    │  4. server.run_sync()  Start HTTP service                        │
    │         │                                                       │
    │         ├── endpoint_url is set →  PUSH mode (Gateway calls)     │
    │         └── endpoint_url=None  →  POLLING mode (Agent polls)     │
    │              + via_gateway=True  → Butler discovers via gateway  │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘

=============================================================================
2. Butler Agent + Job Queue (NEW)
=============================================================================

Agents registered via SDK can be discovered and called by Butler via the Gateway:

    User → Butler → search_job_offerings() → Gateway → Agent (your service)

Butler discovers agents via job_offerings vector search. When an agent is hired:
  - If agent has endpoint_url (PUSH) → Butler calls directly
  - If agent has via_gateway=True → Butler routes via Gateway job queue:
      GET  /gateway/jobs/poll     (agent polls, every 3s)
      POST /gateway/jobs/complete (agent submits result)

Key: set via_gateway=True when endpoint_url=None and you want Butler to call you!

    expose_as_a2a(
        endpoint_url=None,          # Private agent (no public URL)
        via_gateway=True,           # KEY: Butler can discover and route via gateway
        job_offerings=[...],         # REQUIRED: so Butler finds you in search
        ...
    )

SDK automatically detects via_gateway or job_offerings and polls the correct endpoint:
  - job_offerings present or via_gateway=True → /gateway/jobs/poll + /gateway/jobs/complete
  - otherwise → /gateway/tasks/poll + /gateway/tasks/complete

=============================================================================
3. Interactive Authorization Flow
=============================================================================

When UNIBASE_PROXY_AUTH is not found in config.json:

    Step 1: Call POST https://api.pay.unibase.com/v1/init
            → receive {"authUrl": "https://..."}

    Step 2: Print auth URL to stdout:
            "I need your authorization to access the Terminal features."
            "Please click here to approve: https://..."

    Step 3: Read the Authorization token from stdin

    Step 4: Validate token (decode JWT sub claim → wallet address)

    Step 5: Save {UNIBASE_PROXY_AUTH: "<token>"} to config.json

    Step 6: Proceed with registration and startup

=============================================================================
4. Registration API (POST /agents/register)
=============================================================================

SDK calls:

    POST https://api.aip.unibase.com/agents/register
    Authorization: Bearer {UNIBASE_PROXY_AUTH}

Body format (AgentConfig):
    {
        "name": "Agent Name",
        "handle": "unique_handle",
        "description": "...",
        "endpoint_url": "...",
        "skills": [...],
        "job_offerings": [...],
        "cost_model": {"base_call_fee": 0.0, ...},
        "metadata": {"chain_id": 97, ...}
    }

    Auth: Bearer token in Authorization header
    Chain ID 97 → BSC Testnet (default)

=============================================================================
5. Chain ID Reference
=============================================================================

    Chain ID 97  →  BSC Testnet (default, for testing)
    Chain ID 56  →  BSC Mainnet
    Chain ID 1   →  Ethereum Mainnet

=============================================================================
6. Environment Variables & Config File
=============================================================================

Config file: ~/.config/unibase-aip-sdk/config.json
    {"UNIBASE_PROXY_AUTH": "eyJ..."}

Environment variables (optional overrides):
    AIP_ENDPOINT=https://api.aip.unibase.com
    GATEWAY_URL=https://gateway.aip.unibase.com
    AGENT_PUBLIC_URL=http://your-public-ip:8200
    UNIBASE_PROXY_AUTH=eyJ...          (overrides config.json)
    UNIBASE_PAY_URL=https://api.pay.unibase.com
    AGENT_REGISTRATION_CHAIN_ID=97
    AGENT_REGISTRATION_RPC_URL=https://bsc-testnet.publicnode.com
"""

import asyncio
import os
import sys
import json
import base64
import httpx
from pathlib import Path
from datetime import datetime


# ============================================================================
# Config & Authorization
# ============================================================================

CONFIG_DIR = Path.home() / ".config" / "unibase-aip-sdk"
CONFIG_FILE = CONFIG_DIR / "config.json"
UNIBASE_PAY_URL = os.environ.get("UNIBASE_PAY_URL", "https://api.pay.unibase.com")


def load_auth_token() -> str | None:
    """
    Load UNIBASE_PROXY_AUTH from config.json.
    Returns None if not found (interactive auth needed).
    """
    # Env override
    env_token = os.environ.get("UNIBASE_PROXY_AUTH")
    if env_token:
        return env_token

    if not CONFIG_FILE.exists():
        return None

    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        return cfg.get("UNIBASE_PROXY_AUTH")
    except (json.JSONDecodeError, IOError):
        return None


def save_auth_token(token: str, agent_id: str | None = None, agent_wallet: str | None = None) -> None:
    """Save UNIBASE_PROXY_AUTH and optional agent identity to config.json"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {"UNIBASE_PROXY_AUTH": token}
    if agent_id:
        data["AGENT_ID"] = agent_id
    if agent_wallet:
        data["AGENT_WALLET"] = agent_wallet
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✓ Saved auth token to {CONFIG_FILE}")


def load_agent_identity() -> tuple[str | None, str | None]:
    """Load persisted agent_id and agent_wallet from config.json.

    Returns:
        (agent_id, agent_wallet) - either or both may be None if not saved.
    """
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        return cfg.get("AGENT_ID"), cfg.get("AGENT_WALLET")
    except (json.JSONDecodeError, IOError):
        return None, None


def extract_wallet_from_token(token: str) -> str | None:
    """
    Decode JWT payload to extract wallet address from 'sub' claim.
    Returns None if decode fails.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        data = json.loads(base64.b64decode(payload).decode("utf-8"))
        sub = data.get("sub", "")
        # sub can be an address or a privy ID; return as-is for now
        return sub if sub else None
    except Exception:
        return None


async def interactive_auth() -> tuple[str, str]:
    """
    Run interactive authorization flow to get UNIBASE_PROXY_AUTH token.

    Returns:
        (token, wallet_address)
    """
    print("\n" + "=" * 70)
    print("Step 1: Interactive Authorization")
    print("=" * 70)

    # Step 1: Call /v1/init to get authUrl
    print("\n[1/3] Fetching authorization URL...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{UNIBASE_PAY_URL}/v1/init",
                json=True,
            )
            resp.raise_for_status()
            data = resp.json()
            auth_url = data.get("auth_url") or data.get("authUrl")
            if not auth_url:
                raise ValueError(f"No authUrl in response: {data}")
            print(f"  ✓ Got auth URL")
    except Exception as e:
        print(f"  ✗ Failed to fetch auth URL: {e}")
        raise RuntimeError(
            f"Cannot reach {UNIBASE_PAY_URL}. Check your network or UNIBASE_PAY_URL."
        )

    # Step 2: Print auth URL and wait for token
    print(f"\n[2/3] Authorization Required")
    print("  I need your authorization to access the Terminal features.")
    print(f"\n  👉 Please click this link to approve:\n")
    print(f"  {auth_url}")
    print(f"\n  After approval, you'll receive an Authorization token.")
    print(f"\n  👉 Paste your Authorization token below and press Enter:\n")

    token = input("  Token: ").strip()

    if not token:
        raise RuntimeError("No token provided. Aborted.")

    # Step 3: Validate token
    print("\n[3/3] Validating token...")
    wallet = extract_wallet_from_token(token)
    if wallet:
        print(f"  ✓ Token valid. Wallet: {wallet}")
    else:
        print("  ⚠ Token decode failed (no sub claim), proceeding anyway...")

    # Save to config
    save_auth_token(token)

    return token, wallet or ""


_cli_token = None  # Set via --token CLI arg
_cli_gateway_url = None  # Set via --gateway-url CLI arg


def _get_gateway_url() -> str:
    """Get gateway URL from CLI arg, env var, or default."""
    if _cli_gateway_url:
        return _cli_gateway_url
    return os.environ.get("GATEWAY_URL", "https://gateway.aip.unibase.com")


def ensure_auth(token: str = None) -> tuple[str, str]:
    """
    Ensure a valid UNIBASE_PROXY_AUTH token is available.
    Checks CLI arg first, then config.json; if missing, runs interactive auth.
    Returns (token, wallet_address).
    """
    token = token or _cli_token or load_auth_token()

    if token:
        wallet = extract_wallet_from_token(token) or ""
        print(f"\n{'='*70}")
        print("Step 1: Load Authorization")
        print(f"{'='*70}")
        if _cli_token:
            print(f"  ✓ Using token from --token argument")
        else:
            print(f"  ✓ Loaded auth token from {CONFIG_FILE}")
        if wallet:
            print(f"  Wallet: {wallet}")
        else:
            print("  ⚠ Could not decode wallet from token (will resolve on registration)")
        return token, wallet

    # Not found → interactive auth
    token, wallet = asyncio.run(interactive_auth())
    return token, wallet


# ============================================================================
# Binance Price Query Agent (real business logic)
# ============================================================================

class BinancePriceAgent:
    """
    Binance Price Query Agent - queries real-time and historical crypto prices
    using Binance's public API (no auth required).

    Supported queries:
      - "BTC price" / "BTCUSDT price" → current price
      - "BTC 24h change" → 24h stats
      - "BTC klines 1d 10" → last 10 daily candles
      - "ETH price" → current price
    """

    BASE_URL = "https://api.binance.com"

    async def handle(self, message_text: str) -> str:
        """Handle price query requests from Binance public API"""
        print(f"\n[BinancePriceAgent] Received: {message_text}")

        text = message_text.strip().upper()
        text_lower = message_text.strip().lower()

        # Parse symbol
        symbol = self._extract_symbol(text)
        if not symbol:
            return (
                "Usage:\n"
                "  <SYMBOL> price        → current price, e.g. 'BTCUSDT price'\n"
                "  <SYMBOL> 24h change   → 24h stats, e.g. 'ETH 24h change'\n"
                "  <SYMBOL> klines <N>   → N daily candles, e.g. 'SOL klines 30'\n"
                "  <SYMBOL> orderbook    → orderbook depth, e.g. 'BNB orderbook 5'\n"
            )

        # Route to handler
        if "kline" in text_lower or "candle" in text_lower:
            limit = self._extract_limit(text_lower, default=10)
            return await self._get_klines(symbol, limit)
        elif "24h" in text_lower or "change" in text_lower or "stats" in text_lower:
            return await self._get_24hr_stats(symbol)
        elif "orderbook" in text_lower or "depth" in text_lower:
            limit = self._extract_limit(text_lower, default=5)
            return await self._get_orderbook(symbol, limit)
        else:
            return await self._get_current_price(symbol)

    def _extract_symbol(self, text: str) -> str:
        """Extract trading symbol from message, default to USDT quote"""
        clean = (
            text.replace("PRICE", "")
            .replace("KLINE", "")
            .replace("CANDLE", "")
            .replace("24H", "")
            .replace("CHANGE", "")
            .replace("STATS", "")
            .replace("ORDERBOOK", "")
            .replace("DEPTH", "")
            .replace("GET", "")
            .strip()
        )

        for part in clean.split():
            part = part.strip("!?.,")
            if not part:
                continue
            if part.endswith("USDT"):
                return part
            if part.endswith("BTC"):
                return f"{part}BTC"
            if part.endswith("BNB"):
                return f"{part}BNB"
            if part.endswith("ETH"):
                return f"{part}ETH"
            if part.endswith("USD"):
                return f"{part}USD"

        return "BTCUSDT"

    def _extract_limit(self, text: str, default: int = 10) -> int:
        """Extract limit/count from message"""
        import re
        m = re.search(r"(\d+)\s*(kline|candle|limit|count|bar)", text)
        if m:
            return min(int(m.group(1)), 1000)
        m = re.search(r"last\s+(\d+)", text)
        if m:
            return min(int(m.group(1)), 1000)
        return default

    async def _get_current_price(self, symbol: str) -> str:
        """Get current price from Binance"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/api/v3/ticker/price",
                    params={"symbol": symbol}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return (
                        f"💰 {symbol} Current Price\n\n"
                        f"  Price:  ${float(data['price']):,.4f}\n"
                        f"  Symbol: {data['symbol']}\n"
                        f"  Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    )
                elif resp.status_code == 400:
                    return f"❌ Invalid symbol: {symbol}. Try 'BTCUSDT', 'ETHUSDT', etc."
                else:
                    return f"❌ Binance API error: {resp.status_code}"
        except Exception as e:
            return f"❌ Failed to fetch price: {e}"

    async def _get_24hr_stats(self, symbol: str) -> str:
        """Get 24h statistics"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/api/v3/ticker/24hr",
                    params={"symbol": symbol}
                )
                if resp.status_code == 200:
                    d = resp.json()
                    pct = float(d["priceChangePercent"])
                    emoji = "🟢" if pct >= 0 else "🔴"
                    return (
                        f"📊 {symbol} 24h Stats\n\n"
                        f"  {emoji} Change:   {pct:+.2f}%\n"
                        f"  Last Price: ${float(d['lastPrice']):,.4f}\n"
                        f"  High:       ${float(d['highPrice']):,.4f}\n"
                        f"  Low:        ${float(d['lowPrice']):,.4f}\n"
                        f"  Volume:     {float(d['volume']):,.2f} {symbol.replace('USDT','')}\n"
                        f"  Quote Vol:  ${float(d['quoteVolume']):,.2f}\n"
                        f"  Time:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    )
                else:
                    return f"❌ Binance API error: {resp.status_code}"
        except Exception as e:
            return f"❌ Failed to fetch 24h stats: {e}"

    async def _get_klines(self, symbol: str, limit: int = 10) -> str:
        """Get candlestick/kline data"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/api/v3/klines",
                    params={"symbol": symbol, "interval": "1d", "limit": limit}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if not data:
                        return f"📊 {symbol} No kline data available"

                    lines = [f"📊 {symbol} Daily Klines (last {len(data)} bars)\n"]
                    for k in reversed(data[-limit:]):
                        open_time = datetime.fromtimestamp(k[0] / 1000).strftime("%Y-%m-%d")
                        o, h, l, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
                        vol = float(k[5])
                        lines.append(
                            f"  {open_time}  O:{o:>10.4f}  H:{h:>10.4f}  "
                            f"L:{l:>10.4f}  C:{c:>10.4f}  Vol:{vol:>12,.2f}"
                        )
                    return "\n".join(lines)
                else:
                    return f"❌ Binance API error: {resp.status_code}"
        except Exception as e:
            return f"❌ Failed to fetch klines: {e}"

    async def _get_orderbook(self, symbol: str, limit: int = 5) -> str:
        """Get orderbook depth"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/api/v3/depth",
                    params={"symbol": symbol, "limit": limit}
                )
                if resp.status_code == 200:
                    d = resp.json()
                    lines = [f"📋 {symbol} Orderbook (depth {limit})\n"]
                    lines.append("  --- Bids (Buy) ---")
                    for price, qty in d.get("bids", [])[:limit]:
                        lines.append(f"  ${float(price):>12.4f}  × {float(qty):>12.4f}")
                    lines.append("  --- Asks (Sell) ---")
                    for price, qty in d.get("asks", [])[:limit]:
                        lines.append(f"  ${float(price):>12.4f}  × {float(qty):>12.4f}")
                    return "\n".join(lines)
                else:
                    return f"❌ Binance API error: {resp.status_code}"
        except Exception as e:
            return f"❌ Failed to fetch orderbook: {e}"


# ============================================================================
# Job Offerings Config (ERC-8183 marketplace listings)
# ============================================================================

from aip_sdk import CostModel
from aip_sdk.types import AgentJobOffering, AgentJobResource

BINANCE_JOB_OFFERINGS = [
    AgentJobOffering(
        id="binance_price_query",
        name="Crypto Price Query",
        description="Query current price, 24h stats, klines (candles), or orderbook depth for any crypto pair on Binance. Fast, real-time data from Binance public API.",
        type="JOB",
        price=0.0,
        price_v2={
            "type": "fixed",
            "amount": 0,
            "currency": "USDC",
        },
        job_input="Text query: '<SYMBOL> price' | '<SYMBOL> 24h change' | '<SYMBOL> klines <N>' | '<SYMBOL> orderbook'. Example: 'BTCUSDT price' or 'ETH 24h change'",
        job_output="Text or JSON with price data, 24h stats, klines, or orderbook",
        requirement={"type": "object", "required": ["ticker"], "properties": {"ticker": {"type": "string", "description": "ticker"}}},
        deliverable={"type": "object", "required": ["text"], "properties": {"text": {"type": "string", "description": "Complete deliverable"}}},
        sla_minutes=1,
        required_funds=False,
        restricted=False,
        hide=False,
        active=True,
    ),
]

BINANCE_JOB_RESOURCES = [
    AgentJobResource(
        id="binance_api",
        url="https://api.binance.com",
        name="Binance Public API",
        type="RESOURCE",
        description="Binance cryptocurrency exchange public API for price, klines, orderbook, and 24hr stats",
    ),
]


# ============================================================================
# Shared Registration Helper
# ============================================================================

from aip_sdk import AsyncAIPClient, AgentConfig, SkillConfig, expose_as_a2a
from aip_sdk.types import AgentSkillCard


async def register_agent(
    wallet: str,
    auth_token: str,
    handle: str,
    name: str,
    description: str,
    endpoint_url: str | None,
    port: int,
    existing_agent_id: str | None = None,
) -> str:
    """
    Register agent via POST /agents/register (Bearer auth).

    Pass existing_agent_id to reuse an existing registration (avoids creating
    a new ERC-8004 token on agent restart).

    Returns agent_id on success.
    """
    print(f"\n{'='*70}")
    print("Step 2: Agent Registration")
    print(f"{'='*70}")
    print(f"  Endpoint: https://api.aip.unibase.com/agents/register")
    print(f"  Wallet:   {wallet}")
    print(f"  Handle:   {handle}")
    if existing_agent_id:
        print(f"  Existing ID: {existing_agent_id} (will reuse)")

    async with AsyncAIPClient(base_url="https://api.aip.unibase.com") as client:
        is_healthy = await client.health_check()
        if not is_healthy:
            raise RuntimeError("AIP platform unavailable, check service status")
        print("  ✓ Platform healthy")

        agent_config = AgentConfig(
            name=name,
            handle=handle,
            description=description,
            endpoint_url=endpoint_url,
            skills=[
                SkillConfig(
                    skill_id="crypto.price",
                    name="Crypto Price Query",
                    description="Query real-time and historical crypto prices from Binance",
                )
            ],
            cost_model=CostModel(base_call_fee=0.0),
            metadata={
                "chain_id": 97,
                "author": "Unibase Demo",
            },
            job_offerings=BINANCE_JOB_OFFERINGS,
            job_resources=BINANCE_JOB_RESOURCES,
            # Pass existing_agent_id so server returns the same token on restart
            agent_id=existing_agent_id,
        )

        result = await client.register_agent(
            agent_config,
            user_id=wallet,
            privy_token=auth_token,
        )
        agent_id = result.get("agent_id")
        agent_wallet = None
        if result.get("onchain_registration"):
            agent_wallet = result["onchain_registration"].get("agent_wallet")
        print(f"  ✓ Registered. Agent ID: {agent_id}")
        if agent_wallet:
            print(f"  ✓ Agent Wallet: {agent_wallet}")

        # Persist identity so subsequent starts reuse the same token
        save_auth_token(auth_token, agent_id=agent_id, agent_wallet=agent_wallet)
        return agent_id


def build_server(
    wallet: str,
    auth_token: str,
    handle: str,
    name: str,
    description: str,
    endpoint_url: str | None,
    port: int,
    polling: bool = False,
    via_gateway: bool = False,
):
    """
    Build and return A2AServer via expose_as_a2a.
    Does NOT auto-register (registration is done separately).
    """
    agent = BinancePriceAgent()

    mode_tag = "polling" if polling else "push"
    metadata_extra = {"mode": mode_tag}
    if via_gateway:
        metadata_extra["via_gateway"] = True

    print(f"\n{'='*70}")
    print("Step 3: Start Agent Service")
    print(f"{'='*70}")
    print(f"  Name:     {name}")
    print(f"  Handle:   {handle}")
    print(f"  Mode:     {'POLLING (no public URL)' if polling else 'PUSH (public URL)'}")
    if endpoint_url:
        print(f"  URL:      {endpoint_url}")
    if polling:
        if via_gateway:
            print(f"  Queue:    JOB-QUEUE (/gateway/jobs/poll) - Butler can discover this agent")
        else:
            print(f"  Queue:    TASK-QUEUE (/gateway/tasks/poll)")
    print(f"  Port:     {port}")
    print()

    server = expose_as_a2a(
        name=name,
        handler=agent.handle,
        port=port,
        host="0.0.0.0",
        description=description,
        user_id=wallet if wallet else None,
        aip_endpoint="https://api.aip.unibase.com",
        gateway_url=_get_gateway_url(),
        handle=handle,
        auto_register=False,
        endpoint_url=endpoint_url,
        via_gateway=via_gateway,
        cost_model=CostModel(base_call_fee=0.0),
        chain_id=97,
        skills=[
            AgentSkillCard(
                id="crypto.price",
                name="Crypto Price Query",
                description="Query real-time and historical crypto prices from Binance",
                tags=["crypto", "binance", "price", "trading", "defi"],
                examples=[
                    "BTCUSDT price",
                    "ETH 24h change",
                    "SOL klines 30",
                    "BNB orderbook 5",
                ],
            )
        ],
        job_offerings=BINANCE_JOB_OFFERINGS,
        job_resources=BINANCE_JOB_RESOURCES,
        metadata=metadata_extra,
    )

    return server


# ============================================================================
# Example 1: auto register (auto_register=True)
# PUSH mode - public agent with auto registration
# ============================================================================

def example_auto_register():
    """
    Start Binance Price Agent with auto registration (PUSH mode).

    Auth:
      - Checks config.json for UNIBASE_PROXY_AUTH
      - If missing → runs interactive auth (call /v1/init → print authUrl → read token)
      - Token is saved to config.json for future runs
    """
    wallet, auth_token, public_url = _load_env()

    print("\n===== Step 1: Authorization =====")
    # ensure_auth() checks config.json → loads token or runs interactive auth
    auth_token, resolved_wallet = ensure_auth()
    if resolved_wallet:
        wallet = resolved_wallet  # prefer wallet decoded from token

    handle = "binance_price"
    name = "Binance Price Agent"
    description = "Real-time cryptocurrency price queries via Binance public API"

    print("\n===== Step 2: Agent Registration (auto) =====")
    print("  Mode: auto_register=True (SDK registers on server startup)")

    agent = BinancePriceAgent()
    endpoint_url = public_url

    print(f"\n{'='*70}")
    print("Step 3: Start Agent Service")
    print(f"{'='*70}")

    server = expose_as_a2a(
        name=name,
        handler=agent.handle,
        port=8200,
        host="0.0.0.0",
        description=description,
        user_id=wallet if wallet else None,
        privy_token=auth_token,
        aip_endpoint="https://api.aip.unibase.com",
        gateway_url=_get_gateway_url(),
        handle=handle,
        auto_register=True,
        endpoint_url=endpoint_url,
        cost_model=CostModel(base_call_fee=0.0),
        chain_id=97,
        skills=[
            AgentSkillCard(
                id="crypto.price",
                name="Crypto Price Query",
                description="Query real-time and historical crypto prices from Binance",
                tags=["crypto", "binance", "price", "trading"],
            )
        ],
        job_offerings=BINANCE_JOB_OFFERINGS,
        job_resources=BINANCE_JOB_RESOURCES,
        metadata={"mode": "push"},
    )

    print(f"  Mode:     PUSH (auto register on startup)")
    print(f"  URL:      {endpoint_url}")
    print(f"  Register: POST https://api.aip.unibase.com/agents/register")
    print(f"  Auth:     Bearer token from config.json")
    print()
    server.run_sync()


# ============================================================================
# Example 2: manual register (auto_register=False)
# PUSH mode - public agent, step-by-step registration
# ============================================================================

def example_manual_register():
    """
    Start Binance Price Agent with manual registration (PUSH mode).

    Auth + Registration flow:
      - ensure_auth() → load token from config.json or interactive auth
      - register_agent() → call POST /agents/register explicitly
      - expose_as_a2a(..., auto_register=False) → skip duplicate registration
    """
    wallet, auth_token, public_url = _load_env()

    print("\n===== Step 1: Authorization =====")
    auth_token, resolved_wallet = ensure_auth()
    if resolved_wallet:
        wallet = resolved_wallet

    handle = "binance_spot"
    name = "Binance Spot"
    description = "Real-time cryptocurrency price queries via Binance public API"
    endpoint_url = public_url

    # Load persisted agent identity (reuses existing token on restart)
    existing_agent_id, existing_agent_wallet = load_agent_identity()

    # Manual registration (step-by-step)
    # Pass existing_agent_id so server returns the same token instead of creating a new one
    asyncio.run(
        register_agent(
            wallet=wallet,
            auth_token=auth_token,
            handle=handle,
            name=name,
            description=description,
            endpoint_url=endpoint_url,
            port=8201,
            existing_agent_id=existing_agent_id,
        )
    )

    server = build_server(
        wallet=wallet,
        auth_token=auth_token,
        handle=handle,
        name=name,
        description=description,
        endpoint_url=endpoint_url,
        port=8201,
        polling=False,
    )
    server.run_sync()


# ============================================================================
# Example 3: auto register + POLLING mode (private agent)
# ============================================================================

def example_polling_mode():
    """
    Start Binance Price Agent with auto registration (POLLING mode).

    Agent has no public URL → polls Gateway every 3 seconds for tasks.
    No public exposure needed.
    """
    wallet, auth_token, _ = _load_env()

    print("\n===== Step 1: Authorization =====")
    auth_token, resolved_wallet = ensure_auth()
    if resolved_wallet:
        wallet = resolved_wallet

    handle = "binance_spot"
    name = "Binance Spot"
    description = "Real-time cryptocurrency price queries via Binance (polling mode)"

    print("\n===== Step 2: Agent Registration (auto, polling) =====")
    print("  Mode: auto_register=True + endpoint_url=None (triggers polling)")

    agent = BinancePriceAgent()

    print(f"\n{'='*70}")
    print("Step 3: Start Agent Service (POLLING)")
    print(f"{'='*70}")

    server = expose_as_a2a(
        name=name,
        handler=agent.handle,
        port=8202,
        host="0.0.0.0",
        description=description,
        user_id=wallet if wallet else None,
        privy_token=auth_token,
        aip_endpoint="https://api.aip.unibase.com",
        gateway_url=_get_gateway_url(),
        handle=handle,
        auto_register=True,
        endpoint_url=None,
        via_gateway=True,            # KEY: Butler can discover & route via gateway job queue
        cost_model=CostModel(base_call_fee=0.0),
        chain_id=97,
        skills=[
            AgentSkillCard(
                id="crypto.price",
                name="Crypto Price Query",
                description="Query real-time and historical crypto prices from Binance",
                tags=["crypto", "binance", "price", "trading"],
            )
        ],
        job_offerings=BINANCE_JOB_OFFERINGS,
        job_resources=BINANCE_JOB_RESOURCES,
        metadata={"mode": "polling"},
    )

    print(f"  Mode:     POLLING (no public URL)")
    print(f"  Queue:    JOB-QUEUE (/gateway/jobs/poll) - Butler can discover this agent")
    print(f"  Register: POST https://api.aip.unibase.com/agents/register")
    print()
    print("  Chain:")
    print("    Agent → GET  /gateway/tasks/poll (every 3s)")
    print("    Agent → POST /gateway/tasks/complete (after processing)")
    print()
    server.run_sync()


# ============================================================================
# Example 4: manual register + POLLING mode (fully step-by-step)
# ============================================================================

def example_polling_manual():
    """
    Fully manual POLLING mode - step-by-step auth + registration + startup.
    """
    wallet, auth_token, _ = _load_env()

    print("\n===== Step 1: Authorization =====")
    auth_token, resolved_wallet = ensure_auth()
    if resolved_wallet:
        wallet = resolved_wallet

    handle = "binance_price_polling_manual"
    name = "Binance Price Agent (Polling Manual)"
    description = "Real-time cryptocurrency price queries via Binance (polling, manual)"

    asyncio.run(
        register_agent(
            wallet=wallet,
            auth_token=auth_token,
            handle=handle,
            name=name,
            description=description,
            endpoint_url=None,
            port=8203,
        )
    )

    server = build_server(
        wallet=wallet,
        auth_token=auth_token,
        handle=handle,
        name=name,
        description=description,
        endpoint_url=None,
        port=8203,
        polling=True,
        via_gateway=True,
    )
    server.run_sync()


# ============================================================================
# Environment Helpers
# ============================================================================

def _load_env() -> tuple:
    """Load standard env vars, return (wallet, auth_token, public_url)"""
    wallet = os.environ.get(
        "MEMBASE_ACCOUNT",
        "0x5ea13664c5ce67753f208540d25b913788aa3daa"
    )
    auth_token = os.environ.get("UNIBASE_PROXY_AUTH", "")
    public_url = os.environ.get(
        "AGENT_PUBLIC_URL",
        "http://your-public-ip:8200"
    )
    return wallet, auth_token, public_url


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Agent SDK Startup Examples")
    parser.add_argument(
        "mode",
        nargs="?",
        default="auto",
        choices=["auto", "manual", "polling", "polling-manual"],
        help="""
        Startup mode:
          auto           - auto register + PUSH mode (default)
          manual         - manual register + PUSH mode
          polling        - auto register + POLLING mode (private Agent)
          polling-manual - manual register + POLLING mode
        """,
    )
    parser.add_argument("--token", help="Authorization token (skips interactive auth)")
    parser.add_argument("--gateway-url", help="Gateway URL (e.g. http://<ec2-ip>:8081)")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║        Agent SDK Startup Guide - Binance Price Agent       ║
╠══════════════════════════════════════════════════════════════╣
║  Auth:    Check config.json → interactive auth if missing  ║
║  Register: POST /agents/register (Bearer token auth)        ║
║  Chain:   BSC Testnet (chain_id=97)                         ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Set CLI token so ensure_auth() can use it
    import examples.agent_sdk_startup_guide as m
    m._cli_token = args.token
    m._cli_gateway_url = args.gateway_url

    try:
        if args.mode == "auto":
            print(">>> Mode: auto register + PUSH mode")
            example_auto_register()

        elif args.mode == "manual":
            print(">>> Mode: manual register + PUSH mode")
            example_manual_register()

        elif args.mode == "polling":
            print(">>> Mode: auto register + POLLING mode (private Agent)")
            example_polling_mode()

        elif args.mode == "polling-manual":
            print(">>> Mode: manual register + POLLING mode (private Agent)")
            example_polling_manual()

    except KeyboardInterrupt:
        print("\n\nAgent shutdown requested.")
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
