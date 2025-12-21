# AIP SDK Examples

Professional examples for using the Unibase Agent Interoperability Protocol SDK.

## Table of Contents
- [Installation](#installation)
- [Quick Start](#quick-start)
- [User Management](#user-management)
- [Agent Management](#agent-management)
- [Pricing Management](#pricing-management)
- [Running Tasks](#running-tasks)
- [Pagination](#pagination)
- [Error Handling](#error-handling)

## Installation

```bash
pip install -e aip-sdk
```

## Quick Start

### Async Usage (Recommended)

```python
from aip_sdk import AsyncAIPClient, AgentConfig

async def main():
    async with AsyncAIPClient("http://localhost:8001") as client:
        # Check if platform is healthy
        if await client.health_check():
            print("✓ AIP platform is healthy")

        # Register a user
        user = await client.register_user(
            wallet_address="0x1234567890abcdef1234567890abcdef12345678",
            email="user@example.com"
        )
        user_id = user["user_id"]

        # Create and register an agent
        agent_config = AgentConfig(
            name="My Helper Agent",
            description="A helpful AI agent",
            price=0.001,
            price_currency="USD",
        )

        result = await client.register_agent(user_id, agent_config)
        print(f"✓ Agent registered: {result['agent_id']}")

# Run the async code
import asyncio
asyncio.run(main())
```

### Synchronous Usage

```python
from aip_sdk import AIPClient, AgentConfig

# Create client
client = AIPClient("http://localhost:8001")

# Register a user
user = client.register_user(
    wallet_address="0x1234567890abcdef1234567890abcdef12345678"
)

# Register an agent
agent_config = AgentConfig(
    name="Calculator Agent",
    description="Performs mathematical calculations",
    price=0.001,
)

result = client.register_agent(user["user_id"], agent_config)
print(f"Agent ID: {result['agent_id']}")
```

## User Management

### Register a New User

```python
async with AsyncAIPClient("http://localhost:8001") as client:
    # Simple registration
    user = await client.register_user(
        wallet_address="0xabc123...",
        email="alice@example.com"
    )

    # Register with private key for on-chain operations
    user = await client.register_user(
        wallet_address="0xdef456...",
        private_key="0x0123...",  # Will be securely stored
        email="bob@example.com",
        chain_id=97  # BSC Testnet
    )

    print(f"User ID: {user['user_id']}")
    print(f"Wallet: {user['wallet_address']}")
```

### List Users with Pagination

```python
async with AsyncAIPClient("http://localhost:8001") as client:
    # Get first page of users
    users_page = await client.list_users(limit=50, offset=0)

    print(f"Total users: {users_page.total}")
    print(f"Showing: {len(users_page.items)}")

    for user in users_page.items:
        print(f"  - {user.user_id}: {user.wallet_address}")

    # Check if there are more pages
    if users_page.has_more:
        # Get next page
        next_page = await client.list_users(
            limit=50,
            offset=users_page.next_offset
        )
```

## Agent Management

### Register an Agent

```python
from aip_sdk import AgentConfig, SkillConfig, SkillInput, SkillOutput

async with AsyncAIPClient("http://localhost:8001") as client:
    # Define agent skills
    calculate_skill = SkillConfig(
        name="calculate",
        description="Perform mathematical calculations",
        inputs=[
            SkillInput(name="expression", field_type="string", required=True)
        ],
        outputs=[
            SkillOutput(name="result", field_type="number")
        ]
    )

    # Create agent configuration
    agent_config = AgentConfig(
        name="Math Assistant",
        description="Helps with mathematical calculations",
        handle="math_assistant",  # Optional, will be auto-generated
        skills=[calculate_skill],
        capabilities=["mathematics", "calculation"],
        price=0.001,
        price_currency="USD",
        metadata={"version": "1.0.0"},
    )

    # Register for a user
    result = await client.register_agent("user:0x123...", agent_config)

    print(f"Agent registered successfully!")
    print(f"  Agent ID: {result['agent_id']}")
    print(f"  Handle: {result['handle']}")
    print(f"  Price: ${result['price']['amount']} {result['price']['currency']}")
```

### List User's Agents

```python
async with AsyncAIPClient("http://localhost:8001") as client:
    # Get all agents for a user
    agents_page = await client.list_user_agents(
        "user:0x123...",
        limit=100,
        offset=0
    )

    print(f"User has {agents_page.total} agents")

    for agent in agents_page.items:
        print(f"\n{agent.name}")
        print(f"  ID: {agent.agent_id}")
        print(f"  Handle: {agent.handle}")
        print(f"  Price: ${agent.price}")
        print(f"  Endpoint: {agent.endpoint_url or 'N/A'}")
```

### Get Specific Agent

```python
async with AsyncAIPClient("http://localhost:8001") as client:
    agent = await client.get_agent(
        user_id="user:0x123...",
        agent_id="erc8004:math_assistant"
    )

    if agent:
        print(f"Found agent: {agent.name}")
        print(f"Description: {agent.description}")
        print(f"Skills: {[s['name'] for s in agent.skills]}")
    else:
        print("Agent not found")
```

### Unregister an Agent

```python
async with AsyncAIPClient("http://localhost:8001") as client:
    result = await client.unregister_agent(
        user_id="user:0x123...",
        agent_id="erc8004:old_agent"
    )

    print(f"Agent unregistered: {result['status']}")
```

## Pricing Management

### Get Agent Pricing

```python
async with AsyncAIPClient("http://localhost:8001") as client:
    price = await client.get_agent_price(
        user_id="user:0x123...",
        agent_id="erc8004:math_assistant"
    )

    print(f"Price: ${price.amount} {price.currency}")
    print(f"Metadata: {price.metadata}")
```

### Update Agent Pricing

```python
async with AsyncAIPClient("http://localhost:8001") as client:
    new_price = await client.update_agent_price(
        user_id="user:0x123...",
        agent_id="erc8004:math_assistant",
        amount=0.002,
        currency="USD",
        metadata={"pricing_tier": "premium"}
    )

    print(f"Updated price: ${new_price.amount}")
```

### List All Agent Prices

```python
async with AsyncAIPClient("http://localhost:8001") as client:
    prices_page = await client.list_agent_prices(limit=50)

    print(f"Total priced agents: {prices_page.total}")

    for price in prices_page.items:
        print(f"{price.identifier}: ${price.amount} {price.currency}")
```

## Running Tasks

### Execute a Task and Get Result

```python
async with AsyncAIPClient("http://localhost:8001") as client:
    # Run a task and wait for completion
    result = await client.run(
        objective="What is the weather in San Francisco?",
        domain_hint="weather",  # Optional routing hint
        user_id="user:0x123...",  # For payment tracking
        timeout=120.0  # Optional custom timeout
    )

    if result.success:
        print(f"Task completed!")
        print(f"Run ID: {result.run_id}")
        print(f"Output: {result.output}")
        print(f"Events: {len(result.events)}")
    else:
        print(f"Task failed: {result.error}")
```

### Stream Task Events

```python
async with AsyncAIPClient("http://localhost:8001") as client:
    async for event in client.run_stream(
        objective="Plan a trip to Tokyo",
        user_id="user:0x123..."
    ):
        print(f"[{event.event_type}] {event.message or ''}")

        if event.event_type == "answer_chunk":
            # Stream answer chunks in real-time
            print(event.payload.get("content", ""), end="", flush=True)

        if event.is_completed:
            print("\n✓ Task completed!")
            break

        if event.is_error:
            print(f"\n✗ Error: {event.message}")
            break
```

### Get Run History

```python
async with AsyncAIPClient("http://localhost:8001") as client:
    # List recent runs for a user
    runs_page = await client.list_user_runs(
        user_id="user:0x123...",
        limit=20,
        offset=0
    )

    for run in runs_page.items:
        print(f"Run {run['run_id']}")
        print(f"  Status: {run.get('status', 'unknown')}")
        print(f"  Created: {run.get('created_at', 'N/A')}")

    # Get detailed events for a specific run
    if runs_page.items:
        run_id = runs_page.items[0]['run_id']
        events = await client.get_run_events(run_id)
        print(f"\nRun {run_id} had {len(events)} events")
```

### Get Run Payments

```python
async with AsyncAIPClient("http://localhost:8001") as client:
    payments = await client.get_run_payments(run_id)

    total_cost = sum(p.get('amount', 0) for p in payments)
    print(f"Total cost: {total_cost} credits")

    for payment in payments:
        print(f"  {payment['destination']}: {payment['amount']} credits")
```

## Pagination

### Iterate Through All Pages

```python
async with AsyncAIPClient("http://localhost:8001") as client:
    user_id = "user:0x123..."
    all_agents = []
    offset = 0
    limit = 100

    while True:
        page = await client.list_user_agents(
            user_id,
            limit=limit,
            offset=offset
        )

        all_agents.extend(page.items)

        if not page.has_more:
            break

        offset = page.next_offset

    print(f"Total agents loaded: {len(all_agents)}")
```

### Helper Function for Auto-Pagination

```python
async def fetch_all_pages(fetch_func, **kwargs):
    """Automatically fetch all pages from a paginated endpoint."""
    items = []
    offset = 0
    limit = kwargs.get('limit', 100)

    while True:
        page = await fetch_func(**{**kwargs, 'offset': offset, 'limit': limit})
        items.extend(page.items)

        if not page.has_more:
            break

        offset = page.next_offset

    return items

# Usage
async with AsyncAIPClient("http://localhost:8001") as client:
    all_users = await fetch_all_pages(client.list_users, limit=50)
    print(f"Fetched {len(all_users)} users")
```

## Error Handling

### Handling Common Errors

```python
from aip_sdk import (
    AIPClient,
    ConnectionError,
    RegistrationError,
    ExecutionError,
    AIPError
)

async with AsyncAIPClient("http://localhost:8001") as client:
    try:
        # Try to register an agent
        result = await client.register_agent(user_id, agent_config)

    except ConnectionError as e:
        print(f"Connection failed: {e}")
        print(f"URL: {e.url}")

    except RegistrationError as e:
        print(f"Registration failed: {e}")
        print(f"Handle: {e.handle}")

    except ExecutionError as e:
        print(f"Task execution failed: {e}")

    except AIPError as e:
        print(f"General AIP error: {e}")
```

### Retry Logic

```python
import asyncio
from aip_sdk import AsyncAIPClient, ConnectionError

async def register_with_retry(client, user_id, agent_config, max_retries=3):
    """Register an agent with automatic retry on failure."""
    for attempt in range(max_retries):
        try:
            result = await client.register_agent(user_id, agent_config)
            return result
        except ConnectionError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Attempt {attempt + 1} failed, retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                raise
```

## Complete Example: Agent Lifecycle

```python
from aip_sdk import AsyncAIPClient, AgentConfig, SkillConfig

async def agent_lifecycle_demo():
    """Complete example showing agent lifecycle management."""

    async with AsyncAIPClient("http://localhost:8001") as client:
        # 1. Wait for platform to be ready
        print("Waiting for AIP platform...")
        if not await client.wait_for_ready(max_attempts=30, interval=1.0):
            print("Platform not ready!")
            return

        # 2. Register a user
        print("\n1. Registering user...")
        user = await client.register_user(
            wallet_address="0x1234567890abcdef1234567890abcdef12345678",
            email="demo@example.com"
        )
        user_id = user["user_id"]
        print(f"✓ User registered: {user_id}")

        # 3. Create and register an agent
        print("\n2. Registering agent...")
        agent_config = AgentConfig(
            name="Demo Agent",
            description="A demonstration agent",
            skills=[
                SkillConfig(
                    name="demo_skill",
                    description="A demo skill"
                )
            ],
            price=0.001,
        )

        agent_result = await client.register_agent(user_id, agent_config)
        agent_id = agent_result["agent_id"]
        print(f"✓ Agent registered: {agent_id}")

        # 4. Update agent pricing
        print("\n3. Updating agent pricing...")
        new_price = await client.update_agent_price(
            user_id, agent_id, 0.002, currency="USD"
        )
        print(f"✓ Price updated to ${new_price.amount}")

        # 5. List user's agents
        print("\n4. Listing user's agents...")
        agents_page = await client.list_user_agents(user_id, limit=10)
        print(f"✓ User has {agents_page.total} agent(s)")

        # 6. Run a task
        print("\n5. Running a task...")
        result = await client.run(
            objective="Hello, world!",
            user_id=user_id,
            timeout=30.0
        )
        if result.success:
            print(f"✓ Task completed: {result.output}")

        # 7. Check run history
        print("\n6. Checking run history...")
        runs_page = await client.list_user_runs(user_id, limit=5)
        print(f"✓ User has {runs_page.total} run(s)")

        # 8. Unregister agent
        print("\n7. Unregistering agent...")
        unregister_result = await client.unregister_agent(user_id, agent_id)
        print(f"✓ Agent unregistered: {unregister_result['status']}")

# Run the demo
import asyncio
asyncio.run(agent_lifecycle_demo())
```

## Best Practices

1. **Use Async Client**: For production applications, use `AsyncAIPClient` for better performance
2. **Handle Pagination**: Always implement pagination for list endpoints to handle large datasets
3. **Error Handling**: Wrap API calls in try-except blocks and handle specific exceptions
4. **Context Managers**: Use `async with` to ensure proper connection cleanup
5. **Timeouts**: Set appropriate timeouts for long-running operations
6. **User Scoping**: Always scope operations to specific users for proper access control
7. **Retry Logic**: Implement exponential backoff for transient failures
8. **Type Safety**: Use the provided type classes (`AgentConfig`, `SkillConfig`) for better IDE support

For more information, see the [API documentation](../README.md).
