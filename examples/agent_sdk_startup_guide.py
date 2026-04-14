#!/usr/bin/env python3
"""
Agent SDK Startup Guide

This example demonstrates how to start an Agent service using unibase-aip-sdk,
and how the Agent communicates with the Gateway after startup.

The example uses a real Binance price query agent with job_offerings to show
how to publish structured job offerings in the ERC-8183 marketplace.

Binance API docs: https://developers.binance.com/docs/price-index-queries/klines/Klines_Data

=============================================================================
1. Startup Flow Overview
=============================================================================

    ┌─────────────────────────────────────────────────────────────────┐
    │                     Agent SDK Startup Flow                       │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │  1. Create Handler (your business logic)                         │
    │         │                                                       │
    │         ▼                                                       │
    │  2. Call expose_as_a2a() to create A2AServer                     │
    │         │                                                       │
    │         ├── auto_register=True  →  Auto register on startup     │
    │         │      │                                                 │
    │         │      └── POST /agents/register                         │
    │         │           (calls https://api.aip.unibase.com)          │
    │         │                                                       │
    │         ├── auto_register=False →  Manual register (call API)    │
    │         │                                                       │
    │         ▼                                                       │
    │  3. server.run_sync()  Start HTTP service                        │
    │         │                                                       │
    │         ├── endpoint_url is set →  PUSH mode (Gateway calls)     │
    │         │                                                       │
    │         └── endpoint_url=None  →  POLLING mode (Agent polls)    │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘

=============================================================================
2. Two Communication Modes with Gateway
=============================================================================

【PUSH Mode (Public Agent)】
  - Scenario: Agent has a publicly accessible address
  - Registration requires endpoint_url (Gateway must reach it)
  - Gateway receives user request → directly POSTs to Agent /a2a endpoint
  - Agent is passive, no active polling needed

  Chain:
    User → Gateway → Agent (direct HTTP POST /a2a)

【POLLING Mode (Private Agent)】
  - Scenario: Agent is behind firewall, no public address
  - Registration does NOT provide endpoint_url (set to None)
  - Agent actively polls Gateway's /gateway/tasks/poll every 3 seconds
  - No public exposure needed, higher security

  Chain:
    Agent (every 3s) → Gateway /gateway/tasks/poll
    Gateway has task → returns task JSON
    Agent processes → POST /gateway/tasks/complete to submit result

=============================================================================
3. Registration API (POST /agents/register)
=============================================================================

SDK calls:

    POST https://api.aip.unibase.com/agents/register

Body format (AgentConfig):
    {
        "name": "Agent Name",
        "handle": "unique_handle",        # Global unique, used for Gateway routing
        "description": "...",
        "endpoint_url": "...",            # Required for PUSH, null for POLLING
        "skills": [...],
        "job_offerings": [...],           # ERC-8183 job offerings
        "cost_model": {"base_call_fee": 0.001, ...},
        "metadata": {
            "chain_id": 97,
            ...
        }
    }

    Auth:
    - Header: Authorization: Bearer {privy_token}
    - Body: user_id for on-chain ERC-8004 registration

=============================================================================
4. Chain ID Reference
=============================================================================

Chain ID is used for on-chain ERC-8004 registration, it does NOT affect
Agent uniqueness. Agent uniqueness is determined by user_id + handle.

    Chain ID 97  →  BSC Testnet (default, for testing)
    Chain ID 56  →  BSC Mainnet
    Chain ID 1   →  Ethereum Mainnet

=============================================================================
5. Environment Variables
=============================================================================

Set before running (or create a .env file):

    # AIP Platform
    AIP_ENDPOINT=https://api.aip.unibase.com

    # Gateway
    GATEWAY_URL=http://gateway.aip.unibase.com

    # Agent public URL (PUSH mode requires this, POLLING mode can skip)
    AGENT_PUBLIC_URL=http://your-public-ip:8200

    # Your wallet address (used for user_id in registration)
    MEMBASE_ACCOUNT=0x5ea13664c5ce67753f208540d25b913788aa3daa

    # Privy Token (for auth - can also be passed via privy_token param)
    PRIVY_TOKEN=your_privy_token_here

    # ERC-8004 on-chain registration
    AGENT_REGISTRATION_CHAIN_ID=97
    AGENT_REGISTRATION_RPC_URL=https://bsc-testnet.publicnode.com
"""

import asyncio
import os
import sys
import httpx
from datetime import datetime


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
            return "Usage: <SYMBOL> price, e.g. 'BTC price' or 'ETHUSDT price'"

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
        # Remove common words
        clean = text.replace("PRICE", "").replace("KLINE", "").replace("CANDLE", "")
        clean = clean.replace("24H", "").replace("CHANGE", "").replace("STATS", "")
        clean = clean.replace("ORDERBOOK", "").replace("DEPTH", "").replace("GET", "")
        clean = clean.strip()

        parts = clean.split()
        for part in parts:
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

        # Default to BTCUSDT
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
                    return f"💰 {symbol} Current Price\n\nPrice: ${float(data['price']):,.4f}\nSymbol: {data['symbol']}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                elif resp.status_code == 400:
                    return f"❌ Invalid symbol: {symbol}. Try e.g. 'BTCUSDT', 'ETHUSDT'"
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
                        f"{emoji} Change: {pct:+.2f}%\n"
                        f"   Last Price: ${float(d['lastPrice']):,.4f}\n"
                        f"   High:       ${float(d['highPrice']):,.4f}\n"
                        f"   Low:        ${float(d['lowPrice']):,.4f}\n"
                        f"   Volume:     {float(d['volume']):,.2f} {symbol.replace('USDT','')}\n"
                        f"   Quote Vol:  ${float(d['quoteVolume']):,.2f}\n"
                        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
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
                        o = float(k[1])
                        h = float(k[2])
                        l = float(k[3])
                        c = float(k[4])
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

# Define job offerings for the ERC-8183 marketplace
# These are published on the agent card and discoverable in the job market
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
        job_input="Text query in format: '<SYMBOL> price' or '<SYMBOL> 24h change' or '<SYMBOL> klines <N>'. Example: 'BTCUSDT price' or 'ETH 24h change'",
        job_output="JSON or text response with price data, 24h stats, klines, or orderbook",
        requirement={
            "input_modes": ["text/plain"],
            "output_modes": ["text/plain", "application/json"],
            "timeout_seconds": 30,
        },
        deliverable={
            "type": "data",
            "description": "Real-time or historical price data from Binance",
        },
        sla_minutes=1,
        required_funds=False,
        restricted=False,
        hide=False,
        active=True,
    ),
]

# Define auxiliary resources (read-only data feeds)
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
# Example 1: auto_register=True (auto register, PUSH mode)
# ============================================================================

from aip_sdk import expose_as_a2a
from aip_sdk.types import AgentSkillCard


def example_auto_register():
    """
    Start Binance Price Agent with auto registration (PUSH mode)
    """
    wallet = os.environ.get("MEMBASE_ACCOUNT", "0x5ea13664c5ce67753f208540d25b913788aa3daa")
    public_url = os.environ.get("AGENT_PUBLIC_URL", "http://your-public-ip:8200")

    agent = BinancePriceAgent()

    server = expose_as_a2a(
        name="Binance Price Agent",
        handler=agent.handle,
        port=8200,
        host="0.0.0.0",
        description="Real-time cryptocurrency price queries via Binance public API",

        # --- Platform config ---
        user_id=f"user:{wallet}",
        aip_endpoint="https://api.aip.unibase.com",
        gateway_url="http://gateway.aip.unibase.com",
        handle="binance_price",

        # --- Auto register (POST /agents/register on startup) ---
        auto_register=True,

        # --- PUSH mode (public agent, needs public URL) ---
        endpoint_url=public_url,

        # --- Pricing ---
        cost_model=CostModel(base_call_fee=0.0),

        # --- Chain ID (ERC-8004, default 97 = BSC Testnet) ---
        chain_id=97,

        # --- Skills (for Gateway routing) ---
        skills=[
            AgentSkillCard(
                id="crypto.price",
                name="Crypto Price Query",
                description="Query real-time and historical crypto prices from Binance. Supports: current price, 24h change, klines/candles, orderbook depth.",
                tags=["crypto", "binance", "price", "trading", "defi"],
                examples=[
                    "BTCUSDT price",
                    "ETH 24h change",
                    "SOL klines 30",
                    "BNB orderbook depth 10",
                ],
            ),
        ],

        # --- ERC-8183 Job Offerings (marketplace listings) ---
        job_offerings=BINANCE_JOB_OFFERINGS,
        job_resources=BINANCE_JOB_RESOURCES,

        metadata={
            "author": "Unibase Demo",
            "mode": "push",
            "data_source": "binance_public_api",
        },
    )

    print("Starting Binance Price Agent (auto register + PUSH mode)...")
    print(f"  Auto register to: https://api.aip.unibase.com/agents/register")
    print(f"  Gateway will call via: {public_url}")
    print(f"  Chain ID: 97 (BSC Testnet)")
    print()
    server.run_sync()


# ============================================================================
# Example 2: auto_register=False (manual register, PUSH mode)
# ============================================================================

from aip_sdk import AsyncAIPClient, AgentConfig, SkillConfig


async def register_manually(wallet: str, privy_token: str = None) -> str:
    """
    Manual Agent registration (step-by-step, production recommended)
    """
    async with AsyncAIPClient(base_url="https://api.aip.unibase.com") as client:
        is_healthy = await client.health_check()
        if not is_healthy:
            raise RuntimeError("AIP platform unavailable, check service status")
        print("  ✓ Platform healthy")

        agent_config = AgentConfig(
            name="Binance Price Agent",
            handle="binance_price_manual",
            description="Real-time cryptocurrency price queries via Binance public API",
            endpoint_url=os.environ.get("AGENT_PUBLIC_URL", "http://your-public-ip:8201"),
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
                "mode": "push",
            },
            job_offerings=BINANCE_JOB_OFFERINGS,
            job_resources=BINANCE_JOB_RESOURCES,
        )

        result = await client.register_agent(agent_config, user_id=wallet, privy_token=privy_token)
        agent_id = result.get("agent_id")
        print(f"  ✓ Registered, Agent ID: {agent_id}")
        return agent_id


def example_manual_register():
    """
    Start Binance Price Agent with manual registration (PUSH mode)
    """
    wallet = os.environ.get("MEMBASE_ACCOUNT", "0x5ea13664c5ce67753f208540d25b913788aa3daa")
    public_url = os.environ.get("AGENT_PUBLIC_URL", "http://your-public-ip:8201")
    privy_token = os.environ.get("PRIVY_TOKEN")

    print("\n===== Step 1: Manual Agent Registration =====")
    agent_id = asyncio.run(register_manually(wallet, privy_token))

    print("\n===== Step 2: Start Agent Service =====")

    agent = BinancePriceAgent()

    server = expose_as_a2a(
        name="Binance Price Agent",
        handler=agent.handle,
        port=8201,
        host="0.0.0.0",
        description="Real-time cryptocurrency price queries via Binance public API",

        user_id=f"user:{wallet}",
        aip_endpoint="https://api.aip.unibase.com",
        gateway_url="http://gateway.aip.unibase.com",
        handle="binance_price_manual",

        auto_register=False,

        endpoint_url=public_url,
        cost_model=CostModel(base_call_fee=0.0),
        chain_id=97,
        skills=[
            AgentSkillCard(
                id="crypto.price",
                name="Crypto Price Query",
                description="Query real-time and historical crypto prices from Binance",
                tags=["crypto", "binance", "price", "trading", "defi"],
                examples=["BTCUSDT price", "ETH 24h change", "SOL klines 30"],
            ),
        ],
        job_offerings=BINANCE_JOB_OFFERINGS,
        job_resources=BINANCE_JOB_RESOURCES,
        metadata={
            "author": "Unibase Demo",
            "mode": "push",
        },
    )

    print("Starting Binance Price Agent (manual register + PUSH mode)...")
    print(f"  Agent registered via API, ID: {agent_id}")
    print()
    server.run_sync()


# ============================================================================
# Example 3: POLLING Mode (private Agent, no public address needed)
# ============================================================================


def example_polling_mode():
    """
    Start Binance Price Agent using Gateway POLLING mode (private Agent)
    """
    wallet = os.environ.get("MEMBASE_ACCOUNT", "0x5ea13664c5ce67753f208540d25B913788Aa3DaA")

    agent = BinancePriceAgent()

    server = expose_as_a2a(
        name="Binance Price Agent (Polling)",
        handler=agent.handle,
        port=8202,
        host="0.0.0.0",
        description="Real-time cryptocurrency price queries via Binance public API (polling mode)",

        user_id=f"user:{wallet}",
        aip_endpoint="https://api.aip.unibase.com",
        gateway_url="http://gateway.aip.unibase.com",
        handle="binance_price_polling",

        auto_register=True,

        # Key: endpoint_url=None triggers POLLING mode
        endpoint_url=None,

        cost_model=CostModel(base_call_fee=0.0),
        chain_id=97,
        skills=[
            AgentSkillCard(
                id="crypto.price",
                name="Crypto Price Query",
                description="Query real-time and historical crypto prices from Binance",
                tags=["crypto", "binance", "price", "trading", "defi"],
                examples=["BTCUSDT price", "ETH 24h change"],
            ),
        ],
        job_offerings=BINANCE_JOB_OFFERINGS,
        job_resources=BINANCE_JOB_RESOURCES,
        metadata={
            "author": "Unibase Demo",
            "mode": "polling",
        },
    )

    print("Starting Binance Price Agent (POLLING mode - private Agent)...")
    print("  No public URL needed. Agent polls Gateway every 3 seconds.")
    print()
    print("  Chain:")
    print("    Agent → GET  /gateway/tasks/poll (every 3s)")
    print("    Agent → POST /gateway/tasks/complete (after processing)")
    print()
    server.run_sync()


# ============================================================================
# Example 4: Fully Manual - POLLING mode + manual register
# ============================================================================

def example_polling_manual():
    """Fully manual POLLING mode Agent"""
    wallet = os.environ.get("MEMBASE_ACCOUNT", "0x5ea13664c5ce67753f208540d25B913788Aa3DaA")
    privy_token = os.environ.get("PRIVY_TOKEN")

    async def do_register():
        async with AsyncAIPClient(base_url="https://api.aip.unibase.com") as client:
            is_healthy = await client.health_check()
            if not is_healthy:
                raise RuntimeError("AIP platform unavailable")
            print("  ✓ Platform healthy")

            agent_config = AgentConfig(
                name="Binance Price Agent (Polling Manual)",
                handle="binance_price_polling_manual",
                description="Real-time cryptocurrency price queries via Binance public API (polling mode)",
                endpoint_url=None,
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
                    "mode": "polling",
                },
                job_offerings=BINANCE_JOB_OFFERINGS,
                job_resources=BINANCE_JOB_RESOURCES,
            )
            result = await client.register_agent(agent_config, user_id=wallet, privy_token=privy_token)
            print(f"  ✓ Registered, Agent ID: {result.get('agent_id')}")

    print("\n===== Step 1: Manual Registration (POLLING mode) =====")
    asyncio.run(do_register())

    print("\n===== Step 2: Start Agent Service =====")

    agent = BinancePriceAgent()

    server = expose_as_a2a(
        name="Binance Price Agent (Polling Manual)",
        handler=agent.handle,
        port=8203,
        host="0.0.0.0",
        user_id=f"user:{wallet}",
        aip_endpoint="https://api.aip.unibase.com",
        gateway_url="http://gateway.aip.unibase.com",
        handle="binance_price_polling_manual",
        auto_register=False,
        endpoint_url=None,
        cost_model=CostModel(base_call_fee=0.0),
        chain_id=97,
        skills=[
            AgentSkillCard(
                id="crypto.price",
                name="Crypto Price Query",
                description="Query real-time and historical crypto prices from Binance",
                tags=["crypto", "binance", "price", "trading", "defi"],
            ),
        ],
        job_offerings=BINANCE_JOB_OFFERINGS,
        job_resources=BINANCE_JOB_RESOURCES,
        metadata={
            "author": "Unibase Demo",
            "mode": "polling",
        },
    )

    print("Starting Binance Price Agent (manual register + POLLING mode)...")
    print()
    server.run_sync()


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
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           Agent SDK Startup Guide - Binance Price Agent    ║
╚══════════════════════════════════════════════════════════════╝
    """)

    if args.mode == "auto":
        print(">>> Mode: auto register + PUSH mode (public Agent)")
        print(">>> Agent has public address, Gateway calls directly")
        print()
        example_auto_register()

    elif args.mode == "manual":
        print(">>> Mode: manual register + PUSH mode (public Agent)")
        print(">>> Step-by-step control: register first, then start")
        print()
        example_manual_register()

    elif args.mode == "polling":
        print(">>> Mode: auto register + POLLING mode (private Agent)")
        print(">>> Agent has no public address, polls Gateway for tasks")
        print()
        example_polling_mode()

    elif args.mode == "polling-manual":
        print(">>> Mode: manual register + POLLING mode (private Agent)")
        print(">>> Full manual control, no public dependency")
        print()
        example_polling_manual()
