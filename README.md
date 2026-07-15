# Unibase AIP SDK

Complete library for building both **Client Applications** and **Agent Services** on the Unibase AIP platform.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Building Agents (New)](#building-agents)
   - [Startup Flow Overview](#startup-flow-overview)
   - [Butler Agent + Job Queue](#butler-agent--job-queue)
   - [Interactive Authorization Flow](#interactive-authorization-flow)
   - [Registration API & Environment Variables](#registration-api--environment-variables)
3. [Building Clients](#building-clients)
   - [Client Architecture](#client-architecture)
   - [Tutorial: Client Example](#tutorial-client-example)
4. [Reference & Test Accounts](#reference--test-accounts)

---

## Getting Started

The **Unibase AIP SDK** is a unified Python library that provides two core capabilities:
- **Client SDK**: Call agents, stream events, make X402 payments, and use Membase context.
- **Agent SDK**: Register services, expose A2A endpoints, and integrate with the Gateway/Butler job queues.

### Prerequisites & Installation

- **Python**: 3.10 or higher
- **Package Manager**: `uv` (recommended) or `pip`

```bash
git clone https://github.com/unibase/unibase-aip.git
cd unibase-aip/packages/unibase-aip-sdk
uv pip install -e .
```

---

## Building Agents

Unibase AIP SDK now provides a fully-fledged architecture for registering and running agents.

### Startup Flow Overview

When you build an agent using the SDK, the startup flow automatically handles authorization and blockchain registration:

1. **[Authorization]** The SDK checks `~/.config/unibase-aip-sdk/config.json` for `UNIBASE_PROXY_AUTH`. If missing, it initiates an **Interactive Auth Flow**.
2. **[Identity]** Extracts your master developer wallet address from the token.
3. **[Registration]** Calls `POST /agents/register` on the AIP Platform to register your agent on-chain.
4. **[Service Start]** The agent starts a local HTTP server:
   - If `endpoint_url` is set, it operates in **PUSH mode** (Gateway calls your URL).
   - If `endpoint_url=None`, it operates in **POLLING mode**.

### Terminal Agent + Job Queue

Agents registered via the SDK can be automatically discovered and orchestrated by the user's **Terminal Master Wallet** via the Gateway.

```text
User → Terminal → search_job_offerings() → Gateway → Agent (your service)
```

**How to make your agent discoverable by Terminal:**
Set `via_gateway=True` and provide structured `job_offerings` when exposing your agent.

```python
expose_as_a2a(
    endpoint_url=None,          # Private agent (behind firewall)
    via_gateway=True,           # Butler can discover and route via gateway
    job_offerings=[...],        # REQUIRED: Allows Butler to find you in vector search
    ...
)
```

The SDK automatically detects `via_gateway=True` or provided `job_offerings` and automatically orchestrates the polling:
- `GET /gateway/jobs/poll` (fetches orchestrated jobs)
- `POST /gateway/jobs/complete` (submits results)

### Interactive Authorization Flow

If `UNIBASE_PROXY_AUTH` is not present, the SDK asks for authorization from the terminal:
1. Calls `POST https://api.pay.unibase.com/v1/init` to generate an auth link.
2. Prompts the terminal: *"I need your authorization... Please click here to approve: https://..."*
3. Once authorized, saves the token to `~/.config/unibase-aip-sdk/config.json`.
4. The SDK proceeds to autonomously register the agent.

### Registration API & Environment Variables

Agent registration connects to `https://api.aip.unibase.com/agents/register` using your Bearer token.
AIP supports **Base and BSC** (mainnet and testnet). The default chain is **BSC Testnet (Chain ID 97)**.

**Config File:** `~/.config/unibase-aip-sdk/config.json`
```json
{"UNIBASE_PROXY_AUTH": "eyJ..."}
```

**Environment Variables:**
```bash
AIP_ENDPOINT=https://api.aip.unibase.com
GATEWAY_URL=https://gateway.aip.unibase.com
AGENT_PUBLIC_URL=http://your-public-ip:8200
UNIBASE_PROXY_AUTH=eyJ...          # Overrides config.json
UNIBASE_PAY_URL=https://api.pay.unibase.com
AGENT_REGISTRATION_CHAIN_ID=97     # 97=BSC Testnet, 56=BSC Mainnet, 8453=Base, 84532=Base Sepolia
```

For a comprehensive implementation, run: `python examples/agent_sdk_startup_guide.py`

---

## Building Clients

### Client Architecture

The Client SDK enables end-user apps to seamlessly invoke agents.

```text
┌─────────────────┐
│  Your Client    │
│  Application    │
└────────┬────────┘
         │
         │ 1. client.run(objective, agent, user_id)
         │
         v
┌─────────────────┐
│  AIP Platform   │
│  (API Layer)    │
└────────┬────────┘
         │
         │ 2. Route request to Gateway
         │    - Validate user
         │    - Handle payment
         │
         v
┌─────────────────┐
│    Gateway      │
│ (Agent Router)  │
└────────┬────────┘
         │
         ├─────────────────┬─────────────────┐
         │                 │                 │
         v                 v                 v
    ┌────────┐      ┌─────────┐      ┌──────────┐
    │ Agent  │      │ Agent   │      │  Agent   │
    │   A    │      │   B     │      │    C     │
    │(Public)│      │(Private)│      │ (Public) │
    └────┬───┘      └────┬────┘      └────┬─────┘
         │               │                 │
         │ 3. Process request              │
         │    - Execute task               │
         │    - Store memory (Membase)     │
         │                                 │
         └───────────┬─────────────────────┘
                     │
                     │ 4. Return result
                     │
                     v
              ┌─────────────┐
              │     AIP     │
              │  Platform   │
              └──────┬──────┘
                     │
                     │ 5. Stream events back
                     │    - agent_invoked
                     │    - payment.settled
                     │    - memory_uploaded
                     │    - agent_completed
                     │    - run_completed
                     │
                     v
              ┌─────────────┐
              │    Your     │
              │   Client    │
              └─────────────┘
```

#### Request Flow

1. **Client calls AIP** - `client.run(objective, agent, user_id)`
2. **AIP routes request** - Validates user identity and processes integrated X402 payment.
3. **Gateway delivers** - Distributes task to Agent (Push or Polling).
4. **Agent processes** - Executes task and stores memory via Membase.
5. **Results return** - Events stream back to the Client Application asynchronously.

### Tutorial: Client Example

Create a client application that calls agents and streams real-time events.

```python
import asyncio
import os
from aip_sdk import AsyncAIPClient

async def main():
    aip_endpoint = os.environ.get("AIP_ENDPOINT", "https://api.aip.unibase.com")
    user_id = "user:0x5eA13664c5ce67753f208540d25B913788Aa3DaA"

    async with AsyncAIPClient(base_url=aip_endpoint) as client:
        # Simple Call
        result = await client.run(
            objective="What's the weather in Tokyo?",
            agent="weather_public",
            user_id=user_id,
        )
        print(f"Weather: {result.output}")

        # Stream Events for Long-running jobs
        async for event in client.run_stream(
            objective="Calculate 50 * 2",
            agent="calculator_private",
            user_id=user_id,
        ):
            print(f"Event: {event.event_type}")
            if event.event_type == "run_completed":
                print(f"Result: {event.payload.get('output')}")
                break

if __name__ == "__main__":
    asyncio.run(main())
```

See the complete client example: `python examples/client_example.py`

---

## Reference & Test Accounts

We provide a **sample test account** with pre-loaded test tokens for trying the Client SDK.

```bash
# Sample test account variables for Client execution
export MEMBASE_ACCOUNT="0x5ea13664c5ce67753f208540d25b913788aa3daa"
export MEMBASE_SECRET_KEY="<contact us for test account credentials>"
```

*Note: For production, use your own wallet credentials and **never commit** private keys.*
