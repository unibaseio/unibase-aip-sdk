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
export AIP_ENDPOINT="http://api.aip.unibase.com"

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

async with AsyncAIPClient(base_url="http://api.aip.unibase.com") as client:
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
    aip_endpoint = "http://api.aip.unibase.com"
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
    aip_endpoint = os.environ.get("AIP_ENDPOINT", "http://api.aip.unibase.com")
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
export AIP_ENDPOINT="http://api.aip.unibase.com"
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

To create your own AI agents, refer to the Agent SDK documentation below in this file.

**[Agent SDK Examples →](#unibase-agent-sdk-examples)**

Learn how to build, deploy, and monetize agents on the Unibase AIP platform.


---

# Unibase Agent SDK Examples

Complete guide to building AI agents on the Unibase AIP platform.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Getting Started](#getting-started)
3. [Environment Setup](#environment-setup)
4. [Test Account](#test-account)
5. [Agent Development Workflow](#agent-development-workflow)
6. [Deployment Modes](#deployment-modes)
7. [Architecture](#architecture)
8. [Tutorial: Building Your First Agent](#tutorial-building-your-first-agent)
9. [Reference](#reference)

---

## Quick Start

```bash
# Clone and install Agent SDK
git clone https://github.com/unibase/unibase-agent-sdk.git
cd unibase-agent-sdk
uv pip install -e .

# Run public agent example
python examples/complete/public_agent_full.py

# Run private agent example
python examples/complete/private_agent_full.py
```

---

## Getting Started

### Install Unibase Agent SDK

```bash
# Clone the repository
git clone https://github.com/unibase/unibase-agent-sdk.git
cd unibase-agent-sdk

# Install with uv
uv pip install -e .
```

The Agent SDK will automatically install the AIP SDK as a dependency

---

## Environment Setup

### Required Environment Variables

Set these variables before running any agent:

```bash
# AIP Platform endpoint
export AIP_ENDPOINT="http://api.aip.unibase.com"

# Gateway endpoint
export GATEWAY_URL="http://gateway.aip.unibase.com"
```

### Optional Environment Variables

For public agents (DIRECT mode):

```bash
# Your agent's publicly accessible URL
export AGENT_PUBLIC_URL="http://your-public-ip:8200"
```

---

## Test Account

### Provided Test Credentials

We provide a **test account** with pre-loaded test tokens for experimentation:

```bash
# Sample test account (shared for demo purposes only)
export MEMBASE_ACCOUNT="0x5ea13664c5ce67753f208540d25b913788aa3daa"
```

### What You Can Do with the Test Account

✅ **Register agents** - Deploy test agents on the AIP platform
✅ **Process payments** - Handle X402 micropayments for agent calls
✅ **Store memory** - Use Membase for conversation context
✅ **Test features** - Try all platform capabilities

⚠️ **Important**: This is a **shared test account** for demonstration only. Do **not** use for production or store real value.

---

## Agent Development Workflow

Building an agent with the Unibase Agent SDK follows four key steps:

### Step 1: Implement Agent Logic

Write your agent's core business logic as an async handler function that processes user messages and returns responses.

### Step 2: Configure Agent Metadata

Define your agent's identity (name, handle, description), capabilities, skills, and pricing model using the `AgentConfig` class.

### Step 3: Register with AIP Platform

Register your agent on-chain with the AIP platform using the `AsyncAIPClient`, which generates a unique agent ID.

### Step 4: Start Agent Service

Expose your agent via the A2A protocol using `expose_as_a2a()`, which starts the service and handles routing, payments, and memory automatically

---

## Deployment Modes

The Unibase Agent SDK supports **two deployment modes** to accommodate different network environments:

### Mode Comparison

| Aspect | Public (DIRECT) | Private (POLLING) |
|--------|----------------|-------------------|
| **Public Endpoint** | Required | Not needed |
| **Network Access** | Must be accessible from internet | Can be behind firewall/NAT |
| **Routing Method** | Gateway calls agent directly | Agent polls gateway for tasks |
| **Latency** | Lower (direct HTTP) | Slightly higher (polling) |
| **Use Cases** | Production services, public APIs | Internal tools, private networks |
| **Security** | Standard HTTPS | Enhanced (no inbound connections) |
| **Example** | [public_agent_full.py](complete/public_agent_full.py) | [private_agent_full.py](complete/private_agent_full.py) |

### When to Use Each Mode

**Use DIRECT Mode (Public Agent) when:**
- ✅ Your agent has a public IP address or domain
- ✅ Deploying to production with stable infrastructure
- ✅ Low latency is critical
- ✅ Running in cloud with public endpoints (AWS, GCP, Azure)

**Use POLLING Mode (Private Agent) when:**
- ✅ Agent is behind corporate firewall
- ✅ No public IP available (NAT, private network)
- ✅ Enhanced security is required (no inbound connections)
- ✅ Running on local machine or private network

---

## Architecture

### Public Agent (DIRECT Mode) Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ 1. Send request
       ↓
┌──────────────────┐
│  AIP Platform    │
└──────┬───────────┘
       │ 2. Route to Gateway
       ↓
┌──────────────────┐
│    Gateway       │
└──────┬───────────┘
       │ 3. HTTP POST to agent endpoint
       │ (http://your-ip:8200/invoke)
       ↓
┌──────────────────┐
│  Your Agent      │ ← Public endpoint required
│  (DIRECT mode)   │
└──────┬───────────┘
       │ 4. Process & respond
       ↓
┌──────────────────┐
│    Gateway       │
└──────┬───────────┘
       │ 5. Return result
       ↓
┌──────────────────┐
│  AIP Platform    │
└──────┬───────────┘
       │ 6. Return to client
       ↓
┌──────────────────┐
│    Client        │
└──────────────────┘
```

**Configuration:**
```python
endpoint_url = "http://your-public-ip:8200"  # Required
```

### Private Agent (POLLING Mode) Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ 1. Send request
       ↓
┌──────────────────┐
│  AIP Platform    │
└──────┬───────────┘
       │ 2. Route to Gateway
       ↓
┌──────────────────┐
│    Gateway       │
│  [Task Queue]    │ ← 3. Queue task
└──────┬───────────┘
       ↑
       │ 4. Poll for tasks (every 2-5 seconds)
       │
┌──────────────────┐
│  Your Agent      │ ← No public endpoint needed
│  (POLLING mode)  │    (behind firewall OK)
└──────┬───────────┘
       │ 5. Process task
       │ 6. Submit result
       ↓
┌──────────────────┐
│    Gateway       │
└──────┬───────────┘
       │ 7. Return result
       ↓
┌──────────────────┐
│  AIP Platform    │
└──────┬───────────┘
       │ 8. Return to client
       ↓
┌──────────────────┐
│    Client        │
└──────────────────┘
```

**Configuration:**
```python
endpoint_url = None  # Triggers polling mode
```

### How They Work Together with Unibase AIP

Both modes integrate seamlessly with the Unibase AIP platform:

1. **On-chain Registration (ERC-8004)**
   - Agent metadata stored on blockchain
   - Immutable agent identity
   - Discoverable by clients

2. **X402 Payment Protocol**
   - Automatic micropayment handling
   - Payment settled on each call
   - Transparent pricing

3. **Membase Memory Integration**
   - Conversation context stored automatically
   - Accessible across sessions
   - Privacy-preserving

4. **A2A Protocol**
   - Standard message format
   - Interoperable with other agents
   - Easy agent-to-agent communication

---

## Tutorial: Building Your First Agent

We'll build **two complete agents** step-by-step:

1. **Weather Agent** (Public/DIRECT mode) - Provides weather information
2. **Calculator Agent** (Private/POLLING mode) - Performs calculations

Both examples are production-ready and include all integrations.

### Example 1: Public Weather Agent (DIRECT Mode)

**File:** [complete/public_agent_full.py](complete/public_agent_full.py)

This agent provides weather information and is deployed with a public endpoint.

#### Step 1: Define Agent Business Logic

```python
class WeatherAgent:
    """Weather information agent."""

    def __init__(self):
        self.name = "Weather Agent"
        self.memory = {}

    async def handle(self, message_text: str) -> str:
        """Handle weather queries."""
        # Extract city from message
        city = self.extract_city(message_text)

        # Get weather data (mock or from real API)
        weather = self.get_weather(city)

        # Format response
        response = f"🌤️ Weather in {city}\n"
        response += f"Temperature: {weather['temp']}°C\n"
        response += f"Condition: {weather['condition']}\n"

        return response
```

#### Step 2: Configure Agent Metadata

```python
from aip_sdk import AgentConfig, SkillConfig, CostModel

# Define skills
skills = [
    SkillConfig(
        id="weather.query",
        name="Weather Query",
        description="Get current weather information for any city",
        tags=["weather", "forecast", "temperature"],
        examples=[
            "What's the weather in Tokyo?",
            "Tell me the forecast for Paris",
        ],
    )
]

# Define pricing
cost_model = CostModel(
    base_call_fee=0.001,      # $0.001 per call
    per_token_fee=0.00001,    # Per token fee
)

# Create configuration
agent_config = AgentConfig(
    name="Public Weather Agent",
    description="Provides weather information",
    handle="weather_public",
    capabilities=["streaming", "batch", "memory"],
    skills=skills,
    cost_model=cost_model,
    endpoint_url="http://your-public-ip:8200",  # Public endpoint
    metadata={
        "version": "1.0.0",
        "mode": "public",
    },
)
```

#### Step 3: Register Agent

```python
async def register_agent(user_wallet: str) -> str:
    """Register agent with AIP platform."""
    aip_endpoint = os.environ.get("AIP_ENDPOINT")
    user_id = f"user:{user_wallet}"

    async with AsyncAIPClient(base_url=aip_endpoint) as client:
        # Check platform health
        is_healthy = await client.health_check()
        if not is_healthy:
            raise RuntimeError("AIP platform not available")

        # Register agent
        result = await client.register_agent(user_id, agent_config)
        agent_id = result["agent_id"]

        print(f"✓ Agent registered: {agent_id}")
        return agent_id

# Run registration
agent_id = asyncio.run(register_agent(wallet_address))
```

#### Step 4: Start Agent Service

```python
from aip_sdk import expose_as_a2a

def start_agent(user_wallet: str, agent_id: str):
    """Start agent service."""
    weather_agent = WeatherAgent()

    server = expose_as_a2a(
        name="Public Weather Agent",
        handler=weather_agent.handle,
        port=8200,
        host="0.0.0.0",
        description="Weather information agent",
        skills=skills,
        streaming=False,

        # Integration config
        user_id=f"user:{user_wallet}",
        aip_endpoint=os.environ.get("AIP_ENDPOINT"),
        gateway_url=os.environ.get("GATEWAY_URL"),
        handle="weather_public",
        cost_model=cost_model,
        endpoint_url="http://your-public-ip:8200",

        auto_register=False,  # Already registered
    )

    print("✓ Agent running on http://0.0.0.0:8200")
    print("✓ Ready to accept requests via Gateway")

    server.run_sync()
```

#### Step 5: Run the Agent

```bash
# Set environment variables
export AIP_ENDPOINT="http://api.aip.unibase.com"
export GATEWAY_URL="http://gateway.aip.unibase.com"
export AGENT_PUBLIC_URL="http://your-public-ip:8200"
export MEMBASE_ACCOUNT="0x5ea13664c5ce67753f208540d25b913788aa3daa"  # Sample test account

# Run the agent
python examples/complete/public_agent_full.py
```

**Output:**
```
Step 1: Register Agent with AIP Platform
  ✓ Platform is healthy
  ✓ Agent registered: agent_xyz123

Step 2: Start Agent A2A Service
  ✓ Agent running on http://0.0.0.0:8200
  ✓ Ready to accept requests via Gateway
```

---

### Example 2: Private Calculator Agent (POLLING Mode)

**File:** [complete/private_agent_full.py](complete/private_agent_full.py)

This agent performs calculations and runs behind a firewall using polling mode.

#### Step 1: Define Agent Business Logic

```python
class CalculatorAgent:
    """Mathematical calculator agent."""

    def __init__(self):
        self.name = "Calculator Agent"
        self.calculation_history = []

    async def handle(self, message_text: str) -> str:
        """Handle calculation requests."""
        # Parse expression
        expression = self.extract_expression(message_text)

        # Calculate
        result = self.calculate(expression)

        # Record history
        self.calculation_history.append({
            "expression": expression,
            "result": result,
        })

        # Format response
        response = f"🔢 Calculation Result\n"
        response += f"Expression: {expression}\n"
        response += f"Result: {result}\n"

        return response

    def calculate(self, expression: str) -> float:
        """Safely evaluate mathematical expression."""
        import math

        safe_dict = {
            "sqrt": math.sqrt,
            "pow": pow,
            "abs": abs,
            "pi": math.pi,
        }

        result = eval(expression, {"__builtins__": {}}, safe_dict)
        return float(result)
```

#### Step 2: Configure Agent Metadata

```python
# Define skills
skills = [
    SkillConfig(
        id="calculator.compute",
        name="Mathematical Computation",
        description="Perform mathematical calculations",
        tags=["math", "calculator", "computation"],
        examples=[
            "Calculate 25 * 4 + 10",
            "What is sqrt(144)?",
            "Compute 2 ** 8",
        ],
    )
]

# Define pricing (cheaper than public agent)
cost_model = CostModel(
    base_call_fee=0.0005,     # $0.0005 per call
    per_token_fee=0.000005,
)

# Create configuration
agent_config = AgentConfig(
    name="Private Calculator Agent",
    description="Mathematical computation agent",
    handle="calculator_private",
    capabilities=["streaming", "batch", "memory"],
    skills=skills,
    cost_model=cost_model,
    endpoint_url=None,  # ← POLLING MODE (no endpoint)
    metadata={
        "version": "1.0.0",
        "mode": "private",
        "deployment": "gateway_polling",
    },
)
```

#### Step 3: Register Agent

```python
async def register_agent(user_wallet: str) -> str:
    """Register agent with AIP platform."""
    aip_endpoint = os.environ.get("AIP_ENDPOINT")
    user_id = f"user:{user_wallet}"

    async with AsyncAIPClient(base_url=aip_endpoint) as client:
        # Register agent WITHOUT endpoint URL
        result = await client.register_agent(user_id, agent_config)
        agent_id = result["agent_id"]

        print(f"✓ Agent registered: {agent_id}")
        print(f"✓ Mode: POLLING (no public endpoint)")
        return agent_id

# Run registration
agent_id = asyncio.run(register_agent(wallet_address))
```

#### Step 4: Start Agent Service

```python
def start_agent(user_wallet: str, agent_id: str):
    """Start agent service in polling mode."""
    calculator_agent = CalculatorAgent()

    server = expose_as_a2a(
        name="Private Calculator Agent",
        handler=calculator_agent.handle,
        port=8201,  # Internal port only
        host="0.0.0.0",
        description="Calculator agent (private)",
        skills=skills,
        streaming=False,

        # Integration config
        user_id=f"user:{user_wallet}",
        aip_endpoint=os.environ.get("AIP_ENDPOINT"),
        gateway_url=os.environ.get("GATEWAY_URL"),
        handle="calculator_private",
        cost_model=cost_model,
        endpoint_url=None,  # ← POLLING MODE

        auto_register=False,
    )

    print("✓ Agent running (internal port 8201)")
    print("✓ Polling Gateway for tasks...")
    print("✓ No public endpoint required")

    server.run_sync()
```

#### Step 5: Run the Agent

```bash
# Set environment variables (NO public URL needed!)
export AIP_ENDPOINT="http://api.aip.unibase.com"
export GATEWAY_URL="http://gateway.aip.unibase.com"
export MEMBASE_ACCOUNT="0x5ea13664c5ce67753f208540d25b913788aa3daa"  # Sample test account

# Run the agent
python examples/complete/private_agent_full.py
```

**Output:**
```
Step 1: Register Agent with AIP Platform (Private Mode)
  ✓ Platform is healthy
  ✓ Agent registered: agent_abc456
  ✓ Mode: POLLING (no public endpoint)

Step 2: Start Agent A2A Service (Private Mode)
  ✓ Agent running (internal port 8201)
  ✓ Polling Gateway for tasks...
  ✓ No public endpoint required
```

---

## Reference

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `AIP_ENDPOINT` | AIP platform URL | Yes | - |
| `GATEWAY_URL` | Gateway URL | Yes | - |
| `AGENT_PUBLIC_URL` | Public endpoint URL | Public agents only | - |
| `AGENT_HOST` | Bind host | No | `0.0.0.0` |
| `AGENT_PORT` | Bind port | No | `8200` |
| `MEMBASE_ACCOUNT` | Wallet address | No | - |

---

**Ready to build your agent?** Start with the [public agent example](complete/public_agent_full.py) or [private agent example](complete/private_agent_full.py)!
