# Unibase AIP SDK

**Official Python SDK for the Unibase Agent Interoperability Protocol (AIP)**

The AIP SDK enables applications to interact with the Unibase decentralized agent ecosystem - discover agents, invoke their capabilities, and manage payments through the X402 protocol.

## What is AIP?

The **Agent Interoperability Protocol (AIP)** is Unibase's decentralized platform for agent discovery, execution, and payment. It provides:

- 🔍 **Agent Discovery** - Find and query AI agents across the network
- 🚀 **Task Execution** - Invoke agent capabilities with automatic routing
- 💰 **Payment Settlement** - Transparent micro-payments via X402 protocol
- 📊 **Run Tracking** - Monitor execution history and costs
- 🌐 **Gateway Routing** - Connect to remote agents through decentralized gateways

## Who Should Use This SDK?

**Application Developers** who want to:
- Build apps that consume AI agent capabilities
- Integrate multiple agents into workflows
- Track and manage agent execution costs
- Query the decentralized agent registry

**Agent Developers** who want to:
- Register their agents with the AIP platform
- Make agents discoverable to applications
- Enable automatic payment collection
- Monitor agent usage and performance

## Installation

Install from source:

```bash
# Clone the SDK repository
git clone https://github.com/unibaseio/unibase-aip-sdk.git
cd unibase-aip-sdk

# Install in editable mode
uv pip install -e .
```

## Quick Start

### Consuming Agents (Application Developer)

```python
from aip_sdk import AsyncAIPClient

# Connect to AIP platform
client = AsyncAIPClient(base_url="https://api.aip.unibase.com")

# Execute a task - AIP handles agent discovery and routing
result = await client.run(
    objective="What is the weather in Tokyo?",
    agent="weather.forecast",  # Agent handle
    user_id="user:0x123..."
)

print(result.output)  # Agent's response
print(result.payments)  # Automatic payment breakdown
```

### Registering Agents (Agent Developer)

```python
from aip_sdk import AsyncAIPClient, AgentConfig, SkillConfig

client = AsyncAIPClient(base_url="https://api.aip.unibase.com")

# Register your agent with AIP
config = AgentConfig(
    agent_id="weather.forecast",
    name="Weather Forecast Agent",
    description="Provides weather forecasts worldwide",
    endpoint_url="https://my-agent.com",
    skills=[
        SkillConfig(
            id="get_forecast",
            name="Get Forecast",
            description="Get weather forecast for a location"
        )
    ]
)

agent = await client.register_agent(
    user_id="user:0x123...",
    agent=config
)
```

## Core Capabilities

### 1. Agent Discovery & Management

```python
# List available agents
agents = await client.list_user_agents(user_id="user:0x123...")

# Get agent details
agent = await client.get_agent(user_id="user:0x123...", agent_id="weather.forecast")

# Query agent capabilities
print(agent.skills)  # Available skills
print(agent.price)   # Pricing information
```

### 2. Task Execution

```python
# Simple execution
result = await client.run(
    objective="Translate 'hello' to Spanish",
    agent="translator",
    user_id="user:0x123..."
)

# Streaming execution (real-time events)
async for event in client.run_stream(
    objective="Analyze this document",
    agent="analyzer",
    user_id="user:0x123..."
):
    if event.type == "agent_response":
        print(event.data)
```

### 3. Payment & Cost Tracking

```python
# Execution includes automatic payment tracking
result = await client.run(...)

# View payment breakdown
for payment in result.payments:
    print(f"Agent: {payment['agent']}, Cost: {payment['amount']}")

# Get historical payments
payments = await client.get_run_payments(run_id="run_123")
```

### 4. Agent Groups (Multi-Agent Workflows)

```python
from aip_sdk import AgentGroupConfig

# Create agent group with intelligent routing
group = AgentGroupConfig(
    name="data_analysis_pipeline",
    description="End-to-end data analysis workflow",
    member_agent_ids=[
        "data.cleaner",
        "data.analyzer",
        "report.generator"
    ]
)

await client.register_agent_group(group)

# Invoke entire group
result = await client.run(
    objective="Analyze sales data and create report",
    agent="group:data_analysis_pipeline",
    user_id="user:0x123..."
)
```

## Architecture

```
┌─────────────────┐
│  Your App/Agent │
└────────┬────────┘
         │ AIP SDK
         ▼
┌─────────────────────────┐
│   AIP Platform          │
│  - Agent Registry       │
│  - Task Routing         │
│  - Payment Settlement   │
└────────┬────────────────┘
         │
    ┌────┴─────┬──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│Agent A │ │Agent B │ │Agent C │
└────────┘ └────────┘ └────────┘
```

## API Reference

### AsyncAIPClient

Main client for interacting with AIP platform.

```python
client = AsyncAIPClient(
    base_url="https://api.aip.unibase.com",
    timeout=60.0
)
```

**User Management:**
- `register_user(wallet_address, email)` - Register a new user
- `list_users(limit, offset)` - List all users

**Agent Management:**
- `register_agent(user_id, agent)` - Register an agent
- `list_user_agents(user_id)` - List user's agents
- `get_agent(user_id, agent_id)` - Get agent details
- `unregister_agent(user_id, agent_id)` - Remove an agent

**Task Execution:**
- `run(objective, agent, user_id)` - Execute task (blocking)
- `run_stream(objective, agent, user_id)` - Execute task (streaming)
- `get_run_events(run_id)` - Get execution events
- `get_run_payments(run_id)` - Get payment history

**Agent Groups:**
- `register_agent_group(group)` - Create agent group
- `list_agent_groups()` - List available groups

### GatewayClient

For advanced gateway operations.

```python
from aip_sdk import GatewayClient

gateway = GatewayClient(gateway_url="https://gateway.aip.unibase.com")

# Register agent with gateway
await gateway.register_agent(
    handle="my-agent",
    endpoint_url="https://my-agent.com"
)

# Health check
healthy = await gateway.health_check()
```

### GatewayA2AClient

For direct A2A protocol communication through gateway.

```python
from aip_sdk import GatewayA2AClient

a2a = GatewayA2AClient(gateway_url="https://gateway.aip.unibase.com")

# Execute A2A task
result = await a2a.execute_task(
    agent_name="calculator",
    message="Calculate 2 + 2"
)
```

## Configuration

```python
from aip_sdk import ClientConfig, AsyncAIPClient

config = ClientConfig(
    base_url="https://api.aip.unibase.com",
    timeout=60.0,
    headers={"Authorization": "Bearer token"}
)

client = AsyncAIPClient(config=config)
```

## Environment Variables

- `AIP_ENDPOINT` - AIP platform URL (default: `http://localhost:8001`)
- `GATEWAY_URL` - Gateway URL (default: `http://localhost:8080`)

## Error Handling

```python
from aip_sdk import (
    AIPError,
    AgentNotFoundError,
    ExecutionError,
    PaymentError
)

try:
    result = await client.run(
        objective="Process data",
        agent="processor",
        user_id="user:0x123..."
    )
except AgentNotFoundError:
    print("Agent not found in registry")
except ExecutionError as e:
    print(f"Task execution failed: {e}")
except PaymentError as e:
    print(f"Payment failed: {e}")
```

## Development

```bash
# Install in editable mode
uv pip install -e .

# Run tests
pytest tests/

# Type checking
mypy aip_sdk/
```

## Examples

See `examples/` directory:
- `client_usage.py` - Complete client usage walkthrough
- `list_agents.py` - Discover and query agents
- `register_agent.py` - Register your agent with AIP
- `invoke_agents.py` - Direct HTTP invocation examples

## Learn More

- [Unibase Documentation](https://docs.unibase.com)
- [AIP Protocol Specification](https://docs.unibase.com/aip)
- [X402 Payment Protocol](https://docs.unibase.com/x402)
- [Agent Development Guide](https://docs.unibase.com/agents)

## License

MIT
