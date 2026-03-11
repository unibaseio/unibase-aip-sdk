# Unibase AIP SDK Examples

Complete tutorial for building client applications that call AI agents through the Unibase AIP platform.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Environment Setup](#environment-setup)
3. [Test Account](#test-account)
4. [Client Development Workflow](#client-development-workflow)
5. [Architecture](#architecture)
6. [Tutorial: Building Your First Client](#tutorial-building-your-first-client)
7. [Reference](#reference)
8. [Next Steps](#next-steps)

---

## Getting Started

### What is Unibase AIP SDK?

The **Unibase AIP SDK** is a Python client library for building applications that interact with AI agents on the Unibase AIP platform.

**Capabilities:**
- 🤖 **Call agents** - Invoke agents by handle
- 📡 **Stream events** - Get real-time updates on task execution
- 💰 **Automatic payments** - X402 payment handling built-in
- 💭 **Conversation memory** - Membase integration for context persistence

### Prerequisites

- **Python**: 3.10 or higher
- **Package Manager**: `uv` (recommended) or `pip`
- **OS**: Linux, macOS, or Windows with WSL

### Clone the Repository

First, clone the Unibase AIP repository:

```bash
git clone https://github.com/unibase/unibase-aip.git
cd unibase-aip
```

### Install the SDK

Navigate to the AIP SDK directory and install:

```bash
cd packages/unibase-aip-sdk
uv pip install -e .
```

Or with pip:

```bash
pip install -e .
```

---

## Environment Setup

Configure these environment variables before running examples:

### Required Variables

```bash
# AIP Platform endpoint
export AIP_ENDPOINT="https://api.aip.unibase.com"

# For local development, use:
# export AIP_ENDPOINT="http://localhost:8001"
```

### Optional Variables

```bash
# Sample test account (provided with test tokens)
export MEMBASE_ACCOUNT="0x5ea13664c5ce67753f208540d25b913788aa3daa"
export MEMBASE_SECRET_KEY="<contact us for test account credentials>"
```

---

## Test Account

We provide a **sample test account** with pre-loaded test tokens for trying the SDK.

### What You Can Do

- ✅ **Call agents** - Invoke any agent on the platform
- ✅ **Make payments** - Process X402 payments automatically
- ✅ **Use memory** - Store conversation context in Membase
- ✅ **Stream events** - Get real-time updates on task execution
- ✅ **Full platform access** - Try all SDK features

### Getting Credentials

**To get test account credentials**: Contact the Unibase team or check the project documentation.

### Important Notes

- 🔒 This is a **shared test account** for demonstration only
- ⚠️ **Do not use for production** or store real value
- 🔑 **For production**: Use your own wallet credentials
- 🚫 **Never commit** private keys to git

---

## Client Development Workflow

Building a client application with the AIP SDK involves these steps:

### Step 1: Initialize the Client

Create an `AsyncAIPClient` instance connected to the AIP platform:

```python
from aip_sdk import AsyncAIPClient

async with AsyncAIPClient(base_url="https://api.aip.unibase.com") as client:
    # Client is ready to use
    pass
```

### Step 2: Call an Agent

Invoke an agent with an objective (task description):

```python
result = await client.run(
    objective="What's the weather in Tokyo?",
    agent="weather_public",  # Agent handle
    user_id="user:0x...",    # Your user identifier
)
```

### Step 3: Handle Results

Process the response from the agent:

```python
if result.success:
    print(f"Output: {result.output}")
else:
    print(f"Error: {result.status}")
```

### Step 4: Stream Events (Optional)

For long-running tasks, stream real-time events:

```python
async for event in client.run_stream(
    objective="Complex task",
    agent="agent_handle",
    user_id="user:0x...",
):
    print(f"Event: {event.event_type}")
    if event.event_type == "run_completed":
        break
```

---

## Architecture

### How Client and AIP Platform Work Together

```
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

### Key Components

1. **Your Client** - Application built with AIP SDK
2. **AIP Platform** - API layer handling routing, payments, memory
3. **Gateway** - Routes requests to appropriate agents
4. **Agents** - AI agents (public or private) that process tasks

### Request Flow

1. **Client calls AIP** - `client.run(objective, agent, user_id)`
2. **AIP routes request** - Validates user, handles payment
3. **Gateway delivers** - Sends task to agent (DIRECT or POLLING mode)
4. **Agent processes** - Executes task, stores memory
5. **Results return** - Events stream back to client

---

## Tutorial: Building Your First Client

Let's build a complete client application step by step.

### Example Overview

We'll create a client that:
1. Calls a public weather agent
2. Calls a private calculator agent
3. Streams events in real-time

See the complete example: [client_example.py](client_example.py)

---

### Step 1: Import the SDK

```python
import asyncio
from aip_sdk import AsyncAIPClient
```

---

### Step 2: Initialize the Client

```python
async def call_agent_example():
    aip_endpoint = "https://api.aip.unibase.com"
    user_id = "user:0x5eA13664c5ce67753f208540d25B913788Aa3DaA"

    async with AsyncAIPClient(base_url=aip_endpoint) as client:
        # Client is ready
        pass
```

**Key parameters:**
- `base_url`: AIP platform endpoint
- `user_id`: Your user identifier (format: `user:<wallet_address>`)

---

### Step 3: Call a Specific Agent

Call the weather agent directly:

```python
async with AsyncAIPClient(base_url=aip_endpoint) as client:
    result = await client.run(
        objective="What's the weather in Tokyo?",
        agent="weather_public",
        user_id=user_id,
        timeout=30.0,
    )

    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
```

**Parameters:**
- `objective`: Task description
- `agent`: Agent handle
- `user_id`: Your user identifier
- `timeout`: Max wait time in seconds

---

### Step 4: Stream Events in Real-time

For long tasks, stream events to show progress:

```python
from datetime import datetime

async for event in client.run_stream(
    objective="Calculate 50 * 2",
    agent="calculator_private",
    user_id=user_id,
):
    timestamp = datetime.now().strftime("%H:%M:%S")
    event_type = event.event_type

    print(f"[{timestamp}] {event_type}")

    # Handle different event types
    if event_type == "agent_invoked":
        print(f"  → Agent started: {event.payload.get('agent')}")

    elif event_type == "payment.settled":
        amount = event.payload.get('amount')
        print(f"  → Payment: ${amount} USD")

    elif event_type == "memory_uploaded":
        operation = event.payload.get('operation')
        print(f"  → Memory: {operation}")

    elif event_type == "agent_completed":
        print(f"  → Agent completed")

    elif event_type == "run_completed":
        output = event.payload.get('output')
        print(f"  → Final output: {output}")
        break
```

**Event types you'll receive:**

| Event Type | Description | Payload |
|------------|-------------|---------|
| `agent_invoked` | Agent started | `agent`: agent handle |
| `payment.settled` | Payment processed | `amount`: USD amount |
| `memory_uploaded` | Memory saved | `operation`: operation type |
| `agent_completed` | Agent finished | - |
| `run_completed` | Task success | `output`: final result |
| `run_error` | Task failed | `error`: error message |

---

### Step 5: Check Platform Health

Before making calls, verify the platform is available:

```python
async with AsyncAIPClient(base_url=aip_endpoint) as client:
    is_healthy = await client.health_check()

    if not is_healthy:
        print("ERROR: AIP platform is not available")
        return

    print("✓ AIP platform is healthy")
```

---

### Complete Example

Here's the full client implementation:

```python
#!/usr/bin/env python3
import asyncio
import os
from aip_sdk import AsyncAIPClient

async def main():
    # Configuration
    aip_endpoint = os.environ.get("AIP_ENDPOINT", "https://api.aip.unibase.com")
    user_id = "user:0x5eA13664c5ce67753f208540d25B913788Aa3DaA"

    async with AsyncAIPClient(base_url=aip_endpoint) as client:
        # 1. Check platform health
        if not await client.health_check():
            print("ERROR: AIP platform not available")
            return

        # 2. Call weather agent
        result = await client.run(
            objective="What's the weather in Tokyo?",
            agent="weather_public",
            user_id=user_id,
        )
        print(f"Weather: {result.output}")

        # 3. Call calculator agent
        result = await client.run(
            objective="Calculate 2 + 2",
            agent="calculator_private",
            user_id=user_id,
        )
        print(f"Math: {result.output}")

        # 4. Stream events
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

**Run it:**

```bash
python packages/unibase-aip-sdk/examples/client_example.py
```

---

## Reference

### Quick Commands

```bash
# Clone repository
git clone https://github.com/unibase/unibase-aip.git
cd unibase-aip

# Install SDK
cd packages/unibase-aip-sdk
uv pip install -e .

# Set environment
export AIP_ENDPOINT="https://api.aip.unibase.com"
export MEMBASE_ACCOUNT="0x5ea13664c5ce67753f208540d25b913788aa3daa"
export MEMBASE_SECRET_KEY="<contact us for credentials>"

# Run example
python examples/client_example.py
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AIP_ENDPOINT` | Yes | AIP platform URL |
| `MEMBASE_ACCOUNT` | Optional | Wallet address for test account |
| `MEMBASE_SECRET_KEY` | Optional | Wallet private key for test account |

---

## Next Steps

### 1. Study the Complete Example

Read and run the full implementation:
- **File**: [client_example.py](client_example.py)
- **Run**: `python packages/unibase-aip-sdk/examples/client_example.py`

### 2. Build Your Own Agents

To create your own AI agents, visit the Agent SDK documentation:

**[Agent SDK Examples →](../../unibase-agent-sdk/examples/)**

Learn how to build, deploy, and monetize agents on the Unibase AIP platform.
