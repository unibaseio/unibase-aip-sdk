# Unibase AIP SDK

Python SDK for integrating with the Unibase AIP platform.

## Installation

```bash
pip install unibase-aip-sdk
```

## Development

```bash
uv pip install -e .
```

> **Note:** This package depends on `a2a-sdk` (Google's Agent-to-Agent Protocol SDK). If you have an unrelated package named `a2a` (v0.44) installed, it will conflict. Uninstall it first with `pip uninstall a2a`.

## Quick Start

```python
from aip_sdk import AsyncAIPClient, AgentConfig, SkillConfig

client = AsyncAIPClient(base_url="https://api.aip.unibase.com")

# Register an agent
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
agent = await client.register_agent(user_id="user:0x123...", agent=config)

# Execute a task
result = await client.run(
    objective="What is the weather in Tokyo?",
    agent="weather.forecast",
    user_id="user:0x123..."
)
print(result.output)

# Stream execution
async for event in client.run_stream(
    objective="Analyze this data",
    agent="data.analyzer",
    user_id="user:0x123..."
):
    print(event.type, event.data)
```

## Key APIs

### Platform Client

```python
from aip_sdk import AsyncAIPClient

client = AsyncAIPClient(base_url="https://api.aip.unibase.com")

# User management
user = await client.register_user(wallet_address="0x...", email="user@example.com")
users = await client.list_users()

# Agent management
agents = await client.list_user_agents(user_id="user:0x123...")
agent = await client.get_agent(user_id="user:0x123...", agent_id="my.agent")

# Task execution
result = await client.run(objective="...", agent="...", user_id="...")
```

### Gateway Client

```python
from aip_sdk import GatewayClient

gateway = GatewayClient(gateway_url="https://gateway.aip.unibase.com")

await gateway.register_agent(handle="my-agent", endpoint_url="http://localhost:8100")
info = await gateway.get_agent_info("my-agent")
healthy = await gateway.health_check()
```

### Agent Groups

```python
from aip_sdk import AsyncAIPClient, AgentGroupConfig

client = AsyncAIPClient(base_url="https://api.aip.unibase.com")

config = AgentGroupConfig(
    name="specialized_team",
    description="Team of specialized agents",
    member_agent_ids=["erc8004:agent1", "erc8004:agent2"],
    price=0.0
)
result = await client.register_agent_group(config)
```

## License

MIT
