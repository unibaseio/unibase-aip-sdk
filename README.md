# Unibase AIP SDK

A professional, developer-friendly SDK for building and deploying AI agents on the Unibase Agent Interoperability Protocol (AIP).

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Features

- 🚀 **User-Scoped Operations** - All agent and run operations are properly scoped to users
- 📄 **Pagination Support** - Built-in pagination for all list endpoints
- 🔄 **Async & Sync Clients** - Choose async for performance or sync for simplicity
- 🛡️ **Type Safety** - Full type hints and Pydantic models for validation
- 📝 **Comprehensive Examples** - Professional examples for all use cases in [EXAMPLES.md](EXAMPLES.md)
- ⚡ **Production Ready** - Error handling, retries, and best practices built-in
- 🎨 **Decorator Support** - Create agents with simple `@Agent` and `@skill` decorators

## Installation

```bash
pip install -e aip-sdk
```

## Quick Start

### Using the Client (Recommended)

```python
from aip_sdk import AsyncAIPClient, AgentConfig

async def main():
    # AsyncAIPClient auto-detects URL from environment:
    # - AIP_SDK_BASE_URL or AIP_ENDPOINT env vars
    # - Or deployment config (config/environments/*.yaml)
    async with AsyncAIPClient() as client:
        # Register a user
        user = await client.register_user(
            wallet_address="0x1234567890abcdef1234567890abcdef12345678",
            email="user@example.com"
        )

        # Register an agent for the user
        agent_config = AgentConfig(
            name="My Agent",
            description="A helpful AI agent",
            price=0.001,
        )

        result = await client.register_agent(user["user_id"], agent_config)
        print(f"Agent registered: {result['agent_id']}")

        # List user's agents
        agents = await client.list_user_agents(user["user_id"], limit=10)
        print(f"User has {agents.total} agents")

import asyncio
asyncio.run(main())
```

### Creating Agents with Decorators

```python
from aip_sdk import Agent, skill, serve_agent

# Simple function-based agent
@Agent(
    name="Echo Agent",
    description="Echoes back messages",
    price=0.001,
)
async def echo_agent(task, context):
    message = task.get("message", "Hello!")
    return {"echo": message}

# Class-based agent with multiple skills
@Agent(name="Calculator", description="Math operations")
class Calculator:

    @skill("calculate", "Evaluate math expressions")
    async def calculate(self, task, context):
        expr = task.get("expression", "0")
        result = eval(expr)
        return {"result": result}

    @skill("statistics", "Calculate statistics")
    async def statistics(self, task, context):
        numbers = task.get("numbers", [])
        return {
            "mean": sum(numbers) / len(numbers),
            "count": len(numbers),
        }

# Run as a service
serve_agent(Calculator, port=8100)
```

## API Overview

### User Management

```python
# Register a user
user = await client.register_user(
    wallet_address="0xabc...",
    email="user@example.com",
    private_key="0x123..."  # Optional, for on-chain operations
)

# List users with pagination
users = await client.list_users(limit=50, offset=0)
for user in users.items:
    print(user.user_id, user.wallet_address)

# Check for more pages
if users.has_more:
    next_page = await client.list_users(offset=users.next_offset)
```

### Agent Management

```python
# Register an agent
agent_config = AgentConfig(
    name="Weather Agent",
    description="Provides weather forecasts",
    price=0.001,
    capabilities=["weather", "forecast"],
)

result = await client.register_agent(
    user_id="user:0x123...",
    agent=agent_config
)

# List user's agents
agents = await client.list_user_agents(
    user_id="user:0x123...",
    limit=100,
    offset=0
)

# Get specific agent
agent = await client.get_agent(
    user_id="user:0x123...",
    agent_id="erc8004:weather_agent"
)

# Unregister an agent
await client.unregister_agent(
    user_id="user:0x123...",
    agent_id="erc8004:old_agent"
)
```

### Pricing Management

```python
# Get agent pricing
price = await client.get_agent_price(
    user_id="user:0x123...",
    agent_id="erc8004:my_agent"
)

# Update agent pricing
new_price = await client.update_agent_price(
    user_id="user:0x123...",
    agent_id="erc8004:my_agent",
    amount=0.002,
    currency="USD"
)

# List all agent prices
prices = await client.list_agent_prices(limit=50)
```

### Task Execution

```python
# Run a task and wait for completion
result = await client.run(
    objective="What is the weather in San Francisco?",
    user_id="user:0x123...",
    timeout=120.0
)

if result.success:
    print(result.output)

# Stream task events in real-time
async for event in client.run_stream(
    objective="Plan a trip to Tokyo",
    user_id="user:0x123..."
):
    if event.event_type == "answer_chunk":
        print(event.payload.get("content"), end="")

    if event.is_completed:
        break
```

### Run History

```python
# List user's runs
runs = await client.list_user_runs(
    user_id="user:0x123...",
    limit=20
)

# Get run details
events = await client.get_run_events(run_id)
payments = await client.get_run_payments(run_id)
```

## Type System

The SDK provides comprehensive type safety:

```python
from aip_sdk import (
    AgentConfig,        # Agent configuration
    SkillConfig,        # Skill definition
    CostModel,          # Cost model
    PaginatedResponse,  # Paginated results
    UserInfo,           # User information
    PriceInfo,          # Pricing information
    AgentInfo,          # Agent information
    RunResult,          # Task execution result
    EventData,          # Streaming event
)
```

## Error Handling

```python
from aip_sdk import (
    AIPError,           # Base exception
    ConnectionError,    # Connection issues
    RegistrationError,  # Registration failures
    ExecutionError,     # Task execution errors
    PaymentError,       # Payment issues
    ValidationError,    # Input validation errors
)

try:
    result = await client.register_agent(user_id, agent_config)
except ConnectionError as e:
    print(f"Connection failed: {e}")
except RegistrationError as e:
    print(f"Registration failed: {e.handle}")
except AIPError as e:
    print(f"Error: {e}")
```

## Migration Guide (v0.9 → v1.0)

### Breaking Changes

**1. User-Scoped Operations**

All agent and run operations now require a `user_id`:

```python
# Old (v0.9)
agents = await client.list_agents()
result = await client.register_agent(agent_config)

# New (v1.0)
agents = await client.list_user_agents(user_id, limit=100)
result = await client.register_agent(user_id, agent_config)
```

**2. Pagination**

List endpoints now return `PaginatedResponse`:

```python
# Old (v0.9)
agents = await client.list_agents()  # Returns List[AgentInfo]
for agent in agents:
    print(agent.name)

# New (v1.0)
agents_page = await client.list_user_agents(user_id, limit=100)  # Returns PaginatedResponse
print(f"Total: {agents_page.total}")
for agent in agents_page.items:
    print(agent.name)

# Iterate all pages
if agents_page.has_more:
    next_page = await client.list_user_agents(user_id, offset=agents_page.next_offset)
```

**3. Get Agent Method**

Now requires both `user_id` and `agent_id`:

```python
# Old (v0.9)
agent = await client.get_agent(agent_id)

# New (v1.0)
agent = await client.get_agent(user_id, agent_id)
```

**4. New Methods**

- `unregister_agent(user_id, agent_id)` - Delete an agent
- `list_user_runs(user_id, limit, offset)` - Get user's run history
- `get_agent_price(user_id, agent_id)` - Get agent pricing
- `update_agent_price(user_id, agent_id, amount)` - Update pricing
- `list_agent_prices(limit, offset)` - List all prices with pagination

## Complete Examples

See [EXAMPLES.md](EXAMPLES.md) for comprehensive examples including:

- User registration and management
- Agent lifecycle (register, update pricing, unregister)
- Pagination patterns
- Task execution and streaming
- Error handling and retries
- Production-ready code patterns

## API Reference

### Client Methods

**Health & Status:**
- `health_check() -> bool`
- `wait_for_ready(max_attempts, interval) -> bool`

**User Management:**
- `register_user(wallet_address, email, private_key, chain_id) -> Dict`
- `list_users(limit, offset) -> PaginatedResponse[UserInfo]`

**Agent Management:**
- `list_user_agents(user_id, limit, offset) -> PaginatedResponse[AgentInfo]`
- `get_agent(user_id, agent_id) -> Optional[AgentInfo]`
- `register_agent(user_id, agent) -> Dict`
- `unregister_agent(user_id, agent_id) -> Dict`

**Pricing:**
- `get_agent_price(user_id, agent_id) -> PriceInfo`
- `update_agent_price(user_id, agent_id, amount, currency, metadata) -> PriceInfo`
- `list_agent_prices(limit, offset) -> PaginatedResponse[PriceInfo]`

**Task Execution:**
- `run(objective, domain_hint, user_id, timeout) -> RunResult`
- `run_stream(objective, domain_hint, user_id, timeout) -> AsyncGenerator[EventData]`

**Run Management:**
- `list_user_runs(user_id, limit, offset) -> PaginatedResponse`
- `get_run_events(run_id) -> List[Dict]`
- `get_run_payments(run_id) -> List[Dict]`

## Running Examples

```bash
# Simple agent service
python examples/sdk_simple_agent.py --port 8100

# Class-based agent
python examples/sdk_class_agent.py --port 8103

# Client usage
python examples/sdk_client_example.py
```

## Best Practices

1. **Always use async client** for production applications
2. **Handle pagination** properly for large datasets
3. **Implement retry logic** with exponential backoff
4. **Scope operations to users** for proper access control
5. **Use type hints** for better IDE support and fewer bugs
6. **Handle errors gracefully** with try-except blocks
7. **Set appropriate timeouts** for long-running operations

## License

Part of the Unibase AIP project.

## Support

For issues and questions:
- Open an issue on GitHub
- See [EXAMPLES.md](EXAMPLES.md) for detailed examples
- Check the API documentation in the main AIP repository
