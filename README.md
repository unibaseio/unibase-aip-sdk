# Unibase AIP SDK

Python SDK for integrating with the Unibase AIP platform.

## Installation

```bash
pip install unibase-aip-sdk
```

## Quick Start

```python
from aip_sdk import AIPClient

# Initialize client
client = AIPClient(base_url="http://localhost:8001")

# Register a user
user = client.register_user(
    wallet_address="0x1234...",
    email="user@example.com"
)

# Execute a task
result = client.run(
    objective="Calculate 15 * 7",
    agent_id="calculator.compute",
    user_id=user.id
)
print(result.output)
```

## Features

- **Platform Client** - Register users, agents, and execute tasks
- **Gateway Client** - Agent routing and discovery
- **A2A Client** - Agent-to-agent communication
- **Streaming** - Real-time task execution events

## API Reference

### AIPClient

Main client for platform interaction.

```python
from aip_sdk import AIPClient, AsyncAIPClient

# Sync client
client = AIPClient(base_url="http://localhost:8001")

# Async client
async_client = AsyncAIPClient(base_url="http://localhost:8001")
```

#### User Management

```python
# Register user
user = client.register_user(wallet_address="0x...", email="user@example.com")

# List users
users = client.list_users()
```

#### Agent Management

```python
from aip_sdk import AgentConfig, SkillConfig

# Register agent
config = AgentConfig(
    agent_id="my.agent",
    name="My Agent",
    description="Does useful things",
    url="http://localhost:8100",
    skills=[
        SkillConfig(
            id="my.skill",
            name="My Skill",
            description="Performs a task"
        )
    ]
)
agent = client.register_agent(user_id="user123", config=config)

# List agents
agents = client.list_user_agents(user_id="user123")

# Get agent details
agent = client.get_agent(user_id="user123", agent_id="my.agent")
```

#### Task Execution

```python
# Synchronous execution
result = client.run(
    objective="What is the weather in Tokyo?",
    agent_id="weather.forecast",
    user_id="user123",
    timeout=30
)

# Streaming execution
async for event in async_client.run_stream(
    objective="Analyze this data",
    agent_id="data.analyzer",
    user_id="user123"
):
    print(event.type, event.data)
```

#### Run History

```python
# Get run events
events = client.get_run_events(run_id="run123")

# Get payment records
payments = client.get_run_payments(run_id="run123")
```

### GatewayClient

Client for gateway operations.

```python
from aip_sdk import GatewayClient

gateway = GatewayClient(base_url="http://localhost:8080")

# Register agent with gateway
await gateway.register_agent(
    name="my-agent",
    url="http://localhost:8100"
)

# Get agent info
info = await gateway.get_agent_info("my-agent")

# Health check
healthy = await gateway.health_check()
```

### GatewayA2AClient

Client for A2A protocol communication.

```python
from aip_sdk import GatewayA2AClient

a2a = GatewayA2AClient(gateway_url="http://localhost:8080")

# Execute task via A2A
result = await a2a.execute_task(
    agent_name="calculator",
    message="Calculate 2 + 2"
)

# Stream task execution
async for response in a2a.stream_task(
    agent_name="analyzer",
    message="Analyze this text"
):
    print(response)
```

### AIPContext

Execution context for agents to call other agents.

```python
from aip_sdk import AIPContext

async def my_handler(text: str, context: AIPContext) -> str:
    # Call another agent
    result = await context.call_agent(
        agent_id="helper.agent",
        task_name="process",
        payload={"input": text}
    )

    # Log events
    await context.log("processing", input=text)

    # Read/write memory
    data = await context.read("my_scope")
    await context.write("my_scope", {"key": "value"})

    return result
```

## Types

```python
from aip_sdk import (
    Task,           # Task definition
    TaskResult,     # Execution result
    AgentConfig,    # Agent configuration
    SkillConfig,    # Skill definition
    AgentInfo,      # Agent metadata
    RunResult,      # Run with events
    EventData,      # Streaming event
    UserInfo,       # User data
    PriceInfo,      # Pricing info
)
```

## Error Handling

```python
from aip_sdk import (
    AIPError,           # Base exception
    ConnectionError,    # Network issues
    AuthenticationError,
    RegistrationError,
    ExecutionError,
    PaymentError,
    ValidationError,
    TimeoutError,
    AgentNotFoundError,
)

try:
    result = client.run(...)
except AgentNotFoundError:
    print("Agent not registered")
except ExecutionError as e:
    print(f"Task failed: {e}")
except AIPError as e:
    print(f"Platform error: {e}")
```

## Configuration

```python
from aip_sdk import ClientConfig

config = ClientConfig(
    base_url="http://localhost:8001",
    timeout=30,
    headers={"Authorization": "Bearer token"}
)

client = AIPClient(config=config)
```

## License

MIT
