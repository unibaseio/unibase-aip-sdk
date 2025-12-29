# AIP SDK Examples

Examples demonstrating how to use the AIP SDK client to interact with the Unibase AIP platform.

## Prerequisites

1. Start the AIP platform:
   ```bash
   ./scripts/start.sh
   ```

2. Install the SDK:
   ```bash
   pip install -e packages/unibase-aip-sdk
   ```

## Examples

### Client Usage (`client_usage.py`)

Complete example showing:
- Connecting to the platform
- Registering users
- Running tasks
- Streaming events

```bash
python examples/client_usage.py
```

### List Agents (`list_agents.py`)

Query available agents with pagination:

```bash
python examples/list_agents.py
```

## Quick Start

```python
from aip_sdk import AsyncAIPClient

async with AsyncAIPClient("http://localhost:8001") as client:
    # Run a task
    result = await client.run(
        objective="What is 2 + 2?",
        user_id="user:0x1234..."
    )
    print(result.output)
```

## More Information

See the main [README.md](../README.md) and [EXAMPLES.md](../EXAMPLES.md) for comprehensive documentation.
